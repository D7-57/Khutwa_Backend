from pydantic import BaseModel
from uuid import UUID


# ── role tree ──


class RoleChild(BaseModel):
    id: UUID
    name: str
    description: str | None = None

    class Config:
        from_attributes = True


class RoleTreeNode(BaseModel):
    """A parent field with its child specializations."""
    id: UUID
    name: str
    description: str | None = None
    children: list[RoleChild] = []

    class Config:
        from_attributes = True


class RoleOut(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    parent_id: UUID | None = None

    class Config:
        from_attributes = True


# ── user role selection ──


class UserRoleSet(BaseModel):
    """User picks (or AI suggests) a role."""
    role_id: UUID
    source: str = "manual"  # manual | questionnaire | chatbot
    confidence: float = 1.0


class UserRoleOut(BaseModel):
    id: UUID
    role_id: UUID
    role_name: str
    confidence: float
    source: str
    is_primary: bool

    class Config:
        from_attributes = True


# ── role detection (AI) ──


class RoleDetectRequest(BaseModel):
    """Questionnaire answers or free-text for AI role detection."""
    answers: dict | None = None  # structured questionnaire answers
    message: str | None = None   # free-text chatbot message
    context: dict | None = None  # optional extra context (major, interests, etc.)


class RoleSuggestion(BaseModel):
    role_id: UUID
    role_name: str
    confidence: float
    reason: str  # why this role fits


class RoleDetectResponse(BaseModel):
    suggestions: list[RoleSuggestion]
    follow_up: str | None = None  # if AI needs more info