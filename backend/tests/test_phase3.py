"""
Phase 3 tests — auth, DB, RAG corpus/query, gold builder, LLM backend.
Ollama-free (no live model calls); the RAG/gold tests use the demo doc's
already-stored clauses + embeddings when present, else skip cleanly.
"""
import pytest

from storage import store


# ── Auth security (pure) ─────────────────────────────────────────────────────

def test_password_hash_and_verify():
    from auth import security

    h = security.hash_password("password123")
    assert h != "password123"
    assert security.verify_password("password123", h)
    assert not security.verify_password("wrong", h)


def test_jwt_roundtrip():
    from auth import security

    tok = security.create_token("uid-1", "a@b.co", "admin")
    payload = security.decode_token(tok)
    assert payload is not None
    assert payload["sub"] == "uid-1" and payload["role"] == "admin"
    assert security.decode_token("garbage") is None


def test_api_key_format():
    from auth import security

    key = security.new_api_key()
    assert key.startswith("prism_sk_") and len(key) > 20


# ── DB + user repository (SQLite fallback) ───────────────────────────────────

def test_user_crud_sqlite():
    from auth import users
    from db.database import init_db

    init_db()
    import uuid
    email = f"t_{uuid.uuid4().hex[:8]}@prism.dev"
    u = users.create_user(email, "Tester", "password123")
    assert u["email"] == email
    assert users.get_user_by_email(email)["id"] == u["id"]
    assert users.get_user_by_api_key(u["api_key"])["id"] == u["id"]

    with pytest.raises(ValueError):
        users.create_user(email, "Dup", "password123")  # duplicate email

    new_key = users.rotate_api_key(u["id"])
    assert new_key != u["api_key"]
    users.log_usage(u["id"], "test")
    assert users.usage_count(u["id"]) >= 1


# ── LLM backend descriptor ───────────────────────────────────────────────────

def test_llm_backend_descriptor():
    from pipeline import llm_backend

    info = llm_backend.active_backend()
    assert info["kind"] in ("ollama", "groq")
    assert "model" in info


# ── RAG query-engine helpers (pure) ──────────────────────────────────────────

def test_rag_context_and_citations():
    from rag import query_engine

    hits = [
        {"doc_name": "Act A", "section": "Sec 1", "page": 3, "text": "Some clause text.",
         "similarity": 0.9, "doc_id": "d", "clause_id": "c1", "entity_types": "PENALTY"},
    ]
    ctx = query_engine.build_context(hits)
    assert "[Source 1:" in ctx and "Act A" in ctx
    cites = query_engine.citations(hits)
    assert cites[0]["index"] == 1 and cites[0]["clause_id"] == "c1"
    assert 0.0 <= query_engine.retrieval_confidence(hits) <= 1.0
    assert query_engine.retrieval_confidence([]) == 0.0


# ── RAG corpus round-trip (uses demo doc if present) ─────────────────────────

DEMO = "demo_income_tax_2025"


@pytest.mark.skipif(
    store.get_result(DEMO) is None or store.load_embeddings(DEMO) is None,
    reason="demo doc not analysed on this machine",
)
def test_corpus_ingest_and_search():
    from rag import corpus_builder

    res = corpus_builder.ingest_document(DEMO)
    assert res["indexed"] > 0
    stats = corpus_builder.corpus_stats()
    assert stats["total_clauses"] > 0
    hits = corpus_builder.semantic_search("penalty for late filing", n_results=5)
    assert len(hits) > 0
    assert all("clause_id" in h and "similarity" in h for h in hits)


# ── Gold builder (uses demo doc if present) ──────────────────────────────────

@pytest.mark.skipif(
    store.get_result(DEMO) is None,
    reason="demo doc not analysed on this machine",
)
def test_gold_builder_shapes():
    from eval import gold_builder

    result = store.get_result(DEMO)
    import random
    rng = random.Random(0)
    ner = gold_builder.build_ner_gold(result.clauses, 10, rng)
    causal = gold_builder.build_causal_gold(result.clauses, 10, rng)
    rag = gold_builder.build_rag_qa(result.clauses, 5, rng, use_llm=False)
    assert all("gold_entities" in it and it["reviewed"] is False for it in ner)
    assert all("gold_is_causal" in it for it in causal)
    assert all("gold_clause_id" in it and it["question"] for it in rag)
