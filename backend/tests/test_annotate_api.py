"""Annotation API: set listing, blind item view, saving, validation."""
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
pytestmark = pytest.mark.skipif(
    not (BACKEND / "data" / "eval" / "v2" / "manifest.json").exists()
    or not (BACKEND / "data" / "corpus" / "DPDP2023" / "enacted" / "ast.json").exists(),
    reason="evaluation manifest or corpus not available",
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    from routers import annotate
    mp.setattr(annotate, "ANNOTATION_DIR", tmp_path_factory.mktemp("annotations"))
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"email": "annotator.a@example.org", "password": "annotate-pass",
                                               "name": "Annotator A"})
        assert r.status_code == 200, r.text
        c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        yield c
    mp.undo()


def test_sets_and_items(client):
    sets = {s["set"]: s for s in client.get("/api/annotate/sets").json()["sets"]}
    assert sets["test"]["items"] == 300 and sets["pilot"]["items"] == 30
    items = client.get("/api/annotate/sets/pilot").json()["items"]
    assert all(i["status"] == "todo" for i in items)


def test_requires_login(client):
    from fastapi.testclient import TestClient
    from main import app
    assert TestClient(app).get("/api/annotate/sets").status_code == 401


def test_item_view_is_blind_and_saving_round_trips(client):
    item_id = client.get("/api/annotate/sets/pilot").json()["items"][0]["item_id"]
    view = client.get(f"/api/annotate/items/{item_id}").json()
    assert view["text"] and view["annotation"] is None
    assert "llm" not in str(view).lower() and "extraction" not in view

    n = len(view["text"])
    draft = {"status": "draft", "rules": [{"modality": "obligation", "action": {"start": 0, "end": min(10, n)}}]}
    r = client.put(f"/api/annotate/items/{item_id}", json=draft)
    assert r.status_code == 200 and r.json()["status"] == "draft"
    again = client.get(f"/api/annotate/items/{item_id}").json()["annotation"]
    assert again["rules"][0]["action"] == {"start": 0, "end": min(10, n)}
    assert again["annotator_name"] == "Annotator A"


def test_validation(client):
    item_id = client.get("/api/annotate/sets/pilot").json()["items"][1]["item_id"]
    n = len(client.get(f"/api/annotate/items/{item_id}").json()["text"])
    out_of_range = {"status": "draft", "rules": [{"modality": "obligation", "action": {"start": 0, "end": n + 5}}]}
    assert client.put(f"/api/annotate/items/{item_id}", json=out_of_range).status_code == 422
    empty_done = {"status": "done", "rules": []}
    assert client.put(f"/api/annotate/items/{item_id}", json=empty_done).status_code == 422
    bad_effect = {"status": "done", "rules": [{"modality": "obligation",
                                                "effects": [{"kind": "slab_row", "fields": {"rate": 0.05}}]}]}
    assert client.put(f"/api/annotate/items/{item_id}", json=bad_effect).status_code == 422
    no_rule = {"status": "done", "no_rule": True}
    assert client.put(f"/api/annotate/items/{item_id}", json=no_rule).status_code == 200
