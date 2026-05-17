"""
PDPL privacy / consent endpoints.

  GET    /auth/me/privacy              — read current settings
  PATCH  /auth/me/privacy              — update optional toggles
  POST   /auth/me/privacy/accept-terms — record terms acceptance (idempotent)
  DELETE /auth/me/data                 — right-to-erasure (PDPL Article 4)

Real per-feature gating (CV storage, interview history, roadmap
personalization) is wired up in those features' own routers using the
helpers exposed at the bottom of this file.
"""

from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.profile import Profile, CURRENT_TERMS_VERSION, _privacy_default
from app.services.account import delete_user_data
from app.schemas.auth.privacy import (
    PrivacySettingsOut,
    PrivacySettingsUpdate,
    AcceptTermsRequest,
    AcceptTermsResponse,
    PRIVACY_TOGGLE_KEYS,
)

router = APIRouter(prefix="/auth/me", tags=["privacy"])


# ════════════════════════════════════════════════════════════════════
#  HELPERS — used by this router AND by feature routers (CV, roadmap…)
# ════════════════════════════════════════════════════════════════════


def _ensure_privacy_shape(profile: Profile) -> dict:
    """
    Return profile.privacy_settings, backfilling any missing keys with
    the defaults. Existing rows from before this migration get {} as a
    server default — this fills in the rest the first time we touch them.
    """
    current = profile.privacy_settings or {}
    defaults = _privacy_default()
    needs_write = False

    for key, default in defaults.items():
        if key not in current:
            current[key] = default
            needs_write = True

    if needs_write:
        profile.privacy_settings = current
        flag_modified(profile, "privacy_settings")
    return current


def get_privacy_flags(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """
    Non-blocking dependency — returns the flags so the endpoint can branch.

    Use this in feature endpoints that should DEGRADE gracefully when a
    consent toggle is off (e.g. roadmap returns a manual one instead of
    erroring; CV evaluator runs but doesn't persist). Prefer this over
    require_privacy() — it gives the user a working app instead of a 403.
    """
    profile = db.get(Profile, UUID(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _ensure_privacy_shape(profile)


def require_privacy(key: str):
    """
    Hard-blocking dependency — 403s if the consent isn't granted.

    Only use this for endpoints that have NO sensible degraded mode (e.g.
    GET /interviews/history is meaningless if interview_personalization
    is off — there's nothing to return).
    """
    if key not in PRIVACY_TOGGLE_KEYS:
        raise ValueError(f"Unknown privacy key: {key}")

    def checker(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ):
        profile = db.get(Profile, UUID(user_id))
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        settings = _ensure_privacy_shape(profile)
        db.commit()  # persist any backfill from _ensure_privacy_shape

        if not settings.get(key):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PRIVACY_CONSENT_REQUIRED",
                    "key": key,
                    "message": (
                        f"This feature requires the '{key}' privacy "
                        f"setting to be enabled. Update it in Settings → "
                        f"Privacy."
                    ),
                },
            )
        return settings

    return checker


def settings_to_out(settings: dict) -> PrivacySettingsOut:
    """Convert raw JSONB dict → PrivacySettingsOut, computing terms_up_to_date."""
    accepted_version = settings.get("terms_accepted_version")
    return PrivacySettingsOut(
        terms_accepted=bool(settings.get("terms_accepted")),
        terms_accepted_version=accepted_version,
        terms_accepted_at=_parse_iso(settings.get("terms_accepted_at")),
        terms_up_to_date=(
            bool(settings.get("terms_accepted"))
            and accepted_version == CURRENT_TERMS_VERSION
        ),
        interview_personalization=bool(settings.get("interview_personalization")),
        interview_personalization_updated_at=_parse_iso(
            settings.get("interview_personalization_updated_at")
        ),
        roadmap_personalization=bool(settings.get("roadmap_personalization")),
        roadmap_personalization_updated_at=_parse_iso(
            settings.get("roadmap_personalization_updated_at")
        ),
        cv_storage=bool(settings.get("cv_storage")),
        cv_storage_updated_at=_parse_iso(settings.get("cv_storage_updated_at")),
    )


def _parse_iso(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str | None:
    """Best-effort IP extraction, honoring X-Forwarded-For if behind a proxy."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # X-Forwarded-For can be a comma-separated list — first entry is the client
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ════════════════════════════════════════════════════════════════════


# ── GET /auth/me/privacy ──


@router.get("/privacy", response_model=PrivacySettingsOut)
def get_my_privacy(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, UUID(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    settings = _ensure_privacy_shape(profile)
    db.commit()

    return settings_to_out(settings)


# ── PATCH /auth/me/privacy ──


@router.patch("/privacy", response_model=PrivacySettingsOut)
def update_my_privacy(
    body: PrivacySettingsUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update one or more optional consent toggles.

    Per-key updated_at is stamped automatically — this is the audit trail
    PDPL/SDAIA wants if a user later disputes whether/when they consented.

    NOTE: This endpoint canNOT be used to flip terms_accepted. Use the
    accept-terms endpoint for that. Even revoking terms goes through a
    different flow (account deletion) — you can't unilaterally un-accept
    terms while keeping your account.
    """
    profile = db.get(Profile, UUID(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    settings = _ensure_privacy_shape(profile)

    # Apply only the keys the client actually sent.
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        # No-op PATCH — fine, just return current state.
        db.commit()
        return settings_to_out(settings)

    now = _now_iso()
    for key, value in payload.items():
        if key not in PRIVACY_TOGGLE_KEYS:
            # Defensive — schema should prevent this, but belt + suspenders.
            continue
        settings[key] = bool(value)
        settings[f"{key}_updated_at"] = now

    profile.privacy_settings = settings
    flag_modified(profile, "privacy_settings")
    db.commit()
    db.refresh(profile)

    return settings_to_out(profile.privacy_settings)


# ── POST /auth/me/privacy/accept-terms ──


@router.post("/privacy/accept-terms", response_model=AcceptTermsResponse)
def accept_terms(
    body: AcceptTermsRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Record acceptance of the current Terms of Service / Privacy Policy.

    Idempotent: re-calling with the same version is fine and does NOT
    update the timestamp (we want to preserve the original acceptance
    moment for audit). Calling with a NEW version updates the record.

    Stale clients are rejected — if the version they're sending isn't
    the current one, they need to re-fetch the latest terms text.
    """
    if body.version != CURRENT_TERMS_VERSION:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TERMS_VERSION_MISMATCH",
                "client_version": body.version,
                "current_version": CURRENT_TERMS_VERSION,
                "message": (
                    "Your client is showing an outdated version of the "
                    "Terms. Please update the app and try again."
                ),
            },
        )

    profile = db.get(Profile, UUID(user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    settings = _ensure_privacy_shape(profile)

    already_current = (
        settings.get("terms_accepted") is True
        and settings.get("terms_accepted_version") == CURRENT_TERMS_VERSION
    )

    if not already_current:
        settings["terms_accepted"] = True
        settings["terms_accepted_version"] = CURRENT_TERMS_VERSION
        settings["terms_accepted_at"] = _now_iso()
        settings["terms_accepted_ip"] = _client_ip(request)

        profile.privacy_settings = settings
        flag_modified(profile, "privacy_settings")
        db.commit()
        db.refresh(profile)
        settings = profile.privacy_settings

    return AcceptTermsResponse(
        terms_accepted=True,
        terms_accepted_version=settings["terms_accepted_version"],
        terms_accepted_at=_parse_iso(settings["terms_accepted_at"]),
    )


# ── DELETE /auth/me/data ──


@router.delete("/data", status_code=200)
def delete_my_data(
    body: dict,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    PDPL right-to-erasure stub.

    Real per-scope deletion is wired up alongside each feature
    (CV-deletion when we touch the CV router, interview-deletion when
    we touch interviews, etc.). For now this validates the request
    shape and returns 501 with the scope echoed back so the frontend
    can build the UI against a stable contract.

    SCOPE behavior (when implemented):
      - "cv":                       wipe cv_documents + cv_evaluations rows for user
      - "interviews":               wipe interview history rows
      - "roadmap_personalization":  drop user_skills + user_roles rows; KEEP roadmaps
      - "all":                      wipe everything + delete the profile row
                                    (Supabase auth row handled separately)
    """
    confirm = bool(body.get("confirm"))
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="You must set confirm=true to proceed with deletion.",
        )
    # Keep compatibility with old clients that send `scope`.
    # Current app flow uses a full wipe while keeping the account.
    scope = (body.get("scope") or "all").strip().lower()
    if scope not in {"all", "cv", "interviews", "roadmap_personalization"}:
        raise HTTPException(status_code=400, detail="Invalid scope")
    if scope != "all":
        raise HTTPException(
            status_code=501,
            detail={
                "code": "NOT_IMPLEMENTED",
                "scope": scope,
                "message": "Partial-scope deletion is not implemented yet.",
            },
        )

    result = delete_user_data(db, user_id)
    return {
        "ok": True,
        "message": "All personal data has been deleted. Account remains active.",
        "deleted_counts": result.get("counts", {}),
        "storage_warning": result.get("storage_warning"),
    }