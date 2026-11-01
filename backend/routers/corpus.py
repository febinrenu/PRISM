"""
Read-only browsing of the parsed statute corpus.

    GET /api/corpus/statutes                          parsed statutes with counts
    GET /api/corpus/{statute}/{version}/outline       chapters / parts / schedules → sections
    GET /api/corpus/{statute}/{version}/node?path=…   one node: its text and its children
    GET /api/corpus/{statute}/{version}/search?q=…    sections whose own words contain the query
    GET /api/corpus/compare?a=…&b=…                   two statutes matched section by section
    GET /api/corpus/compare/pair?a=…&pa=…&b=…&pb=…    one matched pair: both texts with what changed marked
"""
import json
import re
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

from pipeline.statute.corpus import CORPUS_DIR

router = APIRouter()
_CONTAINERS = {"chapter", "part", "subpart", "schedule", "paragraph"}


def _available() -> dict[str, tuple[str, str]]:
    return {f"{p.parent.parent.name}/{p.parent.name}": (p.parent.parent.name, p.parent.name)
            for p in CORPUS_DIR.glob("*/*/ast.json")}


@lru_cache(maxsize=8)
def _load(statute: str, version: str, mtime: float) -> tuple[dict, str, dict]:
    base = CORPUS_DIR / statute / version
    ast = json.loads((base / "ast.json").read_text(encoding="utf-8"))
    text = (base / "text.txt").read_text(encoding="utf-8")
    src = base / "source.json"
    meta = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    return ast, text, meta


def _get(statute: str, version: str) -> tuple[dict, str, dict]:
    if f"{statute}/{version}" not in _available():   # whitelist: no path traversal
        raise HTTPException(status_code=404, detail="Unknown statute")
    path = CORPUS_DIR / statute / version / "ast.json"
    return _load(statute, version, path.stat().st_mtime)


@lru_cache(maxsize=8)
def _section_texts(statute: str, version: str, mtime: float) -> list[tuple[str, str, str, str]]:
    """(path, number, heading, text) for every enacted section, once per statute."""
    from pipeline.statute.compare import strip_heading_bleed

    ast, text, _ = _load(statute, version, mtime)
    return strip_heading_bleed([(n["path"], n["number"], n.get("heading") or "", text[n["start"]:n["end"]])
                                for n in ast["nodes"] if n["kind"] == "section" and not n["quoted"]])


def _label(n: dict) -> str:
    k = n["kind"]
    if k == "section":
        return f"s.{n['number']}"
    if k in ("chapter", "part", "subpart", "paragraph"):
        return f"{k.capitalize()} {n.get('number', '')}".strip()
    if k == "schedule":
        return f"{n.get('number', '')} Schedule".strip()
    if k in ("subsection", "clause", "subclause", "item", "subitem") and n.get("label"):
        return f"({n['label']})"
    return n.get("label") or k


@router.get("/corpus/statutes")
def statutes():
    out = []
    for key, (statute, version) in sorted(_available().items()):
        ast, text, meta = _get(statute, version)
        nodes = ast["nodes"]
        out.append({"key": key, "statute": statute, "version": version, "title": meta.get("title", statute),
                    "sections": sum(1 for n in nodes if n["kind"] == "section" and not n["quoted"]),
                    "chapters": sum(1 for n in nodes if n["kind"] == "chapter"),
                    "nodes": len(nodes), "characters": len(text)})
    return {"statutes": out}


@router.get("/corpus/{statute}/{version}/outline")
def outline(statute: str, version: str):
    ast, _, meta = _get(statute, version)
    nodes = {n["node_id"]: n for n in ast["nodes"]}
    groups, loose = [], []

    def container_of(n: dict):
        p = nodes.get(n.get("parent") or "")
        while p is not None and p["kind"] not in _CONTAINERS:
            p = nodes.get(p.get("parent") or "")
        return p

    index: dict[str, dict] = {}
    for n in ast["nodes"]:
        if n["kind"] != "section" or n["quoted"]:
            continue
        c = container_of(n)
        entry = {"path": n["path"], "number": n["number"], "heading": n.get("heading") or ""}
        if c is None:
            loose.append(entry)
            continue
        if c["node_id"] not in index:
            index[c["node_id"]] = {"path": c["path"], "label": _label(c), "heading": c.get("heading") or "",
                                   "sections": []}
            groups.append(index[c["node_id"]])
        index[c["node_id"]]["sections"].append(entry)
    schedules = [{"path": n["path"], "label": _label(n), "heading": n.get("heading") or ""}
                 for n in ast["nodes"] if n["kind"] == "schedule"]
    return {"statute": f"{statute}/{version}", "title": meta.get("title", statute),
            # sections outside any chapter (e.g. a preliminary part) come first
            "groups": ([{"path": "", "label": "Sections", "heading": "", "sections": loose}] if loose else []) + groups,
            "schedules": schedules}


@router.get("/corpus/{statute}/{version}/node")
def node(statute: str, version: str, path: str = Query(..., max_length=300)):
    ast, text, _ = _get(statute, version)
    by_path = {n["path"]: n for n in ast["nodes"]}
    n = by_path.get(path)
    if n is None:
        raise HTTPException(status_code=404, detail="Unknown provision path")
    by_id = {x["node_id"]: x for x in ast["nodes"]}
    children = [by_id[c] for c in n.get("children", []) if c in by_id]
    parent = by_id.get(n.get("parent") or "")
    return {
        "path": n["path"], "node_id": n["node_id"], "kind": n["kind"], "label": _label(n),
        "heading": n.get("heading") or "", "page": n.get("page"),
        "text": text[n["start"]:n["end"]], "start": n["start"],
        "parent": parent["path"] if parent else None,
        "children": [{"path": c["path"], "kind": c["kind"], "label": _label(c),
                      "preview": text[c["start"]:min(c["end"], c["start"] + 140)]
                      or "(its words open the provision above)"} for c in children[:400]],
    }


_MAX_HITS = 30


@router.get("/corpus/{statute}/{version}/search")
def search(statute: str, version: str, q: str = Query(..., min_length=3, max_length=100)):
    """Sections whose text holds every word of the query, those with the whole phrase first."""
    _get(statute, version)
    words = [w for w in re.findall(r"[\w'.-]+", q.lower()) if len(w) > 1][:6]
    if not words:
        return {"query": q, "hits": [], "more": False}
    phrase = " ".join(words)
    mtime = (CORPUS_DIR / statute / version / "ast.json").stat().st_mtime
    scored = []
    for path, number, heading, body in _section_texts(statute, version, mtime):
        low = f"{heading}. {body}".lower()           # the heading is not part of the section's own text
        if not all(w in low for w in words):
            continue
        whole = low.count(phrase)
        scored.append((-whole, -sum(low.count(w) for w in words), path, number, heading, body, low))
    scored.sort(key=lambda t: t[:3])
    hits = []
    for _, _, path, number, heading, body, low in scored[:_MAX_HITS]:
        # a snippet comes from the section's words; when only its heading matches, from the opening
        own = body.lower()
        at = own.find(phrase)
        if at < 0:
            found = [own.find(w) for w in words if w in own]
            at = min(found) if len(found) == len(words) else 0
        start = max(0, at - 70)
        hits.append({"path": path, "number": number, "heading": heading,
                     "snippet": ("…" if start else "") + re.sub(r"\s+", " ", body[start:start + 190]).strip()})
    return {"query": q, "hits": hits, "more": len(scored) > _MAX_HITS}


@lru_cache(maxsize=12)
def _compare(key_a: str, key_b: str, mtime_a: float, mtime_b: float) -> dict:
    from pipeline.statute.compare import compare_sections

    out = {}
    for tag, key, mt in (("a", key_a, mtime_a), ("b", key_b, mtime_b)):
        statute, version = key.split("/")
        out[tag] = (key, _section_texts(statute, version, mt), _load(statute, version, mt)[2].get("title", statute))
    secs = {t: [{"path": p, "number": n, "heading": h, "text": x} for p, n, h, x in v[1]] for t, v in out.items()}
    result = compare_sections(secs["a"], secs["b"])
    result["a"] = {"key": out["a"][0], "title": out["a"][2]}
    result["b"] = {"key": out["b"][0], "title": out["b"][2]}
    return result


@router.get("/corpus/compare")
def compare(a: str = Query(..., max_length=80), b: str = Query(..., max_length=80)):
    """Match the sections of two parsed statutes by what they say and report what changed."""
    avail = _available()
    for key in (a, b):
        if key not in avail:
            raise HTTPException(status_code=404, detail="Unknown statute")
    if a == b:
        raise HTTPException(status_code=422, detail="Choose two different statutes")
    mt = lambda k: (CORPUS_DIR / k / "ast.json").stat().st_mtime
    return _compare(a, b, mt(a), mt(b))


def _section(key: str, path: str) -> tuple[str, str, str, str]:
    statute, version = key.split("/")
    mtime = (CORPUS_DIR / key / "ast.json").stat().st_mtime
    for row in _section_texts(statute, version, mtime):
        if row[0] == path:
            return row
    raise HTTPException(status_code=404, detail="Unknown provision path")


@router.get("/corpus/compare/pair")
def compare_pair(a: str = Query(..., max_length=80), pa: str = Query(..., max_length=300),
                 b: str = Query(..., max_length=80), pb: str = Query(..., max_length=300)):
    """One matched pair of sections: each text with the character ranges that the other lacks."""
    from rapidfuzz import fuzz

    from pipeline.statute.compare import compact, diff_ranges, figure_changes

    avail = _available()
    for key in (a, b):
        if key not in avail:
            raise HTTPException(status_code=404, detail="Unknown statute")
    path_a, number_a, heading_a, text_a = _section(a, pa)
    path_b, number_b, heading_b, text_b = _section(b, pb)
    deleted, inserted = diff_ranges(text_a, text_b)
    return {
        "a": {"path": path_a, "number": number_a, "heading": heading_a, "text": text_a, "marked": deleted},
        "b": {"path": path_b, "number": number_b, "heading": heading_b, "text": text_b, "marked": inserted},
        "similarity": round(fuzz.ratio(compact(text_a), compact(text_b)) / 100.0, 4),
        "figures": figure_changes(text_a, text_b),
    }
