from pydantic import BaseModel
from uuid import UUID

class ProfileOut(BaseModel):
    id: UUID
    full_name: str | None = None
    phone: str | None = None
    language: str = "en"

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    language: str | None = None
