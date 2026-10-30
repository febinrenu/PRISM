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

    from rag import statute_index

    law = [statute_index.doc_id_for(s, v) for s, v in statute_index.available()]
    assert law, "the statutes are part of the corpus"
    # a stranger searches the shared document and every statute, never the private one
    assert readable_scope(None, None) == law + ["shared"]
    assert readable_scope(None, {"id": "someone-else", "role": "user"}) == law + ["shared"]
    assert "private" not in readable_scope(None, None)
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


def test_failed_logins_are_throttled_per_address_and_account(client):
    from routers import auth_routes

    auth_routes._failed.clear()
    email = f"nobody-{uuid.uuid4().hex[:6]}@example.com"
    codes = [client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code
             for _ in range(auth_routes._MAX_FAILED_PER_PAIR + 2)]
    assert codes[0] == 401 and codes[-1] == 429
    auth_routes._failed.clear()


def test_a_stranger_cannot_lock_someone_out_from_another_address(client, monkeypatch):
    """Failed attempts at an account count against the address they came from, so another
    address (the real owner) is not locked out by them."""
    from routers import auth_routes

    auth_routes._failed.clear()
    victim = users.create_user(f"victim-{uuid.uuid4().hex[:6]}@example.com", "V", "correct-horse-9")
    monkeypatch.setattr(auth_routes, "_client", lambda request: "203.0.113.9")        # the attacker
    for _ in range(auth_routes._MAX_FAILED_PER_PAIR + 1):
        client.post("/api/auth/login", json={"email": victim["email"], "password": "guess-guess"})
    assert client.post("/api/auth/login", json={"email": victim["email"], "password": "correct-horse-9"}).status_code == 429
    monkeypatch.setattr(auth_routes, "_client", lambda request: "198.51.100.7")       # the owner, elsewhere
    assert client.post("/api/auth/login", json={"email": victim["email"], "password": "correct-horse-9"}).status_code == 200
    auth_routes._failed.clear()


def test_a_right_password_clears_the_failed_count(client, monkeypatch):
    from routers import auth_routes

    auth_routes._failed.clear()
    u = users.create_user(f"ok-{uuid.uuid4().hex[:6]}@example.com", "O", "correct-horse-5")
    monkeypatch.setattr(auth_routes, "_client", lambda request: "192.0.2.4")
    for _ in range(auth_routes._MAX_FAILED_PER_PAIR - 1):
        client.post("/api/auth/login", json={"email": u["email"], "password": "nope-nope"})
    assert client.post("/api/auth/login", json={"email": u["email"], "password": "correct-horse-5"}).status_code == 200
    for _ in range(auth_routes._MAX_FAILED_PER_PAIR - 1):                             # the count started over
        assert client.post("/api/auth/login", json={"email": u["email"], "password": "nope-nope"}).status_code == 401
    auth_routes._failed.clear()


def test_the_proxy_header_is_only_trusted_when_configured(monkeypatch):
    from routers import auth_routes

    class Req:
        headers = {"x-forwarded-for": "6.6.6.6, 198.51.100.7"}      # the client's own claim, then what our proxy saw
        client = type("C", (), {"host": "10.0.0.1"})()

    from auth import client_ip
    monkeypatch.setattr(client_ip, "TRUSTED_PROXY", False)
    assert auth_routes._client(Req()) == "10.0.0.1"
    monkeypatch.setattr(client_ip, "TRUSTED_PROXY", True)
    assert auth_routes._client(Req()) == "198.51.100.7"          # the last hop, not what the client wrote first


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


def test_an_admin_email_cannot_be_taken_by_changing_its_case(client, monkeypatch):
    """Addresses are one account whatever their case; the admin bootstrap must not promote a
    second account made by registering "Admin@x.com" next to "admin@x.com"."""
    from auth import users
    import config
    from routers import auth_routes

    auth_routes._registered.clear()
    boss = f"boss-{uuid.uuid4().hex[:6]}@example.com"
    monkeypatch.setattr(config, "PRISM_ADMIN_EMAIL", boss)
    admin = users.create_user(boss.upper(), "Boss", "correct-horse-7")          # registers in any case
    assert admin["email"] == boss and admin["role"] == "admin"
    r = client.post("/api/auth/register", json={"email": boss.title(), "password": "12345678"})
    assert r.status_code == 409                                                  # not a second account
    assert users.get_user_by_email(boss.upper())["id"] == admin["id"]
    # an ordinary address in mixed case is still an ordinary account
    plain = users.create_user(f"Plain-{uuid.uuid4().hex[:6]}@Example.com", "P", "correct-horse-8")
    assert plain["role"] == "user" and plain["email"] == plain["email"].lower()


def test_login_finds_an_account_stored_in_mixed_case_by_an_older_version(client):
    from auth import security, users
    from db import database

    email = f"Old.Case-{uuid.uuid4().hex[:6]}@Example.com"
    database.execute("INSERT INTO users (id, email, name, password_hash, role, api_key) VALUES (?, ?, ?, ?, ?, ?)",
                     (security.new_user_id(), email, "Old", security.hash_password("correct-horse-3"), "user",
                      security.new_api_key()))
    r = client.post("/api/auth/login", json={"email": email.lower(), "password": "correct-horse-3"})
    assert r.status_code == 200


def test_the_throttle_table_does_not_grow_from_lookups_or_floods(monkeypatch):
    from routers import auth_routes

    auth_routes._failed.clear()
    assert auth_routes._throttled([("pair:1.1.1.1|a@b.c", 8)], auth_routes._failed) is False
    assert auth_routes._failed == {}                         # looking at a key does not create it
    monkeypatch.setattr(auth_routes, "_MAX_TRACKED", 50)
    for i in range(500):
        auth_routes._note([f"pair:9.9.9.9|victim{i}@x.com"], auth_routes._failed)
    assert len(auth_routes._failed) <= 51
    auth_routes._failed.clear()


# ── what anonymous callers cannot do to shared things ────────────────────────

def test_the_html_report_escapes_what_came_from_the_pdf():
    from routers.intelligence import _render_html_report

    evil = '<script>alert(1)</script>'
    report = {
        "doc_id": "d" * 20, "filename": f"{evil}.pdf", "domain": evil, "generated_at": "now",
        "executive_summary": {"total_clauses": 1, "total_entities": 1, "causal_patterns": 1, "critical_risks": 0,
                              "high_risks": 0, "total_pages": 1},
        "compliance_checklist": [{"priority": 'HIGH" onmouseover="x', "item": evil, "action": evil}],
        "causal_analysis": {"risk_matrix": {"CRITICAL": [{"section": evil, "condition_span": evil, "action_span": evil}],
                                            "HIGH": [], "MEDIUM": [], "LOW": []}},
        "entity_inventory": {'OB"><img src=x onerror=y>': [{"text": evil, "confidence": evil, "page": evil}]},
    }
    out = _render_html_report(report)
    assert "<script>alert(1)" not in out and "<img src=x" not in out and 'onmouseover="x' not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out and out.count("<script") == 0


def test_a_simulation_id_cannot_reach_another_documents_runs(tmp_path, monkeypatch):
    from storage import store

    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
    victim = tmp_path / "victim_doc" / "simulations"
    victim.mkdir(parents=True)
    (victim / "sim_deadbeef.json").write_text("{}", encoding="utf-8")
    (tmp_path / "mine").mkdir()
    for sid in ("../../victim_doc/simulations/sim_deadbeef", r"..\..\victim_doc\simulations\sim_deadbeef",
                "sim_deadbeef/../../x", "sim_DEADBEEF", "sim_dead", "", "sim_deadbeef.json"):
        assert store.load_simulation("mine", sid) is None, sid
    assert store.load_simulation("mine", "sim_deadbeef") is None            # a well-formed id, not in this document


def test_the_shared_demo_is_not_changed_by_anonymous_callers(client, monkeypatch):
    from routers import llm
    import routers.rag as rag_routes
    from storage import store

    monkeypatch.setattr(store, "get_result", lambda d: object())
    demo_meta = _meta("demo_income_tax_2025", None)
    monkeypatch.setattr(store, "get_meta", lambda d: demo_meta if d.startswith("demo_") else None)
    # a forced re-read of the demo spends model quota and rewrites its extractions
    assert client.post("/api/analyze/demo_income_tax_2025/llm?force=true").status_code == 403
    # removing it from the Ask index would empty everyone's Ask
    r = client.delete("/api/rag/corpus/demo_income_tax_2025")
    assert r.status_code == 403 and "demo" in r.json()["detail"]
    # an admin may
    admin = users.create_user(f"adm-{uuid.uuid4().hex[:6]}@example.com", "A", "correct-horse-1", role="admin")
    hdr = {"Authorization": "Bearer " + security.create_token(admin["id"], admin["email"], "admin")}
    monkeypatch.setattr(rag_routes.corpus_builder, "remove_document", lambda d: None)
    monkeypatch.setattr(rag_routes.corpus_builder, "corpus_stats", lambda: {"documents": [], "total_clauses": 0})
    assert client.delete("/api/rag/corpus/demo_income_tax_2025", headers=hdr).status_code == 200


def test_an_anonymous_upload_cannot_be_added_to_the_shared_ask_corpus(client, monkeypatch):
    from storage import store
    import routers.rag as rag_routes

    anon = _meta("anon-doc", None)
    mine_owner = users.create_user(f"own-{uuid.uuid4().hex[:6]}@example.com", "O", "correct-horse-2")
    mine = _meta("mine-doc", str(mine_owner["id"]))
    metas = {"anon-doc": anon, "mine-doc": mine}
    monkeypatch.setattr(store, "get_meta", lambda d: metas.get(d))
    monkeypatch.setattr(store, "get_result", lambda d: object())
    monkeypatch.setattr(store, "list_documents", lambda: list(metas.values()))
    ingested = []
    monkeypatch.setattr(rag_routes.corpus_builder, "ingest_document", lambda d: ingested.append(d) or {"doc_id": d, "indexed": 1})
    monkeypatch.setattr(rag_routes.corpus_builder, "corpus_stats", lambda: {"documents": [], "total_clauses": 0})
    r = client.post("/api/rag/ingest/anon-doc")
    assert r.status_code == 403 and "Sign in" in r.json()["detail"] and ingested == []
    owner_hdr = {"Authorization": "Bearer " + security.create_token(mine_owner["id"], mine_owner["email"], "user")}
    assert client.post("/api/rag/ingest/mine-doc", headers=owner_hdr).status_code == 200
    assert client.post("/api/rag/ingest/mine-doc", headers={"Authorization": "Bearer " + security.create_token("999", "x@y.z", "user")}).status_code in (403, 404)
    assert client.post("/api/rag/ingest/no-such-doc").status_code == 404
    # ingest-all adds only the caller's own documents (and the curated demo), never an anonymous upload
    ingested.clear()
    client.post("/api/rag/ingest-all")
    assert ingested == []
    client.post("/api/rag/ingest-all", headers=owner_hdr)
    assert ingested == ["mine-doc"]


def test_model_mode_lime_cannot_be_asked_for_thousands_of_calls():
    from routers.explain import capped_samples
    from config import LIME_LLM_MAX_SAMPLES

    assert capped_samples("llm", 2000) == LIME_LLM_MAX_SAMPLES
    assert capped_samples("llm", None) <= LIME_LLM_MAX_SAMPLES
    assert capped_samples("proxy", 2000) == 2000                  # the rule-based mode is cheap


def test_the_ingest_of_an_unknown_document_is_a_404_not_a_500(client):
    assert client.post("/api/rag/ingest/not-a-doc").status_code == 404


def test_the_expensive_web_routes_have_per_address_limits():
    import main  # noqa: F401  (registers the routes with the limiter)
    from auth.rate_limiter import limiter

    registered = " ".join(limiter._route_limits)
    for route in ("upload_pdf", "create_simulation", "run_scenario", "get_explanation", "stream_explanation", "query", "stream"):
        assert route in registered, route


def test_the_rate_limit_key_is_the_clients_address_not_the_proxys(monkeypatch):
    from auth import client_ip
    from auth.rate_limiter import _key_func

    class Req:
        headers = {"x-forwarded-for": "6.6.6.6, 198.51.100.7"}
        client = type("C", (), {"host": "10.0.0.1"})()

    monkeypatch.setattr(client_ip, "TRUSTED_PROXY", True)
    assert _key_func(Req()) == "198.51.100.7"
    monkeypatch.setattr(client_ip, "TRUSTED_PROXY", False)
    assert _key_func(Req()) == "10.0.0.1"


def test_responses_carry_baseline_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_the_report_is_built_once_per_loaded_analysis(client, monkeypatch):
    from routers import intelligence
    from storage import store

    built = []
    result_a, result_b = object(), object()
    current = {"r": result_a}
    monkeypatch.setattr(intelligence, "_require_result", lambda d: current["r"])
    monkeypatch.setattr(store, "get_meta", lambda d: _meta("shared", None) if d == "shared" else None)
    monkeypatch.setattr(intelligence, "_build_report", lambda d, r, m: built.append(r) or {"doc_id": d, "n": len(built)})
    intelligence._report_cache.clear()
    assert client.get("/api/report/shared").json()["n"] == 1
    assert client.get("/api/report/shared").json()["n"] == 1 and len(built) == 1
    current["r"] = result_b                                     # re-analysed: a new object
    assert client.get("/api/report/shared").json()["n"] == 2
    intelligence._report_cache.clear()
