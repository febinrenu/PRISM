"""
Run one extraction system over one unit and turn its output into grounded
LegalRules.

Every quoted field is grounded in the unit text (grounding.py); a quote that
cannot be found is dropped and counted as a hallucination. Every effect is
validated against the typed effect schema; numbers in an effect are checked
against the quantities in the effect's own grounded quote. The result is an
ExtractionRecord that says exactly what was kept and what was rejected.
"""
import hashlib
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from models.rules import (
    Condition, CrossRef, Effect, Exception_, ExtractionRecord, LegalRule, Provenance, Span, Subject,
)
from pipeline.extraction import prompts
from pipeline.extraction.backends import SYSTEMS, BackendError, generate_json
from pipeline.extraction.grounding import ground
from pipeline.extraction.units import Unit
from pipeline.llm_extractor import parse_llm_json
from pipeline.quantities import extract_quantities

_EFFECT = TypeAdapter(Effect)
_MODALITIES = {"obligation", "prohibition", "permission", "power", "deeming", "definition"}
_MODALITY_ALIASES = {"duty": "obligation", "prohibited": "prohibition", "right": "permission",
                     "discretion": "permission", "deemed": "deeming", "definitional": "definition"}

# Effect fields holding rupee amounts / fractional rates, for numeric checks.
_AMOUNT_FIELDS = ("lower", "upper", "max_income", "max_rebate", "amount", "threshold", "per_day", "max_amount")
_RATE_FIELDS = ("rate", "max_rate", "rate_per_month")


class _Counter:
    def __init__(self):
        self.total = 0
        self.rejected = 0


def _span(unit: Unit, quote: Optional[str], counter: _Counter) -> Optional[Span]:
    if quote is None or (isinstance(quote, str) and not quote.strip()):
        return None
    if not isinstance(quote, str):
        quote = str(quote)
    counter.total += 1
    g = ground(quote, unit.text)
    if g is None:
        counter.rejected += 1
        return None
    return Span(node_id=unit.unit_id, start=unit.start + g.start, end=unit.start + g.end, text=g.text)


def numbers_supported(effect: dict, quote_text: str) -> tuple[int, int]:
    """(numeric fields checked, fields whose value appears in the quote)."""
    qs = extract_quantities(quote_text)
    amounts = {round(q.value, 2) for q in qs if q.kind == "amount_inr"} | \
              {round(q.upper, 2) for q in qs if q.kind == "amount_inr" and q.upper is not None}
    rates = {round(q.value / 100.0, 6) for q in qs if q.kind == "rate_pct"}
    checked = supported = 0
    for f in _AMOUNT_FIELDS:
        v = effect.get(f)
        if isinstance(v, (int, float)) and v not in (0, None):
            checked += 1
            # "From Rs. 3,00,001" encodes a lower bound of 3,00,000.
            if round(float(v), 2) in amounts or round(float(v) + 1, 2) in amounts:
                supported += 1
    for f in _RATE_FIELDS:
        v = effect.get(f)
        if isinstance(v, (int, float)) and v not in (0, None):
            checked += 1
            if round(float(v), 6) in rates or (quote_text and "nil" in quote_text.lower() and v == 0):
                supported += 1
    return checked, supported


def _rule_id(unit: Unit, system: str, i: int, sample: int) -> str:
    return hashlib.sha1(f"{unit.unit_id}|{system}|{sample}|{i}".encode()).hexdigest()[:16]


def to_record(unit: Unit, system: str, raw_text: str, *, model: str, model_version: Optional[str],
              cache_key: str, sample: int = 0) -> tuple[ExtractionRecord, dict]:
    stats = {"effects_total": 0, "effects_invalid": 0, "numbers_checked": 0, "numbers_supported": 0,
             "rules_dropped_modality": 0}
    parsed = parse_llm_json(raw_text)
    if parsed is None:
        return ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status="parse_error",
                                raw_ref=cache_key, error=raw_text[:300]), stats
    raw_rules = parsed.get("rules")
    if not isinstance(raw_rules, list):
        return ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status="schema_invalid",
                                raw_ref=cache_key, error="missing 'rules' list"), stats

    counter = _Counter()
    rules: list[LegalRule] = []
    prov = Provenance(extractor=system, model=model, model_digest=model_version,
                      prompt_version=prompts.EXTRACTION_PROMPT_VERSION, samples=1)
    for i, r in enumerate(raw_rules):
        if not isinstance(r, dict):
            continue
        modality = str(r.get("modality", "")).strip().lower()
        modality = _MODALITY_ALIASES.get(modality, modality)
        if modality not in _MODALITIES:
            stats["rules_dropped_modality"] += 1
            continue
        conditions = []
        for c in r.get("conditions") or []:
            q = c.get("quote") if isinstance(c, dict) else c
            sp = _span(unit, q, counter)
            if sp is not None:
                conditions.append(Condition(span=sp, negated=bool(c.get("negated")) if isinstance(c, dict) else False))
        exceptions = [Exception_(span=sp) for sp in (_span(unit, q, counter) for q in (r.get("exceptions") or [])) if sp]
        cross_refs = [CrossRef(span=sp) for sp in (_span(unit, q, counter) for q in (r.get("cross_refs") or [])) if sp]
        effects = []
        for e in r.get("effects") or []:
            if not isinstance(e, dict):
                continue
            stats["effects_total"] += 1
            quote = e.pop("quote", None)
            sp = _span(unit, quote, counter)
            payload: dict[str, Any] = {k: v for k, v in e.items() if v is not None}
            if sp is not None:
                payload["source_span"] = sp.model_dump()
                chk, sup = numbers_supported(e, sp.text)
                stats["numbers_checked"] += chk
                stats["numbers_supported"] += sup
            try:
                effects.append(_EFFECT.validate_python(payload))
            except ValidationError:
                stats["effects_invalid"] += 1
        rules.append(LegalRule(
            rule_id=_rule_id(unit, system, i, sample), statute=unit.statute, provision=unit.unit_id,
            modality=modality,  # type: ignore[arg-type]
            subject=Subject(span=_span(unit, r.get("subject"), counter), agent_class=r.get("agent_class")),
            conditions=conditions,
            action=_span(unit, r.get("action"), counter),
            consequence=_span(unit, r.get("consequence"), counter),
            exceptions=exceptions, cross_refs=cross_refs, effects=effects,
            executable=bool(effects), provenance=prov,
        ))
    status = "ok"
    if counter.total and counter.rejected == counter.total and rules:
        status = "grounding_rejected"
    rec = ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status=status, rules=rules,
                           hallucinated_fields=counter.rejected, total_span_fields=counter.total,
                           raw_ref=cache_key)
    return rec, stats


def extract_unit(unit: Unit, system: str, *, temperature: float = 0.0, seed: int = 0,
                 use_cache: bool = True) -> tuple[ExtractionRecord, dict]:
    if system not in SYSTEMS:
        raise KeyError(f"unknown system {system}")
    prompt = prompts.render(unit.text, unit.context)
    try:
        res = generate_json(system, prompt, temperature=temperature, seed=seed,
                            prompt_version=prompts.EXTRACTION_PROMPT_VERSION, use_cache=use_cache)
    except BackendError as e:
        return ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status="error", error=str(e)[:300]), {}
    rec, stats = to_record(unit, system, res.text, model=res.model, model_version=res.model_version,
                           cache_key=res.cache_key, sample=seed)
    stats["cached"] = res.cached
    stats["elapsed_ms"] = res.elapsed_ms
    return rec, stats
