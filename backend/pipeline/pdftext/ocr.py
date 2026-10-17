"""
OCR for pages whose text layer cannot be used (quality.py: empty or
garbled): RapidOCR (PP-OCR detection + recognition as ONNX models, CPU,
installed with `pip install rapidocr_onnxruntime`). Optional: without it
`available()` is False and such pages are reported unreadable rather than
guessed.

The page is rendered at DPI, recognised line by line, and mapped back to
PDF coordinates. Lines are grouped into blocks by vertical gaps, so the
rest of the pipeline sees what it sees for a born-digital page. Glued words
are re-spaced (respace.py) only on lines that are evidently glued, and each
line keeps the recogniser's confidence.
"""
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from pipeline.pdftext.respace import respace, respace_token

DPI = 200
GLUED_MEAN_WORD = 7.5    # a line whose words average more letters than this is glued
LONG_TOKEN = 14          # a single token this long is checked on any line


@dataclass
class OcrLine:
    text: str
    bbox: tuple[float, float, float, float]   # PDF points
    confidence: float


@lru_cache(maxsize=1)
def _engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    # The default shrinks a page so its long side is 2,000 px, which loses
    # whole lines of statute print; rotation classification is not needed.
    return RapidOCR(max_side_len=4000, use_cls=False)


def available() -> bool:
    return _engine() is not None


_PUNCT_GLUE = re.compile(r"([,;:])(?=[A-Za-z])")
_WORD = re.compile(r"[A-Za-z]+")


def clean(text: str) -> str:
    """NFKC (full-width brackets → ASCII), spaces after glued punctuation,
    and glued words split where the line is evidently glued."""
    text = unicodedata.normalize("NFKC", text).strip()
    text = _PUNCT_GLUE.sub(r"\1 ", text)
    words = _WORD.findall(text)
    if words and sum(map(len, words)) / len(words) > GLUED_MEAN_WORD:
        return respace(text)
    return _WORD.sub(lambda m: respace_token(m.group(0)) if len(m.group(0)) >= LONG_TOKEN else m.group(0), text)


def ocr_page(page, dpi: int = DPI) -> Optional[list[OcrLine]]:
    """Recognised lines of a page in reading order, or None without OCR."""
    eng = _engine()
    if eng is None:
        return None
    import numpy as np
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
    result, _ = eng(img)
    scale = 72.0 / dpi
    lines = []
    for box, text, conf in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        t = clean(text)
        if t:
            lines.append(OcrLine(t, (min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale), float(conf)))
    # reading order: top to bottom, then left to right within a line band
    lines.sort(key=lambda ln: (round(ln.bbox[1] / 4), ln.bbox[0]))
    return lines


def blocks(lines: list[OcrLine]) -> list[tuple[float, float, float, float, str, float]]:
    """Group lines into blocks at vertical gaps wider than a line:
    (x0, y0, x1, y1, text, mean confidence)."""
    out: list[list[OcrLine]] = []
    for ln in lines:
        if out:
            last = out[-1][-1]
            height = max(1.0, last.bbox[3] - last.bbox[1])
            if ln.bbox[1] - last.bbox[3] <= 0.9 * height:
                out[-1].append(ln)
                continue
        out.append([ln])
    res = []
    for grp in out:
        res.append((min(g.bbox[0] for g in grp), min(g.bbox[1] for g in grp),
                    max(g.bbox[2] for g in grp), max(g.bbox[3] for g in grp),
                    "\n".join(g.text for g in grp), sum(g.confidence for g in grp) / len(grp)))
    return res
