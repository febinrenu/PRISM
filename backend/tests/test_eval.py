"""Evaluation harness — offline metric unit tests (no network/services)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.metrics import (
    binary_prf1, histogram, jaccard, kl_divergence, log_edges, ner_f1, to_bio,
)


def test_binary_prf1_perfect():
    g = [True, False, True, False]
    r = binary_prf1(g, g)
    assert r["precision"] == 1.0 and r["recall"] == 1.0 and r["f1"] == 1.0


def test_binary_prf1_mixed():
    g = [True, True, False, False]
    p = [True, False, True, False]
    r = binary_prf1(g, p)
    assert r["tp"] == 1 and r["fp"] == 1 and r["fn"] == 1 and r["tn"] == 1
    assert r["precision"] == 0.5 and r["recall"] == 0.5


def test_binary_prf1_length_mismatch():
    import pytest
    with pytest.raises(ValueError):
        binary_prf1([True], [True, False])


def test_jaccard():
    assert jaccard(["a", "b"], ["a", "b"]) == 1.0
    assert jaccard(["a", "b"], ["b", "c"]) == round(1 / 3, 4)
    assert jaccard([], []) == 1.0


def test_kl_divergence_identical_is_zero():
    p = [0.25, 0.25, 0.5]
    assert kl_divergence(p, p) == 0.0


def test_kl_divergence_positive_when_different():
    assert kl_divergence([0.9, 0.1], [0.1, 0.9]) > 0.0


def test_histogram_and_log_edges():
    edges = log_edges(1.0, 1000.0, 3)  # 3 log-spaced bins over [1, 1000]
    assert len(edges) == 4
    mass = histogram([2.0, 20.0, 200.0], edges)
    assert abs(sum(mass) - 1.0) < 1e-9
    assert len(mass) == 3


def test_histogram_clamps_outliers():
    edges = [0.0, 1.0, 2.0]
    mass = histogram([-5.0, 100.0], edges)  # both outside → clamped into end bins
    assert abs(sum(mass) - 1.0) < 1e-9


def test_to_bio_basic():
    text = "the assessee shall pay tax"
    ents = [{"label": "ACTOR", "start": 4, "end": 12}]  # "assessee"
    tags = to_bio(text, ents)
    assert tags == ["O", "B-ACTOR", "O", "O", "O"]


def test_ner_f1_optional():
    # ner_f1 returns a dict if seqeval is installed, else None — either is valid.
    out = ner_f1([["B-ACTOR", "O"]], [["B-ACTOR", "O"]])
    assert out is None or out["micro_f1"] == 1.0
