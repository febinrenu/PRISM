"""
Which address a request came from, for the throttles and rate limits.

Behind a reverse proxy every request arrives from the proxy, so the real client is read from
X-Forwarded-For, but only when TRUSTED_PROXY=1 says a proxy we control sets it (the bundled nginx
overwrites it). Then the last entry is the one our proxy added; earlier ones are whatever the client
sent. Without that setting the header is ignored: anyone could write any address into it.
"""
import os

from starlette.requests import Request

TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "").strip().lower() in ("1", "true", "yes")


def client_address(request: Request) -> str:
    if TRUSTED_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"
