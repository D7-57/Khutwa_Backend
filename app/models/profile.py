import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, DateTime, func, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ───────────────────────────────────────────────────────────────────
#  PRIVACY DEFAULT — shape of profiles.privacy_settings (JSONB)
# ───────────────────────────────────────────────────────────────────
#
# All three personalization toggles default OFF (PDPL: consent must be
# explicit + opt-in). Terms must be accepted separately via the
# /auth/me/privacy/accept-terms endpoint, which records the version,
# timestamp, and IP for audit purposes.
#
# Each consent key tracks its own updated_at so we can prove WHEN
# consent was given/revoked — required for PDPL compliance evidence.

CURRENT_TERMS_VERSION = "v1"


def _privacy_default() -> dict:
    return {
        # ── Terms / Privacy Policy acceptance (legal basis: contract) ──
        "terms_accepted": False,
        "terms_accepted_version": None,   # which version they accepted
        "terms_accepted_at": None,        # ISO timestamp
        "terms_accepted_ip": None,        # IP at time of acceptance

        # ── Optional consent toggles (legal basis: explicit consent) ──
        # Each toggle has: on/off + when it was last changed.
        "interview_personalization": False,
        "interview_personalization_updated_at": None,

        "roadmap_personalization": False,
        "roadmap_personalization_updated_at": None,

        "cv_storage": False,
        "cv_storage_updated_at": None,
    }


class Profile(Base):
    __tablename__ = "profiles"

    # matches Supabase auth.users.id
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # profile / onboarding fields
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    major: Mapped[str | None] = mapped_column(String(120), nullable=True)
    university: Mapped[str | None] = mapped_column(String(150), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # categorical bucket — one of "0", "<1", "1", "2", "3+".
    years_of_experience: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # JSON fields for MVP
    certifications: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    languages: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    projects: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    experiences: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)

    # ── PDPL privacy / consent settings ──
    # Single JSONB column so migrations stay cheap as the consent model
    # evolves. See _privacy_default() above for the shape.
    privacy_settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=_privacy_default,
        server_default="{}",  # existing rows get {} on migration; app backfills
    )

    # onboarding tracking
    onboarding_complete: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )