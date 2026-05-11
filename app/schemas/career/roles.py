from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional

from app.schemas.career.questionnaire import QuestionnaireAnswers


# ── role tree ──────────────────────────────────────────────────────────────────


class RoleChild(BaseModel):
    """A selectable leaf role inside a domain."""
    id: UUID
    name: str
    name_en: str
    name_ar: str
    description: str | None = None
    role_type: str = "role"

    class Config:
        from_attributes = True


class RoleTreeNode(BaseModel):
    """A domain (mid-level) with its child leaf roles."""
    id: UUID
    name: str
    name_en: str
    name_ar: str
    description: str | None = None
    role_type: str = "domain"
    field_name: str | None = None   # parent field: 'Information Technology' | 'Engineering' | 'Business'
    children: list[RoleChild] = []

    class Config:
        from_attributes = True


class RoleOut(BaseModel):
    id: UUID
    name: str
    name_en: str
    name_ar: str
    description: str | None = None
    role_type: str
    parent_id: UUID | None = None

    class Config:
        from_attributes = True


# ── user role selection ────────────────────────────────────────────────────────


class UserRoleSet(BaseModel):
    """User picks (or AI suggests) a role."""
    role_id: UUID
    source: str = "manual"    # manual | questionnaire | chatbot | cv
    confidence: float = 1.0


class UserRoleBulkSet(BaseModel):
    """Replace all user roles at once (onboarding multi-select, max 3)."""
    roles: list[UserRoleSet]


class UserRoleOut(BaseModel):
    id: UUID
    role_id: UUID
    role_name: str
    role_name_ar: str
    confidence: float
    source: str
    is_primary: bool

    class Config:
        from_attributes = True


# ── role detection (AI) ────────────────────────────────────────────────────────


class RoleDetectRequest(BaseModel):
    """Accepts either structured questionnaire answers or free-text."""
    answers: QuestionnaireAnswers | None = None
    message: str | None = None    # free-text chatbot message
    context: dict | None = None   # optional extra context (CV, major, etc.)


class RoleSuggestion(BaseModel):
    role_id: UUID
    role_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.85:
            return "Strong match"
        if self.confidence >= 0.65:
            return "Good match"
        return "Worth exploring"

    @property
    def confidence_label_ar(self) -> str:
        if self.confidence >= 0.85:
            return "تطابق قوي"
        if self.confidence >= 0.65:
            return "تطابق جيد"
        return "يستحق الاستكشاف"


class RoleDetectResponse(BaseModel):
    suggestions: list[RoleSuggestion]
    follow_up: Optional[str] = None

    @property
    def top_match(self) -> Optional[RoleSuggestion]:
        return self.suggestions[0] if self.suggestions else None

    @property
    def has_clear_winner(self) -> bool:
        if len(self.suggestions) < 2:
            return bool(self.suggestions)
        return (
            self.suggestions[0].confidence - self.suggestions[1].confidence
        ) > 0.15