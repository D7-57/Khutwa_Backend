from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.auth.profile import (
    ProfileOut,
    ProfileUpdate,
    OnboardingBasicInfo,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_or_create_profile(uid: UUID, db: Session) -> Profile:
    profile = db.get(Profile, uid)
    if profile is None:
        profile = Profile(id=uid, language="en")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


# ── GET /auth/me ──


@router.get("/me", response_model=ProfileOut)
def me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    profile = _get_or_create_profile(uid, db)
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
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
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

    db.commit()
    db.refresh(profile)
    return _profile_to_out(profile)


# ── POST /auth/onboarding/complete  (mark onboarding done) ──


@router.post("/onboarding/complete", response_model=ProfileOut)
def onboarding_complete(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    profile = _get_or_create_profile(uid, db)
    profile.onboarding_complete = True
    db.commit()
    db.refresh(profile)
    return _profile_to_out(profile)


# ── helper ──


def _profile_to_out(profile: Profile) -> ProfileOut:
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
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        certifications=profile.certifications or [],
        languages=profile.languages or [],
        projects=profile.projects or [],
        experiences=profile.experiences or [],
        onboarding_complete=profile.onboarding_complete or False,
        created_at=profile.created_at,
    )