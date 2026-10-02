"""
Dependency-light metric primitives for the evaluation harness.

Kept free of heavy imports (no seqeval/datasets/torch at module load) so the
unit tests run offline and fast. seqeval is imported lazily inside `ner_f1`.
"""
import math
from typing import Optional


# ─── Binary classification ─────────────────────────────────────────────────────

def binary_prf1(gold: list[bool], pred: list[bool]) -> dict:
    """Precision / recall / F1 / accuracy for a binary task. Pure Python so it
    needs no sklearn (though sklearn agrees to numerical precision)."""
    if len(gold) != len(pred):
        raise ValueError("gold and pred must be the same length")
    tp = sum(1 for g, p in zip(gold, pred) if g and p)
    fp = sum(1 for g, p in zip(gold, pred) if not g and p)
    fn = sum(1 for g, p in zip(gold, pred) if g and not p)
    tn = sum(1 for g, p in zip(gold, pred) if not g and not p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    total = tp + fp + fn + tn
    accuracy = (tp + tn) / total if total else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "support": len(gold),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


# ─── Set agreement ──────────────────────────────────────────────────────────────

def jaccard(a: list, b: list) -> float:
    """Jaccard overlap of two token sets (used for LIME proxy-vs-LLM agreement)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return round(len(sa & sb) / len(union), 4) if union else 0.0


# ─── Distribution divergence ────────────────────────────────────────────────────

def kl_divergence(p: list[float], q: list[float], eps: float = 1e-9) -> float:
    """KL(P ‖ Q) over discrete bins. P is the empirical (simulated) mass, Q the
    reference. Both are smoothed and renormalized so zero bins don't blow up."""
    if len(p) != len(q):
        raise ValueError("p and q must be the same length")
    ps = [x + eps for x in p]
    qs = [x + eps for x in q]
    sp, sq = sum(ps), sum(qs)
    ps = [x / sp for x in ps]
    qs = [x / sq for x in qs]
    return round(sum(pi * math.log(pi / qi) for pi, qi in zip(ps, qs)), 4)


def histogram(values: list[float], edges: list[float]) -> list[float]:
    """Normalized histogram mass of `values` over bin `edges` (len(edges)-1 bins).
    Values outside the edges are clamped into the end bins."""
    n_bins = len(edges) - 1
    if n_bins <= 0:
        return []
    counts = [0] * n_bins
    for v in values:
        placed = False
        for i in range(n_bins):
            if edges[i] <= v < edges[i + 1]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[0 if v < edges[0] else n_bins - 1] += 1
    total = sum(counts)
    return [c / total for c in counts] if total else [0.0] * n_bins


def log_edges(lo: float, hi: float, n_bins: int) -> list[float]:
    """Log-spaced bin edges over [lo, hi] — income spans orders of magnitude."""
    lo = max(lo, 1.0)
    step = (math.log(hi) - math.log(lo)) / n_bins
    return [math.exp(math.log(lo) + step * i) for i in range(n_bins + 1)]


# ─── NER: BIO tagging + seqeval ────────────────────────────────────────────────

def to_bio(text: str, entities: list[dict], tokenizer=None) -> list[str]:
    """Convert char-span entity annotations into a BIO tag sequence aligned to a
    whitespace tokenization. Each `entity` is {label, start, end} (char offsets).
    A token is B-/I-LABEL if its span overlaps the entity span.

    `tokenizer` (optional) returns [(token, start, end)]; defaults to whitespace.
    """
    tokens = tokenizer(text) if tokenizer else _whitespace_tokens(text)
    tags = ["O"] * len(tokens)
    for ent in sorted(entities, key=lambda e: e["start"]):
        started = False
        for i, (_, ts, te) in enumerate(tokens):
            # overlap between token [ts,te) and entity [start,end)
            if ts < ent["end"] and te > ent["start"]:
                if tags[i] == "O":
                    tags[i] = ("B-" if not started else "I-") + ent["label"]
                    started = True
    return tags


def _whitespace_tokens(text: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        j = i
        while j < n and not text[j].isspace():
            j += 1
        tokens.append((text[i:j], i, j))
        i = j
    return tokens


def ner_f1(gold_bio: list[list[str]], pred_bio: list[list[str]]) -> Optional[dict]:
    """Entity-level P/R/F1 via seqeval. Returns None if seqeval isn't installed
    (the harness logs and skips rather than crashing)."""
    try:
        from seqeval.metrics import (
            classification_report, f1_score, precision_score, recall_score,
        )
    except ImportError:
        return None
    report = classification_report(gold_bio, pred_bio, output_dict=True, zero_division=0)
    return {
        "macro_f1": round(float(f1_score(gold_bio, pred_bio, average="macro", zero_division=0)), 4),
        "micro_precision": round(float(precision_score(gold_bio, pred_bio, zero_division=0)), 4),
        "micro_recall": round(float(recall_score(gold_bio, pred_bio, zero_division=0)), 4),
        "micro_f1": round(float(f1_score(gold_bio, pred_bio, zero_division=0)), 4),
        "per_label": {
            k: {"precision": round(v["precision"], 4), "recall": round(v["recall"], 4),
                "f1": round(v["f1-score"], 4), "support": int(v["support"])}
            for k, v in report.items()
            if k not in ("macro avg", "micro avg", "weighted avg", "accuracy")
        },
    }
