from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import settings
from models import NotesResponse
from scraper import fetch_assignments, SessionExpiredError


@asynccontextmanager
async def lifespan(app: FastAPI):
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=settings.playwright_headless)
    app.state.browser = browser
    app.state.pw = pw
    yield
    await browser.close()
    await pw.stop()


app = FastAPI(title="Notes Portal API — Collège Blondin", lifespan=lifespan)


@app.get("/notes", response_model=NotesResponse)
async def get_notes(request: Request):
    try:
        assignments = await fetch_assignments(request.app.state.browser)
        return NotesResponse(count=len(assignments), assignments=assignments)
    except PlaywrightTimeoutError as exc:
        return JSONResponse(
            status_code=504,
            content={"detail": f"Portal timeout: {exc}"},
        )
    except SessionExpiredError as exc:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Portal session error: {exc}"},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Unexpected error: {exc}"},
        )


@app.get("/health")
async def health():
    return {"status": "ok"}
