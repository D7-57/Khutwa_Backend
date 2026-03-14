from pydantic import BaseModel
from uuid import UUID


class SkillOut(BaseModel):
    id: UUID
    name: str
    category: str | None = None
    description: str | None = None

    class Config:
        from_attributes = True


class RoleSkillOut(BaseModel):
    """A skill required for a specific role, with importance."""
    skill_id: UUID
    skill_name: str
    category: str | None = None
    importance_weight: float

    class Config:
        from_attributes = True