import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, DateTime, func, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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

    # NEW: categorical bucket — one of "0", "<1", "1", "2", "3+".
    # Stored as a String because "<1" and "3+" don't map cleanly to a single integer.
    years_of_experience: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # JSON fields for MVP
    certifications: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    languages: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    projects: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)
    experiences: Mapped[list] = mapped_column(JSONB, default=list, nullable=True)

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