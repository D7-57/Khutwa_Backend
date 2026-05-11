"""
Account management endpoints.

  DELETE /auth/me/data        — wipe content, keep account ("Delete My Data")
  DELETE /auth/me/account     — wipe content + auth user ("Delete My Account")
  PATCH  /auth/me/contact     — change email/phone (goes through admin API)

The contact update endpoint exists because direct UPDATEs to
profiles.email don't propagate to auth.users.email — and auth.users is
what the login system uses. This endpoint routes the change through the
Supabase Admin API (the supported path) and then mirrors to the profile.
"""

from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.profile import Profile
from app.services.account import delete_user_data, delete_user_account
from app.services.supabase_admin import update_auth_user

router = APIRouter(prefix="/auth/me", tags=["account"])


# ════════════════════════════════════════════════════════════════════
#  Schemas (small enough to live in the router)
# ════════════════════════════════════════════════════════════════════


class DeletionConfirmRequest(BaseModel):
    """
    Both delete endpoints require an explicit confirm flag.

    This is belt-and-suspenders against:
      - A misclick on the frontend
      - A bot/CSRF-style attack that fires the DELETE method on its own
        (the body requirement means a simple HTTP DELETE won't suffice)
    """
    confirm: bool = Field(
        ...,
        description="Must be true. Required to prevent accidental deletes.",
    )


class DeletionResponse(BaseModel):
    message: str
    deleted_counts: dict
    # Only present if Storage cleanup had a problem. DB wipe still succeeded.
    storage_warning: str | None = None


class ContactUpdateRequest(BaseModel):
    """
    At least one of email/phone must be present. Both can be sent in
    a single call; the admin API handles them atomically.
    """
    email: EmailStr | None = None
    phone: str | None = Field(
        None,
        min_length=4,
        max_length=20,
        description="E.164 format recommended (e.g. +966501234567).",
    )


class ContactUpdateResponse(BaseModel):
    email: str | None
    phone: str | None
    updated_at: datetime


# ════════════════════════════════════════════════════════════════════
#  DELETE /auth/me/data — "Delete My Data" button
# ════════════════════════════════════════════════════════════════════


@router.delete("/data", response_model=DeletionResponse)
def delete_my_data(
    body: DeletionConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    PDPL right-to-erasure on user-generated content.

    Wipes CVs, roadmaps, quiz attempts, etc. Resets the three optional
    consent toggles to OFF. KEEPS the account active so the user can
    continue using Khutwa with a fresh slate.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="You must set confirm=true to proceed.",
        )

    result = delete_user_data(db, user_id)

    # TODO(audit-email): send a "your data has been deleted" confirmation
    # email to the user's address (PDPL paper trail). When you wire up
    # the email-sending utility, call it here. For now we just return
    # success — the frontend can show a banner.

    return DeletionResponse(
        message=(
            "All personal data has been deleted. Your account remains "
            "active and you can continue using Khutwa."
        ),
        deleted_counts=result["counts"],
        storage_warning=result.get("storage_warning"),
    )


# ════════════════════════════════════════════════════════════════════
#  DELETE /auth/me/account — "Delete My Account" button
# ════════════════════════════════════════════════════════════════════


@router.delete("/account", response_model=DeletionResponse)
def delete_my_account(
    body: DeletionConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Permanent account deletion. Wipes EVERYTHING and removes the
    auth.users row. Irreversible.

    After this call returns, the bearer token used to authenticate the
    request is invalid — the next request from the same token will 401.
    The frontend should clear local state and redirect to login.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="You must set confirm=true to proceed.",
        )

    result = delete_user_account(db, user_id)

    # TODO(audit-email): send a "your account has been deleted" final
    # email before the auth row is gone. Tricky because we already
    # deleted the auth user above — the email needs to be captured
    # earlier in the flow, OR sent via a queue. Defer to when email is
    # wired up.

    return DeletionResponse(
        message="Account permanently deleted.",
        deleted_counts=result["counts"],
        storage_warning=result.get("storage_warning"),
    )


# ════════════════════════════════════════════════════════════════════
#  PATCH /auth/me/contact — email/phone change (routed through admin API)
# ════════════════════════════════════════════════════════════════════


@router.patch("/contact", response_model=ContactUpdateResponse)
def update_my_contact(
    body: ContactUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update email and/or phone.

    Why this is a separate endpoint (not part of PATCH /auth/me):
      Direct UPDATEs to profiles.email don't propagate to auth.users.email,
      and auth.users is the table the login system uses. Updating only
      the profile silently breaks the user's ability to log in with
      their new address.

    Flow:
      1. Call Supabase Admin API → updates auth.users (source of truth).
      2. Mirror to profiles table on success.
      3. Return the new values to the client.

    email_confirm=True bypasses the confirmation email — this matches
    your current dev/testing setup where signup confirmations are also
    disabled. When you re-enable confirmations for production, change
    update_auth_user's defaults (or expose email_confirm here) so users
    have to click a link before the change applies.
    """
    if body.email is None and body.phone is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: email, phone.",
        )

    uid = UUID(user_id)
    profile = db.get(Profile, uid)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # 1) Update auth.users via admin API. This is the source of truth.
    update_auth_user(
        user_id,
        email=body.email,
        phone=body.phone,
        # Auto-confirm: skip the confirmation email/SMS. Matches the
        # current dashboard setting where signup confirmations are off.
        email_confirm=True,
        phone_confirm=True,
    )

    # 2) Mirror to profile.
    if body.email is not None:
        profile.email = body.email
    if body.phone is not None:
        profile.phone = body.phone

    db.commit()
    db.refresh(profile)

    return ContactUpdateResponse(
        email=profile.email,
        phone=profile.phone,
        updated_at=datetime.now(timezone.utc),
    )