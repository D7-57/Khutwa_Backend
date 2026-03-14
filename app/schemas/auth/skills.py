from pydantic import BaseModel, Field
from uuid import UUID


class UserSkillAdd(BaseModel):
    """Add a skill to the user's profile."""
    skill_id: UUID
    level: str | None = None  # beginner | intermediate | advanced | expert
    years_experience: int | None = None


class UserSkillOut(BaseModel):
    id: UUID
    skill_id: UUID
    skill_name: str  # joined from skills table
    skill_category: str | None = None
    level: str | None = None
    years_experience: int | None = None
    source: str = "manual"

    class Config:
        from_attributes = True


class UserSkillBulkAdd(BaseModel):
    """Replace all user skills at once (onboarding or profile edit)."""
    skills: list[UserSkillAdd]