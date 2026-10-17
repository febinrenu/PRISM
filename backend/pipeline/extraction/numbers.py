"""
Is every number a reading states actually in the law it cites?

For each numeric field of an extracted effect (a slab's bounds and rate, a
rebate's limit and amount, a fee per day …) the verifier looks for the value
among the quantities of the effect's own quote, then of the whole provision:

    quote       the value is stated in the words the effect cites
    provision   it is stated elsewhere in the provision, not in the quote
    missing     the provision does not state it anywhere

Values are compared as the law writes them: rupee amounts in figures or
words ("Rs. 7,00,000", "seven hundred thousand rupees", "Rs. 1.5 lakh"),
rates as per cent ("5 per cent.", "20%", "Nil" for a zero rate). A band's
lower bound may differ from the printed figure by one rupee ("From
Rs. 4,00,001"; "exceeds Rs. 4,00,000" read as 4,00,001). A zero
lower bound and an open upper bound are what a table's first and last rows
mean, not numbers it prints, so they are not checked.

The effect is "verified" when every checked value is in its quote,
"provision" when some are only elsewhere in the provision, "unsupported"
when any is nowhere, and "unchecked" when it has no number to check.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

from pipeline.quantities import extract_quantities

AMOUNT_FIELDS = ("lower", "upper", "max_income", "max_rebate", "amount", "threshold", "per_day", "max_amount")
RATE_FIELDS = ("rate", "max_rate", "rate_per_month")
DAY_FIELDS = ("days",)


@dataclass
class FieldCheck:
    field: str
    value: float
    found: str              # quote | provision | missing


@dataclass
class EffectCheck:
    status: str             # verified | provision | unsupported | unchecked
    fields: list[FieldCheck] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"status": self.status, "fields": [asdict(f) for f in self.fields]}

    @property
    def missing(self) -> list[FieldCheck]:
        return [f for f in self.fields if f.found == "missing"]


@dataclass
class _Values:
    amounts: set
    rates: set
    days: set
    nil: bool


def _values(text: Optional[str]) -> _Values:
    if not text:
        return _Values(set(), set(), set(), False)
    qs = extract_quantities(text)
    amounts = {round(q.value, 2) for q in qs if q.kind == "amount_inr"} | \
              {round(q.upper, 2) for q in qs if q.kind == "amount_inr" and q.upper is not None}
    rates = {round(q.value / 100.0, 6) for q in qs if q.kind == "rate_pct"}
    days = {round(q.value) for q in qs if q.kind == "duration_days"}
    low = text.lower()
    return _Values(amounts, rates, days, "nil" in low or "no tax" in low)


def _in(fieldname: str, v: float, vals: _Values) -> bool:
    if fieldname in RATE_FIELDS:
        return round(float(v), 6) in vals.rates or (float(v) == 0.0 and vals.nil)
    if fieldname in DAY_FIELDS:
        return round(float(v)) in vals.days
    v = round(float(v), 2)
    # A band's lower bound may be written either way round: "From Rs. 3,00,001"
    # for a bound of 3,00,000, or a bound of 3,00,001 for "exceeds Rs. 3,00,000"
    # (the assembler accepts both, within a rupee).
    return v in vals.amounts or (fieldname == "lower" and (round(v + 1, 2) in vals.amounts
                                                            or round(v - 1, 2) in vals.amounts))


def check_effect(effect: dict, quote: Optional[str], provision: str) -> EffectCheck:
    """`effect`: an effect's fields (model_dump of models.rules.Effect, or the
    raw answer); `quote`: the text it cites; `provision`: the whole unit."""
    in_quote, in_prov = _values(quote), _values(provision)
    checks = []
    for f in AMOUNT_FIELDS + RATE_FIELDS + DAY_FIELDS:
        v = effect.get(f)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if f == "lower" and v == 0:
            continue                  # a schedule starts at zero: not a printed number
        if f in AMOUNT_FIELDS and v == 0:
            continue
        found = "quote" if _in(f, v, in_quote) else "provision" if _in(f, v, in_prov) else "missing"
        checks.append(FieldCheck(f, float(v), found))
    if not checks:
        return EffectCheck("unchecked", [])
    if any(c.found == "missing" for c in checks):
        return EffectCheck("unsupported", checks)
    if any(c.found == "provision" for c in checks):
        return EffectCheck("provision", checks)
    return EffectCheck("verified", checks)


def check_record(record, provision_text: str, unit_start: int = 0) -> list[EffectCheck]:
    """One check per effect of an ExtractionRecord, in rule order."""
    out = []
    for r in record.rules:
        for e in r.effects:
            sp = e.source_span
            out.append(check_effect(e.model_dump(exclude_none=True), sp.text if sp else None, provision_text))
    return out


def unsupported_numbers(claims: list[str], source: str) -> list[str]:
    """Numbers stated in free text (a model's condition, action, thresholds)
    that the source text does not contain: rupee amounts and rates only."""
    have = _values(source)
    out = []
    for claim in claims:
        if not claim:
            continue
        for q in extract_quantities(claim):
            if q.kind == "amount_inr":
                ok = round(q.value, 2) in have.amounts
            elif q.kind == "rate_pct":
                ok = round(q.value / 100.0, 6) in have.rates
            else:
                continue
            if not ok:
                label = (q.text or claim[q.start:q.end]).strip()
                if label not in out:
                    out.append(label)
    return out
