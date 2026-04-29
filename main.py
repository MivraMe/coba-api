from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import settings
from models import NotesResponse
from scraper import fetch_assignments, InvalidCredentialsError, SessionExpiredError


@asynccontextmanager
async def lifespan(app: FastAPI):
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=settings.playwright_headless)
    app.state.browser = browser
    app.state.pw = pw
    yield
    await browser.close()
    await pw.stop()


app = FastAPI(
    title="Notes Portal API — Collège Blondin",
    description=(
        "Scrape vos travaux depuis le portail pédagogique. "
        "Authentification via HTTP Basic Auth avec vos identifiants du portail."
    ),
    lifespan=lifespan,
)

security = HTTPBasic()


@app.get("/notes", response_model=NotesResponse)
async def get_notes(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    """
    Retourne la liste de vos travaux (assignments) depuis le portail.

    Authentification : HTTP Basic Auth avec vos identifiants du portail Collège Blondin.
    """
    try:
        assignments = await fetch_assignments(
            request.app.state.browser,
            credentials.username,
            credentials.password,
        )
        return NotesResponse(count=len(assignments), assignments=assignments)

    except InvalidCredentialsError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Basic realm=\"Portail Collège Blondin\""},
        )
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
