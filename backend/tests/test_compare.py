"""Clause-level diff via synthetic embeddings — bucket assignment."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import AnalysisResult, Clause, GraphData
from routers.intelligence import _clause_level_diff
from storage import store


def _clause(doc_id: str, idx: int, text: str) -> Clause:
    return Clause(
        clause_id=f"{doc_id}_c{idx:04d}", doc_id=doc_id, page=1,
        section_hierarchy=[], text=text, char_start=0, char_end=len(text),
    )


def _result(doc_id: str, texts: list[str]) -> AnalysisResult:
    return AnalysisResult(
        doc_id=doc_id,
        clauses=[_clause(doc_id, i, t) for i, t in enumerate(texts)],
        graph=GraphData(nodes=[], edges=[]),
        stats={},
    )


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def test_diff_buckets(monkeypatch):
    dim = 8
    basis = np.eye(dim)

    # Orthogonal basis vectors → an exactly known similarity matrix.
    # Doc A: [identical, modified-source, removed]
    # Doc B: [identical, modified-variant, added]
    identical = basis[0]
    modified_a = basis[1]
    # cos(e1, 0.85·e1 + sqrt(1-0.85²)·e4) = 0.85 → modified bucket
    modified_b = 0.85 * basis[1] + np.sqrt(1 - 0.85**2) * basis[4]
    removed = basis[2]
    added = basis[3]

    vecs_a = np.stack([identical, modified_a, removed]).astype(np.float32)
    vecs_b = np.stack([identical, modified_b, added]).astype(np.float32)

    result_a = _result("da", ["same clause", "old wording", "gone in b"])
    result_b = _result("db", ["same clause", "new wording", "new in b"])

    def fake_load(doc_id):
        return {"da": vecs_a, "db": vecs_b}.get(doc_id)

    monkeypatch.setattr(store, "load_embeddings", fake_load)

    diff = _clause_level_diff("da", "db", result_a, result_b)
    assert diff is not None

    sim_modified = float(vecs_a[1] @ vecs_b[1])
    assert 0.75 <= sim_modified < 0.92, f"fixture drifted: {sim_modified}"

    assert diff["matched"] == 1
    assert [m["clause_a_id"] for m in diff["modified"]] == ["da_c0001"]
    assert diff["added"] == ["db_c0002"]
    assert diff["removed"] == ["da_c0002"]


def test_diff_none_without_embeddings(monkeypatch):
    result_a = _result("dx", ["one"])
    result_b = _result("dy", ["one"])
    monkeypatch.setattr(store, "load_embeddings", lambda doc_id: None)
    assert _clause_level_diff("dx", "dy", result_a, result_b) is None
