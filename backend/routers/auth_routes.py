"""
Phase 3, Module F — authentication API.

POST /api/auth/register  → create account (email + password), returns JWT
POST /api/auth/login     → verify credentials, returns JWT
GET  /api/auth/me        → current user (from bearer JWT)
POST /api/auth/api-key/rotate → issue a fresh API key
GET  /api/auth/dashboard → user's docs, simulations, api-key, usage meter

NextAuth on the frontend delegates its Credentials provider to register/login;
OAuth (GitHub/Google) is handled by NextAuth and mapped to a PRISM user via
these same endpoints (upsert-on-first-login).
"""
import hmac
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from auth import security, users
from auth.deps import current_user
from config import API_RATE_LIMIT, OAUTH_UPSERT_SECRET

router = APIRouter()

# Failed sign-ins and new accounts are throttled per client and per email, so a
# password cannot be guessed at wire speed. In memory: one process, resets on restart.
_WINDOW_S = 300
_MAX_FAILED_LOGINS = 8
_MAX_REGISTRATIONS = 10
_failed: dict[str, deque] = defaultdict(deque)
_registered: dict[str, deque] = defaultdict(deque)


def _recent(bucket: deque, now: float) -> deque:
    while bucket and now - bucket[0] > _WINDOW_S:
        bucket.popleft()
    return bucket


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _throttled(keys: list[str], limit: int, store: dict[str, deque]) -> bool:
    now = time.time()
    return any(len(_recent(store[k], now)) >= limit for k in keys)


def _note(keys: list[str], store: dict[str, deque]) -> None:
    now = time.time()
    for k in keys:
        store[k].append(now)


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class OAuthUpsertBody(BaseModel):
    email: EmailStr
    name: str = ""
    provider: str = "oauth"


def _auth_response(user: dict) -> dict:
    token = security.create_token(user["id"], user["email"], user.get("role", "user"))
    return {"token": token, "user": users.public_user(user)}


@router.post("/auth/register")
def register(body: RegisterBody, request: Request):
    keys = [f"ip:{_client(request)}"]
    if _throttled(keys, _MAX_REGISTRATIONS, _registered):
        raise HTTPException(status_code=429, detail="Too many sign-ups from this address. Try again in a few minutes.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        user = users.create_user(body.email, body.name or body.email.split("@")[0], body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _note(keys, _registered)
    return _auth_response(user)


@router.post("/auth/login")
def login(body: LoginBody, request: Request):
    keys = [f"ip:{_client(request)}", f"email:{body.email.lower()}"]
    if _throttled(keys, _MAX_FAILED_LOGINS, _failed):
        raise HTTPException(status_code=429, detail="Too many failed sign-ins. Try again in a few minutes.")
    user = users.get_user_by_email(body.email)
    if not user or not user.get("password_hash") or not security.verify_password(
        body.password, user["password_hash"]
    ):
        _note(keys, _failed)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user = users.ensure_admin(user)  # promote if email matches PRISM_ADMIN_EMAIL
    return _auth_response(user)


@router.post("/auth/oauth-upsert")
async def oauth_upsert(body: OAuthUpsertBody, x_oauth_secret: str = Header(default="")):
    """Called by NextAuth after a successful GitHub/Google login — create the
    PRISM user on first sign-in, then return a PRISM JWT + API key.

    It trusts the caller's word that the email is verified, so it answers only to
    a server holding OAUTH_UPSERT_SECRET; with none configured it is switched off."""
    if not OAUTH_UPSERT_SECRET:
        raise HTTPException(status_code=404, detail="OAuth sign-in is not enabled.")
    if not hmac.compare_digest(x_oauth_secret.encode(), OAUTH_UPSERT_SECRET.encode()):
        raise HTTPException(status_code=401, detail="Invalid OAuth secret.")
    user = users.get_user_by_email(body.email)
    if not user:
        user = users.create_user(body.email, body.name or body.email.split("@")[0], password=None)
    return _auth_response(user)


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return users.public_user(user)


@router.post("/auth/api-key/rotate")
async def rotate_key(user: dict = Depends(current_user)):
    return {"api_key": users.rotate_api_key(user["id"])}


@router.get("/auth/dashboard")
async def dashboard(user: dict = Depends(current_user)):
    # Parse the free-tier hourly quota ("100/hour") for the usage meter.
    try:
        quota = int(API_RATE_LIMIT.split("/")[0])
    except (ValueError, IndexError):
        quota = 100
    return {
        "user": users.public_user(user),
        "api_key": user["api_key"],
        "rate_limit": API_RATE_LIMIT,
        "usage_total": users.usage_count(user["id"]),
        "usage_hour": users.usage_last_hour(user["id"]),
        "quota_per_hour": quota,
        "documents": [_live_status(d) for d in users.list_documents(user["id"])],
        "simulations": users.list_simulations(user["id"]),
    }


def _live_status(row: dict) -> dict:
    """The stored row records the status at upload; the document store knows the current one."""
    from storage import store
    meta = store.get_meta(row["doc_id"])
    return {**row, "status": meta.status if meta else row.get("status")}
