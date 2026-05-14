from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import get_current_user_id, get_current_auth_user, AuthUser
from app.db.session import get_db
from app.models.profile import Profile, CURRENT_TERMS_VERSION, _privacy_default
from app.schemas.auth.profile import (
    ProfileOut,
    ProfileUpdate,
    OnboardingBasicInfo,
)
from app.routers.auth.privacy import settings_to_out, _client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_or_create_profile(
    uid: UUID,
    db: Session,
    *,
    email: str | None = None,
    phone: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> Profile:
    profile = db.get(Profile, uid)
    if profile is None:
        profile = Profile(
            id=uid,
            language="en",
            email=email,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            privacy_settings=_privacy_default(),
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        # Back-fill any nulls from the JWT claims (one-time repair)
        changed = False
        if profile.email is None and email:
            profile.email = email
            changed = True
        if profile.phone is None and phone:
            profile.phone = phone
            changed = True
        if profile.first_name is None and first_name:
            profile.first_name = first_name
            changed = True
        if profile.last_name is None and last_name:
            profile.last_name = last_name
            changed = True
        # Backfill privacy_settings for rows created before this column
        # had a default. We only fill missing keys — we never overwrite.
        if not profile.privacy_settings:
            profile.privacy_settings = _privacy_default()
            flag_modified(profile, "privacy_settings")
            changed = True
        if changed:
            db.commit()
            db.refresh(profile)
    return profile


# ── GET /auth/me ──


@router.get("/me", response_model=ProfileOut)
def me(
    auth: AuthUser = Depends(get_current_auth_user),
    db: Session = Depends(get_db),
):
    uid = UUID(auth.id)
    profile = _get_or_create_profile(
        uid, db,
        email=auth.email,
        phone=auth.phone,
        first_name=auth.first_name,
        last_name=auth.last_name,
    )
    return _profile_to_out(profile)


# ── PATCH /auth/me  (general profile update) ──


@router.patch("/me", response_model=ProfileOut)
def update_me(
    body: ProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    profile = _get_or_create_profile(uid, db)

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return _profile_to_out(profile)


# ── POST /auth/onboarding/basic  (step 1 of signup) ──


@router.post("/onboarding/basic", response_model=ProfileOut)
def onboarding_basic(
    body: OnboardingBasicInfo,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Step 1 of signup. Collects basic info AND records terms acceptance.

    Per PDPL, terms acceptance must be recorded at signup with version,
    timestamp, and IP for the audit trail. The schema enforces
    accept_terms=True; we additionally validate the version here so a
    stale client can't lock the user into an old version.
    """
    # Validate the version the client sent matches what's currently live.
    if body.terms_version != CURRENT_TERMS_VERSION:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TERMS_VERSION_MISMATCH",
                "client_version": body.terms_version,
                "current_version": CURRENT_TERMS_VERSION,
                "message": (
                    "Your client is showing an outdated version of the "
                    "Terms. Please update the app and try again."
                ),
            },
        )

    uid = UUID(user_id)
    profile = _get_or_create_profile(uid, db)

    profile.first_name = body.first_name.strip()
    profile.last_name = body.last_name.strip()
    profile.language = body.language
    if body.phone is not None:
        profile.phone = body.phone
    if body.major is not None:
        profile.major = body.major
    if body.university is not None:
        profile.university = body.university
    if body.graduation_year is not None:
        profile.graduation_year = body.graduation_year
    if body.current_status is not None:
        profile.current_status = body.current_status
    if body.years_of_experience is not None:
        profile.years_of_experience = body.years_of_experience

    # ── Record terms acceptance ──
    settings = profile.privacy_settings or _privacy_default()
    # Only stamp the timestamp on the FIRST acceptance of this version.
    # If they're already on the current version (e.g. retrying onboarding),
    # don't overwrite the original acceptance moment.
    already_current = (
        settings.get("terms_accepted") is True
        and settings.get("terms_accepted_version") == CURRENT_TERMS_VERSION
    )
    if not already_current:
        settings["terms_accepted"] = True
        settings["terms_accepted_version"] = CURRENT_TERMS_VERSION
        settings["terms_accepted_at"] = datetime.now(timezone.utc).isoformat()
        settings["terms_accepted_ip"] = _client_ip(request)
        profile.privacy_settings = settings
        flag_modified(profile, "privacy_settings")

    db.commit()
    db.refresh(profile)
    return _profile_to_out(profile)


# ── POST /auth/onboarding/complete  (mark onboarding done) ──


@router.post("/onboarding/complete", response_model=ProfileOut)
def onboarding_complete(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Finalize onboarding.

    PDPL guard: refuses to mark onboarding complete if terms were not
    accepted. This catches clients that somehow skipped /onboarding/basic
    and tries to jump straight here.
    """
    uid = UUID(user_id)
    profile = _get_or_create_profile(uid, db)

    settings = profile.privacy_settings or {}
    if not settings.get("terms_accepted"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TERMS_NOT_ACCEPTED",
                "message": (
                    "Terms of Service must be accepted before completing "
                    "onboarding."
                ),
            },
        )

    profile.onboarding_complete = True
    db.commit()
    db.refresh(profile)
    return _profile_to_out(profile)


# ── helper ──


def _profile_to_out(profile: Profile) -> ProfileOut:
    settings = profile.privacy_settings or _privacy_default()
    return ProfileOut(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        username=profile.username,
        phone=profile.phone,
        language=profile.language,
        bio=profile.bio,
        major=profile.major,
        university=profile.university,
        graduation_year=profile.graduation_year,
        current_status=profile.current_status,
        years_of_experience=profile.years_of_experience,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        certifications=profile.certifications or [],
        languages=profile.languages or [],
        projects=profile.projects or [],
        experiences=profile.experiences or [],
        onboarding_complete=profile.onboarding_complete or False,
        privacy=settings_to_out(settings),
        created_at=profile.created_at,
    )

