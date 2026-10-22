"""
Rule-based extraction system ("rules"): the transparent baseline.

Produces the same grounded LegalRules as the language-model systems, so all
systems are scored by one evaluation and one assembler:

  modality     pipeline.deontic
  condition    IF/WHERE/PROVIDED patterns (pipeline.causal_detector), exact offsets
  action       from the modal verb to the end of its sentence
  effects      slab rows from rate-table lines ("From Rs. A to Rs. B | 10 per
               cent.", "(2) where the total income exceeds … | 5 per cent. …"),
               fees and penalties from amounts with "for every day" / "maximum"

Every span is an exact substring by construction (no grounding step needed).
"""
import re
from typing import Optional

from models.rules import (
    Condition, ExtractionRecord, LegalRule, Penalty, Provenance, SlabRow, Span, Subject,
)
from pipeline.causal_detector import detect_causal_patterns
from pipeline.deontic import modality
from pipeline.extraction.units import Unit
from pipeline.quantities import extract_quantities

SYSTEM = "rules"
# The rule baseline as reported is version 1 and stays as it is. Version 2
# ("rules-v2") fixes two defects the held-out check exposed, and is reported
# separately as a post-hoc baseline:
#   - a figure printed with a space before its comma ("Rs. 10 ,00,000") was
#     read as Rs. 10; v2 joins the figure before reading the row
#   - schedules printed without row labels were not rebuilt; v2 reads its
#     rows from table view 2 (pipeline.statute.tables.load_v2)
RULE_VERSIONS = {"rules": 1, "rules-v2": 2}
_SPLIT_FIGURE = re.compile(r"(\d)\s+,(?=\d)")


def _row_text(line: str, version: int) -> str:
    return _SPLIT_FIGURE.sub(r"\1,", line) if version >= 2 else line
_MODAL = re.compile(r"\b(?:shall|must|may|is\s+required\s+to|are\s+required\s+to|liable\s+to)\b", re.I)
_SENT_END = re.compile(r"(?<=[.;:])\s|$")


def _span(unit: Unit, s: int, e: int) -> Span:
    return Span(node_id=unit.unit_id, start=unit.start + s, end=unit.start + e, text=unit.text[s:e])


def _slab_from_line(line: str) -> Optional[dict]:
    """Parse one rate-table line into slab-row fields, or None."""
    if "|" not in line:
        return None
    cells = line.split("|")
    # The rate is the last cell; everything before it describes the income band
    # ("1. | Upto Rs. 4,00,000 | Nil" has a serial-number cell first).
    left, right = " ".join(cells[:-1]), cells[-1]
    right_l = right.lower()
    if "nil" in right_l[:20]:
        rate = 0.0
    else:
        rates = [q for q in extract_quantities(right) if q.kind == "rate_pct"]
        if not rates:
            return None
        rate = rates[0].value / 100.0
    amounts = [q for q in extract_quantities(left) if q.kind == "amount_inr"]
    if not amounts:
        return None
    a = amounts[0]
    ll = left.lower()
    if a.comparator == "range" and a.upper is not None:
        return {"lower": a.value, "upper": a.upper, "rate": rate}
    if re.search(r"\bfrom\b", ll) and len(amounts) >= 2:
        return {"lower": a.value - 1 if a.value % 10 == 1 else a.value, "upper": amounts[1].value, "rate": rate}
    if re.search(r"\b(?:up\s*to|upto)\b|does not exceed|not exceeding", ll):
        return {"lower": 0.0, "upper": a.value, "rate": rate}
    if re.search(r"\babove\b|\bexceeds\b|\bexceeding\b", ll):
        return {"lower": a.value, "upper": None, "rate": rate}
    return None


_AY_INTRO = re.compile(r"assessment\s+year\s+beginning\s+on\s+(?:or\s+after\s+)?the\s+1st\s+(?:day\s+of\s+)?April,?\s+(\d{4})", re.I)


def _row_years(text: str, rows: list) -> list:
    """The assessment year each rebuilt row's table is introduced with ("for
    any previous year relevant to the assessment year beginning on the 1st
    day of April, 2024, ... the following Table"), when the provision holds
    tables for more than one year; otherwise None for every row."""
    years = []
    for _, start, _ in rows:
        found = list(_AY_INTRO.finditer(text, 0, start))
        y = int(found[-1].group(1)) if found else None
        years.append(f"{y}-{(y + 1) % 100:02d}" if y else None)
    return years if len({y for y in years if y}) > 1 else [None] * len(rows)


def _fee_effects(text: str) -> list[dict]:
    if not re.search(r"\b(?:late\s+fee|penalty|fine|fee)\b", text, re.I):
        return []
    qs = [q for q in extract_quantities(text) if q.kind == "amount_inr"]
    if not qs:
        return []
    out: dict = {"kind": "fee" if re.search(r"\bfee\b", text, re.I) else "penalty"}
    for q in qs:
        if q.per == "day" and "per_day" not in out:
            out["per_day"] = q.value
        elif q.comparator == "le" and "max_amount" not in out:
            out["max_amount"] = q.value
        elif "amount" not in out and "per_day" not in out:
            out["amount"] = q.value
    return [out]


def extract_unit(unit: Unit, rows: Optional[list] = None, version: int = 1) -> tuple[ExtractionRecord, dict]:
    """`rows`: rebuilt table rows of the unit as (text, start, end) relative
    to unit.text (pipeline.statute.tables). Slab rows are then read from
    them, cited to each row's span, and the canonical lines they cover are
    not read again."""
    prov = Provenance(extractor=SYSTEM if version == 1 else f"{SYSTEM}-v{version}", model="regex+deontic",
                      prompt_version=None)
    text = unit.text
    rules: list[LegalRule] = []
    stats = {"effects_total": 0, "effects_invalid": 0, "numbers_checked": 0, "numbers_supported": 0}

    # Rate-table lines → one rule carrying all slab rows of the unit.
    slabs = []
    covered = []
    rows = rows or []
    for (row_text, rs, re_), ay in zip(rows, _row_years(text, rows)):
        fields = _slab_from_line(_row_text(row_text, version))
        if fields is not None:
            slabs.append(SlabRow(source_span=_span(unit, rs, re_), applies_to_ay=ay, **fields))
            covered.append((rs, re_))
    offset = 0
    for line in text.split("\n"):
        inside = any(a <= offset < b or a < offset + len(line) <= b for a, b in covered)
        fields = None if inside else _slab_from_line(_row_text(line, version))
        if fields is not None:
            src = _span(unit, offset, offset + len(line))
            slabs.append(SlabRow(source_span=src, **fields))
        offset += len(line) + 1
    if slabs:
        rules.append(LegalRule(rule_id=f"{unit.unit_id}:rules:slabs", statute=unit.statute, provision=unit.unit_id,
                               modality="obligation", effects=slabs, provenance=prov))
        stats["effects_total"] += len(slabs)

    mod = modality(text, in_definitions=(unit.section == "2"))
    if mod is not None:
        m = _MODAL.search(text)
        action = None
        subject = None
        if m:
            end_m = _SENT_END.search(text, m.end())
            end = end_m.start() if end_m else len(text)
            action = _span(unit, m.start(), min(end, m.start() + 400))
            # Subject: the words just before the modal verb within the sentence.
            sent_start = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start()), text.rfind(",", 0, m.start())) + 1
            subj = text[sent_start:m.start()].strip()
            if 0 < len(subj) <= 120:
                s0 = text.index(subj, sent_start)
                subject = _span(unit, s0, s0 + len(subj))
        conditions = []
        for p in detect_causal_patterns(text, unit.unit_id):
            if p.condition_start is not None and p.condition_end is not None:
                conditions.append(Condition(span=_span(unit, p.condition_start, p.condition_end)))
        fees = []
        for f in _fee_effects(text):
            fees.append(Penalty(**f))
        stats["effects_total"] += len(fees)
        rules.append(LegalRule(
            rule_id=f"{unit.unit_id}:rules:main", statute=unit.statute, provision=unit.unit_id,
            modality=mod,  # type: ignore[arg-type]
            subject=Subject(span=subject), conditions=conditions[:4], action=action,
            effects=fees, executable=bool(fees), provenance=prov,
        ))
    return ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status="ok", rules=rules,
                            hallucinated_fields=0, total_span_fields=0), stats
