import asyncio
import base64
import time
from dataclasses import dataclass, field

from playwright.async_api import Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from config import settings
from models import Assignment, UserProfile


class SessionExpiredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


@dataclass
class _UserSession:
    context: BrowserContext
    landing_url: str
    login_time: float = field(default_factory=time.time)


# Per-user session store and per-user locks
_sessions: dict[str, _UserSession] = {}
_user_locks: dict[str, asyncio.Lock] = {}
_store_lock = asyncio.Lock()  # protects _sessions and _user_locks dicts


async def _get_user_lock(username: str) -> asyncio.Lock:
    async with _store_lock:
        if username not in _user_locks:
            _user_locks[username] = asyncio.Lock()
        return _user_locks[username]


async def _invalidate_session(username: str) -> None:
    async with _store_lock:
        session = _sessions.pop(username, None)
    if session:
        try:
            await session.context.close()
        except Exception:
            pass


async def _do_login(browser: Browser, username: str, password: str) -> _UserSession:
    context = await browser.new_context()
    page = await context.new_page()
    login_url = settings.portal_url + settings.portal_login_path
    try:
        await page.goto(login_url, timeout=settings.playwright_timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)
        await page.fill(settings.selector_username_input, username)
        await page.fill(settings.selector_password_input, password)
        await page.click(settings.selector_login_button)

        try:
            await page.wait_for_url(
                lambda url: settings.portal_login_path not in url,
                timeout=settings.playwright_timeout_ms,
            )
        except PlaywrightTimeoutError:
            await context.close()
            raise InvalidCredentialsError(
                "Login failed — portal did not redirect. "
                "Check username and password."
            )

        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)
        landing_url = page.url
    finally:
        await page.close()

    return _UserSession(context=context, landing_url=landing_url)


async def _get_or_create_session(
    browser: Browser, username: str, password: str
) -> _UserSession:
    lock = await _get_user_lock(username)
    async with lock:
        now = time.time()
        existing = _sessions.get(username)
        if existing and (now - existing.login_time) < settings.session_ttl_seconds:
            return existing

        if existing:
            try:
                await existing.context.close()
            except Exception:
                pass

        session = await _do_login(browser, username, password)
        async with _store_lock:
            _sessions[username] = session
        return session


async def _fetch_photo_base64(page, src: str) -> str | None:
    """Download a portal image via the authenticated browser context and return base64."""
    if not src:
        return None
    if src.startswith("data:"):
        return src  # already a data URI
    absolute = src if src.startswith("http") else settings.portal_url + "/" + src.lstrip("/")
    try:
        response = await page.context.request.get(absolute)
        if response.ok:
            mime = response.headers.get("content-type", "image/jpeg").split(";")[0]
            data = await response.body()
            return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        pass
    return None


async def fetch_profile(
    browser: Browser, username: str, password: str
) -> UserProfile:
    session = await _get_or_create_session(browser, username, password)
    page = await session.context.new_page()
    try:
        await page.goto(session.landing_url, timeout=settings.playwright_timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

        if settings.portal_login_path in page.url:
            await _invalidate_session(username)
            raise SessionExpiredError("Portal redirected to login — session expired")

        async def _text(selector: str) -> str:
            el = await page.query_selector(selector)
            return (await el.inner_text()).strip() if el else ""

        full_name = await _text(settings.selector_profile_name)
        permanent_code = await _text(settings.selector_profile_code)

        photo_base64: str | None = None
        photo_el = await page.query_selector(settings.selector_profile_photo)
        if photo_el:
            src = await photo_el.get_attribute("src") or ""
            photo_base64 = await _fetch_photo_base64(page, src)

        return UserProfile(
            full_name=full_name,
            permanent_code=permanent_code,
            photo_base64=photo_base64,
        )
    except (PlaywrightTimeoutError, SessionExpiredError, InvalidCredentialsError):
        raise
    except Exception:
        await _invalidate_session(username)
        raise
    finally:
        await page.close()


async def fetch_onboarding(
    browser: Browser, username: str, password: str
) -> tuple[UserProfile, list[Assignment]]:
    """Fetch profile and assignments in a single authenticated session."""
    for attempt in range(2):
        session = await _get_or_create_session(browser, username, password)
        page = await session.context.new_page()
        try:
            await page.goto(session.landing_url, timeout=settings.playwright_timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

            if settings.portal_login_path in page.url:
                await _invalidate_session(username)
                if attempt == 0:
                    continue
                raise SessionExpiredError("Portal redirected to login — session expired")

            # --- Profile (home page) ---
            async def _text(selector: str) -> str:
                el = await page.query_selector(selector)
                return (await el.inner_text()).strip() if el else ""

            full_name = await _text(settings.selector_profile_name)
            permanent_code = await _text(settings.selector_profile_code)

            photo_base64: str | None = None
            photo_el = await page.query_selector(settings.selector_profile_photo)
            if photo_el:
                src = await photo_el.get_attribute("src") or ""
                photo_base64 = await _fetch_photo_base64(page, src)

            profile = UserProfile(
                full_name=full_name,
                permanent_code=permanent_code,
                photo_base64=photo_base64,
            )

            # --- Navigate to Travaux ---
            nav_travaux = page.locator("div.treeview__elem", has_text="Travaux").first
            await nav_travaux.wait_for(state="visible", timeout=settings.playwright_timeout_ms)
            await nav_travaux.click()
            await page.wait_for_selector(
                "h3:has-text('TRAVAUX')",
                timeout=settings.playwright_timeout_ms,
            )

            # --- Assignments ---
            assignments: list[Assignment] = []
            course_blocks = await page.query_selector_all(settings.selector_course_block)

            for block in course_blocks:
                course_name: str = await block.evaluate("""el => {
                    let sib = el.previousElementSibling;
                    while (sib) {
                        if (sib.tagName === 'H4') return sib.innerText.trim();
                        sib = sib.previousElementSibling;
                    }
                    const h4 = el.parentElement && el.parentElement.querySelector('h4');
                    return h4 ? h4.innerText.trim() : '';
                }""")

                rows = await block.query_selector_all(settings.selector_assignment_row)
                for row in rows:
                    cells = await row.query_selector_all("td")
                    texts = [(await c.inner_text()).strip() for c in cells]

                    if len(texts) < 3 or not texts[2]:
                        continue

                    assignments.append(
                        Assignment(
                            course=course_name,
                            category=texts[1] if len(texts) > 1 else "",
                            title=texts[2] if len(texts) > 2 else "",
                            weight=texts[3] if len(texts) > 3 else "",
                            date_assigned=texts[4] or None if len(texts) > 4 else None,
                            date_due=texts[5] or None if len(texts) > 5 else None,
                            date_completed=texts[6] or None if len(texts) > 6 else None,
                            result=texts[7] or None if len(texts) > 7 else None,
                        )
                    )

            return profile, assignments

        except (PlaywrightTimeoutError, SessionExpiredError, InvalidCredentialsError):
            raise
        except Exception:
            await _invalidate_session(username)
            raise
        finally:
            await page.close()

    raise SessionExpiredError("Could not establish a valid portal session after retry")


async def fetch_assignments(
    browser: Browser, username: str, password: str
) -> list[Assignment]:
    for attempt in range(2):
        session = await _get_or_create_session(browser, username, password)
        page = await session.context.new_page()
        try:
            await page.goto(session.landing_url, timeout=settings.playwright_timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

            if settings.portal_login_path in page.url:
                await _invalidate_session(username)
                if attempt == 0:
                    continue
                raise SessionExpiredError("Portal redirected to login — session expired")

            nav_travaux = page.locator("div.treeview__elem", has_text="Travaux").first
            await nav_travaux.wait_for(state="visible", timeout=settings.playwright_timeout_ms)
            await nav_travaux.click()
            await page.wait_for_selector(
                "h3:has-text('TRAVAUX')",
                timeout=settings.playwright_timeout_ms,
            )

            assignments: list[Assignment] = []
            course_blocks = await page.query_selector_all(settings.selector_course_block)

            for block in course_blocks:
                course_name: str = await block.evaluate("""el => {
                    let sib = el.previousElementSibling;
                    while (sib) {
                        if (sib.tagName === 'H4') return sib.innerText.trim();
                        sib = sib.previousElementSibling;
                    }
                    const h4 = el.parentElement && el.parentElement.querySelector('h4');
                    return h4 ? h4.innerText.trim() : '';
                }""")

                rows = await block.query_selector_all(settings.selector_assignment_row)
                for row in rows:
                    cells = await row.query_selector_all("td")
                    texts = [(await c.inner_text()).strip() for c in cells]

                    # [0] icon  [1] Catégorie  [2] Travail  [3] Pond.
                    # [4] Date assignée  [5] Date due  [6] Date complétée  [7] Résultat
                    if len(texts) < 3 or not texts[2]:
                        continue

                    assignments.append(
                        Assignment(
                            course=course_name,
                            category=texts[1] if len(texts) > 1 else "",
                            title=texts[2] if len(texts) > 2 else "",
                            weight=texts[3] if len(texts) > 3 else "",
                            date_assigned=texts[4] or None if len(texts) > 4 else None,
                            date_due=texts[5] or None if len(texts) > 5 else None,
                            date_completed=texts[6] or None if len(texts) > 6 else None,
                            result=texts[7] or None if len(texts) > 7 else None,
                        )
                    )

            return assignments

        except (PlaywrightTimeoutError, SessionExpiredError, InvalidCredentialsError):
            raise
        except Exception:
            await _invalidate_session(username)
            raise
        finally:
            await page.close()

    raise SessionExpiredError("Could not establish a valid portal session after retry")
