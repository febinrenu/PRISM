"""
Rate tables rebuilt cell by cell: a derived view of the corpus.

The canonical text (text.txt) is frozen: evaluation sets point into it by
offset. Some of its tables were linearised badly. In a two-column schedule
("(2) where the total income exceeds … | 5 per cent. of the amount by which
…") each column wraps on its own, and when the rate column's first line is
indented, or a justified line is printed word by word, the parser read the
two columns line by line and interleaved them:

    (2) where the total income exceeds Rs. 2,50,000 but does not exceed Rs. 5,00,000 | income exceeds Rs. 2,50,000;
    5 per cent. of the amount by which the total

This module rebuilds those tables from the PDF geometry instead: it finds
runs of numbered rows "(1) (2) (3) …", locates the empty vertical gutter
between the condition column and the rate column, and gives each row
everything printed in its band on either side of the gutter. Boxed tables
("Sl. No. | Total income | Rate of tax"), which the canonical text already
holds one row per line, are read from the text.

Every rebuilt row keeps the offsets of the canonical text it covers, so
anything quoted from a rebuilt row is still cited to the frozen text. The
result is written to data/corpus/<statute>/<version>/tables.json with the
hashes of the PDF and text it was built from; a view built from other text
is never used.
"""
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pipeline.statute.corpus import CORPUS_DIR

BUILDER_VERSION = 1

# "(2) where the total income …", or "(2)" printed as a piece of its own
# when a justified line is set word by word
_ANCHOR_RE = re.compile(r"^\s*\((\d{1,2})\)(?:\s|$)")
_RATE_RE = re.compile(r"\bnil\b|per\s*cent|%", re.I)
_DIGITS_RE = re.compile(r"\d[\d,]*")
_MATCH_MIN = 0.9          # share of a rebuilt row's numbers found in its canonical row


@dataclass
class Row:
    label: str                       # "(2)", "3."
    cells: list[str]                 # condition, rate (two-column) or income, rate (boxed)
    start: int = -1                  # offsets into the canonical text
    end: int = -1
    exact: bool = True               # the span holds exactly the row's characters, reordered

    @property
    def text(self) -> str:
        return (f"{self.label} " if self.label else "") + " | ".join(self.cells)


@dataclass
class Table:
    kind: str                        # two_column | boxed
    origin: str                      # pdf | text
    page: Optional[int]              # 0-based page of a PDF table
    rows: list[Row] = field(default_factory=list)
    match: float = 1.0               # share of row numbers found in the canonical rows

    @property
    def start(self) -> int:
        return min(r.start for r in self.rows)

    @property
    def end(self) -> int:
        return max(r.end for r in self.rows)


# ── two-column schedules, from the PDF ──────────────────────────────────────

def _gutter(segs: list, lo: float, hi: float) -> Optional[float]:
    """Middle of the widest x-interval in [lo, hi] that no segment crosses,
    with text on both sides; None if there is none at least 3pt wide."""
    spans = sorted((s.x0, s.x1) for s in segs)
    best, best_w = None, 3.0
    reach = spans[0][1] if spans else 0.0
    for x0, x1 in spans[1:]:
        if x0 > reach:
            a, b = max(reach, lo), min(x0, hi)
            if b - a > best_w:
                best, best_w = (a + b) / 2, b - a
        reach = max(reach, x1)
    return best


def _join(segs: list) -> str:
    from pipeline.statute.layout import normalise
    segs = sorted(segs, key=lambda s: (round(s.yc), s.x0))
    return normalise(" ".join(s.text for s in segs))


@dataclass
class _Fragment:
    """The rows of one numbered run on one page. A table that crosses a page
    break is two fragments: the last run of one page (ending at its foot)
    and the first run of the next (numbering continues)."""
    page: int
    first: int                       # number of the first row
    rows: list[Row]
    first_on_page: bool
    last_on_page: bool
    at_foot: bool                    # nothing printed below it
    lead: tuple[str, str] = ("", "")  # lines above the first row (a row carried over)


def _label_no(seg) -> int:
    return int(_ANCHOR_RE.match(seg.text).group(1))


def _page_fragments(segs: list, width: float, pno: int) -> list[_Fragment]:
    if not segs:
        return []
    size = sorted(s.size for s in segs)[len(segs) // 2]
    tol = 0.6 * size
    anchors = sorted((s for s in segs if _ANCHOR_RE.match(s.text) and s.x0 < 0.45 * width), key=lambda s: s.y0)
    # Runs of rows numbered n, n+1, n+2 … with no long vertical break. A run
    # starts at (1), or at any number when it opens the page (a table
    # continued from the previous page).
    runs: list[list] = []
    for a in anchors:
        n = _label_no(a)
        if runs and n == _label_no(runs[-1][-1]) + 1 and a.y0 - runs[-1][-1].y0 < 8 * size:
            runs[-1].append(a)
        elif n == 1 or not runs:
            runs.append([a])
    out = []
    for ri, run in enumerate(runs):
        built = _run_rows(run, segs, width, size, [_ANCHOR_RE.match(a.text).group(0).strip() for a in run])
        if built is None:
            continue
        rows, gx, top, bottom = built
        # Lines between the last line crossing the gutter above the run (the
        # running head) and the run: the end of a row begun on the previous page.
        above = [s for s in segs if s.y1 <= top + 0.5]
        cut = max((s.y1 for s in above if s.x0 < gx < s.x1), default=-1.0)
        lead = [s for s in above if s.y0 >= cut and not (s.x0 < gx < s.x1)]
        out.append(_Fragment(
            page=pno, first=_label_no(run[0]), rows=rows,
            first_on_page=ri == 0, last_on_page=ri == len(runs) - 1,
            at_foot=not any(s.y0 > bottom + 0.5 for s in segs),
            lead=(_join([s for s in lead if s.x1 <= gx]), _join([s for s in lead if s.x0 >= gx])),
        ))
    return out


def _run_rows(run: list, segs: list, width: float, size: float, labels: list[str]):
    """The rows of one run of row anchors: (rows, gutter, top, bottom), or
    None if the run is not a two-column table."""
    tol = 0.6 * size
    top = run[0].y0 - tol
    probe = [s for s in segs if top <= s.y0 <= run[-1].y1 + tol]
    gx = _gutter(probe, 0.3 * width, 0.75 * width)
    if gx is None:
        return None
    # The run goes down to the last line before a line that crosses the
    # gutter (the next paragraph) or a vertical break.
    below = sorted((s for s in segs if s.y0 > run[-1].y0 - tol), key=lambda s: s.y0)
    bottom = run[-1].y1
    for s in below:
        if s.y0 > bottom + 1.2 * size or s.x0 < gx < s.x1:
            break
        bottom = max(bottom, s.y1)
    region = [s for s in segs if top <= s.y0 and s.y1 <= bottom + 0.5 and not (s.x0 < gx < s.x1)]
    rows = []
    for i, (a, label) in enumerate(zip(run, labels)):
        lo = a.y0 - tol
        hi = run[i + 1].y0 - tol if i + 1 < len(run) else bottom + 1
        band = [s for s in region if lo <= s.y0 < hi]
        left = [s for s in band if s.x1 <= gx]
        right = [s for s in band if s.x0 >= gx]
        if not left or not right:
            return None
        cond = _join(left)
        if label and cond.startswith(label):
            cond = cond[len(label):].strip()
        rows.append(Row(label=label, cells=[cond, _join(right)]))
    return rows, gx, top, bottom


# v2 only: a schedule printed without row labels, each row opening with the
# words of its condition ("where the total income exceeds …"; FA 2024 (No. 2)
# Part III item (III)). Not used for the frozen view (tables.json).
_UNLABELLED_RE = re.compile(r"^\s*where\s+the\s+total\s+income\b", re.I)


def _unlabelled_tables(segs: list, width: float, pno: int) -> list[Table]:
    if not segs:
        return []
    size = sorted(s.size for s in segs)[len(segs) // 2]
    labelled_y = [s.y0 for s in segs if _ANCHOR_RE.match(s.text)]
    anchors = sorted((s for s in segs if _UNLABELLED_RE.match(s.text) and s.x0 < 0.45 * width
                      and not any(abs(s.y0 - y) < 0.5 * size for y in labelled_y)), key=lambda s: s.y0)
    runs: list[list] = []
    for a in anchors:
        if runs and a.y0 - runs[-1][-1].y0 < 8 * size:
            runs[-1].append(a)
        else:
            runs.append([a])
    out = []
    for run in runs:
        if len(run) < 2:
            continue
        built = _run_rows(run, segs, width, size, [""] * len(run))
        if built is not None and _is_rate_table(built[0]):
            out.append(Table(kind="two_column", origin="pdf", page=pno, rows=built[0]))
    return out


def _is_rate_table(rows: list[Row]) -> bool:
    return len(rows) >= 2 and sum(bool(_RATE_RE.search(r.cells[1])) for r in rows) >= 0.6 * len(rows)


def pdf_tables(pdf_path: str, unlabelled: bool = False) -> list[Table]:
    """Two-column rate tables of a PDF. `unlabelled` (view v2) also reads
    schedules printed without "(1) (2) …" row labels."""
    import fitz

    from pipeline.statute.layout import _raw_segments
    frags: list[_Fragment] = []
    extra: list[Table] = []
    with fitz.open(pdf_path) as doc:
        for pno, page in enumerate(doc):
            segs = _raw_segments(page, pno)
            frags += _page_fragments(segs, page.rect.width, pno)
            if unlabelled:
                extra += _unlabelled_tables(segs, page.rect.width, pno)
    out = _stitch(frags)
    return sorted(out + extra, key=lambda t: t.page) if extra else out


def _stitch(frags: list[_Fragment]) -> list[Table]:
    """Whole tables from per-page fragments: a run that ends at the foot of a
    page continues with the next page's opening run when the numbering
    carries on."""
    out = []
    i = 0
    while i < len(frags):
        f = frags[i]
        if f.first != 1:
            i += 1
            continue
        rows = list(f.rows)
        j = i
        while (frags[j].last_on_page and frags[j].at_foot and j + 1 < len(frags)
               and frags[j + 1].page == frags[j].page + 1 and frags[j + 1].first_on_page
               and frags[j + 1].first == int(rows[-1].label.strip("()")) + 1):
            nxt = frags[j + 1]
            left, right = nxt.lead
            if left or right:
                last = rows[-1]
                rows[-1] = Row(label=last.label, cells=[" ".join(x for x in (last.cells[0], left) if x),
                                                        " ".join(x for x in (last.cells[1], right) if x)])
            rows += nxt.rows
            j += 1
        if _is_rate_table(rows):
            out.append(Table(kind="two_column", origin="pdf", page=f.page, rows=rows))
        i = j + 1
    return out


# OCR reads a row label's "1" as a letter ("(l)", "(I)") and drops the space
# after a label; and it joins the two columns of a row when they share a
# baseline, leaving a double space at the join.
_OCR_ONE = re.compile(r"^\(\s*[lI|!]\s*\)\s*")
_LABEL_GLUED = re.compile(r"^(\(\d{1,2}\))(?=\S)")
_COLUMN_JOIN = re.compile(r"\s{2,}")
_CELL_END = re.compile(r"(?:Rs\.?|₹)\s*[\d,]+$")


def _ocr_label(text: str) -> str:
    text = _OCR_ONE.sub("(1) ", text)
    return _LABEL_GLUED.sub(r"\1 ", text)


def _ocr_parts(x0: float, x1: float, text: str, column_x: Optional[float] = None) -> list[tuple[float, float, str]]:
    """Split a recognised line at a double space. Each part is placed by its
    share of the line's characters; when the page's right column is known
    (`column_x`, where its lines start), a two-part line is split there, since
    characters are not all of one width."""
    parts = [m for m in re.finditer(r"\S+(?:\s\S+)*", text)]
    if len(parts) < 2 or not _COLUMN_JOIN.search(text):
        if column_x is not None and x0 < column_x - 20 and x1 > column_x + 20:
            # joined with a single space: split near where the column's edge
            # falls in the line, and only after an amount, as a condition cell
            # ends ("... does not exceed Rs. 5,00,000"); a line of prose that
            # spans the page is left whole
            at = (column_x - x0) / max(1e-6, x1 - x0) * len(text)
            spaces = [i for i, ch in enumerate(text) if ch == " " and abs(i - at) <= 8
                      and _CELL_END.search(text[:i])]
            if spaces:
                k = min(spaces, key=lambda i: abs(i - at))
                left, right = text[:k].strip(), text[k + 1:].strip()
                if left and right:
                    return [(x0, column_x - 5.0, left), (column_x, x1, right)]
        return [(x0, x1, text.strip())]
    width = (x1 - x0) / max(1, len(text))
    out = [(x0 + m.start() * width, x0 + m.end() * width, m.group(0)) for m in parts]
    if column_x is not None and len(out) == 2 and x0 < column_x < x1:
        out = [(x0, column_x - 5.0, out[0][2]), (column_x, x1, out[1][2])]   # leave the gutter open
    return out


def _right_column_x(lines: list, width: float) -> Optional[float]:
    """Where a page's right column starts: the smallest left edge that at
    least two lines starting right of the page's centre share (a rate's first line is
    often indented; its wrapped lines start at the column's edge)."""
    from collections import Counter
    starts = Counter(round(x0) for x0, _y0, _x1, _y1, text, _c in lines
                     # right of the page's centre: a centred title starts left of it
                     if 0.5 * width < x0 < 0.75 * width and not _COLUMN_JOIN.search(text.strip()))
    shared = [x for x, n in starts.items() if n >= 2]
    return float(min(shared)) if shared else None


def tables_from_lines(pages: dict) -> list[Table]:
    """Two-column rate tables of OCR'd pages: {page number (1-based):
    {"width", "lines": [[x0, y0, x1, y1, text, conf]]}}. Each recognised line
    stands in for a text segment (no font information: not bold, its size
    taken from its height)."""
    from pipeline.statute.layout import Line
    frags: list[_Fragment] = []
    for pno in sorted(pages):
        p = pages[pno]
        col = _right_column_x(p["lines"], p["width"])
        segs = [Line(page=pno - 1, x0=a, y0=y0, x1=b, y1=y1, size=round(0.8 * max(1.0, y1 - y0), 1),
                     bold=False, text=part)
                for x0, y0, x1, y1, text, _conf in p["lines"]
                for a, b, part in _ocr_parts(x0, x1, _ocr_label(text), col)]
        frags += _page_fragments(segs, p["width"], pno - 1)
    return [Table(kind=t.kind, origin="ocr", page=t.page, rows=t.rows) for t in _stitch(frags)]


def _numbers(s: str) -> list[str]:
    return [d.replace(",", "") for d in _DIGITS_RE.findall(s)]


def _place(table: Table, text: str, cursor: int) -> Optional[int]:
    """Give each row the canonical offsets of its row: from its label to the
    next row's label. Returns where the table ends, or None if the rows'
    numbers are not found there (another table, or a different reading)."""
    def key(r: Row) -> str:
        # a row is found by its label, or (unlabelled rows) its opening words
        return r.label + " " if r.label else " ".join(r.cells[0].split()[:4])

    for start in [m.start() for m in re.finditer(re.escape(key(table.rows[0])), text[cursor:])]:
        pos = cursor + start
        starts = [pos]
        ok = True
        for prev, r in zip(table.rows, table.rows[1:]):
            j = text.find(key(r), starts[-1] + 1)
            # a row's text in the canonical file is about as long as the row
            if j < 0 or j - starts[-1] > 2 * len(prev.text) + 80:
                ok = False
                break
            starts.append(j)
        if not ok:
            continue
        ends = starts[1:] + [None]
        found = total = 0
        spans = []
        for r, s, e in zip(table.rows, starts, ends):
            limit = e if e is not None else min(len(text), s + 3 * len(r.text) + 40)
            seg = text[s:limit]
            if e is None:
                # The last row ends with the line holding the last of its
                # numbers: each number is matched to its earliest unused
                # occurrence near the label, never to a later paragraph.
                occ = [(m.group(0).replace(",", ""), s + m.end()) for m in _DIGITS_RE.finditer(seg)]
                last = s
                for num in _numbers(" ".join(r.cells)):
                    k = next((i for i, (v, _) in enumerate(occ) if v == num), None)
                    if k is not None:
                        last = max(last, occ.pop(k)[1])
                eol = text.find("\n", last)
                limit = eol if 0 <= eol < limit else limit
                seg = text[s:limit]
            want = _numbers(" ".join(r.cells))
            have = _numbers(seg)
            for num in want:
                total += 1
                if num in have:
                    have.remove(num)
                    found += 1
            spans.append((s, len(text[s:limit].rstrip()) + s))
        score = found / max(total, 1)
        if score >= _MATCH_MIN:
            for r, (s, e) in zip(table.rows, spans):
                r.start, r.end, r.exact = _fit(r, text, s, e)
            table.match = round(score, 4)
            return max(r.end for r in table.rows)
    return None


def _chars(s: str) -> Counter:
    return Counter(c for c in s if not c.isspace() and c != "|")


def _fit(row: Row, text: str, s: int, e: int) -> tuple[int, int, bool]:
    """Fit a row's canonical span to the row: drop trailing characters the
    row does not have (the next paragraph run onto the same line), and
    extend over characters the row has but its span lacks (a cell the
    linearisation carried into the next row). `exact` says whether the span
    is then exactly the row's characters in another order."""
    want = _chars(row.label + "".join(row.cells))
    have = _chars(text[s:e])
    while e > s and (text[e - 1].isspace() or text[e - 1] == "|" or have[text[e - 1]] > want[text[e - 1]]):
        if not (text[e - 1].isspace() or text[e - 1] == "|"):
            have[text[e - 1]] -= 1
        e -= 1
    if want - have:
        limit = min(len(text), e + 2 * len(row.text))
        k = e
        need = want - have
        while k < limit and need:
            c = text[k]
            if need[c] > 0:
                need[c] -= 1
                if need[c] == 0:
                    del need[c]
            k += 1
        if not need:
            e = k
            have = _chars(text[s:e])
    return s, e, have == want


# ── boxed tables, from the canonical text ───────────────────────────────────

_HEADER_CELL = re.compile(r"^\s*(?:\(?\d{1,2}\)?|[A-Z]|sl\.?\s*no\.?|s\.?\s*no\.?|total income|rate of (?:income-)?tax)\s*$", re.I)
_SERIAL = re.compile(r"^\s*(\d{1,2}\.)\s*")


def boxed_tables(text: str, skip: list[tuple[int, int]]) -> list[Table]:
    """Tables introduced by a "TABLE" line or an "Sl. No." header, one row
    per line with " | " between cells."""
    out: list[Table] = []
    lines = []
    pos = 0
    for ln in text.split("\n"):
        lines.append((pos, ln))
        pos += len(ln) + 1
    i = 0
    while i < len(lines):
        s, ln = lines[i]
        opener = re.fullmatch(r"\s*table\s*[.:]?\s*", ln, re.I) or re.match(r"\s*sl\.?\s*no\.?\s*\|", ln, re.I) \
            or re.search(r"\bTABLE\s*$", ln)
        if not opener:
            i += 1
            continue
        j = i + 1 if not re.match(r"\s*sl\.?\s*no", ln, re.I) else i
        rows: list[Row] = []
        while j < len(lines) and "|" in lines[j][1]:
            ls, lt = lines[j]
            cells = [c.strip() for c in lt.split("|")]
            j += 1
            if all(_HEADER_CELL.match(c) or not c for c in cells):
                continue
            label = ""
            if _SERIAL.fullmatch(cells[0] + " ") and len(cells) > 2:
                label, cells = cells[0], cells[1:]
            elif (m := _SERIAL.match(cells[0])):
                label, cells = m.group(1), [cells[0][m.end():]] + cells[1:]
            if len(cells) < 2 or any(a <= ls < b for a, b in skip):
                continue
            # Only rate rows: an amount in the band, Nil / a rate in the last cell.
            if not (_DIGITS_RE.search(" ".join(cells[:-1])) and _RATE_RE.search(cells[-1])):
                continue
            rows.append(Row(label=label, cells=cells, start=ls, end=ls + len(lt.rstrip())))
        if len(rows) >= 2:
            out.append(Table(kind="boxed", origin="text", page=None, rows=rows))
        i = max(j, i + 1)
    return out


# ── build, store, load ──────────────────────────────────────────────────────

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(statute: str, version: str, unlabelled: bool = False) -> dict:
    base = CORPUS_DIR / statute / version
    text = (base / "text.txt").read_text(encoding="utf-8")
    pdf = base / "source.pdf"
    tables: list[Table] = []
    unplaced = 0
    if pdf.exists():
        cursor = 0
        for t in pdf_tables(str(pdf), unlabelled=unlabelled):
            end = _place(t, text, cursor)
            if end is None:
                end = _place(t, text, 0)       # out of reading order (rare)
            if end is None:
                unplaced += 1
                continue
            tables.append(t)
            cursor = max(cursor, end)
    tables += boxed_tables(text, [(t.start, t.end) for t in tables])
    tables.sort(key=lambda t: t.start)
    return {
        "builder_version": BUILDER_VERSION,
        "statute": f"{statute}/{version}",
        "source_sha256": _sha(pdf) if pdf.exists() else None,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "unplaced_pdf_tables": unplaced,
        "tables": [{**{k: v for k, v in asdict(t).items() if k != "rows"},
                    "rows": [asdict(r) for r in t.rows]} for t in tables],
    }


def write(statute: str, version: str) -> Path:
    out = CORPUS_DIR / statute / version / "tables.json"
    out.write_text(json.dumps(build(statute, version), indent=1, ensure_ascii=False), encoding="utf-8")
    return out


@lru_cache(maxsize=32)
def load(statute_key: str) -> list[Table]:
    """The rebuilt tables of "FA2025/enacted", or [] if none were built or
    the view was built from different text."""
    base = CORPUS_DIR / statute_key
    path = base / "tables.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    text_sha = hashlib.sha256((base / "text.txt").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if data.get("text_sha256") != text_sha or data.get("builder_version") != BUILDER_VERSION:
        return []
    return [Table(kind=t["kind"], origin=t["origin"], page=t["page"], match=t.get("match", 1.0),
                  rows=[Row(**r) for r in t["rows"]]) for t in data["tables"]]


@lru_cache(maxsize=32)
def load_v2(statute_key: str) -> list[Table]:
    """View v2, built in memory and never written: also reads schedules
    printed without row labels. Used by the post-hoc rule baseline
    (rules-v2) only, so every run on the frozen view (tables.json) keeps its
    inputs."""
    statute, version = statute_key.split("/")
    if not (CORPUS_DIR / statute / version / "text.txt").exists():
        return []
    data = build(statute, version, unlabelled=True)
    return [Table(kind=t["kind"], origin=t["origin"], page=t["page"], match=t.get("match", 1.0),
                  rows=[Row(**r) for r in t["rows"]]) for t in data["tables"]]


def tables_in(statute_key: str, start: int, end: int, view: int = 1) -> list[Table]:
    """Tables lying wholly inside [start, end) of the canonical text."""
    tabs = load(statute_key) if view == 1 else load_v2(statute_key)
    return [t for t in tabs if start <= t.start and t.end <= end]


def render(tables: list[Table]) -> str:
    lines = []
    for i, t in enumerate(tables, 1):
        lines.append(f"Table {i}")
        lines += [r.text for r in t.rows]
    return "\n".join(lines)
