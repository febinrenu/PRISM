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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from auth import security, users
from auth.deps import current_user
from config import API_RATE_LIMIT

router = APIRouter()


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
async def register(body: RegisterBody):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        user = users.create_user(body.email, body.name or body.email.split("@")[0], body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _auth_response(user)


@router.post("/auth/login")
async def login(body: LoginBody):
    user = users.get_user_by_email(body.email)
    if not user or not user.get("password_hash") or not security.verify_password(
        body.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user = users.ensure_admin(user)  # promote if email matches PRISM_ADMIN_EMAIL
    return _auth_response(user)


@router.post("/auth/oauth-upsert")
async def oauth_upsert(body: OAuthUpsertBody):
    """Called by NextAuth after a successful GitHub/Google login — create the
    PRISM user on first sign-in, then return a PRISM JWT + API key."""
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
        "quota_per_hour": quota,
        "documents": users.list_documents(user["id"]),
        "simulations": users.list_simulations(user["id"]),
    }
