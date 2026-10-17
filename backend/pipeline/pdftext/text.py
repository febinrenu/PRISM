"""
A page's text as PyMuPDF's "dict" structure, with unmapped fonts decoded.

On a page without Type3 fonts lacking a Unicode map this is exactly
`page.get_text("dict")`, so every statute that extracts cleanly reads as it
always did. On a page with such fonts, characters are read one by one,
decoded through the fonts' glyph names (glyphs.py), and word spaces are
placed from the gaps between glyphs: the extractor's own space insertion is
switched off there, because it writes a space as character code 32, which
in these fonts is some other glyph.
"""
from collections import Counter, defaultdict

import fitz

from pipeline.pdftext.glyphs import font_maps, font_weights

SPACE_GAP = 0.18      # a gap wider than this share of the font size is a word space
BOLD_RATIO = 1.3      # ink density against the page's main font of the same size


def text_dict(page) -> dict:
    maps = font_maps(page)
    if not maps:
        return page.get_text("dict")
    raw = page.get_text("rawdict", flags=fitz.TEXTFLAGS_RAWDICT | fitz.TEXT_INHIBIT_SPACES)
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            prev = None              # right edge of the previous glyph on the line
            for span in line.get("spans", []):
                cmap = maps.get(span["font"], {})
                out: list[str] = []
                for c in span.get("chars", []):
                    ch = cmap.get(c["c"], c["c"])
                    if prev is not None and ch != " " and c["bbox"][0] - prev > SPACE_GAP * span["size"]:
                        if out and out[-1] != " ":
                            out.append(" ")
                        elif not out:
                            out.append(" ")      # the gap falls between two spans
                    out.append(ch)
                    prev = c["bbox"][2]
                span["text"] = "".join(out)
                span.pop("chars", None)
    _mark_bold(page, raw, maps)
    raw["decoded_fonts"] = sorted(maps)
    return raw


def _mark_bold(page, raw: dict, maps: dict) -> None:
    """Type3 fonts have no weight in their names: a decoded font is bold when
    its glyphs carry markedly more ink than the main font of the same size on
    the page (set as PyMuPDF's bold flag, 16)."""
    weights = font_weights(page)
    use: dict = defaultdict(Counter)
    for b in raw.get("blocks", []):
        for ln in b.get("lines", []):
            for s in ln.get("spans", []):
                if s["font"] in maps:
                    use[round(s["size"] * 2) / 2][s["font"]] += len(s["text"].strip())
    body = {size: c.most_common(1)[0][0] for size, c in use.items() if c}
    for b in raw.get("blocks", []):
        for ln in b.get("lines", []):
            for s in ln.get("spans", []):
                ref = body.get(round(s["size"] * 2) / 2)
                w, w0 = weights.get(s["font"]), weights.get(ref)
                if s["font"] in maps and ref and w and w0 and s["font"] != ref and w >= BOLD_RATIO * w0:
                    s["flags"] = s.get("flags", 0) | 16


def page_text(page) -> str:
    """Plain text of a page, one line per text line."""
    return "\n".join("".join(s["text"] for s in ln["spans"])
                     for b in text_dict(page).get("blocks", []) if b.get("type", 0) == 0
                     for ln in b.get("lines", []))
