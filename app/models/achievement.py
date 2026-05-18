"""
Achievements system — Steam/PlayStation-style.

Two tables:
  • achievements        — catalog (seeded, immutable at runtime)
  • user_achievements   — per-user unlock log; one row per user-per-achievement

Design notes:
  • UUID PKs with default=uuid.uuid4 to match every other model in this codebase.
  • profile FK with ondelete=CASCADE so deleting a profile cleans up unlocks.
  • `seen` flag drives the "offline-earned pop-up" queue: a row is inserted at
    award time with seen=False, and only flips to True when the client either
    displays the toast or batches-up an explicit /mark-seen call.
  • Unique (user_id, achievement_id) prevents accidental double-awards from
    racing triggers (e.g. interview finalize firing twice).
  • Composite index on (user_id, seen) makes the unseen-pop-up query
    (`WHERE user_id=? AND seen=FALSE`) an index-only scan, which is the hot
    path every time the app resumes.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Achievement(Base):
    """
    Catalog row — one per achievement type. Seeded via seeds/achievements_seed.py.
    Bilingual title + description; `key` is the stable string ID used by triggers
    and the seeder's get_or_create.
    """

    __tablename__ = "achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Stable identifier (e.g. "interview_first", "cv_ats_80"). NEVER renamed
    # after seeding — the seed script and the services use this to look up rows.
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)

    # Bilingual presentation. Both required — no fallback at render-time.
    title_en: Mapped[str] = mapped_column(String(120), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)

    # Display: emoji icon and tier (bronze | silver | gold | platinum).
    # Tier drives the gradient on the toast and the catalog card border.
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="🏆")
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="bronze", server_default="bronze"
    )

    # Grouping for the achievements page (interview | cv | community | roadmap | meta).
    category: Mapped[str] = mapped_column(String(40), nullable=False)

    # Secret achievements display as ??? in the catalog until unlocked.
    is_secret: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Sort order in the UI grid. Lower = earlier. Doesn't have to be unique.
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserAchievement(Base):
    """
    Per-user unlock log. Inserted by app.services.achievements.check_and_award
    when a trigger condition is met. The `seen` flag drives the toast queue
    for offline-earned pop-ups (see /achievements/unseen).
    """

    __tablename__ = "user_achievements"
    __table_args__ = (
        # Idempotency: an achievement can only be earned once per user.
        # Multiple triggers firing in the same request all upsert against this.
        UniqueConstraint(
            "user_id", "achievement_id", name="uq_user_achievement"
        ),
        # Hot path: "give me everything this user hasn't seen yet".
        # Composite + matches the WHERE clause column order.
        Index("ix_user_achievements_user_seen", "user_id", "seen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
    )

    # False until the client confirms it displayed the toast (either via the
    # /mark-seen batch or by receiving it inline as new_achievements on the
    # response that caused the unlock). Drives the offline-pop-up queue.
    seen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    achievement: Mapped["Achievement"] = relationship("Achievement", lazy="joined")