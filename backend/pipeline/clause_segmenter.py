"""
Clause segmentation for legal documents.
Uses structural markers (section numbers, legal keywords) to split text into
clauses. Table regions (flagged by the PDF parser) are emitted as a single
`table` clause each and never split as prose.
"""
import re
from dataclasses import dataclass, field
from pipeline.pdf_parser import PageData


@dataclass
class RawClause:
    text: str
    page: int
    char_start: int  # global char offset
    char_end: int
    section_hierarchy: list[str] = field(default_factory=list)
    bbox: list[float] | None = None
    is_table: bool = False


# Patterns that indicate the start of a new clause / sub-clause.
# A section marker is either at the start of a line, or follows sentence-end
# punctuation ("… April, 2026. 4. Exemption …") — legal drafting frequently
# runs several numbered sections together in one text block, and matching only
# at line starts left them lumped into one giant clause. The number may be
# followed by "." or ")" (e.g. "1." / "1)") before the whitespace.
_SECTION_RE = re.compile(
    r"(?m)(?:^|(?<=[.;:]\s))\s*"
    r"(\d{1,3}(?:\.\d{1,3}){0,4})"       # numbered: 1, 1.2, 1.2.3
    r"[.)]?\s+"                            # optional "." or ")" then space
    r"(?=[A-Z(\"])"                        # followed by uppercase / paren / quote
)

_LEGAL_MARKERS = [
    r"\bProvided\s+that\b",
    r"\bExplanation\s*[\d.\-]*[.:—]",
    r"\bNotwithstanding\s+anything",
    r"\bSubject\s+to\s+the\s+provisions",
    r"\bFor\s+the\s+purposes\s+of\s+this\s+(?:section|clause|act)",
    r"\bWhere\s+(?:any|a|an)\b",
    r"\bIn\s+(?:this|the)\s+(?:section|clause|act|sub-section)\b",
]

_LEGAL_MARKER_RE = re.compile("|".join(_LEGAL_MARKERS), re.IGNORECASE)

MIN_CLAUSE_CHARS = 30
MAX_CLAUSE_CHARS = 3000

# Semantic segmentation: adjacent-sentence cosine below this = topic shift =
# extra boundary. Only consulted when SEGMENTATION_MODE == "semantic".
SEMANTIC_THRESHOLD = 0.30
_SEMANTIC_MAX_SENTENCES = 60  # skip embedding on very large regions (cost guard)
_SENTENCE_BOUNDARY_RE = re.compile(r'(?<=\.)\s+(?=[A-Z("])')


def _semantic_enabled() -> bool:
    try:
        from config import SEGMENTATION_MODE
        return SEGMENTATION_MODE == "semantic"
    except Exception:
        return False


def _semantic_split_positions(region: str, base: int) -> list[int]:
    """Extra boundary positions from an embedding-cohesion check: split where
    adjacent sentences are semantically dissimilar (a topic shift the structural
    markers missed). All returned positions are char offsets into the page text
    (base + offset-in-region), so the exact-substring offset invariant holds.

    Returns [] on any failure (embedder unavailable, too few/many sentences) so
    segmentation always degrades to the structural path."""
    bounds = [m.end() for m in _SENTENCE_BOUNDARY_RE.finditer(region)]
    starts = [0] + bounds
    ends = bounds + [len(region)]
    sents = [(s, region[s:e]) for s, e in zip(starts, ends) if len(region[s:e].strip()) > 15]
    if not (3 <= len(sents) <= _SEMANTIC_MAX_SENTENCES):
        return []

    try:
        from pipeline.embedder import embed_texts
        emb = embed_texts([t for _, t in sents])  # normalized → dot = cosine
    except Exception:
        return []

    positions: list[int] = []
    for i in range(1, len(sents)):
        sim = float(emb[i - 1] @ emb[i])
        if sim < SEMANTIC_THRESHOLD:
            positions.append(base + sents[i][0])
    return positions


def _parse_section_number(text: str) -> list[str]:
    """Extract leading section number hierarchy from clause text."""
    m = re.match(r"^\s*(\d{1,3}(?:\.\d{1,3}){0,4})[.)]?\s+", text)
    if m:
        return m.group(1).split(".")
    return []


def _find_split_positions(text: str, base: int = 0) -> list[int]:
    """Return character positions (offset by `base`) where new clauses start."""
    positions: set[int] = {base}

    for m in _SECTION_RE.finditer(text):
        positions.add(base + m.start())

    for m in _LEGAL_MARKER_RE.finditer(text):
        positions.add(base + m.start())

    return sorted(positions)


def _iter_regions(text: str, table_spans: list[tuple[int, int]]):
    """Yield (start, end, is_table) regions covering `text`, with table spans
    kept intact and the prose gaps between them yielded separately."""
    spans = sorted(s for s in table_spans if s[0] < s[1])
    cursor = 0
    for ts, te in spans:
        ts = max(ts, cursor)
        if ts > cursor:
            yield (cursor, ts, False)
        if te > ts:
            yield (ts, te, True)
        cursor = max(cursor, te)
    if cursor < len(text):
        yield (cursor, len(text), False)


def segment_clauses(pages: list[PageData]) -> list[RawClause]:
    """
    Segment all pages into clauses.
    Returns list of RawClause objects sorted by position.
    """
    all_clauses: list[RawClause] = []
    semantic = _semantic_enabled()

    for page in pages:
        text = page.text
        if not text.strip():
            continue

        for rstart, rend, is_table in _iter_regions(text, page.table_spans):
            region = text[rstart:rend]

            if is_table:
                _emit(all_clauses, page, region, rstart, is_table=True)
                continue

            # Prose region: split on section/legal markers (+ semantic cohesion
            # boundaries when enabled), then size-bound.
            positions = set(_find_split_positions(region, base=rstart))
            if semantic:
                positions.update(_semantic_split_positions(region, rstart))
            split_positions = sorted(positions)
            split_positions.append(rend)  # sentinel

            for i in range(len(split_positions) - 1):
                start = split_positions[i]
                end = split_positions[i + 1]
                raw_segment = text[start:end]

                if len(raw_segment.strip()) < MIN_CLAUSE_CHARS:
                    continue
                if len(raw_segment.strip()) > MAX_CLAUSE_CHARS:
                    sub_segments = _split_long_segment(raw_segment)
                else:
                    sub_segments = [(raw_segment, 0)]

                for sub_raw, sub_offset in sub_segments:
                    _emit(all_clauses, page, sub_raw, start + sub_offset, is_table=False)

    return all_clauses


def _emit(all_clauses: list[RawClause], page: PageData, raw: str, seg_start: int,
          *, is_table: bool) -> None:
    """Strip whitespace but account for it in the offsets so that
    text[local_start:local_end] == clause text exactly — the PDF overlay and
    bbox lookup depend on this invariant."""
    lead = len(raw) - len(raw.lstrip())
    sub = raw.strip()
    if len(sub) < MIN_CLAUSE_CHARS:
        return
    local_start = seg_start + lead
    local_end = local_start + len(sub)
    global_start = page.char_offset + local_start
    global_end = page.char_offset + local_end
    hierarchy = [] if is_table else _parse_section_number(sub)
    bbox = _find_bbox_for_text(page, local_start, local_end)

    all_clauses.append(RawClause(
        text=sub,
        page=page.page_num,
        char_start=global_start,
        char_end=global_end,
        section_hierarchy=hierarchy,
        bbox=bbox,
        is_table=is_table,
    ))


def _split_long_segment(text: str) -> list[tuple[str, int]]:
    """
    Split very long text at sentence boundaries.
    Returns (chunk, offset_in_text) pairs where each chunk is a true
    substring of `text` starting at its offset — offsets never drift.
    """
    boundaries = [m.end() for m in re.finditer(r"(?<=\.)\s+(?=[A-Z(])", text)]
    boundaries.append(len(text))

    result: list[tuple[str, int]] = []
    chunk_start = 0
    for boundary in boundaries:
        if boundary - chunk_start >= MIN_CLAUSE_CHARS * 3 or boundary == len(text):
            if boundary > chunk_start:
                result.append((text[chunk_start:boundary], chunk_start))
            chunk_start = boundary
    return result if result else [(text, 0)]


def _find_bbox_for_text(page: PageData, local_start: int, local_end: int) -> list[float] | None:
    """
    Approximate bounding box for a text range on a page.
    Returns normalized [x0, y0, x1, y1] or None.
    """
    if not page.blocks:
        return None

    # Build a mapping: cumulative char offset -> block
    cumulative = 0
    matching_blocks: list = []
    for block in page.blocks:
        block_len = len(block.text)
        block_start = cumulative
        block_end = cumulative + block_len
        # Check overlap
        if block_start < local_end and block_end > local_start:
            matching_blocks.append(block)
        cumulative += block_len + 1  # +1 for newline separator

    if not matching_blocks:
        return None

    # Merge bboxes of all matching blocks (normalized)
    x0 = min(b.bbox_norm[0] for b in matching_blocks)
    y0 = min(b.bbox_norm[1] for b in matching_blocks)
    x1 = max(b.bbox_norm[2] for b in matching_blocks)
    y1 = max(b.bbox_norm[3] for b in matching_blocks)
    return [x0, y0, x1, y1]
