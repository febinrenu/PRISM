"""
Phase 3, Module F — per-API-key rate limiting (slowapi).

Keys the limit on the API key (falls back to client IP) so each free-tier user
gets their own 100/hour budget. Attached to the app in main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from config import API_RATE_LIMIT


def _key_func(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer prism_sk_"):
        return auth.split(" ", 1)[1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func, default_limits=[])

# Applied as a decorator string on public /v1 routes.
PUBLIC_RATE_LIMIT = API_RATE_LIMIT
