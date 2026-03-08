import httpx
from fastapi import HTTPException
from app.core.config import settings

def _normalize_project_url(project_url: str) -> str:
    # Ensure it's like: https://xxxxx.supabase.co
    return project_url.rstrip("/").replace("/storage/v1", "")

def create_signed_url(*, bucket: str, object_path: str, expires_in: int, user_jwt: str) -> str:
    base = _normalize_project_url(settings.SUPABASE_URL)

    # Create signed url (POST)
    sign_endpoint = f"{base}/storage/v1/object/sign/{bucket}/{object_path}"

    headers = {
        "authorization": f"Bearer {user_jwt}",
        "apikey": settings.SUPABASE_ANON_KEY,
        "content-type": "application/json",
    }

    r = httpx.post(sign_endpoint, headers=headers, json={"expiresIn": expires_in}, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Signed URL failed: {r.text}")

    data = r.json()
    signed = data.get("signedURL")
    if not signed:
        raise HTTPException(status_code=400, detail="Signed URL missing from response")

    # If already absolute, return it
    if signed.startswith("http"):
        return signed

    # If it starts with "/object/..." add "/storage/v1"
    if signed.startswith("/object/"):
        signed = "/storage/v1" + signed

    # If it already starts with "/storage/v1", keep it
    if not signed.startswith("/storage/v1/"):
        # last-resort fallback
        signed = "/storage/v1" + (signed if signed.startswith("/") else "/" + signed)

    return base + signed
