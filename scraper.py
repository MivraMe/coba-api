import asyncio
import time

from playwright.async_api import Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from config import settings
from models import Note


class SessionExpiredError(Exception):
    pass


_session: BrowserContext | None = None
_session_lock = asyncio.Lock()
_last_login_at: float = 0.0


def _invalidate_session() -> None:
    global _session, _last_login_at
    _session = None
    _last_login_at = 0.0


async def _do_login(browser: Browser) -> BrowserContext:
    context = await browser.new_context()
    page = await context.new_page()
    login_url = settings.portal_url + settings.portal_login_path
    try:
        await page.goto(login_url, timeout=settings.playwright_timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)
        await page.fill(settings.selector_username_input, settings.portal_username)
        await page.fill(settings.selector_password_input, settings.portal_password)
        await page.click(settings.selector_login_button)

        # Wait for navigation away from the login page; if we stay, login failed
        try:
            await page.wait_for_url(
                lambda url: settings.portal_login_path not in url,
                timeout=settings.playwright_timeout_ms,
            )
        except PlaywrightTimeoutError:
            raise SessionExpiredError(
                "Login failed — portal did not redirect after submit "
                "(wrong credentials or form structure changed)"
            )

        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

        if settings.selector_login_success:
            await page.wait_for_selector(
                settings.selector_login_success,
                timeout=settings.playwright_timeout_ms,
            )
    finally:
        await page.close()

    return context


async def _get_or_create_session(browser: Browser) -> BrowserContext:
    global _session, _last_login_at

    async with _session_lock:
        now = time.time()
        if _session is not None and (now - _last_login_at) < settings.session_ttl_seconds:
            return _session

        if _session is not None:
            try:
                await _session.close()
            except Exception:
                pass

        _session = await _do_login(browser)
        _last_login_at = time.time()
        return _session


async def fetch_notes(browser: Browser) -> list[Note]:
    for attempt in range(2):
        context = await _get_or_create_session(browser)
        page = await context.new_page()
        try:
            await page.goto(
                settings.portal_url + settings.portal_notes_path,
                timeout=settings.playwright_timeout_ms,
            )
            await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

            # Detect redirect back to login page — session expired server-side
            if settings.portal_login_path in page.url:
                _invalidate_session()
                if attempt == 0:
                    continue
                raise SessionExpiredError("Portal redirected to login after navigation — login failed")

            await page.wait_for_selector(
                settings.selector_note_container,
                timeout=settings.playwright_timeout_ms,
            )

            containers = await page.query_selector_all(settings.selector_note_container)
            notes: list[Note] = []
            for container in containers:
                title_el = await container.query_selector(settings.selector_note_title)
                body_el = await container.query_selector(settings.selector_note_body)
                date_el = (
                    await container.query_selector(settings.selector_note_date)
                    if settings.selector_note_date
                    else None
                )
                notes.append(
                    Note(
                        title=await title_el.inner_text() if title_el else "",
                        body=await body_el.inner_text() if body_el else "",
                        date=await date_el.inner_text() if date_el else None,
                    )
                )
            return notes

        except PlaywrightTimeoutError:
            raise
        except SessionExpiredError:
            raise
        except Exception:
            _invalidate_session()
            raise
        finally:
            await page.close()

    raise SessionExpiredError("Could not establish a valid portal session after retry")
