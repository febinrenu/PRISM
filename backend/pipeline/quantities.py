"""
Typed quantities in statute text, with exact character offsets.

    ₹5,00,000 · Rs. 50 crores · 2.5 lakh rupees · fifty thousand rupees
    twelve hundred thousand rupees · one hundred rupees for every day
    20% · ten per cent. · 4.5 per cent per month · thirty days · six months

Indian statutes write amounts in three ways (digits with Indian grouping,
digits with lakh/crore, or entirely in words), so all three are parsed to a
rupee value. Ranges ("exceeds Rs. 3,00,000 but does not exceed Rs. 7,00,000")
and comparators ("not exceeding", "more than") are attached when present.
"""
import re
from dataclasses import dataclass
from typing import Optional

_SCALE = {"thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7,
          "million": 1e6, "billion": 1e9, "hundred": 1e2}
_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "a": 1, "half": 0.5, "one-half": 0.5,
}
_NUMBER_WORD = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|lakhs?|crores?|million|billion|and|a)"
_WORDS_RE = rf"(?:{_NUMBER_WORD}(?:[\s-]+{_NUMBER_WORD})*)"


def words_to_number(phrase: str) -> Optional[float]:
    """'twelve hundred thousand' → 1,200,000; 'two lakh fifty thousand' → 250,000."""
    phrase = re.sub(r"\b(?:one|a)[\s-]+half\b", "half", phrase.lower().strip())
    tokens = [t for t in re.split(r"[\s-]+", phrase) if t and t != "and"]
    if not tokens:
        return None
    total = 0.0
    current = 0.0
    seen = False
    for t in tokens:
        if t in _UNITS:
            current += _UNITS[t]
            seen = True
        elif t == "hundred":
            # "twelve hundred" = 1,200; the group stays open for a following
            # scale word ("twelve hundred thousand" = 12,00,000).
            current = (current or 1) * 100
            seen = True
        elif t in _SCALE:
            total += (current or 1) * _SCALE[t]
            current = 0.0
            seen = True
        else:
            return None
    total += current
    return total if seen else None


def _digits(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


@dataclass
class Quantity:
    kind: str                     # amount_inr | rate_pct | duration_days | count
    value: float
    start: int
    end: int
    text: str
    comparator: Optional[str] = None
    upper: Optional[float] = None
    per: Optional[str] = None


_CUR = r"(?:Rs\.?|INR|₹)"
_NUM = r"\d[\d,]*(?:\.\d+)?"
_SCALE_WORD = r"(?:thousand|lakhs?|crores?|million|billion)"

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # ₹ 5,00,000 / Rs. 50 crores / INR 2.5 lakh
    ("amount_digits", re.compile(rf"(?<![\w]){_CUR}\s*({_NUM})(?:\s*({_SCALE_WORD})\b)?", re.I)),
    # 2.5 lakh rupees / 50 crore rupees / 5,000 rupees
    ("amount_digits_words", re.compile(rf"\b({_NUM})\s*(?:({_SCALE_WORD})\s+)?rupees\b", re.I)),
    # fifty thousand rupees / twelve hundred thousand rupees
    ("amount_words", re.compile(rf"\b({_WORDS_RE})\s+rupees\b", re.I)),
    # 20% / 4.5 per cent / ten per cent.
    ("rate_digits", re.compile(rf"(?<![\w.])({_NUM})\s*(?:%|per\s*cent\.?)(?!\w)", re.I)),
    ("rate_words", re.compile(rf"\b({_WORDS_RE})\s+per\s*cent\.?(?!\w)", re.I)),
    # thirty days / 6 months / one year
    ("duration", re.compile(rf"\b({_NUM}|{_WORDS_RE})\s+(days?|months?|years?)\b", re.I)),
]

_COMPARATORS = [
    (re.compile(r"(?:does\s+not|shall\s+not|not)\s+exceed(?:ing)?\s*$|up\s*to\s*$|upto\s*$|not\s+more\s+than\s*$|maximum\s+of\s*$|subject\s+to\s+a\s+maximum\s+(?:amount\s+)?of\s*$", re.I), "le"),
    (re.compile(r"(?:exceeds?|exceeding|more\s+than|above|in\s+excess\s+of)\s*$", re.I), "gt"),
    (re.compile(r"(?:less\s+than|below)\s*$", re.I), "lt"),
    (re.compile(r"(?:not\s+less\s+than|at\s+least|minimum\s+of)\s*$", re.I), "ge"),
]
_PER_RE = re.compile(r"^\s*(?:for\s+(?:every|each)|per|a)\s+(day|month|year)\b", re.I)


def _comparator(text: str, start: int) -> Optional[str]:
    window = text[max(0, start - 45):start]
    for rx, cmp_ in _COMPARATORS:
        if rx.search(window):
            return cmp_
    return None


def extract_quantities(text: str) -> list[Quantity]:
    found: list[Quantity] = []
    taken: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in taken)

    for name, rx in _PATTERNS:
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if overlaps(s, e):
                continue
            q: Optional[Quantity] = None
            g1 = m.group(1)
            if name == "amount_digits":
                v = _digits(g1) * (_SCALE.get((m.group(2) or "").lower(), 1.0))
                q = Quantity("amount_inr", v, s, e, text[s:e])
            elif name == "amount_digits_words":
                v = _digits(g1) * (_SCALE.get((m.group(2) or "").lower(), 1.0))
                q = Quantity("amount_inr", v, s, e, text[s:e])
            elif name == "amount_words":
                v = words_to_number(g1)
                if v is not None and v > 0:
                    q = Quantity("amount_inr", v, s, e, text[s:e])
            elif name == "rate_digits":
                q = Quantity("rate_pct", _digits(g1), s, e, text[s:e])
            elif name == "rate_words":
                v = words_to_number(g1)
                if v is not None:
                    q = Quantity("rate_pct", v, s, e, text[s:e])
            elif name == "duration":
                raw = g1
                v = _digits(raw) if re.match(r"\d", raw) else words_to_number(raw)
                if v is not None and v > 0:
                    unit = m.group(2).lower().rstrip("s")
                    days = {"day": 1, "month": 30, "year": 365}[unit]
                    q = Quantity("duration_days", v * days, s, e, text[s:e])
            if q is None:
                continue
            q.comparator = _comparator(text, s)
            per = _PER_RE.match(text[e:e + 30])
            if per and q.kind == "amount_inr":
                q.per = per.group(1).lower()
            found.append(q)
            taken.append((s, e))

    found.sort(key=lambda q: q.start)
    # "exceeds Rs. 3,00,000 but does not exceed Rs. 7,00,000" → one range.
    merged: list[Quantity] = []
    for q in found:
        prev = merged[-1] if merged else None
        if (prev is not None and prev.kind == q.kind == "amount_inr" and prev.comparator == "gt"
                and q.comparator == "le" and q.start - prev.end < 40
                and re.search(r"\bbut\b|\bto\b|-", text[prev.end:q.start])):
            prev.comparator, prev.upper = "range", q.value
            prev.end, prev.text = q.end, text[prev.start:q.end]
            continue
        merged.append(q)
    return merged
