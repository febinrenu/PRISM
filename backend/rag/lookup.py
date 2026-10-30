"""
Exact section lookup in the statute corpus.

When a question names a section ("what is the rebate under section 156?"), the
section's own words are fetched from the parsed statute tree, not searched for.
Several Acts have a section 156, so when the question does not say which, the
candidates are ranked against the question by the cross-encoder, and the one that
fits ("rebate" is the Income-tax Act 2025's, not the 1961 Act's "notice of demand")
comes first.
"""
from functools import lru_cache
from typing import Optional

from rag import statute_index as si
from rag.query_plan import Plan, SectionRef

MAX_SECTION_CHARS = 3600
MAX_REFS = 3
KEEP_WITHIN = 5.0          # keep a candidate whose re-ranker score is this close to the best


@lru_cache(maxsize=16)
def _index(statute: str, version: str, stamp: str):
    ast, text = si.load_statute(statute, version)
    by_id = {n["node_id"]: n for n in ast["nodes"]}
    by_number: dict[str, dict] = {}
    for n in ast["nodes"]:
        if n["kind"] == "section" and not n["quoted"]:
            by_number.setdefault(str(n["number"]).upper(), n)
    return by_number, by_id, text, ast.get("title") or statute


def resolve(statute: str, version: str, ref: SectionRef) -> Optional[tuple[dict, bool, str, str]]:
    """(node, whether every sub-reference was found, text, act title) for a reference
    in one statute, or None when it has no such section."""
    by_number, by_id, text, title = _index(statute, version, si._stamp(statute, version))
    node = by_number.get(ref.number)
    if node is None:
        return None
    exact = True
    for sub in ref.subs:
        kids = [by_id[c] for c in node.get("children", []) if c in by_id]
        nxt = next((k for k in kids if str(k.get("label", "")).strip("()").lower() == sub.lower()), None)
        if nxt is None:
            exact = False          # a sub-provision we cannot find: fall back to the whole section
            break
        node = nxt
    return node, exact, text[node["start"]:node["end"]], title


def _cut(body: str) -> tuple[str, bool]:
    if len(body) <= MAX_SECTION_CHARS:
        return body, False
    cut = body.rfind("\n", 0, MAX_SECTION_CHARS)
    cut = cut if cut > MAX_SECTION_CHARS // 2 else MAX_SECTION_CHARS
    return body[:cut].rstrip(), True


def _hit(statute: str, version: str, ref: SectionRef, found: tuple) -> dict:
    node, exact, body, title = found
    text, truncated = _cut(body)
    section = str(ref) if exact else ref.number
    return {
        "id": f"{si.doc_id_for(statute, version)}::{node['path']}", "text": text, "similarity": None,
        "doc_id": si.doc_id_for(statute, version), "doc_name": title, "clause_id": node["path"],
        "section": section, "heading": node.get("heading") or "", "page": int(node.get("page") or 0),
        "entity_types": "", "has_causal": False, "kind": "statute", "node_path": node["path"],
        "statute_key": f"{statute}/{version}", "match": "section", "exact_sub": exact,
        "truncated": truncated, "rerank_score": None,
    }


def _scope(plan: Plan, doc_ids: Optional[list[str]]) -> list[tuple[str, str]]:
    """The (statute, version) pairs a lookup may read: the Acts the question names,
    else all; and only those the caller's document filter allows."""
    pairs = si.available()
    if plan.acts:
        named = {a for a, _ in plan.acts}
        versions = {a: v for a, v in plan.acts if v}
        pairs = [(s, v) for s, v in pairs if s in named and (s not in versions or v == versions[s])]
    if doc_ids:
        pairs = [(s, v) for s, v in pairs if si.doc_id_for(s, v) in set(doc_ids)]
    return pairs


def lookup(plan: Plan, doc_ids: Optional[list[str]] = None, per_ref: int = 3) -> list[dict]:
    """The sections the question names, as retrieval hits flagged match="section"."""
    if not plan.refs:
        return []
    pairs = _scope(plan, doc_ids)
    if not pairs:
        return []
    out: list[dict] = []
    for ref in plan.refs[:MAX_REFS]:
        cands = []
        for statute, version in pairs:
            try:
                found = resolve(statute, version, ref)
            except (OSError, ValueError, KeyError):
                continue
            if found is not None:
                cands.append(_hit(statute, version, ref, found))
        # both versions of one Act with the same words are one candidate: keep the current law
        seen: dict[str, dict] = {}
        for c in cands:
            key = f"{c['doc_name'].split(' (as amended')[0]}|{c['text']}"
            if key not in seen or c["statute_key"].endswith("amended_fa2026"):
                seen[key] = c
        cands = list(seen.values())
        if len(cands) > 1 and not plan.acts:
            from rag.hybrid import rerank
            scores = rerank(plan.standalone, [f"{c['doc_name']}, section {c['section']}. {c['heading']}\n{c['text']}"
                                              for c in cands])
            for c, s in zip(cands, scores):
                c["rerank_score"] = round(float(s), 4)
            cands.sort(key=lambda c: -c["rerank_score"])
            best = cands[0]["rerank_score"]
            cands = [c for c in cands if c["rerank_score"] >= best - KEEP_WITHIN]
        out += cands[:per_ref]
    return out
