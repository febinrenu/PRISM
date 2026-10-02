"""
PDF parsing using PyMuPDF (fitz).
Extracts text per page with character offsets and bounding boxes.

Text is normalized as it is read (layout newlines collapsed, line-break
hyphenation joined, mis-decoded glyphs repaired) so downstream regex/NLP
sees clean prose. Tables are detected and linearized into a single block
flagged `is_table` — they are kept as one clause and excluded from prose
analysis (causal detection / LIME) instead of being shredded into garbage
fragments.
"""
import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF


@dataclass
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 (absolute)
    bbox_norm: tuple[float, float, float, float]  # normalized 0-1
    is_table: bool = False


@dataclass
class PageData:
    page_num: int  # 1-indexed
    width: float
    height: float
    text: str
    blocks: list[TextBlock] = field(default_factory=list)
    char_offset: int = 0  # global char offset for this page's text start
    # Local char ranges (within `text`) that are tabular data — the segmenter
    # emits each as exactly one `table` clause and never splits it as prose.
    table_spans: list[tuple[int, int]] = field(default_factory=list)


# ─── Text normalization ────────────────────────────────────────────────────────

_SMART_QUOTES = {
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
    "–": "-", "—": "-",  # en/em dash → hyphen
}


def normalize_text(s: str) -> str:
    """Collapse layout whitespace, join line-break hyphenation, repair glyphs.

    PyMuPDF preserves the PDF's visual line breaks inside a block, which turns
    real prose into fragments like "provides \\nscientific \\nstorage" and
    splits words such as "punish-\\nable". This makes a block read as one line.
    """
    if not s:
        return ""
    # Join words split across a line break: "foo-\n bar" → "foobar"
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)
    # Collapse any run of whitespace (incl. newlines) to a single space
    s = re.sub(r"\s+", " ", s)
    # A backtick before a number or a currency unit is a mis-decoded rupee sign
    # ("`50 Crores", "in ` Lakhs" → "₹50 Crores", "in ₹ Lakhs").
    s = re.sub(r"`\s*(?=\d|[Ll]akh|[Cc]rore|[Tt]housand)", "₹", s)
    for bad, good in _SMART_QUOTES.items():
        s = s.replace(bad, good)
    return s.strip()


def _dedupe_join(block_texts: list[str]) -> str:
    """Join a table's constituent block texts into readable, single-clause
    text. `table.extract()` mangles double-struck/bold PDFs into doubled
    characters ("VViissiioonn"), so we use the clean per-block text instead and
    drop the adjacent duplicate blocks that fake-bold rendering produces."""
    out: list[str] = []
    for t in block_texts:
        t = t.strip()
        if not t or (out and out[-1] == t):
            continue
        out.append(t)
    return "\n".join(out)


def _block_in_table(block_bbox, table_rects: list["fitz.Rect"]) -> int:
    """Return the index of the table whose region contains this block's
    center, or -1 if the block is ordinary prose."""
    x0, y0, x1, y1 = block_bbox[:4]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for i, rect in enumerate(table_rects):
        if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1:
            return i
    return -1


def _extract_one_page(doc: "fitz.Document", page_idx: int) -> dict:
    """Extract everything local to a single page — text blocks, table
    detection/linearization — without assigning any global char_offset
    (that's a separate sequential accumulation over all pages' results).

    NOTE: page.find_tables() / get_text("blocks") are NOT safe to run
    concurrently across threads even with one fitz.Document per thread —
    verified empirically (see extract_pages docstring): MuPDF appears to
    share glyph/font-metric caches process-wide, so parallelizing this
    function across threads silently corrupts bbox coordinates (text stays
    correct, geometry doesn't) without raising. Do not parallelize this
    without switching to a process pool instead of threads."""
    page = doc[page_idx]
    width = page.rect.width or 1.0
    height = page.rect.height or 1.0

    raw_blocks = page.get_text("blocks")  # [(x0,y0,x1,y1,text,no,type)]

    # Detect tables on this page (best-effort; never fatal).
    try:
        tables = list(page.find_tables().tables)
    except Exception:
        tables = []
    table_rects = [fitz.Rect(t.bbox) for t in tables]

    text_blocks: list[TextBlock] = []
    page_text_parts: list[str] = []
    table_spans: list[tuple[int, int]] = []
    emitted_tables: set[int] = set()
    running = 0  # local char offset into the eventual page_text

    def _append_part(part_text: str, bbox_abs, is_table: bool):
        nonlocal running
        x0, y0, x1, y1 = bbox_abs
        block = TextBlock(
            text=part_text,
            bbox=(x0, y0, x1, y1),
            bbox_norm=(
                round(x0 / width, 4),
                round(y0 / height, 4),
                round(x1 / width, 4),
                round(y1 / height, 4),
            ),
            is_table=is_table,
        )
        text_blocks.append(block)
        page_text_parts.append(part_text)
        start = running
        end = start + len(part_text)
        if is_table:
            table_spans.append((start, end))
        # +1 accounts for the "\n" join separator between parts
        running = end + 1

    # First pass: normalize each text block and tag it with its table
    # (or -1 for prose), preserving reading order.
    tagged: list[tuple[str, tuple, int]] = []
    table_block_texts: dict[int, list[str]] = {}
    for block in raw_blocks:
        if block[6] != 0:  # skip non-text blocks (images = type 1)
            continue
        btext = normalize_text(block[4])
        if not btext:
            continue
        tbl_idx = _block_in_table(block, table_rects)
        tagged.append((btext, (block[0], block[1], block[2], block[3]), tbl_idx))
        if tbl_idx >= 0:
            table_block_texts.setdefault(tbl_idx, []).append(btext)

    # Second pass: emit prose blocks individually and each table once
    # (at its first block's position) as one clean, de-duplicated part.
    for btext, bbox, tbl_idx in tagged:
        if tbl_idx < 0:
            _append_part(btext, bbox, is_table=False)
            continue
        if tbl_idx in emitted_tables:
            continue
        emitted_tables.add(tbl_idx)
        table_text = _dedupe_join(table_block_texts[tbl_idx])
        if table_text:
            _append_part(table_text, tables[tbl_idx].bbox, is_table=True)

    return {
        "page_num": page_idx + 1,
        "width": width,
        "height": height,
        "text": "\n".join(page_text_parts),
        "blocks": text_blocks,
        "table_spans": table_spans,
    }


def extract_pages(pdf_path: str) -> list[PageData]:
    """
    Extract all pages from a PDF, returning structured page data.
    Each PageData contains the full (normalized) text, list of text blocks
    with bboxes, the global character offset of this page's text, and the
    char ranges of any detected tables.

    Sequential by design: an earlier attempt to parallelize find_tables()
    across pages with a thread pool (one fitz.Document handle per thread,
    the officially-documented PyMuPDF thread-safety pattern) measured
    *slower* wall time than sequential AND silently corrupted bounding-box
    coordinates (text content matched exactly; y0/y1 differed by ~1pt on
    many blocks) — MuPDF evidently shares some non-thread-safe glyph/font
    cache across "independent" documents in the same process. A process
    pool would sidestep that but adds per-run interpreter startup cost this
    codebase hasn't measured as worthwhile yet.
    """
    with fitz.open(pdf_path) as doc:
        page_results = [_extract_one_page(doc, i) for i in range(len(doc))]

    pages: list[PageData] = []
    global_offset = 0
    for r in page_results:
        pages.append(PageData(
            page_num=r["page_num"],
            width=r["width"],
            height=r["height"],
            text=r["text"],
            blocks=r["blocks"],
            char_offset=global_offset,
            table_spans=r["table_spans"],
        ))
        global_offset += len(r["text"]) + 1  # +1 for page separator

    return pages


def get_page_count(pdf_path: str) -> int:
    with fitz.open(pdf_path) as doc:
        return len(doc)
