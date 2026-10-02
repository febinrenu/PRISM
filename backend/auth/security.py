"""
Phase 3, Module F — auth primitives.

- Password hashing (passlib/bcrypt, with a pbkdf2 stdlib fallback so the stack
  runs even if bcrypt isn't compiled).
- JWT session tokens (PyJWT) for the web app.
- Per-user API keys (`prism_sk_...`) for the public /v1 API.

User rows live in the `users` table (see db.database). This module is the only
place that knows how credentials are verified.
"""
import hashlib
import hmac
import os
import secrets
import time
import uuid
from typing import Optional

import jwt

from config import JWT_SECRET

_JWT_ALG = "HS256"
_JWT_TTL_S = 60 * 60 * 24 * 7  # 7 days

# --- password hashing ---
# Use the `bcrypt` module directly (bcrypt hashes start with "$2"); passlib 1.7.4
# mis-detects the bcrypt 4.x backend, so we skip it. bcrypt caps input at 72
# bytes — truncate explicitly. pbkdf2_sha256 ("pbkdf2$...") is the stdlib
# fallback so the auth stack never hard-depends on a compiled bcrypt wheel.
try:
    import bcrypt as _bcrypt
    _HAS_BCRYPT = True
except Exception:  # pragma: no cover
    _HAS_BCRYPT = False


def _pbkdf2_hash(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def _pbkdf2_verify(pw: str, hashed: str) -> bool:
    try:
        _, salt_hex, dk_hex = hashed.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def hash_password(pw: str) -> str:
    if _HAS_BCRYPT:
        return _bcrypt.hashpw(pw.encode("utf-8")[:72], _bcrypt.gensalt()).decode("utf-8")
    return _pbkdf2_hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    if hashed.startswith("pbkdf2$"):
        return _pbkdf2_verify(pw, hashed)
    if _HAS_BCRYPT and hashed.startswith("$2"):
        try:
            return _bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
        except Exception:
            return False
    return False


def new_api_key() -> str:
    return "prism_sk_" + secrets.token_hex(24)


def new_user_id() -> str:
    return str(uuid.uuid4())


def create_token(user_id: str, email: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "email": email, "role": role, "iat": now, "exp": now + _JWT_TTL_S}
    return jwt.encode(payload, JWT_SECRET, algorithm=_JWT_ALG)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None
