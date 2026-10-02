"""
Phase 2, Module C — translation of extracted causal rules (LLM or
rule-based) into executable SimulationRule objects.

Threshold strings like "Rs. 5,00,000", "5 lakh", "2 crore", "20%",
"30 days" are parsed into numeric values; actor mentions are mapped to
agent types by keyword. Unparseable fields get conservative defaults.
"""
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from models.schemas import AnalysisResult
from simulation.params import (
    BASE_COMPLIANCE_COST,
    BASE_PENALTY_AMOUNT,
    COST_SCALE_EXPONENT,
    COST_SCALE_PIVOT,
    DEFAULT_PENALTY_PROBABILITY,
    MAX_RATE_PERCENT,
    PENALTY_COST_MULTIPLE,
    TAXABLE_SLICE,
)

ALL_AGENT_TYPES = [
    "low_income", "middle_income", "high_income", "small_business", "large_corporate",
]

HOUSEHOLD_TYPES = ["low_income", "middle_income", "high_income"]
BUSINESS_TYPES = ["small_business", "large_corporate"]


@dataclass
class SimulationRule:
    clause_id: str
    description: str
    threshold_value: Optional[float] = None  # ₹ amount when threshold_kind == "amount"
    threshold_kind: Optional[Literal["amount", "percent", "duration"]] = None
    rate_percent: Optional[float] = None  # levy as % of income when present
    base_compliance_cost: float = BASE_COMPLIANCE_COST  # flat ₹ cost fallback
    base_penalty_amount: float = BASE_PENALTY_AMOUNT     # flat ₹ penalty fallback
    penalty_probability: float = DEFAULT_PENALTY_PROBABILITY
    affected_agent_types: list[str] = field(default_factory=lambda: list(ALL_AGENT_TYPES))
    source: Literal["llm", "rule_based"] = "rule_based"
    confidence: float = 0.5
    # Tax-base regime for a percent rate:
    #   marginal=True   → rate applies only to income ABOVE threshold_value
    #                     (a genuine above-threshold / slab levy)
    #   full_base=True  → rate applies to the WHOLE income/turnover (e.g. a
    #                     turnover levy on firms)
    #   otherwise       → rate applies to TAXABLE_SLICE of income (an effective
    #                     post-deduction base for a headline income-tax rate)
    marginal: bool = False
    full_base: bool = False
    # Module-C template translator: which template matched this clause (if any)
    # and its cosine score. None = fell back to the regex/keyword parser.
    matched_template: Optional[str] = None
    match_score: Optional[float] = None

    def compliance_cost_for(self, income: float) -> float:
        """Annual ₹ cost of complying with this rule."""
        if self.rate_percent is not None:
            if self.marginal and self.threshold_value is not None and self.threshold_kind == "amount":
                # Above-threshold levy: the rate bites only the income above the
                # limit, so an agent below the threshold owes nothing — the
                # defining feature of a progressive/marginal tax.
                taxable = max(0.0, income - self.threshold_value)
                return taxable * self.rate_percent / 100.0
            base = income if self.full_base else income * TAXABLE_SLICE
            return base * self.rate_percent / 100.0
        # Flat costs scale gently with income so corporates aren't modeled
        # as paying household-sized fees.
        scale = max(1.0, (income / COST_SCALE_PIVOT) ** COST_SCALE_EXPONENT)
        return self.base_compliance_cost * scale

    def penalty_amount_for(self, income: float) -> float:
        """Annual-equivalent ₹ penalty exposure for defaulting on this rule."""
        return PENALTY_COST_MULTIPLE * self.compliance_cost_for(income)


# ─── Threshold parsing ────────────────────────────────────────────────────────

_LAKH = 1.0e5
_CRORE = 1.0e7

_AMOUNT_RE = re.compile(
    r"(?i)(?:Rs\.?|INR|₹|rupees?)\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|thousand)?"
)
_UNIT_AMOUNT_RE = re.compile(r"(?i)\b(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores)\b")
_PLAIN_RUPEES_RE = re.compile(r"(?i)\b(\d[\d,]{3,}(?:\.\d+)?)\s*rupees?\b")
_PERCENT_RE = re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*(?:percent|per\s*cent|%)")
_DURATION_RE = re.compile(r"(?i)\b(\d+)\s*(days?|months?|years?)\b")

_UNIT_MULTIPLIER = {
    "lakh": _LAKH, "lakhs": _LAKH,
    "crore": _CRORE, "crores": _CRORE,
    "thousand": 1.0e3,
}


def parse_threshold_string(s: str) -> Optional[dict]:
    """
    Parse one threshold mention. Returns
    {"kind": "amount"|"percent"|"duration", "value": float} or None.
    Duration values are normalized to days.
    """
    if not s:
        return None

    m = _AMOUNT_RE.search(s)
    if m:
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        value *= _UNIT_MULTIPLIER.get(unit, 1.0)
        return {"kind": "amount", "value": value}

    m = _UNIT_AMOUNT_RE.search(s)
    if m:
        value = float(m.group(1).replace(",", "")) * _UNIT_MULTIPLIER[m.group(2).lower()]
        return {"kind": "amount", "value": value}

    m = _PLAIN_RUPEES_RE.search(s)
    if m:
        return {"kind": "amount", "value": float(m.group(1).replace(",", ""))}

    m = _PERCENT_RE.search(s)
    if m:
        return {"kind": "percent", "value": float(m.group(1))}

    m = _DURATION_RE.search(s)
    if m:
        value = float(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("month"):
            value *= 30
        elif unit.startswith("year"):
            value *= 365
        return {"kind": "duration", "value": value}

    return None


# ─── Actor → agent-type mapping ───────────────────────────────────────────────

_BUSINESS_KEYWORDS = re.compile(
    r"(?i)\b(compan(?:y|ies)|firms?|LLP|limited\s+liability|corporate|corporation|"
    r"business|enterprise|turnover|employer)\b"
)
_HOUSEHOLD_KEYWORDS = re.compile(
    r"(?i)\b(assessee|individuals?|persons?|taxpayers?|employees?|residents?|"
    r"citizens?|households?|widows?|senior\s+citizens?)\b"
)


def map_actors_to_agent_types(actors: list[str]) -> list[str]:
    """Keyword-map actor mentions to agent types; unmatched → all types."""
    types: set[str] = set()
    for actor in actors:
        if _BUSINESS_KEYWORDS.search(actor):
            types.update(BUSINESS_TYPES)
        if _HOUSEHOLD_KEYWORDS.search(actor):
            types.update(HOUSEHOLD_TYPES)
    return sorted(types) if types else list(ALL_AGENT_TYPES)


# ─── Template translation (Module C novelty) ──────────────────────────────────

def _apply_template(rule: SimulationRule, text: str) -> SimulationRule:
    """Try to recognize a known policy-rule template from the clause text and,
    if confident, override the rule's parameters with the template's structured
    reading. Falls through unchanged (matched_template=None) when no template is
    confident, so the regex/keyword parse remains the safety net.

    Import is local + guarded because the matcher needs the MiniLM embedder,
    which isn't available in every context (e.g. some unit tests)."""
    try:
        from simulation.templates import match_template
        match = match_template(text)
    except Exception:
        match = None
    if match is None:
        return rule

    rule.matched_template = match.key
    rule.match_score = match.score
    for key, value in match.params.items():
        if value is not None:
            setattr(rule, key, value)
    return rule


# ─── Rule construction ────────────────────────────────────────────────────────

def _rule_from_llm(clause_id: str, extraction: dict) -> SimulationRule:
    thresholds = [parse_threshold_string(t) for t in extraction.get("thresholds", [])]
    thresholds = [t for t in thresholds if t is not None]

    amount = next((t for t in thresholds if t["kind"] == "amount"), None)
    percent = next((t for t in thresholds if t["kind"] == "percent"), None)

    confidence = float(extraction.get("confidence", 0.5) or 0.5)
    description = (
        extraction.get("condition")
        or extraction.get("action")
        or extraction.get("consequence")
        or "extracted rule"
    )

    # A percent rate paired with an amount threshold is naturally an
    # above-threshold levy → marginal (rate hits only income above the limit).
    marginal = bool(percent and amount)

    return SimulationRule(
        clause_id=clause_id,
        description=str(description)[:200],
        threshold_value=amount["value"] if amount else None,
        threshold_kind=amount["kind"] if amount else (percent["kind"] if percent else None),
        rate_percent=min(percent["value"], MAX_RATE_PERCENT) if percent else None,
        marginal=marginal,
        penalty_probability=max(0.05, min(0.9, 0.3 + 0.3 * confidence)),
        affected_agent_types=map_actors_to_agent_types(extraction.get("actors", [])),
        source="llm",
        confidence=confidence,
    )


def _rule_from_pattern(clause_id: str, pattern, clause_text: str, actors: list[str]) -> SimulationRule:
    combined = f"{pattern.condition_span} {pattern.action_span}"
    parsed = parse_threshold_string(combined)
    amount = parsed if parsed and parsed["kind"] == "amount" else None
    percent = parsed if parsed and parsed["kind"] == "percent" else None

    marginal = bool(percent and amount)

    return SimulationRule(
        clause_id=clause_id,
        description=pattern.condition_span[:200],
        threshold_value=amount["value"] if amount else None,
        threshold_kind=parsed["kind"] if parsed else None,
        rate_percent=min(percent["value"], MAX_RATE_PERCENT) if percent else None,
        marginal=marginal,
        penalty_probability=max(0.05, min(0.9, 0.3 * pattern.confidence + 0.2 * pattern.impact_score)),
        affected_agent_types=map_actors_to_agent_types(actors),
        source="rule_based",
        confidence=pattern.confidence,
    )


def build_simulation_rules(
    result: AnalysisResult,
    rule_clause_ids: Optional[list[str]] = None,
    max_rules: int = 25,
) -> tuple[list[SimulationRule], str]:
    """
    Build executable rules from a document's extractions.
    Prefers LLM extractions (is_causal=true); falls back to rule-based
    causal patterns when no LLM extraction exists, so the Simulation
    Theater works before Module B has run.
    Returns (rules, rules_source).
    """
    wanted = set(rule_clause_ids) if rule_clause_ids else None
    llm_rules: list[SimulationRule] = []
    pattern_rules: list[SimulationRule] = []

    for clause in result.clauses:
        if wanted is not None and clause.clause_id not in wanted:
            continue

        actor_mentions = [e.text for e in clause.entities if e.label in ("ACTOR", "BENEFICIARY")]

        if clause.llm_extraction is not None and clause.llm_extraction.is_causal:
            extraction = clause.llm_extraction.model_dump()
            if not extraction.get("actors"):
                extraction["actors"] = actor_mentions
            rule = _rule_from_llm(clause.clause_id, extraction)
            # Match against the whole clause text (richer signal than the
            # truncated description) for the template translator.
            llm_rules.append(_apply_template(rule, clause.text))
        elif clause.causal_patterns:
            best = max(clause.causal_patterns, key=lambda p: p.impact_score)
            rule = _rule_from_pattern(clause.clause_id, best, clause.text, actor_mentions)
            pattern_rules.append(_apply_template(rule, clause.text))

    if llm_rules:
        rules, source = llm_rules, "llm"
    else:
        rules, source = pattern_rules, "rule_based"

    # Highest-impact rules first; cap so a 1,000-pattern bill stays simulable.
    rules.sort(key=lambda r: (r.rate_percent or 0.0, r.confidence), reverse=True)
    return rules[:max_rules], source
