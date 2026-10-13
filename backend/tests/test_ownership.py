"""Document ownership: listing is scoped to the owner; removal needs the owner."""
from fastapi.testclient import TestClient

from auth.deps import can_list, can_manage
from models.schemas import DocumentMeta


def _meta(owner):
    return DocumentMeta(doc_id="d", filename="x.pdf", pages=1, file_size_kb=1.0, owner_id=owner)


def test_listing_and_management_rules():
    alice, bob, admin = {"id": "1", "role": "user"}, {"id": "2", "role": "user"}, {"id": "9", "role": "admin"}
    shared, owned = _meta(None), _meta("1")
    assert can_list(shared, None) and can_list(shared, bob)
    assert can_list(owned, alice) and can_list(owned, admin)
    assert not can_list(owned, bob) and not can_list(owned, None)
    assert can_manage(owned, alice) and can_manage(owned, admin)
    assert not can_manage(owned, bob) and not can_manage(owned, None)


def test_document_list_hides_other_users_documents(monkeypatch):
    import main
    from routers import data
    docs = [_meta(None).model_copy(update={"doc_id": "shared"}), _meta("42").model_copy(update={"doc_id": "theirs"})]
    monkeypatch.setattr(data, "list_documents", lambda: docs)
    ids = {d["doc_id"] for d in TestClient(main.app).get("/api/documents").json()["documents"]}
    assert ids == {"shared"}
