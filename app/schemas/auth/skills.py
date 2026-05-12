from pydantic import BaseModel, Field, model_validator
from uuid import UUID


class UserSkillAdd(BaseModel):
    """
    Add a skill to the user's profile.

    Provide EITHER `skill_id` (catalog row) OR `custom_name` (free
    text). The model validator below enforces that exactly one is set.
    """
    skill_id: UUID | None = None
    custom_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description=(
            "Free-text skill name. Use only when no matching catalog "
            "skill exists. Trimmed and stored as-is."
        ),
    )
    level: str | None = None  # beginner | intermediate | advanced | expert
    years_experience: int | None = None

    @model_validator(mode="after")
    def _check_one_set(self):
        has_id = self.skill_id is not None
        has_custom = bool(self.custom_name and self.custom_name.strip())
        if has_id and has_custom:
            raise ValueError(
                "Provide skill_id OR custom_name, not both. "
                "If the catalog has this skill, prefer skill_id."
            )
        if not has_id and not has_custom:
            raise ValueError(
                "Must provide either skill_id or custom_name."
            )
        if has_custom:
            self.custom_name = self.custom_name.strip()
        return self


class UserSkillOut(BaseModel):
    id: UUID

    # Either skill_id is set (catalog skill) or it's None and we fall
    # back to custom_name. The client should display whichever isn't None.
    skill_id: UUID | None = None
    skill_name: str  # joined from skills table OR mirror of custom_name
    skill_category: str | None = None
    custom_name: str | None = None
    is_custom: bool = False  # convenience for the frontend

    level: str | None = None
    years_experience: int | None = None
    source: str = "manual"

    class Config:
        from_attributes = True


class UserSkillBulkAdd(BaseModel):
    """Replace all user skills at once (onboarding or profile edit)."""
    skills: list[UserSkillAdd]