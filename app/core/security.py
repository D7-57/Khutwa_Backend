from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
import httpx
from dataclasses import dataclass

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

_JWKS_CACHE: dict | None = None


def _get_jwks() -> dict:
    global _JWKS_CACHE
    if _JWKS_CACHE is not None:
        return _JWKS_CACHE

    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    resp = httpx.get(jwks_url, timeout=10)
    resp.raise_for_status()
    _JWKS_CACHE = resp.json()
    return _JWKS_CACHE


@dataclass
class AuthUser:
    """Decoded token info — passed as a dependency to route handlers."""
    id: str
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def _decode_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")

    if alg != "ES256":
        raise HTTPException(status_code=401, detail=f"Unsupported token alg: {alg}")

    jwks = _get_jwks()

    return jwt.decode(
        token,
        jwks,
        algorithms=["ES256"],
        options={"verify_aud": False},
    )


def get_current_user_id(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Legacy dependency — returns just the user ID string."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = _decode_token(creds.credentials)
    except (JWTError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id (sub)")

    return user_id


def get_current_auth_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthUser:
    """Rich dependency — returns user ID + email + metadata from JWT."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = _decode_token(creds.credentials)
    except (JWTError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id (sub)")

    # Supabase puts email at top level, user_metadata has first/last/phone
    email = payload.get("email")
    meta = payload.get("user_metadata") or {}
    phone = meta.get("phone") or payload.get("phone")
    first_name = meta.get("first_name")
    last_name = meta.get("last_name")

    return AuthUser(
        id=user_id,
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
    )
