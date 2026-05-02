"""
Mock API for testing — same endpoints as main.py but with in-memory data.

Credentials: any username / any password are accepted.
Test users with pre-loaded data:
  - user: "alice"  password: "any"
  - user: "bob"    password: "any"
  - Any other user gets an empty assignment list.

Extra endpoints (not in prod):
  POST /notes          — add an assignment for the authenticated user
  DELETE /notes/{idx}  — remove an assignment by index
  POST /reset          — reset data to defaults
"""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Annotated
import copy

from models import Assignment, NotesResponse, OnboardingResponse, UserProfile


app = FastAPI(
    title="Mock Notes API — Collège Blondin (TEST)",
    description="Fausse API pour les tests. Même interface que la prod, données en mémoire.",
)

security = HTTPBasic()

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED: dict[str, dict] = {
    "alice": {
        "profile": UserProfile(
            full_name="Alice Tremblay",
            permanent_code="TREA12345678",
            photo_base64=None,
        ),
        "assignments": [
            Assignment(
                course="Mathématiques 103",
                category="Examen",
                title="Examen intra",
                weight="30%",
                date_assigned="2026-02-10",
                date_due="2026-02-24",
                date_completed="2026-02-24",
                result="78/100",
            ),
            Assignment(
                course="Français 101",
                category="Travail",
                title="Dissertation comparative",
                weight="20%",
                date_assigned="2026-01-15",
                date_due="2026-02-01",
                date_completed="2026-02-01",
                result="85/100",
            ),
            Assignment(
                course="Informatique 420",
                category="Laboratoire",
                title="Lab 3 — Python",
                weight="10%",
                date_assigned="2026-03-01",
                date_due="2026-03-08",
                date_completed=None,
                result=None,
            ),
        ],
    },
    "bob": {
        "profile": UserProfile(
            full_name="Bob Gagné",
            permanent_code="GAGB98765432",
            photo_base64=None,
        ),
        "assignments": [
            Assignment(
                course="Histoire 330",
                category="Examen",
                title="Examen final",
                weight="40%",
                date_assigned="2026-04-01",
                date_due="2026-04-20",
                date_completed="2026-04-20",
                result="91/100",
            ),
        ],
    },
}

# Mutable in-memory store (deep copy so mutations don't touch seed)
_store: dict[str, dict] = copy.deepcopy(_SEED)


def _get_user_data(username: str) -> dict:
    if username not in _store:
        _store[username] = {
            "profile": UserProfile(
                full_name=username.capitalize(),
                permanent_code="MOCK00000000",
                photo_base64=None,
            ),
            "assignments": [],
        }
    return _store[username]


# ---------------------------------------------------------------------------
# Shared endpoints (mirror prod)
# ---------------------------------------------------------------------------

@app.get("/notes", response_model=NotesResponse)
def get_notes(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    """Retourne les notes de l'utilisateur (données fictives)."""
    data = _get_user_data(credentials.username)
    assignments = data["assignments"]
    return NotesResponse(count=len(assignments), assignments=assignments)


@app.get("/profile")
def get_profile(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    """Retourne le profil fictif de l'étudiant."""
    data = _get_user_data(credentials.username)
    return data["profile"]


@app.get("/onboarding", response_model=OnboardingResponse)
def get_onboarding(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    """Retourne profil + notes en une seule requête."""
    data = _get_user_data(credentials.username)
    assignments = data["assignments"]
    return OnboardingResponse(
        profile=data["profile"],
        count=len(assignments),
        assignments=assignments,
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": "mock"}


# ---------------------------------------------------------------------------
# Extra test-only endpoints
# ---------------------------------------------------------------------------

@app.post("/notes", response_model=NotesResponse, status_code=201)
def add_note(
    assignment: Assignment,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    """Ajoute une nouvelle note pour l'utilisateur connecté."""
    data = _get_user_data(credentials.username)
    data["assignments"].append(assignment)
    return NotesResponse(count=len(data["assignments"]), assignments=data["assignments"])


@app.delete("/notes/{index}", response_model=NotesResponse)
def delete_note(
    index: int,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    """Supprime une note par index (0-based)."""
    data = _get_user_data(credentials.username)
    assignments = data["assignments"]
    if index < 0 or index >= len(assignments):
        return JSONResponse(
            status_code=404,
            content={"detail": f"Index {index} hors limites (total: {len(assignments)})"},
        )
    assignments.pop(index)
    return NotesResponse(count=len(assignments), assignments=assignments)


@app.put("/notes/{index}", response_model=NotesResponse)
def update_note(
    index: int,
    assignment: Assignment,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    """Remplace une note existante par index (0-based)."""
    data = _get_user_data(credentials.username)
    assignments = data["assignments"]
    if index < 0 or index >= len(assignments):
        return JSONResponse(
            status_code=404,
            content={"detail": f"Index {index} hors limites (total: {len(assignments)})"},
        )
    assignments[index] = assignment
    return NotesResponse(count=len(assignments), assignments=assignments)


@app.post("/reset", status_code=200)
def reset(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    """Réinitialise les données de l'utilisateur aux valeurs par défaut (seed)."""
    username = credentials.username
    if username in _SEED:
        _store[username] = copy.deepcopy(_SEED[username])
        return {"detail": f"Données de '{username}' réinitialisées."}
    elif username in _store:
        del _store[username]
        return {"detail": f"Données de '{username}' supprimées (utilisateur non-seed)."}
    return {"detail": f"Rien à réinitialiser pour '{username}'."}
