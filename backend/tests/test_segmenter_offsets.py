"""
Offset invariant: for every clause, slicing the page text with the clause's
char offsets must reproduce the clause text exactly. PDF highlight overlays
and bbox lookup depend on this.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEMO_DIR, DEMO_PDF_NAME
from pipeline.pdf_parser import extract_pages
from pipeline.clause_segmenter import segment_clauses, _split_long_segment


def test_split_long_segment_returns_true_substrings():
    text = (
        "The assessee shall furnish the return of income on or before the due date. "
        "Provided that the Assessing Officer may extend the period on sufficient cause being shown. "
        "Where the return is not furnished within the time allowed, interest shall be payable. "
        "The Central Government may notify exemptions for certain classes of persons. "
    ) * 12  # comfortably beyond MAX_CLAUSE_CHARS

    chunks = _split_long_segment(text)
    assert len(chunks) > 1
    for chunk, offset in chunks:
        assert text[offset:offset + len(chunk)] == chunk


def test_demo_pdf_clause_offsets_align():
    demo_path = DEMO_DIR / DEMO_PDF_NAME
    if not demo_path.exists():
        import pytest
        pytest.skip("demo PDF not present")

    pages = extract_pages(str(demo_path))
    page_by_num = {p.page_num: p for p in pages}
    clauses = segment_clauses(pages)

    assert len(clauses) > 0
    for clause in clauses:
        page = page_by_num[clause.page]
        local_start = clause.char_start - page.char_offset
        local_end = clause.char_end - page.char_offset
        assert page.text[local_start:local_end] == clause.text, (
            f"Offset drift on page {clause.page}: "
            f"expected clause text at [{local_start}:{local_end}]"
        )


if __name__ == "__main__":
    test_split_long_segment_returns_true_substrings()
    print("✓ _split_long_segment substring invariant")
    test_demo_pdf_clause_offsets_align()
    print("✓ demo PDF clause offsets align")
