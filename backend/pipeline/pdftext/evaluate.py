"""
How well does each reading path read?

    ocr      born-digital statute pages are rendered to images and OCR'd; the
             recognised words are compared with the page's own text layer
             (bag of words, so reading order does not count against OCR)
    decoded  pages decoded through glyph names are compared with an OCR of
             the same page: wherever both read a line, they should agree

    python -m cli ocr-eval [--pages 8]
"""
import collections
import json
import re
import unicodedata

from config import BASE_DIR
from pipeline.pdftext import ocr
from pipeline.pdftext.text import page_text
from pipeline.statute.corpus import CORPUS_DIR

OUT = BASE_DIR / "data" / "eval" / "ocr.json"
# born-digital Acts with a clean text layer, and pages spread through each
SAMPLE = [("FA2025/enacted", (10, 30, 51, 70)), ("ITA2025/amended_fa2026", (40, 200, 420, 600)),
          ("CGST2017/consolidated", (20, 120))]
DECODED = ("ITA1961/consolidated", (5, 150, 400, 650, 900, 1050))

_TRANS = {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-"}


def _words(text: str) -> collections.Counter:
    text = unicodedata.normalize("NFKC", text)
    for a, b in _TRANS.items():
        text = text.replace(a, b)
    return collections.Counter(re.findall(r"[a-z]+|\d[\d,]*", text.lower()))


def _ocr_words(page) -> collections.Counter:
    return _words(" ".join(ln.text for ln in ocr.ocr_page(page) or []))


def _score(ref: collections.Counter, got: collections.Counter) -> dict:
    inter = sum((ref & got).values())
    return {"words": sum(ref.values()), "recall": inter / max(1, sum(ref.values())),
            "precision": inter / max(1, sum(got.values()))}


def run(pages: int = 10, progress=print) -> dict:
    import fitz
    if not ocr.available():
        raise RuntimeError("OCR is not installed: pip install rapidocr_onnxruntime")
    rows = []
    budget = pages
    for key, nums in SAMPLE:
        pdf = CORPUS_DIR / key / "source.pdf"
        if not pdf.exists():
            continue
        doc = fitz.open(pdf)
        for n in nums:
            if budget <= 0 or n >= len(doc):
                break
            budget -= 1
            s = _score(_words(doc[n].get_text()), _ocr_words(doc[n]))
            rows.append({"statute": key, "page": n + 1, **s})
            progress(f"ocr {key} p.{n + 1}: recall {s['recall']:.3f} precision {s['precision']:.3f}")
    dec = []
    pdf = CORPUS_DIR / DECODED[0] / "source.pdf"
    if pdf.exists():
        doc = fitz.open(pdf)
        for n in DECODED[1][: max(1, pages // 3)]:
            s = _score(_ocr_words(doc[n]), _words(page_text(doc[n])))
            # here the OCR is the reference: recall = share of OCR's words the
            # decoder also has; precision = share of decoded words OCR confirms
            dec.append({"statute": DECODED[0], "page": n + 1, **s})
            progress(f"decoded {DECODED[0]} p.{n + 1}: agreement {s['recall']:.3f} / {s['precision']:.3f}")

    def pooled(rs):
        if not rs:
            return None
        w = sum(r["words"] for r in rs)
        return {"pages": len(rs), "words": w,
                "recall": round(sum(r["recall"] * r["words"] for r in rs) / w, 4),
                "precision": round(sum(r["precision"] * r["words"] for r in rs) / w, 4)}

    out = {"engine": "rapidocr_onnxruntime (PP-OCRv4)", "dpi": ocr.DPI,
           "ocr": {"pooled": pooled(rows), "pages": rows},
           "decoded_vs_ocr": {"pooled": pooled(dec), "pages": dec}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
