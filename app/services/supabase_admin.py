"""
Supabase Admin API wrapper.

Centralizes all calls that use the SERVICE_ROLE_KEY so we can audit them
in one place. The service role bypasses RLS and can read/write
auth.users — treat it like a root key, never expose it to clients,
never log it.

Why httpx and not the supabase-py SDK: the rest of this codebase already
uses raw httpx (see services/supabase_storage.py). Keeping it consistent
avoids adding a dependency for two endpoints.
"""

import httpx
from fastapi import HTTPException

from app.core.config import settings


# ── internals ──


def _base_url() -> str:
    return settings.SUPABASE_URL.rstrip("/").replace("/storage/v1", "")


def _admin_headers() -> dict:
    """Headers for any call that needs SERVICE ROLE privileges."""
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=500,
            detail=(
                "SUPABASE_SERVICE_ROLE_KEY is not configured. Admin "
                "operations (account deletion, auth user updates) are "
                "disabled."
            ),
        )
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


# ════════════════════════════════════════════════════════════════════
#  AUTH USER MANAGEMENT
# ════════════════════════════════════════════════════════════════════


def update_auth_user(
    user_id: str,
    *,
    email: str | None = None,
    phone: str | None = None,
    user_metadata: dict | None = None,
    email_confirm: bool = True,
    phone_confirm: bool = True,
) -> dict:
    """
    Update auth.users via the Admin API.

    PUT /auth/v1/admin/users/{id}

    Why this instead of a DB trigger:
      The auth schema is owned by GoTrue. Writing to it directly via SQL
      bypasses confirmation flows, audit logs, and any internal hooks
      GoTrue may add in future versions. The admin API is the supported
      path.

    email_confirm=True and phone_confirm=True bypass the confirmation
    email/SMS — equivalent to "auto-confirm" which is what we want while
    email confirmations are disabled in dashboard config for testing.
    When that's re-enabled in production, flip these to False and the
    confirmation flow takes over automatically.
    """
    url = f"{_base_url()}/auth/v1/admin/users/{user_id}"

    payload: dict = {}
    if email is not None:
        payload["email"] = email
        payload["email_confirm"] = email_confirm
    if phone is not None:
        payload["phone"] = phone
        payload["phone_confirm"] = phone_confirm
    if user_metadata is not None:
        payload["user_metadata"] = user_metadata

    if not payload:
        raise ValueError("update_auth_user called with no fields to update")

    resp = httpx.put(url, headers=_admin_headers(), json=payload, timeout=30)

    if resp.status_code >= 400:
        # Surface Supabase's error message but don't leak headers/keys.
        raise HTTPException(
            status_code=resp.status_code if resp.status_code < 500 else 502,
            detail=f"Supabase admin update failed: {resp.text}",
        )

    return resp.json()


def delete_auth_user(user_id: str) -> None:
    """
    Delete a user from auth.users.

    DELETE /auth/v1/admin/users/{id}

    This is the actual erasure call for the account-deletion flow.
    Because profiles.id has ON DELETE CASCADE pointing at auth.users.id
    (see db/triggers.sql), this single call ALSO deletes the profile
    row — which CASCADEs further into cv_documents, user_roadmaps, etc.
    via their FKs.

    404 is treated as success: if the auth user is already gone, the
    deletion goal is already met.
    """
    url = f"{_base_url()}/auth/v1/admin/users/{user_id}"

    resp = httpx.delete(url, headers=_admin_headers(), timeout=30)

    if resp.status_code == 404:
        return  # already deleted — idempotent

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=resp.status_code if resp.status_code < 500 else 502,
            detail=f"Supabase admin delete failed: {resp.text}",
        )


# ════════════════════════════════════════════════════════════════════
#  STORAGE — for wiping uploaded CV files
# ════════════════════════════════════════════════════════════════════


def delete_storage_objects(bucket: str, object_paths: list[str]) -> None:
    """
    Bulk-delete objects from a Storage bucket.

    DELETE /storage/v1/object/{bucket}  body: {"prefixes": [...]}

    Used by the "Delete My Data" flow to wipe actual CV PDFs/DOCXs from
    Storage — without this, you'd delete the DB row but leave orphaned
    files sitting in the bucket, which is a PDPL violation in itself.

    Silently no-ops on empty list. On 404 for a specific object we don't
    error out — partial-success is acceptable for a bulk wipe.
    """
    if not object_paths:
        return

    url = f"{_base_url()}/storage/v1/object/{bucket}"
    resp = httpx.request(
        "DELETE",
        url,
        headers=_admin_headers(),
        json={"prefixes": object_paths},
        timeout=60,
    )

    if resp.status_code >= 400 and resp.status_code != 404:
        # Don't fail the whole deletion just because storage cleanup
        # had a hiccup — log via the exception, but let the caller
        # decide whether to roll back.
        raise HTTPException(
            status_code=502,
            detail=f"Supabase storage cleanup failed: {resp.text}",
        )