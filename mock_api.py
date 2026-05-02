"""
Mock API for testing — same endpoints as main.py but with in-memory data.

Credentials: any username / any password are accepted.
Test users with pre-loaded data:
  - user: "alice"  password: "any"  (49 assignments matching real API format)
  - user: "bob"    password: "any"  (minimal data)
  - Any other user gets an empty assignment list.

Extra endpoints (not in prod):
  POST /notes          — add an assignment for the authenticated user
  PUT  /notes/{idx}    — replace an assignment by index (0-based)
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
# Seed data — format identique à la vraie API
# ---------------------------------------------------------------------------

_SEED: dict[str, dict] = {
    "alice": {
        "profile": UserProfile(
            full_name="Alice Tremblay",
            permanent_code="TREA12345678",
            photo_base64=None,
        ),
        "assignments": [
            # ANF418
            Assignment(course="ANF418 - Anglais enrichi", category="Discussion", title="Contextualisation", weight="50", date_assigned="03-02-2026", date_due="03-02-2026 à 23:59", date_completed=None, result="14,5 / 20 (72,5 %)"),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="Everyday participation", weight="10", date_assigned="03-02-2026", date_due="30-06-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="Favorite band", weight="40", date_assigned="03-02-2026", date_due="22-05-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="ANF418 - Anglais enrichi", category="Reinvestment", title="Reading reinvestment", weight="30", date_assigned="03-02-2026", date_due="22-04-2026 à 23:59", date_completed=None, result="14,5 / 18 (80,6 %)"),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="Video reinvestment", weight="20", date_assigned="03-02-2026", date_due="04-05-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="Marketing", weight="20", date_assigned="03-02-2026", date_due="11-02-2026 à 23:59", date_completed=None, result="10,0 / 10 (100,0 %)"),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="End year: reading", weight="30", date_assigned="03-02-2026", date_due="30-06-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="ANF418 - Anglais enrichi", category="Writing", title="Marketing", weight="30", date_assigned="03-02-2026", date_due="11-02-2026 à 23:59", date_completed=None, result="19,0 / 20 (95,0 %)"),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="Project - presentation", weight="30", date_assigned="03-02-2026", date_due="13-04-2026 à 23:59", date_completed=None, result="14,0 / 15 (93,3 %)"),
            Assignment(course="ANF418 - Anglais enrichi", category="", title="End year: writing", weight="40", date_assigned="03-02-2026", date_due="30-06-2026 à 23:59", date_completed=None, result=None),
            # CCQ408
            Assignment(course="CCQ408 - Culture et citoyenneté québécoise", category="Étudier des RC", title="sondage et JVSS", weight="1", date_assigned="30-04-2026", date_due="30-04-2026 à 23:59", date_completed=None, result="95,0 / 100 (95,0 %)"),
            # EDP404
            Assignment(course="EDP404 - Éducation physique et à la santé", category="Agir", title="Mise en place du plan", weight="1", date_assigned="26-02-2026", date_due="26-02-2026 à 23:59", date_completed=None, result="B-"),
            Assignment(course="EDP404 - Éducation physique et à la santé", category="", title="LSS - Mise en place du plan", weight="1", date_assigned="14-04-2026", date_due="14-04-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="EDP404 - Éducation physique et à la santé", category="Interagir", title="Création de stratégies", weight="1", date_assigned="19-03-2026", date_due="19-03-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="EDP404 - Éducation physique et à la santé", category="", title="Mise en place des stratégies", weight="1", date_assigned="19-03-2026", date_due="19-03-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="EDP404 - Éducation physique et à la santé", category="Adopter", title="Création - Plan d'entraînement", weight="1", date_assigned="26-02-2026", date_due="26-02-2026 à 23:59", date_completed=None, result="A-"),
            Assignment(course="EDP404 - Éducation physique et à la santé", category="", title="LSS - Pace", weight="1", date_assigned="14-04-2026", date_due="14-04-2026 à 23:59", date_completed=None, result=None),
            # FRA406
            Assignment(course="FRA406 - Français, langue d'enseignement", category="Sommaire", title="Exposé portant sur une chanson", weight="1", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="Sommaire", title="Test de grammaire 3", weight="15", date_assigned=None, date_due=None, date_completed=None, result="44,0 / 45 (97,8 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Fakir - Qualité de langue", weight="5", date_assigned=None, date_due=None, date_completed=None, result="20,0 / 20 (100,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Production écrite de type ARG", weight="60", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Poème / Test de grammaire 4", weight="20", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="Sommaire", title="Mi-année - Partie 1", weight="9", date_assigned=None, date_due=None, date_completed=None, result="15,0 / 20 (75,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Mi-année - Partie 2", weight="11", date_assigned=None, date_due=None, date_completed=None, result="23,0 / 25 (92,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Fakir - Cahier de préparation", weight="5", date_assigned=None, date_due=None, date_completed=None, result="5,0 / 5 (100,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Fakir - Évaluation - Partie 1", weight="10", date_assigned=None, date_due=None, date_completed=None, result="19,0 / 20 (95,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="Fakir - Évaluation - Partie 2", weight="10", date_assigned=None, date_due=None, date_completed=None, result="17,0 / 20 (85,0 %)"),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="M. Linh - Test de lecture", weight="15", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA406 - Français, langue d'enseignement", category="", title="M. Linh - Fin d'année", weight="40", date_assigned=None, date_due=None, date_completed=None, result=None),
            # FRA410
            Assignment(course="FRA410 - Français enrichi (PEI)", category="Sommaire", title="Yamabuki - P2 - Contenu", weight="30", date_assigned=None, date_due=None, date_completed=None, result="20,0 / 20 (100,0 %)"),
            Assignment(course="FRA410 - Français enrichi (PEI)", category="", title="Langue - Yamabuki", weight="10", date_assigned=None, date_due=None, date_completed=None, result="20,0 / 20 (100,0 %)"),
            Assignment(course="FRA410 - Français enrichi (PEI)", category="", title="Roman au choix - P1 - Contenu", weight="20", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA410 - Français enrichi (PEI)", category="", title="Roman au choix - P2 - Contenu", weight="30", date_assigned=None, date_due=None, date_completed=None, result=None),
            Assignment(course="FRA410 - Français enrichi (PEI)", category="", title="Langue - Roman au choix", weight="10", date_assigned=None, date_due=None, date_completed=None, result=None),
            # HIS408
            Assignment(course="HIS408 - Histoire du Québec et du Canada", category="étape 3", title="Évaluation ch. 3", weight="35", date_assigned="02-02-2021", date_due="08-04-2026 à 14:25", date_completed=None, result="27,0 / 33 (81,8 %)"),
            Assignment(course="HIS408 - Histoire du Québec et du Canada", category="", title="Évaluation ch4", weight="35", date_assigned="17-03-2021", date_due="12-05-2026 à 12:03", date_completed=None, result=None),
            Assignment(course="HIS408 - Histoire du Québec et du Canada", category="", title="Travail 1ere partie", weight="15", date_assigned="19-02-2024", date_due="24-03-2026 à 23:59", date_completed=None, result="90,0 / 100 (90,0 %)"),
            Assignment(course="HIS408 - Histoire du Québec et du Canada", category="", title="Travail 2e partie", weight="15", date_assigned="18-03-2025", date_due="28-04-2026 à 23:59", date_completed=None, result=None),
            # MAT416
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="NOTES", title="Une ferme reptilienne", weight="25", date_assigned="16-02-2026", date_due="16-02-2026 à 23:59", date_completed=None, result="98,0 / 100 (98,0 %)"),
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="", title="Les jumeaux Lazure", weight="25", date_assigned=None, date_due=None, date_completed=None, result="96,0 / 100 (96,0 %)"),
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="NOTES", title="Partie entière/démonstrations", weight="25", date_assigned=None, date_due="20-03-2026 à 23:59", date_completed=None, result="88,0 / 100 (88,0 %)"),
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="", title="Géométrie analytique", weight="25", date_assigned=None, date_due="16-04-2026 à 23:59", date_completed=None, result="76,0 / 100 (76,0 %)"),
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="", title="Systèmes d'équations", weight="25", date_assigned=None, date_due="01-05-2026 à 23:59", date_completed=None, result=None),
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="", title="Les statistiques", weight="25", date_assigned=None, date_due="14-05-2026 à 23:59", date_completed=None, result=None),
            # SCI404
            Assignment(course="SCI404 - Science et technologie", category="Laboratoires", title="Examen Laboratoire loi d'Ohm", weight="1", date_assigned="26-02-2026", date_due="26-02-2026 à 23:59", date_completed=None, result="B"),
            Assignment(course="SCI404 - Science et technologie", category="CD2", title="Examen chapitre 5 et rendement", weight="25", date_assigned="25-03-2026", date_due="25-03-2026 à 23:59", date_completed=None, result="52,0 / 60 (86,7 %)"),
            # SCI414
            Assignment(course="SCI414 - Science et technologie de l'environnement", category="Laboratoire", title="Laboratoire rendement CD1", weight="1", date_assigned="27-02-2026", date_due="27-02-2026 à 23:59", date_completed=None, result="A"),
            Assignment(course="SCI414 - Science et technologie de l'environnement", category="Laboratoire CD2", title="Laboratoire rendement CD2", weight="1", date_assigned="19-02-2026", date_due="27-02-2026 à 23:59", date_completed=None, result="12,0 / 12 (100,0 %)"),
            Assignment(course="SCI414 - Science et technologie de l'environnement", category="", title="Examen chapitre 5", weight="45", date_assigned="27-03-2026", date_due="27-03-2026 à 23:59", date_completed=None, result="27,0 / 28 (96,4 %)"),
        ],
    },
    "bob": {
        "profile": UserProfile(
            full_name="Bob Gagné",
            permanent_code="GAGB98765432",
            photo_base64=None,
        ),
        "assignments": [
            Assignment(course="MAT416 - Mathématique: Sciences naturelles", category="NOTES", title="Examen final", weight="40", date_assigned="20-04-2026", date_due="20-04-2026 à 14:00", date_completed=None, result="91,0 / 100 (91,0 %)"),
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
