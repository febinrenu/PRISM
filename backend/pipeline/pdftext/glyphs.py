"""
Recover text from fonts that have no Unicode mapping.

Some government PDFs (PageMaker → Distiller, as the India Code copy of the
Income-tax Act, 1961) draw their text with Type3 fonts that carry no
ToUnicode table. A text extractor then returns each glyph's raw code — a
private, per-font numbering — and the text layer reads as control
characters. The fonts still say what each glyph is: their /Encoding
/Differences array names every code's glyph, and PageMaker names them
"/c<decimal>" or "/G<decimal>" with the character's Windows-1252 code
(/c73 = "I", /c147 = "“", /G151 = "—"). Standard glyph names (/a,
/period) the extractor already decodes itself, so only these numeric names
are mapped: a code the extractor has already turned into its character is
never touched again.

`font_maps(page)` reads those arrays for every font on a page that has no
ToUnicode table;
`repair(text, cmap)` replaces raw codes by the characters they name. Text in
fonts that already map to Unicode is never touched, and a code whose glyph
name says nothing is left as it is (and is counted, so the caller can fall
back to OCR).
"""
import re
from typing import Optional

_C_NAME = re.compile(r"^[cCgG](\d{2,3})$")
_DIFF = re.compile(r"/Differences\s*\[(.*?)\]", re.S)


def _glyph_char(name: str) -> Optional[str]:
    """The character a numeric glyph name stands for, or None."""
    m = _C_NAME.match(name)
    if not m:
        return None
    code = int(m.group(1))
    if 32 <= code <= 255:
        try:
            return bytes([code]).decode("cp1252")
        except UnicodeDecodeError:
            return None
    return None


def _differences(doc, enc_xref_or_obj: str) -> dict[int, str]:
    """code → glyph name from an /Encoding object (inline or by reference)."""
    m = _DIFF.search(enc_xref_or_obj)
    if not m:
        ref = re.search(r"(\d+)\s+0\s+R", enc_xref_or_obj)
        if not ref:
            return {}
        m = _DIFF.search(doc.xref_object(int(ref.group(1))))
        if not m:
            return {}
    out, code = {}, 0
    for tok in re.findall(r"\d+|/[^\s/\[\]]+", m.group(1)):
        if tok[0] == "/":
            out[code] = tok[1:]
            code += 1
        else:
            code = int(tok)
    return out


def font_maps(page) -> dict[str, dict[str, str]]:
    """{font name as the extractor reports it: {raw char: real char}} for the
    page's fonts without a ToUnicode table whose glyphs have numeric names."""
    doc = page.parent
    maps: dict[str, dict[str, str]] = {}
    for xref, _ext, ftype, basefont, name, *_ in page.get_fonts(full=True):
        if ftype not in ("Type3", "Type1", "TrueType", "Type1C", "MMType1"):
            continue
        obj = doc.xref_object(xref)
        if "/ToUnicode" in obj:
            continue
        enc = re.search(r"/Encoding\s+(\d+\s+0\s+R|<<.*?>>)", obj, re.S)
        if not enc:
            continue
        diffs = _differences(doc, enc.group(1))
        cmap = {}
        for code, gname in diffs.items():
            ch = _glyph_char(gname)
            if ch is not None:
                cmap[chr(code)] = ch
        if cmap:
            # spans name an embedded subset without its "ABCDEF+" prefix
            for key in {basefont, name, re.sub(r"^[A-Z]{6}\+", "", basefont or "")}:
                if key:
                    maps[key] = cmap
    return maps


def repair(text: str, cmap: Optional[dict[str, str]]) -> str:
    if not cmap:
        return text
    return "".join(cmap.get(c, c) for c in text)


def control_share(text: str) -> float:
    """Share of non-space characters that are control or private-use
    characters (what an unmapped font extracts as)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    bad = sum(1 for c in chars if ord(c) < 32 or 0xE000 <= ord(c) <= 0xF8FF or c == "�")
    return bad / len(chars)


def _ink(stream: bytes) -> Optional[float]:
    """Share of a bitmap glyph's pixels that are inked (an image mask: a
    0 bit paints, unless the mask is inverted)."""
    m = re.search(rb"/W (\d+)\s*/H (\d+)(.*?)ID\n(.*)EI", stream, re.S)
    if not m:
        return None
    w, h, opts, data = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    if w * h < 20:
        return None
    data = data[: ((w + 7) // 8) * h]
    ones = sum(bin(x).count("1") for x in data)
    inked = ones if re.search(rb"/D(?:ecode)?\s*\[\s*1\s+0\s*\]", opts) else (w * h - ones)
    return inked / (w * h)


def font_weights(page) -> dict[str, float]:
    """Mean ink density of the letters and digits of each bitmap Type3 font
    on the page (heavier for a bold face of the same size)."""
    doc = page.parent
    out: dict[str, float] = {}
    for xref, _ext, ftype, basefont, name, *_ in page.get_fonts(full=True):
        if ftype != "Type3":
            continue
        obj = doc.xref_object(xref)
        cp = re.search(r"/CharProcs\s+(\d+)\s+0\s+R", obj)
        if not cp:
            continue
        vals = []
        for gname, x in re.findall(r"/(\S+)\s+(\d+)\s+0\s+R", doc.xref_object(int(cp.group(1)))):
            ch = _glyph_char(gname)
            if ch and ch.isalnum():
                v = _ink(doc.xref_stream(int(x)))
                if v is not None:
                    vals.append(v)
        if len(vals) >= 3:
            for key in {basefont, name}:
                if key:
                    out[key] = sum(vals) / len(vals)
    return out
