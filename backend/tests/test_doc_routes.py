"""Single-document and single-clause routes, and who may add documents to the shared corpus."""
from fastapi.testclient import TestClient

from main import app
from storage import store

DEMO = "demo_income_tax_2025"
client = TestClient(app)


def test_document_metadata_hides_storage_details():
    r = client.get(f"/api/documents/{DEMO}")
    assert r.status_code == 200
    d = r.json()
    assert d["filename"] == "income_tax_2025.pdf" and d["pages"] > 0
    assert "pdf_path" not in d and "owner_id" not in d
    assert client.get("/api/documents/no-such-doc").status_code == 404


def test_single_clause():
    first = store.get_result(DEMO).clauses[5]
    r = client.get(f"/api/clause/{DEMO}/{first.clause_id}")
    assert r.status_code == 200 and r.json()["clause"]["text"] == first.text
    assert client.get(f"/api/clause/{DEMO}/nope").status_code == 404
    # the LLM route under /clauses is unaffected
    assert client.get(f"/api/clauses/{DEMO}/llm").status_code == 200


def test_private_documents_stay_out_of_the_shared_corpus(monkeypatch):
    from routers import rag
    seen = []
    monkeypatch.setattr(rag.corpus_builder, "ingest_document", lambda d: seen.append(d) or {"doc_id": d})
    monkeypatch.setattr(rag.corpus_builder, "corpus_stats", lambda: {})
    metas = store.list_documents()
    private = next((m for m in metas if m.owner_id), None)
    r = client.post("/api/rag/ingest-all")
    assert r.status_code == 200
    assert all(store.get_meta(d).owner_id is None for d in seen)
    if private is not None:
        assert client.post(f"/api/rag/ingest/{private.doc_id}").status_code == 403


def test_demo_is_never_reanalysed():
    r = client.get(f"/api/analyze/{DEMO}?force=true")
    assert r.status_code == 403


def test_saved_runs_are_listed_newest_first(tmp_path, monkeypatch):
    r = client.get(f"/api/simulate/{DEMO}/runs")
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert runs == sorted(runs, key=lambda x: x["created_at"], reverse=True)


def test_explaining_a_clause_does_not_rewrite_the_result(monkeypatch):
    """The LIME cache file is the record; result.json stays as analysed."""
    from pipeline import lime_explainer
    calls = []
    monkeypatch.setattr(store, "update_result", lambda *a, **k: calls.append(a))
    import inspect
    src = inspect.getsource(lime_explainer)
    assert "update_result" not in src
    cid = store.get_result(DEMO).clauses[7].clause_id
    monkeypatch.setattr(store, "lime_explained_ids", lambda d: {cid})
    from routers import data
    monkeypatch.setattr(data, "lime_explained_ids", lambda d: {cid})
    r = client.get(f"/api/clause/{DEMO}/{cid}")
    assert r.json()["clause"]["lime_available"] is True
    assert not calls
