"""
Phase 3, Module F — FastAPI auth dependencies.

- `current_user`      → resolves a JWT bearer token (web app sessions).
- `api_key_user`      → resolves an `Authorization: Bearer prism_sk_...` key
                        (public /v1 API); logs usage for the meter.
- `require_admin`     → gate admin-only routes.
"""
from fastapi import Depends, Header, HTTPException

from auth import security, users


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


async def current_user(authorization: str | None = Header(None)) -> dict:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    payload = security.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = users.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


async def api_key_user(authorization: str | None = Header(None)) -> dict:
    key = _bearer(authorization)
    if not key or not key.startswith("prism_sk_"):
        raise HTTPException(status_code=401, detail="Missing or malformed API key.")
    user = users.get_user_by_api_key(key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
