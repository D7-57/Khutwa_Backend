from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


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
    source: str = "template"
    is_ai_generated: bool = False
    overall_progress: float = 0.0
    created_at: datetime
    stages: list[StageOut] = []

    class Config:
        from_attributes = True


class RoadmapSummary(BaseModel):
    """Lightweight view for listing multiple roadmaps."""
    id: UUID
    title: str
    title_ar: str | None = None
    role_id: UUID | None = None
    role_name: str | None = None
    source: str = "template"
    is_ai_generated: bool = False
    overall_progress: float = 0.0
    stage_count: int = 0
    task_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class RoadmapGenerateRequest(BaseModel):
    role_id: UUID | None = None
    force_ai: bool = False
    language: str = "en"


class RoadmapGenerateResponse(BaseModel):
    roadmap: RoadmapOut
    source: str
    skill_gap: list[str] = []
    skills_matched: list[str] = []


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
