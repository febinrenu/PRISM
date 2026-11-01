"""
Section-by-section comparison of two parsed statutes (or two versions of one).

The sections of A are matched to the sections of B by what they say, not by their number: an Act
that renumbers, splits or rewrites a provision still finds its counterpart. A match is made in
three steps:

  1. a section whose words are identical (after the number is stripped) is paired at once,
     preferring the one with the same number;
  2. the rest are scored by TF-IDF cosine over heading and text, with a bonus when the heading or
     the number is the same, and paired greedily from the best score down, each section used once
     (a match must score at least MIN_SCORE);
  3. what is left over is "only in A" (removed) or "only in B" (added).

A pair is "unchanged" when the text is identical, "formatting" when it differs only in how the two
sources print it (Act citations such as "(43 of 1961)", amendment brackets, dashes, spacing, words the PDF broke in two),
"renumbered" when it is the same under a new number, and "modified" otherwise. For every modified pair the rupee amounts and percentages that
appear in one text and not the other are listed, because a changed rate is the change a reader of
a tax law looks for first.
"""
import re
from collections import Counter

import numpy as np
from rapidfuzz import fuzz
from rapidfuzz.distance import Indel
from sklearn.feature_extraction.text import TfidfVectorizer

MIN_SCORE = 0.30
UNCHANGED_RATIO = 99.5          # rapidfuzz ratio (0-100) at or above which two texts are the same

_PREFIX = re.compile(r"^\s*\d+[A-Z]{0,3}\.\s*")
_WS = re.compile(r"\s+")
_FIGURE = re.compile(
    r"(?:₹|\brs\.?|\brupees)\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|crore|thousand|million))?"
    r"|\d+(?:\.\d+)?\s*(?:%|per\s*cent)",
    re.I,
)


_CITATION = re.compile(r"\(\s*\d+\s+of\s+\d{4}\s*\)")
_COSMETIC = [
    (re.compile(r"[`\[\]]"), ""),                              # amendment brackets and their marker
    (_CITATION, ""),                                             # "(43 of 1961)"
    (re.compile(r"\s*[–—-]\s*"), "-"),                         # dashes, spaced or not
    (re.compile(r"[‘’]"), "'"),
    (re.compile(r"[“”]"), '"'),
]


def _raw(text: str) -> str:
    return _WS.sub(" ", _PREFIX.sub("", text)).strip().lower()


def clean(text: str) -> str:
    """The text as it reads, without the sources' printing differences (the front end mirrors this)."""
    for pat, rep in _COSMETIC:
        text = pat.sub(rep, text)
    return _WS.sub(" ", text).strip()


_NON_ALNUM = re.compile(r"[\W_]+")


def compact(text: str) -> str:
    """Letters and digits only, lower-cased: equal for two prints of one text however they space, hyphenate
    or break its words."""
    return _NON_ALNUM.sub("", clean(text).lower())


def strip_heading_bleed(rows: list[tuple]) -> list[tuple]:
    """(path, number, heading, text) rows with the next section's marginal heading cut from the end of
    a section's text, where the PDF's layout ran it on."""
    out = []
    for k, (path, number, heading, text) in enumerate(rows):
        nxt = rows[k + 1][2] if k + 1 < len(rows) else ""
        words = re.findall(r"\w+", nxt)
        if len(words) >= 2:
            m = re.search(r"\W*".join(map(re.escape, words)) + r"\W*$", text, re.I | re.S)
            if m and m.start() > 0.3 * len(text):
                text = text[: m.start()].rstrip()
        out.append((path, number, heading, text))
    return out


def diff_ranges(a: str, b: str) -> tuple[list[list[int]], list[list[int]]]:
    """Where `a` loses words and `b` gains them, as character ranges into the texts as given.
    Differences in spacing, punctuation, case and word breaks do not count."""
    def squeeze(t: str) -> tuple[str, list[int]]:
        chars, idx = [], []
        skip = bytearray(len(t))
        for m in _CITATION.finditer(t):          # an Act's citation is how the source prints it, not a change
            skip[m.start():m.end()] = b"" * (m.end() - m.start())
        for i, ch in enumerate(t):
            if ch.isalnum() and not skip[i]:
                chars.append(ch.lower())
                idx.append(i)
        return "".join(chars), idx

    ca, ia = squeeze(a)
    cb, ib = squeeze(b)
    dels: list[list[int]] = []
    ins: list[list[int]] = []
    for tag, i1, i2, j1, j2 in Indel.opcodes(ca, cb):
        if tag in ("delete", "replace") and i2 > i1:
            dels.append([ia[i1], ia[i2 - 1] + 1])
        if tag in ("insert", "replace") and j2 > j1:
            ins.append([ib[j1], ib[j2 - 1] + 1])

    def widen(ranges: list[list[int]], text: str) -> list[list[int]]:
        out: list[list[int]] = []
        for s_, e_ in ranges:
            while s_ > 0 and not text[s_ - 1].isspace():
                s_ -= 1
            while e_ < len(text) and not text[e_].isspace():
                e_ += 1
            if out and s_ <= out[-1][1] + 1:
                out[-1][1] = max(out[-1][1], e_)
            else:
                out.append([s_, e_])
        return out

    return widen(dels, a), widen(ins, b)


def _norm(text: str) -> str:
    return _WS.sub(" ", clean(_PREFIX.sub("", text))).strip().lower()


def _head(heading: str) -> str:
    return _WS.sub(" ", re.sub(r"[^\w\s]", " ", heading.lower())).strip()


def _figure_key(s: str) -> str:
    s = s.lower().replace("rupees", "₹").replace("rs.", "₹").replace("rs", "₹")
    s = re.sub(r"per\s*cent", "%", s)
    return re.sub(r"[\s,]", "", s)


def figures(text: str) -> dict[str, str]:
    """Rupee amounts and percentages in `text`, as {normalised: as printed}."""
    out: dict[str, str] = {}
    for m in _FIGURE.finditer(text):
        out.setdefault(_figure_key(m.group(0)), " ".join(m.group(0).split()))
    return out


def figure_changes(a: str, b: str) -> dict | None:
    fa, fb = figures(a), figures(b)
    removed = [fa[k] for k in fa if k not in fb]
    added = [fb[k] for k in fb if k not in fa]
    return {"removed": removed[:12], "added": added[:12]} if removed or added else None


def _entry(s: dict | None) -> dict | None:
    return None if s is None else {"path": s["path"], "number": s["number"], "heading": s["heading"]}


def compare_sections(a: list[dict], b: list[dict]) -> dict:
    """`a`, `b`: sections as {path, number, heading, text}. Returns the summary and the ordered rows."""
    na, nb = [_norm(s["text"]) for s in a], [_norm(s["text"]) for s in b]
    ra, rb = [_raw(s["text"]) for s in a], [_raw(s["text"]) for s in b]
    ca, cb = [compact(_PREFIX.sub("", s["text"])) for s in a], [compact(_PREFIX.sub("", s["text"])) for s in b]
    pair_of_a: dict[int, int] = {}
    score_of: dict[int, float] = {}
    used_b: set[int] = set()

    # 1. identical words
    by_text: dict[str, list[int]] = {}
    for j, t in enumerate(cb):
        if len(t) > 40:
            by_text.setdefault(t, []).append(j)
    for i, t in enumerate(ca):
        cands = [j for j in by_text.get(t, []) if j not in used_b]
        if len(t) > 40 and cands:
            j = next((j for j in cands if b[j]["number"] == a[i]["number"]), cands[0])
            pair_of_a[i], score_of[i] = j, 1.0
            used_b.add(j)

    # 2. by meaning
    free_a = [i for i in range(len(a)) if i not in pair_of_a]
    free_b = [j for j in range(len(b)) if j not in used_b]
    if free_a and free_b:
        docs = [f"{_head(s['heading'])} {_head(s['heading'])} {t}" for s, t in
                [(a[i], na[i]) for i in free_a] + [(b[j], nb[j]) for j in free_b]]
        try:
            many = len(docs) > 60               # rare words only mean something across a large Act
            vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=2 if many else 1,
                                  max_df=0.6 if many else 1.0,
                                  max_features=300_000, dtype=np.float32)
            X = vec.fit_transform(docs)
        except ValueError:                       # nothing left worth indexing
            X = None
        if X is not None:
            S = (X[: len(free_a)] @ X[len(free_a):].T).toarray()
            heads_b = {}
            for jj, j in enumerate(free_b):
                if b[j]["heading"]:
                    heads_b.setdefault(_head(b[j]["heading"]), []).append(jj)
            nums_b = {b[j]["number"]: jj for jj, j in enumerate(free_b)}
            for ii, i in enumerate(free_a):
                for jj in heads_b.get(_head(a[i]["heading"]), []) if a[i]["heading"] else []:
                    S[ii, jj] += 0.20
                jj = nums_b.get(a[i]["number"])
                if jj is not None:
                    S[ii, jj] += 0.05
            cand = np.argwhere(S >= MIN_SCORE)
            order = np.argsort(-S[cand[:, 0], cand[:, 1]], kind="stable")
            taken_a: set[int] = set()
            taken_b: set[int] = set()
            for k in order:
                ii, jj = int(cand[k, 0]), int(cand[k, 1])
                if ii in taken_a or jj in taken_b:
                    continue
                taken_a.add(ii)
                taken_b.add(jj)
                pair_of_a[free_a[ii]], score_of[free_a[ii]] = free_b[jj], float(min(1.0, S[ii, jj]))
                used_b.add(free_b[jj])

    # rows in A's order, with B-only sections placed where B puts them
    rows: list[dict] = []
    pairs_by_b = {j: i for i, j in pair_of_a.items()}
    emitted_b: set[int] = set()

    def emit_b_only_before(jlimit: int) -> None:
        for j in range(len(b)):
            if j >= jlimit:
                break
            if j not in pairs_by_b and j not in emitted_b:
                emitted_b.add(j)
                rows.append({"id": f"added::{b[j]['path']}", "status": "added", "a": None, "b": _entry(b[j]),
                             "similarity": None, "score": None, "figures": None})

    for i, s in enumerate(a):
        j = pair_of_a.get(i)
        if j is None:
            rows.append({"id": f"removed:{s['path']}:", "status": "removed", "a": _entry(s), "b": None,
                         "similarity": None, "score": None, "figures": None})
            continue
        emit_b_only_before(j)
        emitted_b.add(j)
        ratio = 100.0 if ca[i] == cb[j] else fuzz.ratio(ca[i], cb[j])
        same = ratio >= UNCHANGED_RATIO
        if not same:
            status = "modified"
        elif a[i]["number"] != b[j]["number"]:
            status = "renumbered"
        else:
            status = "unchanged" if ra[i] == rb[j] else "formatting"
        rows.append({
            "id": f"{status}:{s['path']}:{b[j]['path']}", "status": status, "a": _entry(s), "b": _entry(b[j]),
            "similarity": round(ratio / 100.0, 4), "score": round(score_of[i], 4),
            "figures": None if same else figure_changes(s["text"], b[j]["text"]),
        })
    emit_b_only_before(len(b))

    counts = Counter(r["status"] for r in rows)
    return {
        "summary": {
            "sections_a": len(a), "sections_b": len(b), "matched": len(pair_of_a),
            "unchanged": counts["unchanged"], "formatting": counts["formatting"], "renumbered": counts["renumbered"], "modified": counts["modified"],
            "removed": counts["removed"], "added": counts["added"],
            "figures_changed": sum(1 for r in rows if r["figures"]),
        },
        "rows": rows,
    }
