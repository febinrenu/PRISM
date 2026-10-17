"""
Put back the word spaces OCR drops.

Text recognisers trained mostly on Chinese (RapidOCR's PP-OCR models) often
read tightly set English without its spaces: "tosomuchof theincomebywayof".
A glued token is split where the split is far more probable than the token,
using word frequencies from the statute corpus itself (words.tsv, built by
`cli ocr-vocab`): the legal vocabulary the documents use. A token that is
itself a known word, or that cannot be split into known words, is kept.
"""
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

WORDS = Path(__file__).with_name("words.tsv")
MIN_LEN = 6              # shorter tokens are left alone
MAX_WORD = 24
_TOKEN = re.compile(r"[A-Za-z]+")


@lru_cache(maxsize=1)
def _costs() -> dict[str, float]:
    if not WORDS.exists():
        return {}
    freq: dict[str, int] = {}
    for line in WORDS.read_text(encoding="utf-8").splitlines():
        w, _, n = line.partition("\t")
        if w and n.isdigit():
            freq[w] = int(n)
    total = sum(freq.values()) or 1
    return {w: -math.log(n / total) for w, n in freq.items()}


def _split(token: str, costs: dict[str, float]) -> Optional[list[str]]:
    """Cheapest segmentation of a lowercase token into known words, or None."""
    n = len(token)
    best = [0.0] + [math.inf] * n
    back = [0] * (n + 1)
    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_WORD), i):
            c = costs.get(token[j:i])
            if c is not None and best[j] + c < best[i]:
                best[i], back[i] = best[j] + c, j
    if math.isinf(best[n]):
        return None
    out, i = [], n
    while i > 0:
        out.append(token[back[i]:i])
        i = back[i]
    return out[::-1]


def respace_token(token: str, costs: Optional[dict[str, float]] = None) -> str:
    costs = _costs() if costs is None else costs
    low = token.lower()
    if len(token) < MIN_LEN or not costs or low in costs:
        return token
    parts = _split(low, costs)
    if not parts or len(parts) < 2:
        return token
    # restore the original letter case, part by part
    out, k = [], 0
    for p in parts:
        out.append(token[k:k + len(p)])
        k += len(p)
    return " ".join(out)


def respace(text: str, costs: Optional[dict[str, float]] = None) -> str:
    costs = _costs() if costs is None else costs
    if not costs:
        return text
    return _TOKEN.sub(lambda m: respace_token(m.group(0), costs), text)


def build_vocabulary(texts: list[str], min_count: int = 2) -> dict[str, int]:
    """Lowercase word counts over the corpus texts."""
    counts: dict[str, int] = {}
    for t in texts:
        for w in _TOKEN.findall(t):
            w = w.lower()
            counts[w] = counts.get(w, 0) + 1
    return {w: n for w, n in counts.items() if n >= min_count and (len(w) > 1 or w in ("a", "i"))}


def write_vocabulary(counts: dict[str, int]) -> Path:
    lines = [f"{w}\t{n}" for w, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    WORDS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _costs.cache_clear()
    return WORDS
