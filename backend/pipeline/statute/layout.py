"""
Layout layer of the statute parser: PDF → classified lines.

Every text line on every page is read with its geometry and font, segments
that sit on the same baseline are merged into one row, and each row is
classified as one of:

    body           statute text
    header/footer  running heads, gazette banners, page numbers
    margin_number  the line numbers printed in a Bill's margin (5, 10, 15 …)
    marginal_note  section headings / citations printed in the side margin
    footnote       small-print notes in the text column (consolidated Acts)

Classification is learnt per document (body font size, text column, which
top/bottom strings repeat across pages), so the same code handles Lok Sabha
Bills, Gazette Acts, CBIC consolidations and India Code PDFs.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median

import fitz  # PyMuPDF

# A segment that is only a structural label: "(43)", "(a)", "(iv)", "2.", "1A."
LABEL_ONLY_RE = re.compile(r"^\s*[‘“'\"]?(?:\(\s*[0-9A-Za-z]{1,6}\s*\)|\d+[A-Z]{0,5}\.)\s*$")
_DIGITS_RE = re.compile(r"\d+")
_PAGE_NO_RE = re.compile(r"^\s*(?:page\s*)?[\(\[]?[ivxlcdm\d]{1,4}[\)\]]?\s*(?:of\s*\d+)?\s*$", re.I)
_MARGIN_NO_RE = re.compile(r"^\s*\d{1,3}\s*$")
_AMENDMENT_NOTE_RE = re.compile(
    r"^\s*(?:\d{1,3}\s*)?(?:Inserted|Substituted|Omitted|Added|Renumbered|Re-numbered|Ins\.|Subs\.)\b"
    r"|^\s*\d{1,3}\s*(?:Words?|The\s+words|Clause|Sub-section|Section|Proviso|Explanation)\b")

# Glyphs that some Government PDFs emit through broken font encodings.
_GLYPH_FIXES = {
    "―": "“", "‖": "”",          # CBIC consolidations
    "­": "",                 # soft hyphen
    "ﬁ": "fi", "ﬂ": "fl",
}


def normalise(text: str) -> str:
    for bad, good in _GLYPH_FIXES.items():
        text = text.replace(bad, good)
    # A backtick before an amount is a mis-decoded rupee sign.
    text = re.sub(r"`\s*(?=\d)", "₹", text)
    text = text.replace("\t", " ")
    return re.sub(r"[  ]{2,}", " ", text).strip()


@dataclass
class Line:
    page: int          # 0-based page index
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    text: str
    is_table_row: bool = False
    cells: list[str] = field(default_factory=list)
    kind: str = "body"

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class PageInfo:
    width: float
    height: float


def _raw_segments(page: "fitz.Page", pno: int) -> list[Line]:
    segs: list[Line] = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for ln in block.get("lines", []):
            spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            # Footnote reference markers are tiny digit-only spans set inside a
            # body line ("… returns 69 Inserted …"); drop them from the text.
            big = max(sp["size"] for sp in spans)
            kept = [sp for sp in ln["spans"]
                    if not (sp["size"] < 0.75 * big and re.fullmatch(r"\s*\d{1,3}\s*", sp["text"]))]
            text = normalise("".join(sp["text"] for sp in kept))
            if not text:
                continue
            chars = sum(len(s["text"]) for s in spans) or 1
            size = sum(s["size"] * len(s["text"]) for s in spans) / chars
            # A line is "bold" when it *starts* bold: statutes set only the
            # section number in bold ("52. In section 115BAB …").
            first = spans[0]
            bold = "Bold" in first.get("font", "") or bool(first.get("flags", 0) & 16)
            x0, y0, x1, y1 = ln["bbox"]
            segs.append(Line(page=pno, x0=x0, y0=y0, x1=x1, y1=y1, size=round(size, 1),
                             bold=bold, text=text))
    return segs


def _merge_rows(segs: list[Line]) -> list[Line]:
    """Merge segments sharing a baseline and font size into one row. A label
    followed by its text ("(43)" + "“electronic cash ledger” means…") is
    joined with a space; widely separated segments are table cells."""
    segs = sorted(segs, key=lambda s: (round(s.yc), s.x0))
    rows: list[list[Line]] = []
    for s in segs:
        placed = False
        for row in reversed(rows[-6:]):
            ref = row[0]
            if abs(ref.yc - s.yc) <= 0.45 * max(ref.size, s.size) and abs(ref.size - s.size) <= 1.0:
                row.append(s)
                placed = True
                break
        if not placed:
            rows.append([s])

    merged: list[Line] = []
    for row in rows:
        row.sort(key=lambda s: s.x0)
        if len(row) == 1:
            merged.append(row[0])
            continue
        parts = [row[0].text]
        cells = [row[0].text]
        is_table = False
        for prev, cur in zip(row, row[1:]):
            gap = cur.x0 - prev.x1
            label_then_text = (LABEL_ONLY_RE.match(prev.text) and not LABEL_ONLY_RE.match(cur.text)
                               and gap <= 6 * cur.size)
            if gap <= 2.2 * cur.size or label_then_text:
                parts.append(" " + cur.text)
                cells[-1] = cells[-1] + " " + cur.text
            else:
                is_table = True
                parts.append(" | " + cur.text)
                cells.append(cur.text)
        first = row[0]
        merged.append(Line(
            page=first.page, x0=first.x0, y0=min(s.y0 for s in row), x1=max(s.x1 for s in row),
            y1=max(s.y1 for s in row), size=first.size, bold=first.bold,
            text=normalise("".join(parts)), is_table_row=is_table,
            cells=cells if is_table else [],
        ))
    return merged


_ROW_ANCHOR_RE = re.compile(r"^\s*(?:\(\s*[0-9]{1,3}[A-Z]?\s*\)|\([a-z]{1,3}\)|\d{1,3}\.)\s")


def _two_column_rows(segs: list[Line], page_width: float) -> list[Line]:
    """Rebuild two-column rate tables (Finance Act schedules): a left column
    of conditions "(1) where the total income exceeds / Rs. 2,50,000 …" and a
    right column of rates, each wrapping independently. Each left-column item
    opens a row that takes every line of both columns down to the next item;
    the row becomes one table line "condition | rate"."""
    if len(segs) < 6:
        return segs
    starts = Counter(round(s.x0) for s in segs if 0.42 * page_width < s.x0 < 0.75 * page_width)
    if not starts:
        return segs
    xr, count = starts.most_common(1)[0]
    if count < 3:
        return segs
    right = [s for s in segs if abs(s.x0 - xr) <= 3]
    left = [s for s in segs if s.x1 < xr - 2]
    anchors = sorted((s for s in left if _ROW_ANCHOR_RE.match(s.text)), key=lambda s: s.y0)
    if len(anchors) < 2:
        return segs
    # A row band runs from one anchor to the next; only anchors that sit
    # beside right-column text start rows.
    rows_out: list[Line] = []
    used: set[int] = set()
    line_gap = max(min((b.y0 - a.y0 for a, b in zip(anchors, anchors[1:]) if b.y0 > a.y0), default=12.0), 8.0)
    full_width = [s for s in segs if s.x0 < xr - 2 and s.x1 > xr + 20]
    for i, a in enumerate(anchors):
        # A rate often starts a few points above its condition's first line.
        tol = 0.8 * a.size
        top = a.y0 - tol
        bottom = anchors[i + 1].y0 - tol if i + 1 < len(anchors) else a.y0 + 3 * line_gap
        # A full-width line (the next paragraph) ends the row.
        stops = [s.y0 for s in full_width if a.y0 < s.y0 < bottom]
        if stops:
            bottom = min(stops) - 0.5
        r_in = [s for s in right if top <= s.y0 < bottom and id(s) not in used]
        if not r_in:
            continue
        # Left-column continuation lines are printed near the item's indent;
        # a line far to its left belongs to the surrounding paragraph.
        l_in = [s for s in left if top <= s.y0 < bottom and id(s) not in used
                and s.x0 >= a.x0 - 30
                and (s is a or not _ROW_ANCHOR_RE.match(s.text))]
        if i + 1 == len(anchors):
            # Last row: stop at the first vertical gap in the right column.
            r_in.sort(key=lambda s: s.y0)
            kept = [r_in[0]]
            for s in r_in[1:]:
                if s.y0 - kept[-1].y1 > 1.2 * s.size:
                    break
                kept.append(s)
            r_in = kept
            limit = r_in[-1].y1 + 2
            l_in = [s for s in l_in if s.y0 <= limit]
        l_in.sort(key=lambda s: s.y0)
        r_in.sort(key=lambda s: s.y0)
        for s in l_in + r_in:
            used.add(id(s))
        left_text = " ".join(s.text for s in l_in)
        right_text = " ".join(s.text for s in r_in)
        rows_out.append(Line(
            page=a.page, x0=a.x0, y0=min(s.y0 for s in l_in + r_in), x1=max(s.x1 for s in l_in + r_in),
            y1=max(s.y1 for s in l_in + r_in), size=a.size, bold=a.bold,
            text=normalise(f"{left_text} | {right_text}"), is_table_row=True, cells=[left_text, right_text],
            kind="two_col_row",
        ))
    if not rows_out:
        return segs
    return [s for s in segs if id(s) not in used] + rows_out


def _body_size(lines: list[Line]) -> float:
    weight: Counter = Counter()
    for ln in lines:
        weight[round(ln.size * 2) / 2] += len(ln.text)
    return weight.most_common(1)[0][0] if weight else 10.0


def _repeat_key(text: str) -> str:
    return _DIGITS_RE.sub("#", re.sub(r"\s+", " ", text.lower())).strip()


def classify(lines: list[Line], pages: list[PageInfo], col_left: float, col_right: float) -> dict:
    """Assign `kind` to every line in place; returns document statistics."""
    body = _body_size(lines)
    small = body - 0.9

    # Strings in the top / bottom band that recur on many pages are running
    # heads (gazette banners, "Page n"); a band string that also appears in
    # the same band of an adjacent page is a running title (e.g. "CHAPTER I
    # PRELIMINARY" printed atop every page of that chapter).
    n_pages = max(len(pages), 1)
    band_counts: Counter = Counter()
    band_pages: dict[str, set[int]] = {}
    for ln in lines:
        h = pages[ln.page].height
        if ln.y0 < 0.11 * h or ln.y1 > 0.92 * h:
            key = _repeat_key(ln.text)
            band_counts[key] += 1
            band_pages.setdefault(key, set()).add(ln.page)
    repeat_min = max(3, int(0.08 * n_pages))

    def _adjacent_repeat(key: str, page: int) -> bool:
        seen = band_pages.get(key, set())
        return (page - 1) in seen or (page + 1) in seen

    last_note: Line | None = None
    for ln in lines:
        h = pages[ln.page].height
        in_band = ln.y0 < 0.11 * h or ln.y1 > 0.92 * h
        key = _repeat_key(ln.text)
        if ln.kind == "footnote":
            last_note = ln
        if in_band and (band_counts[key] >= repeat_min or _PAGE_NO_RE.match(ln.text)
                        or _adjacent_repeat(key, ln.page)):
            ln.kind = "header" if ln.y0 < 0.5 * h else "footer"
        elif _MARGIN_NO_RE.match(ln.text) and (ln.size < small or ln.kind == "margin_pending"):
            ln.kind = "margin_number"
        elif ln.kind == "margin_pending" or (ln.size < small and (ln.x1 <= col_left + 4 or ln.x0 >= col_right - 4)):
            ln.kind = "marginal_note"
        elif (ln.size < small and ln.y0 > 0.65 * h
              and re.match(r"^\s*(?:\d{1,3}\s*\.|\d{1,3}\s+[A-Z]|\*|†|\[)", ln.text)):
            ln.kind = "footnote"
        elif ln.size < small and (_AMENDMENT_NOTE_RE.match(ln.text) or (
                last_note is not None and last_note.page == ln.page
                and abs(last_note.size - ln.size) < 0.6 and 0 <= ln.y0 - last_note.y1 < 2 * ln.size)):
            # Consolidations print amendment notes in very small type, often
            # mid-page beside the provision they annotate; a note's wrapped
            # continuation lines follow it directly in the same small size.
            ln.kind = "footnote"
        else:
            ln.kind = "body"
        if ln.kind == "footnote":
            last_note = ln
    return {
        "body_size": body,
        "col_left": round(col_left, 1),
        "col_right": round(col_right, 1),
        "kinds": dict(Counter(ln.kind for ln in lines)),
    }


def _text_column(segs: list[Line], pages: list[PageInfo]) -> tuple[float, float]:
    """Left and right edge of the main text column, from body-size segments
    that start in the left part of the page (so side-margin notes, which
    start beyond the column, do not widen it)."""
    body = _body_size(segs)
    cand = [s for s in segs if abs(s.size - body) <= 1.0
            and s.x0 < 0.45 * pages[s.page].width and s.x1 - s.x0 > 0.35 * pages[s.page].width]
    if not cand:
        cand = segs
    xs0 = sorted(s.x0 for s in cand)
    xs1 = sorted(s.x1 for s in cand)
    return xs0[int(0.02 * (len(xs0) - 1))], xs1[int(0.98 * (len(xs1) - 1))]


def read_lines(pdf_path: str) -> tuple[list[Line], list[PageInfo], dict]:
    """All rows of the document in reading order, classified."""
    pages: list[PageInfo] = []
    raw: list[list[Line]] = []
    with fitz.open(pdf_path) as doc:
        for pno, page in enumerate(doc):
            pages.append(PageInfo(width=page.rect.width, height=page.rect.height))
            raw.append(_raw_segments(page, pno))
    col_left, col_right = _text_column([s for page in raw for s in page], pages)

    body_size = _body_size([s for page in raw for s in page])
    lines: list[Line] = []
    for segs in raw:
        # Side-margin segments (marginal notes, Bill line numbers) are set
        # aside before row merging so they never fuse with the text beside them.
        # Small print is judged against this page's own text extent (schedule
        # pages run wider than the body column).
        body_segs = [s for s in segs if abs(s.size - body_size) <= 1.0 and len(s.text) > 8]
        page_left = min((s.x0 for s in body_segs), default=col_left)
        page_right = max((s.x1 for s in body_segs), default=col_right)
        inside, margin = [], []
        for s in segs:
            small = s.size < body_size - 0.9
            if (s.x0 >= col_right - 3 or s.x1 <= col_left + 3
                    or (small and (s.x0 >= page_right - 2 or s.x1 <= page_left + 2))):
                margin.append(s)
            else:
                inside.append(s)
        for s in margin:
            s.kind = "margin_pending"
        page_width = pages[segs[0].page].width if segs else 595.0
        inside = _two_column_rows(inside, page_width)
        built = [s for s in inside if s.kind == "two_col_row"]
        rows = _merge_rows([s for s in inside if s.kind != "two_col_row"]) + built + margin
        rows.sort(key=lambda r: (r.y0, r.x0))
        lines.extend(rows)
    stats = classify(lines, pages, col_left, col_right)
    return lines, pages, stats
