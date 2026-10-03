"""
Statute-parser segmentation for the analysis workspace.

Turns an uploaded PDF into the RawClause list the analysis pipeline expects,
using the statute AST instead of the regex segmenter: one clause per
extraction unit (a provision with its clauses, provisos and explanations),
with exact text, page and bounding box, and a hierarchy read from the AST
path ("Chapter IV › s.80C › (1) › (a)").

Documents that are not statutes (annual reports, notices) produce too few
sections for the parser to be meaningful; `segment` then returns None and
the caller falls back to the regex segmenter.
"""
from typing import Optional

import fitz

from pipeline.clause_segmenter import RawClause
from pipeline.extraction.units import build_units
from pipeline.statute.parser import parse_statute

MIN_SECTIONS = 3


def _container(node_id: str, by_id: dict) -> Optional[str]:
    """'Chapter IV' / 'Schedule FIRST' enclosing a node, if any."""
    n = by_id.get(node_id)
    while n is not None:
        if n["kind"] == "chapter":
            return f"Chapter {n['number']}"
        if n["kind"] == "schedule":
            return f"Schedule {n['number']}".strip()
        n = by_id.get(n.get("parent") or "")
    return None


def _hierarchy(path: str, container: Optional[str]) -> list[str]:
    parts = path.split("/")[1:]
    out = [container] if container else []
    for p in parts:
        if p.startswith("s") and p[1:2].isdigit():
            out.append(f"s.{p[1:]}")
        elif p.startswith("sch"):
            if not container:
                out.append(f"Schedule {p[3:]}".strip())
        elif p.startswith("pt"):
            out.append(f"Part {p[2:]}")
        elif p.startswith("para"):
            out.append(f"Paragraph {p[4:]}")
        elif p.startswith("q"):
            out.append("inserted text")
        elif p.startswith("(") or p.startswith("proviso") or p.startswith("expl"):
            out.append(p)
    return out


def segment(pdf_path: str, doc_key: str = "DOC") -> Optional[list[RawClause]]:
    ast = parse_statute(pdf_path, doc_key, "upload", "act")
    if ast.stats["sections"] < MIN_SECTIONS:
        return None
    ast_dict = ast.to_dict()
    units = build_units(doc_key, "upload", ast=ast_dict, text=ast.text)
    if not units:
        return None
    by_id = {n["node_id"]: n for n in ast.nodes}
    with fitz.open(pdf_path) as doc:
        sizes = [(p.rect.width or 1.0, p.rect.height or 1.0) for p in doc]

    clauses: list[RawClause] = []
    for u in units:
        node = by_id.get(u.unit_id, {})
        boxes = node.get("boxes") or []
        if not boxes:
            # Units opened by an inline label share their parent's paragraph.
            parent = by_id.get(node.get("parent") or "", {})
            boxes = parent.get("boxes") or []
        page = boxes[0][0] if boxes else 1
        bbox = None
        same_page = [b for b in boxes if b[0] == page]
        if same_page:
            w, h = sizes[page - 1]
            x0 = min(b[1] for b in same_page) / w
            y0 = min(b[2] for b in same_page) / h
            x1 = max(b[3] for b in same_page) / w
            y1 = max(b[4] for b in same_page) / h
            bbox = [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]
        is_table = node.get("kind") == "table_row" or (u.text.count("|") >= 2 and u.text.count("\n") >= 2)
        clauses.append(RawClause(
            text=u.text, page=page, char_start=u.start, char_end=u.end,
            section_hierarchy=_hierarchy(u.path, _container(u.unit_id, by_id)), bbox=bbox,
            is_table=is_table, node_id=u.unit_id,
        ))
    return clauses
