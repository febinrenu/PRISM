"""
Ground a model-quoted span in the source text.

A model is asked to quote its condition / action / consequence verbatim. The
quote is accepted only if it can be located in the provision:

    1. exact substring
    2. same after normalising case, whitespace, quotes and dashes
    3. rapidfuzz partial alignment with score ≥ FUZZY_MIN, snapped to the
       aligned source substring

Otherwise the field is rejected and counted as a hallucination. Accepted
spans are always the *source* substring, never the model's paraphrase.
"""
import re
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

FUZZY_MIN = 90.0
_MIN_QUOTE_CHARS = 3

_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-", " ": " "})


def _norm_map(s: str) -> tuple[str, list[int]]:
    """Normalised text plus, for each normalised char, its index in `s`."""
    out, idx = [], []
    prev_space = False
    for i, ch in enumerate(s.translate(_TRANS)):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch.lower())
        idx.append(i)
    return "".join(out), idx


@dataclass
class Grounded:
    start: int
    end: int
    text: str
    method: str          # exact | normalised | fuzzy
    score: float


def ground(quote: Optional[str], source: str) -> Optional[Grounded]:
    if not quote:
        return None
    q = quote.strip().strip("\"'“”‘’")
    if len(q) < _MIN_QUOTE_CHARS:
        return None
    i = source.find(q)
    if i >= 0:
        return Grounded(i, i + len(q), source[i:i + len(q)], "exact", 100.0)

    nsrc, idx = _norm_map(source)
    nq, _ = _norm_map(q)
    nq = nq.strip()
    j = nsrc.find(nq)
    if j >= 0 and nq:
        s, e = idx[j], idx[j + len(nq) - 1] + 1
        return Grounded(s, e, source[s:e], "normalised", 100.0)

    if len(nq) < 12:
        return None  # too short for a meaningful fuzzy match
    al = fuzz.partial_ratio_alignment(nq, nsrc, score_cutoff=FUZZY_MIN)
    if al is None:
        return None
    s, e = idx[al.dest_start], idx[max(al.dest_end - 1, al.dest_start)] + 1
    # Snap outward to word boundaries so a span never starts mid-word.
    while s > 0 and source[s - 1].isalnum():
        s -= 1
    while e < len(source) and source[e].isalnum():
        e += 1
    # Include a closing bracket the alignment stopped just short of.
    if e < len(source) and source[e] == ")" and source[s:e].count("(") > source[s:e].count(")"):
        e += 1
    return Grounded(s, e, source[s:e], "fuzzy", float(al.score))


def ground_many(quotes: list[str], source: str) -> tuple[list[Grounded], int]:
    """(grounded spans, number rejected)."""
    out, rejected = [], 0
    for q in quotes:
        g = ground(q, source)
        if g is None:
            rejected += 1
        else:
            out.append(g)
    return out, rejected


def quantity_consistent(value: float, kind: str, span_text: str) -> bool:
    """A quantity must re-parse from its own grounded span with the same value."""
    from pipeline.quantities import extract_quantities

    for q in extract_quantities(span_text):
        if q.kind != kind:
            continue
        if abs(q.value - value) <= 1e-6 * max(1.0, abs(value)):
            return True
        if q.upper is not None and abs(q.upper - value) <= 1e-6 * max(1.0, abs(value)):
            return True
    return False


_WS = re.compile(r"\s+")
