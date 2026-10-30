"""Access control: private documents are closed to other users on every route,
the OAuth shortcut is off unless configured, and sign-ins are throttled."""
import uuid

import pytest
from fastapi.testclient import TestClient

from auth import security, users
from models.schemas import DocumentMeta


def _meta(doc_id, owner):
    return DocumentMeta(doc_id=doc_id, filename="x.pdf", pages=1, file_size_kb=1.0, owner_id=owner)


@pytest.fixture()
def client(monkeypatch):
    import main
    from db.database import init_db
    from storage import store

    init_db()
    owner = users.create_user(f"owner-{uuid.uuid4().hex[:8]}@example.com", "Owner", "correct-horse-1")
    other = users.create_user(f"other-{uuid.uuid4().hex[:8]}@example.com", "Other", "correct-horse-2")
    metas = {
        "shared": _meta("shared", None),
        "private": _meta("private", str(owner["id"])),
    }
    monkeypatch.setattr(store, "get_meta", lambda d: metas.get(d))
    monkeypatch.setattr(store, "list_documents", lambda: list(metas.values()))
    c = TestClient(main.app)
    c.owner_id = str(owner["id"])
    c.owner_headers = {"Authorization": "Bearer " + security.create_token(owner["id"], owner["email"], "user")}
    c.other_headers = {"Authorization": "Bearer " + security.create_token(other["id"], other["email"], "user")}
    return c


# Routes that carry a {doc_id}: all must refuse a stranger.
DOC_ROUTES = [
    "/api/clauses/{d}", "/api/stats/{d}", "/api/graph/{d}", "/api/causal/{d}",
    "/api/report/{d}", "/api/pdf/{d}", "/api/simulate/{d}/runs", "/api/schedules/{d}",
]


def _hidden(response):
    """A private document does not exist for a stranger: the guard's own answer,
    not a route's "no analysis yet"."""
    return response.status_code == 404 and response.json().get("detail") == "Document not found."


@pytest.mark.parametrize("route", DOC_ROUTES)
def test_private_document_routes_are_hidden_from_strangers(client, route):
    url = route.format(d="private")
    assert _hidden(client.get(url))
    assert _hidden(client.get(url, headers=client.other_headers))


@pytest.mark.parametrize("route", DOC_ROUTES)
def test_the_guard_lets_the_owner_and_everyone_on_a_shared_document_through(client, route):
    from auth.deps import ensure_readable, user_from_authorization

    ensure_readable("private", user_from_authorization(client.owner_headers["Authorization"]))
    ensure_readable("shared", None)


def test_compare_needs_access_to_both(client):
    body = {"doc_id_a": "shared", "doc_id_b": "private"}
    assert _hidden(client.post("/api/compare", json=body))
    assert not _hidden(client.post("/api/compare", json=body, headers=client.owner_headers))


def test_ask_cannot_name_a_private_document(client):
    r = client.post("/api/rag/query", json={"question": "rebate", "doc_ids": ["private"]})
    assert _hidden(r)
    r = client.get("/api/rag/stream", params={"q": "rebate", "docs": "private"})
    assert _hidden(r)


def test_unfiltered_search_is_narrowed_to_readable_documents(client):
    from auth.deps import readable_scope

    assert readable_scope(None, None) == ["shared"]
    assert readable_scope(None, {"id": "someone-else", "role": "user"}) == ["shared"]
    # Nothing is hidden from the owner, so the search stays unfiltered.
    assert readable_scope(None, {"id": client.owner_id, "role": "user"}) is None


def test_corpus_listing_hides_other_users_documents():
    from auth.deps import filter_corpus_stats
    from storage import store

    stats = {"total_clauses": 5, "documents": [
        {"doc_id": "shared", "doc_name": "s", "clauses": 2, "causal": 0},
        {"doc_id": "private", "doc_name": "p", "clauses": 3, "causal": 0},
    ]}
    metas = {"shared": _meta("shared", None), "private": _meta("private", "7")}
    orig = store.get_meta
    store.get_meta = lambda d: metas.get(d)
    try:
        out = filter_corpus_stats(stats, None)
    finally:
        store.get_meta = orig
    assert [d["doc_id"] for d in out["documents"]] == ["shared"]
    assert out["total_clauses"] == 2


def test_oauth_upsert_is_disabled_without_a_secret(client, monkeypatch):
    from routers import auth_routes

    monkeypatch.setattr(auth_routes, "OAUTH_UPSERT_SECRET", "")
    r = client.post("/api/auth/oauth-upsert", json={"email": "victim@example.com"})
    assert r.status_code == 404


def test_oauth_upsert_checks_the_secret(client, monkeypatch):
    from routers import auth_routes

    monkeypatch.setattr(auth_routes, "OAUTH_UPSERT_SECRET", "s3cret-value")
    body = {"email": "someone@example.com"}
    assert client.post("/api/auth/oauth-upsert", json=body).status_code == 401
    assert client.post("/api/auth/oauth-upsert", json=body,
                       headers={"X-OAuth-Secret": "wrong"}).status_code == 401
    ok = client.post("/api/auth/oauth-upsert", json=body, headers={"X-OAuth-Secret": "s3cret-value"})
    assert ok.status_code == 200 and ok.json()["token"]


def test_failed_logins_are_throttled(client):
    from routers import auth_routes

    auth_routes._failed.clear()
    email = f"nobody-{uuid.uuid4().hex[:6]}@example.com"
    codes = [client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code
             for _ in range(auth_routes._MAX_FAILED_LOGINS + 2)]
    assert codes[0] == 401
    assert codes[-1] == 429
    auth_routes._failed.clear()


def test_public_document_payload_hides_paths(client, monkeypatch):
    owner = users.create_user(f"k-{uuid.uuid4().hex[:6]}@example.com", "K", "correct-horse-3")
    key = owner["api_key"]
    r = client.get("/v1/documents/shared", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    assert "pdf_path" not in r.json() and "owner_id" not in r.json()


def test_signing_key_is_not_the_old_hardcoded_default():
    from config import JWT_SECRET

    assert JWT_SECRET != "prism-dev-secret-change-in-production"
    assert len(JWT_SECRET) >= 32
