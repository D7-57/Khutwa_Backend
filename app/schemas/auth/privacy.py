"""
PDPL privacy / consent schemas.

Three optional toggles + one mandatory terms acceptance, exposed
through GET/PATCH /auth/me/privacy and POST /auth/me/privacy/accept-terms.
"""

from pydantic import BaseModel, Field
from datetime import datetime


# ── allowed keys for the consent toggles ──
# (terms is handled by its own endpoint, not via this list)

PRIVACY_TOGGLE_KEYS = {
    "interview_personalization",
    "roadmap_personalization",
    "cv_storage",
}


# ── output: what GET /auth/me/privacy returns ──

class PrivacySettingsOut(BaseModel):
    """Full snapshot of a user's privacy state."""

    # Terms section — read-only via this endpoint; modified by accept-terms.
    terms_accepted: bool = False
    terms_accepted_version: str | None = None
    terms_accepted_at: datetime | None = None
    # NOTE: terms_accepted_ip is intentionally NOT exposed to the client.
    # It's audit data, not user-facing.

    # Whether the version they accepted is the current version.
    # If False, the client should show a "please re-accept updated terms"
    # modal on next app open. Computed in the router.
    terms_up_to_date: bool = False

    # The three optional consent toggles.
    interview_personalization: bool = False
    interview_personalization_updated_at: datetime | None = None

    roadmap_personalization: bool = False
    roadmap_personalization_updated_at: datetime | None = None

    cv_storage: bool = False
    cv_storage_updated_at: datetime | None = None


# ── input: PATCH /auth/me/privacy ──

class PrivacySettingsUpdate(BaseModel):
    """
    Update one or more of the optional consent toggles.

    All fields optional — only provided keys are changed. Terms acceptance
    is NOT changeable through this endpoint (use accept-terms instead) to
    prevent accidental mass-revoke flows and to keep the audit trail clean.
    """

    interview_personalization: bool | None = None
    roadmap_personalization: bool | None = None
    cv_storage: bool | None = None


# ── input: POST /auth/me/privacy/accept-terms ──

class AcceptTermsRequest(BaseModel):
    """
    Idempotent terms acceptance.

    Client sends the version string of the terms they're agreeing to.
    Server validates it matches the current version (so a stale client
    can't lock a user into accepting an old version) and records the
    acceptance with timestamp + IP.
    """

    version: str = Field(..., min_length=1, max_length=20)


class AcceptTermsResponse(BaseModel):
    terms_accepted: bool
    terms_accepted_version: str
    terms_accepted_at: datetime


# ── input: DELETE /auth/me/data ──

class DataDeletionRequest(BaseModel):
    """
    Right-to-erasure request (PDPL Article 4 — data subject rights).

    Scope determines what gets wiped:
      - "cv"                       → all CV docs + evaluations
      - "interviews"               → interview history + scoring data
      - "roadmap_personalization"  → skill-derived roadmap metadata
                                     (does NOT delete the roadmap itself)
      - "all"                      → full account wipe (profile + everything)
    """

    scope: str = Field(..., pattern="^(cv|interviews|roadmap_personalization|all)$")
    confirm: bool = Field(
        ...,
        description="Must be true. Belt-and-suspenders against accidental DELETEs.",
    )