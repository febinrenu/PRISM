"""
Phase 3, Module F — FastAPI auth dependencies.

- `current_user`      → resolves a JWT bearer token (web app sessions).
- `api_key_user`      → resolves an `Authorization: Bearer prism_sk_...` key
                        (public /v1 API); logs usage for the meter.
- `require_admin`     → gate admin-only routes.
"""
from fastapi import Depends, Header, HTTPException, Request

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


async def optional_user(authorization: str | None = Header(None)) -> dict | None:
    """The signed-in user, or None (anonymous, or a token that is missing,
    invalid or expired): for routes that work without signing in."""
    token = _bearer(authorization)
    if not token or token.startswith("prism_sk_"):
        return None
    payload = security.decode_token(token)
    return users.get_user_by_id(payload["sub"]) if payload else None


def can_manage(meta, user: dict | None) -> bool:
    """Owner or admin; a shared (ownerless) document by anyone."""
    if meta is None:
        return False
    if meta.owner_id is None:
        return True
    return bool(user) and (str(user.get("id")) == meta.owner_id or user.get("role") == "admin")


def is_demo(doc_id: str) -> bool:
    """The bundled demo and any other curated shared document (ids start "demo_")."""
    return str(doc_id).startswith("demo_")


def ensure_can_modify(doc_id: str, meta, user: dict | None, what: str = "changed") -> None:
    """403 unless `user` may change this document or what is stored about it. The shared demo is
    changed by an admin only; any other document by its owner or an admin (an anonymous upload,
    which has no owner, by anyone, as before)."""
    admin = bool(user) and user.get("role") == "admin"
    if is_demo(doc_id) and not admin:
        raise HTTPException(status_code=403, detail=f"The shared demo cannot be {what}.")
    if meta is not None and not can_manage(meta, user):
        raise HTTPException(status_code=403, detail=f"Only the document's owner can have it {what}.")


def can_list(meta, user: dict | None) -> bool:
    if meta is None:
        return False            # no such document: nothing to show
    return meta.owner_id is None or (bool(user) and (str(user.get("id")) == meta.owner_id
                                                     or user.get("role") == "admin"))


def user_from_authorization(authorization: str | None) -> dict | None:
    """The user behind a bearer JWT or a prism_sk_ API key, or None."""
    token = _bearer(authorization)
    if not token:
        return None
    if token.startswith("prism_sk_"):
        return users.get_user_by_api_key(token)
    payload = security.decode_token(token)
    return users.get_user_by_id(payload["sub"]) if payload else None


def ensure_readable(doc_id: str, user: dict | None) -> None:
    """404 unless `user` may see this document: a private one does not exist for
    anyone else (as in the document list). A shared (ownerless) one is open to
    everyone; an unknown id passes, so the route answers its own 404."""
    from storage import store

    meta = store.get_meta(doc_id)
    if meta is not None and not can_list(meta, user):
        raise HTTPException(status_code=404, detail="Document not found.")


def ensure_all_readable(doc_ids: list[str] | None, user: dict | None) -> None:
    for d in doc_ids or []:
        ensure_readable(d, user)


def readable_scope(requested: list[str] | None, user: dict | None) -> list[str] | None:
    """The document filter a search may use for `user`.

    Naming a private document the user cannot read is a 404. With no filter, the
    search is narrowed to what the user may see, but only when some document is
    hidden from them, so the common case still searches the whole corpus."""
    from storage import store

    ensure_all_readable(requested, user)
    if requested:
        return requested
    docs = store.list_documents()
    hidden = {m.doc_id for m in docs if not can_list(m, user)}
    if not hidden:
        return None
    # An allow-list, so it names the statutes too: they are in the corpus but have no
    # document record, and leaving them out would make Ask forget the law.
    from rag import statute_index

    statutes = [statute_index.doc_id_for(s, v) for s, v in statute_index.available()]
    return statutes + [m.doc_id for m in docs if m.doc_id not in hidden]


def filter_corpus_stats(stats: dict, user: dict | None) -> dict:
    """Drop private documents of other users from a corpus listing."""
    from storage import store

    visible = []
    for d in stats.get("documents", []):
        meta = store.get_meta(d["doc_id"])
        if meta is None or can_list(meta, user):
            visible.append(d)
    return {**stats, "documents": visible, "total_clauses": sum(d["clauses"] for d in visible)}


async def enforce_doc_access(request: Request, authorization: str | None = Header(None),
                             user: dict | None = Depends(optional_user)) -> None:
    """App-wide guard: any route with a {doc_id} in its path is readable only by
    the document's owner (or an admin) when the document is private. The user is
    the signed-in one (a JWT) or, on the public /v1 API, the owner of the API key."""
    doc_id = request.path_params.get("doc_id")
    if doc_id:
        ensure_readable(doc_id, user or user_from_authorization(authorization))


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
