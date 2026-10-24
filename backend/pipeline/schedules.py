"""
The rate schedules of a document, read and checked.

Finds every income-tax style rate table in a PDF, reads each row into a band
(lower, upper, rate) with the rule baseline's deterministic row reader, and
runs the assembler's structural checks on the result: a schedule must start
at zero, its bands must meet without gaps or overlaps, its last band must be
open, and its rates must not fall. A table that fails is a review item, with
the reason.

Two kinds of table are read:
  boxed       one row per line with cells separated by " | " (the layout
              reader joins a table row's cells that way)
  two-column  numbered "(1) where the total income … | rate" schedules,
              rebuilt from the PDF geometry (pipeline.statute.tables)

Every band comes from the words of its own row, so its numbers are in the
document by construction; the row text is returned with it.
"""
import re
from typing import Optional

from models.rules import SlabRow
from pipeline.extraction.rule_based import _slab_from_line
from pipeline.statute.tables import _RATE_RE, Row, Table, boxed_tables, pdf_tables
from simulation.translate.assemble import build_schedule

_AY = re.compile(r"assessment\s+year\s+beginning\s+on\s+(?:or\s+after\s+)?the\s+1st\s+(?:day\s+of\s+)?April,?\s+(\d{4})"
                 r"|tax\s+year\s+(?:beginning\s+on\s+(?:or\s+after\s+)?the\s+1st\s+(?:day\s+of\s+)?April,?\s+)?(\d{4})", re.I)


_GENERIC = re.compile(r"^\s*(?:table|rates?\s+of\s+(?:income-)?tax|sl\.?\s*no\.?|\(\d\)|[A-C])\s*[.:—-]*\s*$", re.I)


_OPENS = re.compile(r"^(?:\((?:I{1,3}|IV|V|VI|i{1,3}|iv|v|vi|[a-z])\)\s|In the case of\b|Paragraph [A-Z]\b|\d+[A-Z]*\.\s)")


def _read(rows: list[Row]) -> list[dict]:
    out = []
    for r in rows:
        f = _slab_from_line(r.text)
        out.append({"label": r.label, "text": r.text, **({"lower": f["lower"], "upper": f["upper"], "rate": f["rate"]}
                                                       if f else {"lower": None, "upper": None, "rate": None})})
    return out


def _check(read: list[dict]) -> dict:
    bands = [SlabRow(lower=r["lower"], upper=r["upper"], rate=r["rate"]) for r in read if r["rate"] is not None]
    unread = [r["label"] or r["text"][:30] for r in read if r["rate"] is None]
    slabs, why = build_schedule(bands)
    if unread:
        return {"ok": False, "reason": f"rows that could not be read: {', '.join(unread)}"}
    return {"ok": slabs is not None, "reason": why}


def _context(lines: list[tuple[int, str]], idx: int) -> tuple[str, Optional[str]]:
    """The clause that introduces a table ("(I) In the case of every
    individual …", "(ii) for any previous year relevant to …") and the
    assessment year named before it."""
    before = [t.strip() for _, t in lines[max(0, idx - 12):idx] if "|" not in t and not _GENERIC.match(t)]
    start = next((k for k in range(len(before) - 1, -1, -1) if _OPENS.match(before[k])), None)
    heading = " ".join(before[start:]) if start is not None else (before[-1] if before else "")
    if len(heading) > 170:
        heading = heading[:167].rsplit(" ", 1)[0] + " …"
    ay = None
    for m in _AY.finditer(" ".join(before[-8:])):
        y = int(m.group(1) or m.group(2))
        ay = f"{y}-{(y + 1) % 100:02d}"
    return heading, ay


def find_schedules(pdf_path: str, ocr_pages: Optional[dict] = None) -> list[dict]:
    """`ocr_pages`: the recognised lines of a document's scanned pages, as the
    analysis stored them ({page: {"width", "height", "lines"}}): their
    two-column schedules are read from those lines."""
    from pipeline.statute.layout import read_lines
    from pipeline.statute.tables import _ocr_label, tables_from_lines

    lines_raw, _pages, _ = read_lines(pdf_path)
    body = [(ln.page + 1, ln.text) for ln in lines_raw if ln.kind == "body"]
    if ocr_pages:
        # a scanned page has no text layer: its recognised lines, top to bottom
        for pno, p in ocr_pages.items():
            body += [(pno, _ocr_label(ln[4])) for ln in sorted(p["lines"], key=lambda ln: (round(ln[1] / 4), ln[0]))]
        body.sort(key=lambda x: x[0])          # stable: each page keeps its order
    text = "\n".join(t for _, t in body)
    starts, pos = [], 0
    for _, t in body:
        starts.append(pos)
        pos += len(t) + 1

    def line_at(offset: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    found: list[tuple[int, Table, int]] = []        # (page, table, line index)
    for t in boxed_tables(text, []):
        i = line_at(t.rows[0].start)
        found.append((body[i][0], t, i))
    used: set[int] = set()
    for t in pdf_tables(pdf_path) + (tables_from_lines(ocr_pages) if ocr_pages else []):
        # place a rebuilt schedule by its first row's label and opening words;
        # several schedules on a page share them, so each takes the next
        # occurrence not yet taken
        head = (t.rows[0].label + " " + t.rows[0].cells[0])[:22]
        i = next((k for k, (pg, s) in enumerate(body) if pg == t.page + 1 and k not in used and s.startswith(head)), None)
        if i is None:
            i = next((k for k, (pg, _s) in enumerate(body) if pg == t.page + 1 and k not in used), 0)
        used.add(i)
        found.append((t.page + 1, t, i))

    out = []
    for page, t, i in sorted(found, key=lambda x: (x[0], x[2])):
        if not all(_RATE_RE.search(r.cells[-1]) for r in t.rows):
            continue
        read = _read(t.rows)
        if sum(1 for r in read if r["rate"] is not None) < 2:
            continue
        heading, ay = _context(body, i)
        out.append({"page": page, "kind": t.kind, "heading": heading, "assessment_year": ay,
                    "rows": read, "check": _check(read)})
    return out
