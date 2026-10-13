"""Statute browser and research inspection endpoints."""
import pytest
from fastapi.testclient import TestClient

from pipeline.statute.corpus import CORPUS_DIR

pytestmark = pytest.mark.skipif(not (CORPUS_DIR / "ITA2025" / "amended_fa2026" / "ast.json").exists(),
                                reason="corpus not parsed")


@pytest.fixture(scope="module")
def client():
    import main
    return TestClient(main.app)


def test_statutes_outline_and_node(client):
    keys = {s["key"] for s in client.get("/api/corpus/statutes").json()["statutes"]}
    assert "ITA2025/amended_fa2026" in keys
    outline = client.get("/api/corpus/ITA2025/amended_fa2026/outline").json()
    sections = {s["number"]: s for g in outline["groups"] for s in g["sections"]}
    assert sections["156"]["heading"].startswith("Rebate of income-tax")
    node = client.get("/api/corpus/ITA2025/amended_fa2026/node", params={"path": "ITA2025/s156"}).json()
    assert node["text"].startswith("156. (1)") and [c["label"] for c in node["children"]] == ["(1)", "(2)", "(3)"]


def test_unknown_statute_and_path_are_404(client):
    assert client.get("/api/corpus/..%2F..%2Fsecrets/x/outline").status_code == 404
    assert client.get("/api/corpus/ITA2025/amended_fa2026/node", params={"path": "nope"}).status_code == 404
    assert client.get("/api/research/inspect/nope/rules").status_code == 404


def test_inspect_rule_baseline_spans_point_into_the_provision(client):
    data = client.get("/api/research/inspect/FA2020_new_regime/rules").json()
    unit = data["targets"][0]["units"][0]
    assert unit["effects"], "the rule baseline reads the FA 2020 table"
    for e in unit["effects"]:
        a, b = e["span"]
        assert unit["text"][a:b] == e["quote"]
