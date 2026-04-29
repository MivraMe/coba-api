from pydantic import BaseModel


class Assignment(BaseModel):
    course: str
    category: str
    title: str
    weight: str
    date_assigned: str | None = None
    date_due: str | None = None
    date_completed: str | None = None
    result: str | None = None


class NotesResponse(BaseModel):
    count: int
    assignments: list[Assignment]
