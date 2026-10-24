"""Deleting a document removes everything stored for it, and only its owner
(or an admin; anyone for an anonymous upload) may do it."""
import fitz
import pytest
from fastapi.testclient import TestClient

from models.schemas import DocumentMeta


@pytest.fixture
def env(tmp_path, monkeypatch):
    import config
    from routers import data
    from storage import store
    store_dir, uploads = tmp_path / "store", tmp_path / "uploads"
    store_dir.mkdir()
    uploads.mkdir()
    monkeypatch.setattr(config, "STORE_DIR", store_dir)
    monkeypatch.setattr(store, "STORE_DIR", store_dir)
    monkeypatch.setattr(config, "UPLOAD_DIR", uploads)
    for cache in (store._meta_store, store._result_store, store._embeddings_cache):
        cache.clear()
    forgotten = []
    monkeypatch.setattr("auth.users.forget_document", lambda doc_id: forgotten.append(doc_id) or [])
    monkeypatch.setattr("rag.corpus_builder.remove_document", lambda doc_id: None)
    import main
    yield TestClient(main.app), store, uploads, forgotten, data
    for cache in (store._meta_store, store._result_store, store._embeddings_cache):
        cache.clear()


def _doc(store, uploads, doc_id, owner=None, status="complete"):
    pdf = uploads / f"{doc_id}.pdf"
    d = fitz.open()
    d.new_page()
    d.save(pdf)
    store.save_meta(DocumentMeta(doc_id=doc_id, filename="x.pdf", pages=1, file_size_kb=1.0,
                                 owner_id=owner, status=status))
    store.save_path(doc_id, str(pdf))
    (store._doc_dir(doc_id) / "ocr_lines.json").write_text("{}", encoding="utf-8")
    return pdf


def test_anonymous_upload_is_deleted_with_everything(env):
    client, store, uploads, forgotten, _ = env
    pdf = _doc(store, uploads, "doc1")
    r = client.delete("/api/documents/doc1")
    assert r.status_code == 200, r.text
    assert r.json()["removed"]["folder"] and r.json()["removed"]["pdf"]
    assert not pdf.exists() and not store._doc_dir("doc1").exists()
    assert forgotten == ["doc1"]
    assert client.get("/api/documents/doc1").status_code == 404


def test_demo_cannot_be_deleted(env):
    client, store, uploads, _, _ = env
    _doc(store, uploads, "demo_x")
    assert client.delete("/api/documents/demo_x").status_code == 403
    assert store._doc_dir("demo_x").exists()


def test_only_the_owner_deletes_a_private_document(env, monkeypatch):
    client, store, uploads, _, data = env
    pdf = _doc(store, uploads, "mine", owner="7")
    # someone else, or nobody: the document does not exist for them
    assert client.delete("/api/documents/mine").status_code == 404
    from auth import deps
    app = client.app
    app.dependency_overrides[deps.optional_user] = lambda: {"id": "8", "role": "user"}
    try:
        assert client.delete("/api/documents/mine").status_code == 404
        app.dependency_overrides[deps.optional_user] = lambda: {"id": "7", "role": "user"}
        assert client.delete("/api/documents/mine").status_code == 200
    finally:
        app.dependency_overrides.clear()
    assert not pdf.exists()


def test_not_while_it_is_being_analysed(env):
    client, store, uploads, _, _ = env
    _doc(store, uploads, "busy", status="processing")
    assert client.delete("/api/documents/busy").status_code == 409
    assert store._doc_dir("busy").exists()


def test_a_pdf_outside_the_uploads_is_never_removed(env, tmp_path):
    """A document pointing at a corpus or demo PDF loses its record, not the PDF."""
    client, store, uploads, _, _ = env
    elsewhere = tmp_path / "corpus.pdf"
    d = fitz.open()
    d.new_page()
    d.save(elsewhere)
    store.save_meta(DocumentMeta(doc_id="ref", filename="c.pdf", pages=1, file_size_kb=1.0))
    store.save_path("ref", str(elsewhere))
    assert client.delete("/api/documents/ref").status_code == 200
    assert elsewhere.exists()


def test_database_rows_are_forgotten():
    """The owner's listing and saved sandbox runs go with the document (test
    database, isolated by conftest)."""
    from auth import users
    from db import database
    database.init_db()
    uid = str(users.create_user("del@example.com", "Deleter", "pw123456")["id"])
    users.record_document(uid, "gone", "gone.pdf", r2_key="k/gone.pdf")
    users.record_document(uid, "kept", "kept.pdf")
    users.record_simulation(uid, "gone", {"a": 1}, {"b": 2})
    assert users.forget_document("gone") == ["k/gone.pdf"]
    assert [d["doc_id"] for d in users.list_documents(uid)] == ["kept"]
    assert all(s["doc_id"] != "gone" for s in users.list_simulations(uid))
