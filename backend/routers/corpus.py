"""
Read-only browsing of the parsed statute corpus.

    GET /api/corpus/statutes                          parsed statutes with counts
    GET /api/corpus/{statute}/{version}/outline       chapters / parts / schedules → sections
    GET /api/corpus/{statute}/{version}/node?path=…   one node: its text and its children
"""
import json
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
