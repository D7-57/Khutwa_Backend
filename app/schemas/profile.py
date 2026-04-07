from pydantic import BaseModel
from uuid import UUID

class ProfileOut(BaseModel):
    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language: str = "en"

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language: str | None = None