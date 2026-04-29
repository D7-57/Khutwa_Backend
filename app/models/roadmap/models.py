import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ────────────────────────────────────────────────────────────────
#  ROADMAP TEMPLATES — pre-built stage/task structures per role
# ────────────────────────────────────────────────────────────────

class RoadmapTemplate(Base):
    __tablename__ = "roadmap_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # JSONB contains both languages per field:
    # stages[].title / title_ar, description / description_ar
    # stages[].tasks[].title / title_ar, description / description_ar
    stages_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


# ────────────────────────────────────────────────────────────────
#  USER ROADMAP — one active roadmap per user
# ────────────────────────────────────────────────────────────────

class UserRoadmap(Base):
    __tablename__ = "user_roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)

    source: Mapped[str] = mapped_column(
        String(30), default="template", nullable=False,
    )
    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    overall_progress: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ────────────────────────────────────────────────────────────────
#  ROADMAP STAGE
# ────────────────────────────────────────────────────────────────

class RoadmapStage(Base):
    __tablename__ = "roadmap_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_roadmaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_unlocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    progress: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False,
    )


# ────────────────────────────────────────────────────────────────
#  ROADMAP TASK
# ────────────────────────────────────────────────────────────────

class RoadmapTask(Base):
    __tablename__ = "roadmap_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmap_stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    skill_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    resources: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    is_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
