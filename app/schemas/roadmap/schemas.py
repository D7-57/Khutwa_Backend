"""
Pydantic schemas for the roadmap feature.

Notes for reviewers:
  - We intentionally do NOT include the manual-creation or publish
    schemas. They were partially scaffolded but pulled until we do
    them properly. The roadmap model also does not carry an
    is_published column for the same reason.
  - skill_focus / include_tangible_outcome on RoadmapGenerateRequest
    are optional — when omitted, /regenerate inherits from the
    existing roadmap row, /generate defaults to None / False.
"""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# ── Resources (embedded in tasks) ──

class ResourceItem(BaseModel):
    type: str = Field(..., description="course | article | video | book")
    title: str
    url: str = ""

    class Config:
        from_attributes = True


# ── Task ──

class TaskOut(BaseModel):
    id: UUID
    order: int
    title: str
    title_ar: str | None = None
    description: str | None = None
    description_ar: str | None = None
    skill_name: str | None = None
    resources: list[ResourceItem] = []
    is_completed: bool = False
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class TaskComplete(BaseModel):
    task_id: UUID
    stage_progress: float
    overall_progress: float
    stage_completed: bool
    next_stage_unlocked: bool


# ── Stage ──

class StageOut(BaseModel):
    id: UUID
    order: int
    title: str
    title_ar: str | None = None
    description: str | None = None
    description_ar: str | None = None
    is_unlocked: bool = False
    is_completed: bool = False
    progress: float = 0.0
    tasks: list[TaskOut] = []

    class Config:
        from_attributes = True


# ── Roadmap ──

class RoadmapOut(BaseModel):
    id: UUID
    title: str
    title_ar: str | None = None
    role_id: UUID | None = None
    role_name: str | None = None
    role_name_ar: str | None = None
    source: str = "template"
    is_ai_generated: bool = False
    overall_progress: float = 0.0
    created_at: datetime
    stages: list[StageOut] = []

    # NEW: persisted generation context so the UI can render badges
    # ("Focused on AWS", "Ends with a capstone") and the Regenerate
    # sheet can pre-fill the same values.
    skill_focus: str | None = None
    include_tangible_outcome: bool = False

    class Config:
        from_attributes = True


class RoadmapSummary(BaseModel):
    """Lightweight view for listing multiple roadmaps."""
    id: UUID
    title: str
    title_ar: str | None = None
    role_id: UUID | None = None
    role_name: str | None = None
    role_name_ar: str | None = None
    source: str = "template"
    is_ai_generated: bool = False
    overall_progress: float = 0.0
    stage_count: int = 0
    task_count: int = 0
    created_at: datetime

    skill_focus: str | None = None
    include_tangible_outcome: bool = False

    class Config:
        from_attributes = True


# ── Generation request / response ──

class RoadmapGenerateRequest(BaseModel):
    role_id: UUID | None = None
    force_ai: bool = False
    language: str = "en"

    # ── Task 1: Custom Skill Input ──────────────────────────────────────
    # Free-text focus the user typed in the "Create roadmap" sheet:
    # "Get AWS certified", "Build a portfolio in React", etc.
    # Empty string and None both mean "no focus".
    skill_focus: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional free-text focus (e.g. 'Get AWS certified', "
            "'Build a React portfolio'). Gets prepended to the AI prompt "
            "as a SPECIFIC FOCUS section."
        ),
    )

    # ── Task 5: Tangible Outcomes ───────────────────────────────────────
    # When True, the AI is instructed to end the roadmap with a final
    # capstone stage that produces something the user can show:
    # a small project, deployed app, or a certification.
    include_tangible_outcome: bool = Field(
        default=False,
        description=(
            "If True, ask the AI to end the roadmap with a tangible "
            "deliverable (project or certification)."
        ),
    )


class RoadmapGenerateResponse(BaseModel):
    roadmap: RoadmapOut
    source: str

    # Skill names the user already had that matched the role's requirements.
    skills_matched: list[str] = []

    # Skill names the user is missing for this role — the gap the
    # roadmap is filling. Used by the frontend to show a "Gap analysis"
    # banner above the new roadmap.
    skill_gap: list[str] = []

    # NEW: skills extracted from the user's PREVIOUS roadmaps. The frontend
    # can show these as "Previously covered — we won't repeat these"
    # to make the Skill Gap Analysis (Task 4) visible to the user.
    previously_covered_skills: list[str] = []


# ── Template preview ──

class TemplatePreview(BaseModel):
    id: UUID
    role_id: UUID
    role_name: str | None = None
    title: str
    title_ar: str | None = None
    stage_count: int
    task_count: int
    stages_json: dict

    class Config:
        from_attributes = True