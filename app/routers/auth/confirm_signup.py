"""Dev helper: confirm Supabase user email via Admin API (when email confirmation blocks sign-up)."""

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class ConfirmSignupBody(BaseModel):
    user_id: str


@router.post("/confirm-signup")
def confirm_signup(
    body: ConfirmSignupBody,
    x_khutwa_dev_key: str | None = Header(None, alias="X-Khutwa-Dev-Key"),
):
    """
    Requires backend `.env`:
      - SUPABASE_SERVICE_ROLE_KEY
      - KHUTWA_DEV_CONFIRM_KEY (same string as Flutter `KHUTWA_DEV_CONFIRM_KEY`)

    Flutter calls without user JWT right after signUp when session is null.
    """
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Server missing SUPABASE_SERVICE_ROLE_KEY — cannot confirm users.",
        )
    if not settings.KHUTWA_DEV_CONFIRM_KEY:
        raise HTTPException(
            status_code=503,
            detail="Server missing KHUTWA_DEV_CONFIRM_KEY — add it to backend and Flutter .env, "
            "or disable email confirmation in Supabase Auth settings.",
        )
    if not x_khutwa_dev_key or x_khutwa_dev_key != settings.KHUTWA_DEV_CONFIRM_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Khutwa-Dev-Key header.")

    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{body.user_id}"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.patch(
            url,
            headers=headers,
            json={"email_confirm": True},
            timeout=15,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supabase admin request failed: {e}") from e

    if r.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=f"Supabase admin error ({r.status_code}): {r.text}",
        )

    return {"ok": True, "user_id": body.user_id}
