from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime


# Allowed buckets for years_of_experience.
# Kept as strings because "<1" and "3+" don't map cleanly to a single integer.
ALLOWED_YEARS_OF_EXPERIENCE = {"0", "<1", "1", "2", "3+"}


# ── reusable nested shapes for JSONB columns ──


class CertificationItem(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None  # "2024-06" or free-text
    url: str | None = None


class ProjectItem(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    tech: list[str] = []


class ExperienceItem(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None  # None = "present"
    description: str | None = None


class LanguageItem(BaseModel):
    language: str
    level: str | None = None  # native / fluent / intermediate / beginner


# ── profile output ──


class ProfileOut(BaseModel):
    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    language: str = "en"

    # academic / status
    bio: str | None = None
    major: str | None = None
    university: str | None = None
    graduation_year: int | None = None
    current_status: str | None = None  # student | fresh_graduate | job_seeker | employed

    # NEW: one of "0", "<1", "1", "2", "3+"
    years_of_experience: str | None = None

    # links
    linkedin_url: str | None = None
    github_url: str | None = None

    # JSONB lists
    certifications: list[CertificationItem] = []
    languages: list[LanguageItem] = []
    projects: list[ProjectItem] = []
    experiences: list[ExperienceItem] = []

    # onboarding progress flag
    onboarding_complete: bool = False

    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ── profile update (PATCH) – every field optional ──


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language: str | None = None

    bio: str | None = None
    major: str | None = None
    university: str | None = None
    graduation_year: int | None = None
    current_status: str | None = None

    # NEW
    years_of_experience: str | None = None

    linkedin_url: str | None = None
    github_url: str | None = None

    certifications: list[CertificationItem] | None = None
    languages: list[LanguageItem] | None = None
    projects: list[ProjectItem] | None = None
    experiences: list[ExperienceItem] | None = None

    @field_validator("years_of_experience")
    @classmethod
    def _check_yoe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_YEARS_OF_EXPERIENCE:
            raise ValueError(
                f"years_of_experience must be one of {sorted(ALLOWED_YEARS_OF_EXPERIENCE)}"
            )
        return v


# ── onboarding step 1: basic info ──


class OnboardingBasicInfo(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    phone: str | None = None
    major: str | None = None
    university: str | None = None
    graduation_year: int | None = None
    current_status: str | None = None  # student | fresh_graduate | job_seeker | employed
    language: str = "en"

    # NEW – optional at this step so older clients don't break.
    years_of_experience: str | None = None

    @field_validator("years_of_experience")
    @classmethod
    def _check_yoe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALLOWED_YEARS_OF_EXPERIENCE:
            raise ValueError(
                f"years_of_experience must be one of {sorted(ALLOWED_YEARS_OF_EXPERIENCE)}"
            )
        return v