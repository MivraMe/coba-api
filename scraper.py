import asyncio
import time

from playwright.async_api import Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from config import settings
from models import Assignment


class SessionExpiredError(Exception):
    pass


_session: BrowserContext | None = None
_session_url: str | None = None   # post-login URL (contains server session token)
_session_lock = asyncio.Lock()
_last_login_at: float = 0.0


def _invalidate_session() -> None:
    global _session, _session_url, _last_login_at
    _session = None
    _session_url = None
    _last_login_at = 0.0


async def _do_login(browser: Browser) -> tuple[BrowserContext, str]:
    """Returns the authenticated BrowserContext and the post-login landing URL."""
    context = await browser.new_context()
    page = await context.new_page()
    login_url = settings.portal_url + settings.portal_login_path
    try:
        await page.goto(login_url, timeout=settings.playwright_timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)
        await page.fill(settings.selector_username_input, settings.portal_username)
        await page.fill(settings.selector_password_input, settings.portal_password)
        await page.click(settings.selector_login_button)

        # Wait for redirect away from login page
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
        landing_url = page.url
    finally:
        await page.close()

    return context, landing_url


async def _get_or_create_session(browser: Browser) -> tuple[BrowserContext, str]:
    global _session, _session_url, _last_login_at

    async with _session_lock:
        now = time.time()
        if _session is not None and _session_url and (now - _last_login_at) < settings.session_ttl_seconds:
            return _session, _session_url

        if _session is not None:
            try:
                await _session.close()
            except Exception:
                pass

        _session, _session_url = await _do_login(browser)
        _last_login_at = time.time()
        return _session, _session_url


async def fetch_assignments(browser: Browser) -> list[Assignment]:
    for attempt in range(2):
        context, landing_url = await _get_or_create_session(browser)
        page = await context.new_page()
        try:
            await page.goto(landing_url, timeout=settings.playwright_timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)

            # Detect redirect back to login — session expired server-side
            if settings.portal_login_path in page.url:
                _invalidate_session()
                if attempt == 0:
                    continue
                raise SessionExpiredError("Portal redirected to login — session expired")

            # Click the "Travaux" nav item (mixed case in portal HTML).
            # The portal uses client-side postback navigation — the URL never
            # changes, so we can't use wait_for_url.
            # tr.grid3__row already exists on the Actualités landing page
            # (11 rows), so we can't use that as a readiness signal either.
            # Instead, wait for <h3> "TRAVAUX" which only appears as the
            # section heading on the Travaux content page.
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
                # The h4 course heading is a sibling element before the
                # tableres block, not a child of it.
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

                    # Row layout (8 cells):
                    # [0] icon (open_in_new)  ← skip
                    # [1] Catégorie
                    # [2] Travail
                    # [3] Pondération
                    # [4] Date assignée
                    # [5] Date due
                    # [6] Date complétée
                    # [7] Résultat
                    if len(texts) < 3 or not texts[2]:
                        continue  # skip separator / header rows

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
