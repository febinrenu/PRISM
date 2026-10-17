"""
How far can a page's text layer be trusted?

    ok        readable text
    empty     (almost) no text, but the page is printed: a scan or an image
    garbled   text that is not language: control characters from a font
              without a Unicode map, or strings that are not words

A page that is not ok is read by OCR when it is available (ocr.py).
"""
import re
from dataclasses import dataclass

from pipeline.pdftext.glyphs import control_share

MIN_CHARS = 25          # fewer non-space characters than this is no text
MAX_CONTROL = 0.15      # share of control / private-use characters
MIN_WORDLIKE = 0.5      # share of alphabetic tokens that look like words
MIN_IMAGE_COVER = 0.25  # share of the page an image must cover to be a scan
MIN_TOKENS = 20         # fewer alphabetic tokens than this: too little prose to judge the words

_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
_VOWEL = re.compile(r"[aeiouyAEIOUY]")


@dataclass
class PageQuality:
    verdict: str            # ok | empty | garbled
    chars: int
    control_share: float
    wordlike_share: float
    image_cover: float

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "chars": self.chars, "control_share": round(self.control_share, 4),
                "wordlike_share": round(self.wordlike_share, 4), "image_cover": round(self.image_cover, 4)}


def wordlike_share(text: str) -> float:
    """Share of alphabetic tokens of 3+ letters that look like words of a
    Latin-script language (a vowel, not absurdly long). Non-Latin scripts
    count as words: this test only catches mojibake."""
    toks = [t for t in _TOKEN.findall(text) if len(t) >= 3]
    if len(toks) < MIN_TOKENS:
        return 1.0          # a table of figures, a title page: nothing to judge
    good = 0
    for t in toks:
        latin = all(ord(c) < 0x250 for c in t)
        if not latin or (_VOWEL.search(t) and len(t) <= 24) or t.isupper():
            good += 1
    return good / len(toks)


def image_cover(page) -> float:
    area = abs(page.rect) or 1.0
    covered = 0.0
    try:
        for info in page.get_image_info():
            x0, y0, x1, y1 = info["bbox"]
            covered += max(0.0, x1 - x0) * max(0.0, y1 - y0)
    except Exception:  # noqa: BLE001 - a malformed image never stops reading
        return 0.0
    return min(1.0, covered / area)


def assess(text: str, page=None) -> PageQuality:
    chars = sum(1 for c in text if not c.isspace())
    ctrl = control_share(text)
    words = wordlike_share(text)
    cover = image_cover(page) if page is not None else 0.0
    if chars < MIN_CHARS:
        verdict = "empty" if cover >= MIN_IMAGE_COVER else "ok"   # a blank page is fine
    elif ctrl > MAX_CONTROL or words < MIN_WORDLIKE:
        verdict = "garbled"
    else:
        verdict = "ok"
    return PageQuality(verdict, chars, ctrl, words, cover)
