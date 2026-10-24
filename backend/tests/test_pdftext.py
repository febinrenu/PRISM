"""Reading PDFs that do not give up their text: fonts without a Unicode map
(decoded through glyph names), scanned pages (OCR), and the per-page check
that decides between them (pipeline/pdftext)."""
import fitz
import pytest

from pipeline.pdftext import ocr, quality, respace
from pipeline.pdftext.glyphs import control_share
from pipeline.pdftext.text import page_text, text_dict
from pipeline.statute.corpus import CORPUS_DIR

ITA1961 = CORPUS_DIR / "ITA1961" / "consolidated"
needs_ita = pytest.mark.skipif(not (ITA1961 / "source.pdf").exists(), reason="ITA 1961 PDF not downloaded")
needs_ocr = pytest.mark.skipif(not ocr.available(), reason="rapidocr_onnxruntime not installed")

STATUTE_LINES = ["The Finance Act, 2025", "In section 115BAC of the Income-tax Act, in sub-section (1A),",
                 "the income-tax payable in respect of the total income of a person shall be computed",
                 "at the rate of tax given in the following Table, namely:"]


def _text_pdf(path, lines=STATUTE_LINES, size=12):
    doc = fitz.open()
    page = doc.new_page()
    y = 90
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=size, fontname="tiro")
        y += 2 * size
    doc.save(path)
    return path


def _scanned_pdf(src, path, dpi=200):
    """Each page of `src` as an image only (no text layer): a scan."""
    s = fitz.open(src)
    out = fitz.open()
    for p in s:
        pg = out.new_page(width=p.rect.width, height=p.rect.height)
        pg.insert_image(pg.rect, pixmap=p.get_pixmap(dpi=dpi))
    out.save(path)
    return path


# ── page quality ─────────────────────────────────────────────────────────────

def test_quality_verdicts():
    prose = " ".join(STATUTE_LINES * 3)
    assert quality.assess(prose).verdict == "ok"
    assert quality.assess("\x0b\x06\x10\x04\x15\x14\x10\x0e " * 20).verdict == "garbled"
    assert quality.assess("xqzt brkl " * 30).verdict == "garbled"
    # a table of figures is not judged by its words
    assert quality.assess("1. Rs. 2,50,000 | Nil\n2. Rs. 5,00,000 | 5 per cent.\n" * 6).verdict == "ok"
    assert quality.assess("").verdict == "ok"          # a blank page without page context
    assert control_share("ab\x01\x02") == 0.5


def test_empty_page_is_a_scan_only_when_printed(tmp_path):
    blank = fitz.open()
    blank.new_page()
    assert quality.assess("", blank[0]).verdict == "ok"
    scan = fitz.open(_scanned_pdf(_text_pdf(tmp_path / "t.pdf"), tmp_path / "s.pdf"))
    assert quality.assess(scan[0].get_text(), scan[0]).verdict == "empty"


# ── respacing ────────────────────────────────────────────────────────────────

def test_respace_splits_only_glued_known_words():
    costs = respace._costs()
    if not costs:
        pytest.skip("vocabulary not built (python -m cli ocr-vocab)")
    assert respace.respace("tosomuchof theincomebywayof") == "to so much of the income by way of"
    assert respace.respace("Ratesofincome-tax") == "Rates of income-tax"
    assert respace.respace("notwithstanding the assessee") == "notwithstanding the assessee"
    assert respace.respace("Xyzzyplugh") == "Xyzzyplugh"            # unknown pieces: kept
    assert ocr.clean("of,or India;or") == "of, or India; or"
    assert ocr.clean("（1） This Act") == "(1) This Act"             # full-width brackets


def test_respace_without_vocabulary_is_identity():
    assert respace.respace("theincome", costs={}) == "theincome"


# ── fonts without a Unicode map ──────────────────────────────────────────────

def test_ordinary_pages_are_read_exactly_as_before(tmp_path):
    doc = fitz.open(_text_pdf(tmp_path / "t.pdf"))
    assert text_dict(doc[0]) == doc[0].get_text("dict")


@needs_ita
def test_type3_fonts_are_decoded_through_glyph_names():
    doc = fitz.open(ITA1961 / "source.pdf")
    raw = doc[40].get_text()
    assert control_share(raw) > 0.5                    # what a plain extractor sees
    text = page_text(doc[40])
    assert control_share(text) == 0.0
    assert "(b) a person who is a resident, except where the royalty is payable in" in text
    # word spaces come from glyph gaps, never from code 32 (a letter in these fonts)
    assert "such person outside India or for the purposes of making or" in text


@needs_ita
def test_bold_is_read_from_glyph_ink():
    d = text_dict(fitz.open(ITA1961 / "source.pdf")[0])
    spans = [s for b in d["blocks"] for ln in b.get("lines", []) for s in ln["spans"]]
    heading = next(s for s in spans if s["text"].startswith("Definitions"))
    body = next(s for s in spans if s["text"].startswith("In this Act, unless the context"))
    assert heading["flags"] & 16 and not body["flags"] & 16


@needs_ita
def test_income_tax_act_1961_is_in_the_corpus():
    import json
    ast = json.loads((ITA1961 / "ast.json").read_text(encoding="utf-8"))
    text = (ITA1961 / "text.txt").read_text(encoding="utf-8")
    secs = {n["number"]: n for n in ast["nodes"] if n["kind"] == "section" and not n["quoted"]}
    assert len(secs) > 800 and control_share(text) == 0.0
    s87a = secs["87A"]
    assert s87a["heading"] == "Rebate of income-tax in case of certain individuals"
    assert text[s87a["start"]:s87a["end"]].startswith("87A. An assessee, being an individual resident in India")
    # numbering is in order
    import re
    key = [(int(re.match(r"\d+", n).group()), n) for n in secs]
    assert [k for k, _ in key] == sorted(k for k, _ in key)


# ── the document parser ──────────────────────────────────────────────────────

def test_born_digital_pages_keep_their_text(tmp_path):
    from pipeline.pdf_parser import extract_pages, reading_summary
    pages = extract_pages(str(_text_pdf(tmp_path / "t.pdf")))
    assert [p.source for p in pages] == ["text"]
    assert reading_summary(pages)["text"] == 1 and reading_summary(pages)["ocr_available"] is None


def test_scan_without_ocr_is_unreadable_not_garbage(tmp_path, monkeypatch):
    from pipeline import pdf_parser
    monkeypatch.setattr(pdf_parser.ocr, "ocr_page", lambda page, dpi=200: None)
    monkeypatch.setattr(pdf_parser.ocr, "available", lambda: False)
    pages = pdf_parser.extract_pages(str(_scanned_pdf(_text_pdf(tmp_path / "t.pdf"), tmp_path / "s.pdf")))
    assert pages[0].source == "unreadable" and pages[0].text == ""
    summary = pdf_parser.reading_summary(pages)
    assert summary["unreadable_pages"] == [1] and summary["ocr_available"] is False


@needs_ocr
def test_scanned_page_is_read_by_ocr(tmp_path):
    from pipeline.pdf_parser import extract_pages, reading_summary
    pages = extract_pages(str(_scanned_pdf(_text_pdf(tmp_path / "t.pdf"), tmp_path / "s.pdf")))
    p = pages[0]
    assert p.source == "ocr" and p.ocr_confidence > 0.8
    words = set(p.text.lower().replace(",", " ").split())
    expected = set(" ".join(STATUTE_LINES).lower().replace(",", " ").split())
    assert len(words & expected) / len(expected) > 0.9
    # blocks carry page coordinates, so clauses can be highlighted on the PDF
    assert all(0 <= b.bbox_norm[1] < b.bbox_norm[3] <= 1.01 for b in p.blocks)
    assert reading_summary(pages)["ocr_pages"] == [1]


@needs_ita
def test_analysis_reads_decoded_pages(tmp_path):
    from pipeline.pdf_parser import extract_pages, reading_summary
    src = fitz.open(ITA1961 / "source.pdf")
    out = fitz.open()
    out.insert_pdf(src, from_page=40, to_page=40)
    out.save(tmp_path / "ita.pdf")
    pages = extract_pages(str(tmp_path / "ita.pdf"))
    assert pages[0].source == "decoded" and "royalty is payable" in pages[0].text
    assert reading_summary(pages)["decoded"] == 1


@needs_ocr
@pytest.mark.skipif(not (CORPUS_DIR / "FA2025" / "enacted" / "source.pdf").exists(), reason="FA 2025 PDF not downloaded")
def test_rate_schedules_are_read_from_a_scanned_page(tmp_path):
    """FA 2025 p.52 as an image only: the three old-regime schedules are read
    from the OCR lines (labels misread as "(l)", columns OCR joined on one
    line) with the same bands as from the text layer."""
    from pipeline.pdf_parser import extract_pages
    from pipeline.schedules import find_schedules
    src = fitz.open(CORPUS_DIR / "FA2025" / "enacted" / "source.pdf")
    one = fitz.open()
    one.insert_pdf(src, from_page=51, to_page=51)
    one.save(tmp_path / "p52.pdf")
    scan = tmp_path / "scan.pdf"
    _scanned_pdf(tmp_path / "p52.pdf", scan)
    pages = extract_pages(str(scan))
    ocr_pages = {p.page_num: {"width": p.width, "height": p.height, "lines": p.ocr_lines} for p in pages if p.ocr_lines}
    sch = find_schedules(str(scan), ocr_pages)
    bands = [[(r["lower"], r["upper"], r["rate"]) for r in s["rows"]] for s in sch]
    assert bands == [
        [(0.0, 250000.0, 0.0), (250000.0, 500000.0, 0.05), (500000.0, 1000000.0, 0.2), (1000000.0, None, 0.3)],
        [(0.0, 300000.0, 0.0), (300000.0, 500000.0, 0.05), (500000.0, 1000000.0, 0.2), (1000000.0, None, 0.3)],
        [(0.0, 500000.0, 0.0), (500000.0, 1000000.0, 0.2), (1000000.0, None, 0.3)],
    ]
    assert all(s["check"]["ok"] for s in sch)
    assert find_schedules(str(scan)) == []          # without the OCR lines a scan has no tables to read
