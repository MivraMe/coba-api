from pydantic import BaseModel


class Note(BaseModel):
    title: str
    body: str
    date: str | None = None


class NotesResponse(BaseModel):
    count: int
    notes: list[Note]
