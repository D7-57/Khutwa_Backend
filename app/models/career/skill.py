import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class UserSkill(Base):
    """
    A skill the user claims to have.

    EITHER `skill_id` (points to a catalog row in `skills`) OR
    `custom_name` (free-text) is set. Both can be set if the user
    typed something we then resolved to a catalog row later, but
    only one is required.

    The free-text path exists because the AI-generated roadmaps produce
    task.skill_name as free-text strings (e.g. "React Hooks") that
    may not match anything in our catalog. We let users record them
    anyway, then run periodic dedup jobs to merge custom_name entries
    into the catalog.
    """
    __tablename__ = "user_skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # NOW NULLABLE — for free-text skills that don't match the catalog.
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Free-text skill name used when skill_id is NULL.
    custom_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # source: "manual" (onboarding/profile edit) or "roadmap" (added
    # after completing a roadmap task). Useful for both dedup heuristics
    # and showing the user where the skill came from.
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Existing constraint stays: a user can't have the same catalog skill
        # twice. NULL values in skill_id are treated as distinct by Postgres,
        # so this doesn't apply to free-text entries.
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),

        # NEW: partial unique index so a user can't have the same
        # free-text skill name twice (case-insensitive). Only applies
        # when skill_id is NULL.
        Index(
            "uq_user_custom_skill",
            "user_id",
            text("lower(custom_name)"),
            unique=True,
            postgresql_where=text("skill_id IS NULL AND custom_name IS NOT NULL"),
        ),
    )