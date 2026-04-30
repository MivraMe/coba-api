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


class UserProfile(BaseModel):
    full_name: str
    permanent_code: str
    photo_base64: str | None = None  # base64-encoded image (data URI ready)


class OnboardingResponse(BaseModel):
    profile: UserProfile
    count: int
    assignments: list[Assignment]
