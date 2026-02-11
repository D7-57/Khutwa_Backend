from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
import httpx

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


def get_current_user_id(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = creds.credentials

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        # Supabase is giving you ES256 tokens
        if alg != "ES256":
            raise HTTPException(status_code=401, detail=f"Unsupported token alg: {alg}")

        jwks = _get_jwks()

        payload = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

    except (JWTError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id (sub)")

    return user_id
