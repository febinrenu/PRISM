"""
Statute parser tests.

A synthetic Gazette-style Act exercises every structural case (running
headers, margin line numbers, marginal-note headings, bold section numbers,
(a)…(h)/(i) letter-vs-roman disambiguation, provisos, explanations, a quoted
insertion with a rate table, and text continuing across a page break). Corpus
regression tests run only when the downloaded statutes are present.
"""
import json
from pathlib import Path

import fitz
import pytest

from pipeline.statute.parser import parse_statute

BACKEND = Path(__file__).parent.parent
CORPUS = BACKEND / "data" / "corpus"

BODY, SMALL = 10.5, 7.5
LEFT, INDENT = 120, 24


# Base-14 Helvetica has no glyphs for em-dashes or curly quotes, so the
# synthetic Act uses their ASCII forms ("--", "'"), which the parser also
# accepts; real Unicode punctuation is exercised by the corpus tests.
_ASCII = str.maketrans({"—": "--", "‘": "'", "’": "'", "“": '"', "”": '"'})


def _write(page, x, y, text, size=BODY, bold=False):
    text = text.translate(_ASCII)
    page.insert_text((x, y), text, fontsize=size, fontname="hebo" if bold else "helv")


def _gazette_page(doc, number):
    page = doc.new_page(width=595, height=842)
    _write(page, 120, 40, "THE GAZETTE OF INDIA EXTRAORDINARY", size=9)
    _write(page, 470, 40, str(number), size=9)
    for i, y in enumerate(range(120, 760, 70)):
        _write(page, 92, y, str((i + 1) * 5), size=SMALL)   # Bill-style margin numbers
    return page


def _build_synthetic(path: Path) -> Path:
    doc = fitz.open()
    p = _gazette_page(doc, 1)
    y = 90
    line = 15

    def body(text, level=0, bold=False, first_indent=True, page=None):
        nonlocal y
        pg = page or p
        x = LEFT + INDENT * (level + (1 if first_indent else 0))
        _write(pg, x, y, text, bold=bold)
        y += line

    _write(p, 260, y, "THE SAMPLE TAX ACT, 2026", bold=True)
    y += 2 * line
    _write(p, 270, y, "CHAPTER I", bold=True)
    y += line
    _write(p, 262, y, "PRELIMINARY")
    y += 2 * line
    _write(p, 40, y, "Short title.", size=SMALL)
    body("1. (1) This Act may be called the Sample Tax Act, 2026.", bold=True)
    body("(2) It shall come into force on the 1st day of April, 2026.")
    y += line
    _write(p, 40, y, "Definitions.", size=SMALL)
    body("2. In this Act, unless the context otherwise requires,—", bold=True)
    for letter in "abcdefgh":
        body(f"({letter}) “term {letter}” means a thing defined for the purpose {letter};", level=1)
    body("(i) “income” means—", level=1)
    body("(i) any salary received in the tax year; and", level=2)
    body("(ii) any rent received from house property;", level=2)
    y += line
    _write(p, 40, y, "Return of income.", size=SMALL)
    body("3. (1) Every person whose total income exceeds Rs. 5,00,000 shall", bold=True)
    body("furnish a return of income on or before the due date:", level=0, first_indent=False)
    body("Provided that no return is required where the income is exempt.", level=0)
    body("(2) Where any person fails to furnish the return under sub-section (1),")

    # Page 2: the sentence above continues across the page break.
    p = _gazette_page(doc, 2)
    y = 90
    body("he shall pay a penalty of Rs. 5,000.", level=0, first_indent=False, page=p)
    body("Explanation.—For the purposes of this section, “due date” means the", page=p)
    body("31st day of July of the assessment year.", level=0, first_indent=False, page=p)
    y += line
    _write(p, 40, y, "Insertion of new section.", size=SMALL)
    body("4. After section 3, the following section shall be inserted, namely:—", bold=True, page=p)
    body("‘3A. Income-tax shall be charged at the rates in the following Table:—", level=1, page=p)
    y += 4
    for row in (("1.", "Up to Rs. 3,00,000", "Nil"),
                ("2.", "From Rs. 3,00,001 to Rs. 7,00,000", "5 per cent."),
                ("3.", "Above Rs. 7,00,000", "10 per cent.’.")):
        _write(p, 190, y, row[0])
        _write(p, 230, y, row[1])
        _write(p, 430, y, row[2])
        y += line
    y += line
    _write(p, 40, y, "Penalty.", size=SMALL)
    body("5. Whoever contravenes section 3 shall be liable to a penalty.", bold=True, page=p)
    y += 2 * line
    _write(p, 200, y, "STATEMENT OF OBJECTS AND REASONS", bold=True)
    y += line
    body("This text explains the Bill and must not be parsed as law.", page=p)
    doc.save(str(path))
    return path


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    pdf = _build_synthetic(tmp_path_factory.mktemp("statute") / "sample.pdf")
    ast = parse_statute(str(pdf), "SAMPLE", "test", "act")
    by_path = {n["path"]: n for n in ast.nodes}
    return ast, by_path


def _own(ast, node):
    return ast.text[node["start"]:node["own_end"]]


def test_noise_is_removed(synthetic):
    ast, _ = synthetic
    assert "GAZETTE" not in ast.text
    assert "STATEMENT OF OBJECTS" not in ast.text and "must not be parsed" not in ast.text
    assert " 5 10 " not in ast.text and "\n10\n" not in ast.text


def test_sections_and_headings(synthetic):
    ast, by_path = synthetic
    sections = [n for n in ast.nodes if n["kind"] == "section" and not n["quoted"]]
    assert [s["number"] for s in sections] == ["1", "2", "3", "4", "5"]
    assert by_path["SAMPLE/s2"]["heading"] == "Definitions"
    assert by_path["SAMPLE/s3"]["heading"] == "Return of income"
    assert [n["number"] for n in ast.nodes if n["kind"] == "chapter"] == ["I"]


def test_letter_i_after_h_is_a_clause_and_roman_nests(synthetic):
    _, by_path = synthetic
    assert by_path["SAMPLE/s2/(i)"]["kind"] == "clause"
    assert by_path["SAMPLE/s2/(i)/(i)"]["kind"] == "subclause"
    assert by_path["SAMPLE/s2/(i)/(ii)"]["kind"] == "subclause"


def test_inline_subsection_and_sibling(synthetic):
    _, by_path = synthetic
    assert by_path["SAMPLE/s1/(1)"]["kind"] == "subsection"
    assert by_path["SAMPLE/s1/(2)"]["kind"] == "subsection"


def test_proviso_attaches_and_page_break_is_joined(synthetic):
    ast, by_path = synthetic
    s3 = by_path["SAMPLE/s3"]
    kinds = [ast_node["kind"] for ast_node in ast.nodes if ast_node["parent"] == s3["node_id"]
             or ast_node["parent"] in s3["children"]]
    assert "proviso" in kinds
    sub2 = by_path["SAMPLE/s3/(2)"]
    assert _own(ast, sub2).endswith("he shall pay a penalty of Rs. 5,000.")
    assert any(n["kind"] == "explanation" for n in ast.nodes if n["path"].startswith("SAMPLE/s3"))


def test_quoted_insertion_with_table(synthetic):
    ast, by_path = synthetic
    inserted = [n for n in ast.nodes if n["kind"] == "section" and n["quoted"]]
    assert [n["number"] for n in inserted] == ["3A"]
    rows = [n for n in ast.nodes if n["kind"] == "table_row"]
    assert len(rows) == 3
    assert "From Rs. 3,00,001 to Rs. 7,00,000 | 5 per cent." in _own(ast, rows[1])
    # The table belongs to the inserted section, not to the amending one.
    assert all(r["path"].startswith("SAMPLE/s4/q1/s3A") for r in rows)


def test_offsets_and_ids_are_consistent(synthetic):
    ast, _ = synthetic
    ids = [n["node_id"] for n in ast.nodes]
    assert len(ids) == len(set(ids))
    for n in ast.nodes:
        assert 0 <= n["start"] <= n["own_end"] <= n["end"] <= len(ast.text)


def test_ids_are_stable_across_parses(tmp_path):
    pdf = _build_synthetic(tmp_path / "again.pdf")
    first = [n["node_id"] for n in parse_statute(str(pdf), "SAMPLE", "test", "act").nodes]
    second = [n["node_id"] for n in parse_statute(str(pdf), "SAMPLE", "test", "act").nodes]
    assert first == second


# ── corpus regression (skipped when PDFs are not downloaded) ─────────────────

def _corpus_ast(statute, version):
    path = CORPUS / statute / version / "ast.json"
    if not path.exists():
        pytest.skip(f"{statute}/{version} not parsed (run cli ingest + parse)")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("statute, version, sections, chapters", [
    ("DPDP2023", "enacted", 44, 9),
    ("COW2019", "enacted", 69, 9),
    ("CGST2017", "consolidated", None, 21),
    ("ITA2025", "enacted", None, 23),
])
def test_corpus_structure_counts(statute, version, sections, chapters):
    ast = _corpus_ast(statute, version)
    secs = {n["number"] for n in ast["nodes"] if n["kind"] == "section" and not n["quoted"]}
    if sections is not None:
        assert len(secs) == sections
    assert sum(1 for n in ast["nodes"] if n["kind"] == "chapter") == chapters


def test_corpus_fa2020_new_regime_table():
    ast = _corpus_ast("FA2020", "enacted")
    text = (CORPUS / "FA2020" / "enacted" / "text.txt").read_text(encoding="utf-8")
    sec = next(n for n in ast["nodes"] if n["kind"] == "section" and n["number"] == "115BAC")
    rows = [n for n in ast["nodes"] if n["kind"] == "table_row" and n["start"] >= sec["start"]
            and n["end"] <= sec["end"]]
    slab_rows = [text[r["start"]:r["own_end"]] for r in rows if "per cent" in text[r["start"]:r["own_end"]]
                 or "Nil" in text[r["start"]:r["own_end"]]]
    assert slab_rows[0].startswith("1. Up to Rs. 2,50,000")
    assert len(slab_rows) == 7
