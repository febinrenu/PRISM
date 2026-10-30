"""
Phase 3, Module F — per-API-key rate limiting (slowapi).

Keys the limit on the API key (falls back to client IP) so each free-tier user
gets their own 100/hour budget. Attached to the app in main.py.
"""
from slowapi import Limiter
from starlette.requests import Request

from auth.client_ip import client_address
from config import API_RATE_LIMIT


def _key_func(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer prism_sk_"):
        return auth.split(" ", 1)[1].strip()
    return client_address(request)


limiter = Limiter(key_func=_key_func, default_limits=[])

# Applied as a decorator string on public /v1 routes.
PUBLIC_RATE_LIMIT = API_RATE_LIMIT

# Per-address budgets for the expensive routes of the web app (each key is the address, as above).
# Generous for a person using the page (the policy sandbox prices on every edit), tight for a script.
UPLOAD_LIMIT = "20/hour"
SIMULATE_LIMIT = "60/hour"
SCENARIO_LIMIT = "1500/hour"
ASK_LIMIT = "150/hour"
LIME_LIMIT = "120/hour"
