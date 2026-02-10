from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=ProfileOut)
def me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    profile = db.get(Profile, uid)

    # Auto-create profile on first login
    if profile is None:
        profile = Profile(id=uid, language="en")
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile

@router.patch("/me", response_model=ProfileOut)
def update_me(
    body: ProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    uid = UUID(user_id)
    profile = db.get(Profile, uid)

    if profile is None:
        profile = Profile(id=uid, language="en")
        db.add(profile)

    if body.full_name is not None:
        profile.full_name = body.full_name
    if body.phone is not None:
        profile.phone = body.phone
    if body.language is not None:
        profile.language = body.language

    db.commit()
    db.refresh(profile)
    return profile
