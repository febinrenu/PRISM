"""
Phase 3, Module C novelty — template-matching rule translator.

The Phase-2 translator (rules.py) was a pure threshold-regex + actor-keyword
parser. The research proposal claims a *template library + semantic matching +
LLM fallback* for turning extracted rules into agent parameters. This module is
that mechanism.

A `PolicyTemplate` is a recognizable statute pattern (percentage tax above a
threshold, flat late fee, per-day penalty, filing deadline, …). Each carries a
few natural-language exemplars and a parameter extractor. Matching is semantic:
we embed the clause/extraction text with the same MiniLM encoder used elsewhere
and cosine-match against the mean exemplar embedding of each template (encoder
output is normalized, so dot product = cosine). The highest-scoring template
above MATCH_THRESHOLD wins and its extractor fills the SimulationRule
parameters; below threshold the caller falls back to the LLM/regex path.

Extractors reuse `parse_threshold_string` / `map_actors_to_agent_types` from
rules.py, so numeric parsing stays in one place.
"""
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

MATCH_THRESHOLD = 0.42  # cosine below this → not confident, fall back


@dataclass
class TemplateMatch:
    key: str
    score: float
    params: dict  # SimulationRule field overrides


@dataclass
class PolicyTemplate:
    key: str
    description: str
    exemplars: list[str]
    extract: Callable[[str, dict], dict]


# ─── Extractors ────────────────────────────────────────────────────────────────
# Each returns a dict of SimulationRule field overrides. `text` is the clause /
# rule description; `ex` is the (possibly empty) LLM extraction dict.

def _amounts(text: str):
    from simulation.rules import parse_threshold_string
    return parse_threshold_string(text)


def _percent_above_threshold(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE, parse_threshold_string
    rate = None
    m = _PERCENT_RE.search(text)
    if m:
        rate = min(float(m.group(1)), 40.0)
    parsed = parse_threshold_string(text)
    thr = parsed["value"] if parsed and parsed["kind"] == "amount" else None
    return {"rate_percent": rate, "threshold_value": thr,
            "threshold_kind": "amount" if thr else ("percent" if rate else None),
            # An above-threshold rate is a marginal levy: it applies only to
            # income above the limit, so sub-threshold agents owe nothing.
            "marginal": thr is not None,
            "penalty_probability": 0.5}


def _flat_fee(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    amt = parsed["value"] if parsed and parsed["kind"] == "amount" else 2000.0
    return {"base_compliance_cost": amt, "base_penalty_amount": 2.0 * amt,
            "penalty_probability": 0.4, "threshold_kind": None}


def _per_day_penalty(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    daily = parsed["value"] if parsed and parsed["kind"] == "amount" else 200.0
    # Annualize a per-day charge to a representative default exposure (~90 days).
    return {"base_penalty_amount": daily * 90.0, "base_compliance_cost": daily * 30.0,
            "penalty_probability": 0.6}


def _turnover_levy(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE
    m = _PERCENT_RE.search(text)
    # A turnover levy applies to the whole turnover, not a taxable slice.
    return {"rate_percent": min(float(m.group(1)), 40.0) if m else 5.0,
            "full_base": True,
            "affected_agent_types": ["small_business", "large_corporate"],
            "penalty_probability": 0.5}


def _deadline(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    days = parsed["value"] if parsed and parsed["kind"] == "duration" else 30.0
    return {"threshold_value": days, "threshold_kind": "duration",
            "base_compliance_cost": 1500.0, "penalty_probability": 0.45}


def _withholding(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE
    m = _PERCENT_RE.search(text)
    return {"rate_percent": min(float(m.group(1)), 40.0) if m else 10.0,
            "penalty_probability": 0.5}


def _exemption(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    thr = parsed["value"] if parsed and parsed["kind"] == "amount" else None
    # Exemption below a threshold → low burden, low enforcement.
    return {"threshold_value": thr, "threshold_kind": "amount" if thr else None,
            "base_compliance_cost": 500.0, "penalty_probability": 0.1}


def _interest(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE
    m = _PERCENT_RE.search(text)
    return {"rate_percent": min(float(m.group(1)), 24.0) if m else 12.0,
            "penalty_probability": 0.55}


def _registration(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    days = parsed["value"] if parsed and parsed["kind"] == "duration" else 30.0
    return {"threshold_value": days, "threshold_kind": "duration",
            "base_compliance_cost": 1000.0, "penalty_probability": 0.4}


def _fixed_offence(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    fine = parsed["value"] if parsed and parsed["kind"] == "amount" else 10000.0
    return {"base_penalty_amount": fine, "base_compliance_cost": fine * 0.25,
            "penalty_probability": 0.7}


def _surcharge(text: str, ex: dict) -> dict:
    return {**_percent_above_threshold(text, ex),
            "affected_agent_types": ["high_income", "large_corporate"],
            "penalty_probability": 0.5}


def _audit(text: str, ex: dict) -> dict:
    parsed = _amounts(text)
    thr = parsed["value"] if parsed and parsed["kind"] == "amount" else None
    return {"threshold_value": thr, "threshold_kind": "amount" if thr else None,
            "affected_agent_types": ["small_business", "large_corporate"],
            "base_compliance_cost": 25000.0, "penalty_probability": 0.35}


def _advance_tax(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE
    m = _PERCENT_RE.search(text)
    return {"rate_percent": min(float(m.group(1)), 40.0) if m else 15.0,
            "penalty_probability": 0.45}


def _cess(text: str, ex: dict) -> dict:
    from simulation.rules import _PERCENT_RE
    m = _PERCENT_RE.search(text)
    return {"rate_percent": min(float(m.group(1)), 10.0) if m else 4.0,
            "penalty_probability": 0.5}


def _rebate(text: str, ex: dict) -> dict:
    return {"base_compliance_cost": 300.0, "penalty_probability": 0.1,
            "affected_agent_types": ["low_income", "middle_income"]}


TEMPLATES: list[PolicyTemplate] = [
    PolicyTemplate("percentage_tax_above_threshold", "tax at a % rate on income above a limit",
        ["tax shall be charged at the rate of thirty per cent on income exceeding ten lakh rupees",
         "income above five lakh is taxed at twenty percent"], _percent_above_threshold),
    PolicyTemplate("flat_late_fee", "fixed fee for late filing",
        ["a late fee of five thousand rupees shall be payable for failure to furnish the return",
         "flat fee of Rs. 1000 for delayed submission"], _flat_fee),
    PolicyTemplate("per_day_penalty", "penalty accruing per day of default",
        ["a penalty of two hundred rupees for every day during which the default continues",
         "fine of Rs. 100 per day of delay"], _per_day_penalty),
    PolicyTemplate("turnover_based_levy", "levy as a % of business turnover",
        ["a levy of two per cent on the turnover of the company",
         "tax at 5% of annual turnover of the enterprise"], _turnover_levy),
    PolicyTemplate("filing_deadline", "obligation to file within a time limit",
        ["the return of income shall be furnished within thirty days",
         "the statement must be submitted before the due date of sixty days"], _deadline),
    PolicyTemplate("tds_withholding", "deduct tax at source at a rate",
        ["tax shall be deducted at source at the rate of ten per cent",
         "withhold 2% TDS on the payment"], _withholding),
    PolicyTemplate("exemption_below_threshold", "no tax where income is below a limit",
        ["no tax shall be payable where the total income does not exceed two lakh fifty thousand",
         "income below the basic exemption limit is not chargeable"], _exemption),
    PolicyTemplate("compounding_interest", "interest per month on unpaid amounts",
        ["interest at one per cent per month shall be charged on the amount unpaid",
         "simple interest of 1.5% per month on outstanding tax"], _interest),
    PolicyTemplate("registration_obligation", "obligation to register within a period",
        ["every person liable shall apply for registration within thirty days",
         "the dealer must register within one month of becoming liable"], _registration),
    PolicyTemplate("fixed_penalty_offence", "offence punishable with a fixed fine",
        ["any person who contravenes this section shall be punishable with a fine of ten thousand rupees",
         "the offence is punishable with a fine of Rs. 25000"], _fixed_offence),
    PolicyTemplate("surcharge_high_income", "surcharge on high incomes",
        ["a surcharge of ten per cent where total income exceeds fifty lakh rupees",
         "additional surcharge of 15% on income above one crore"], _surcharge),
    PolicyTemplate("audit_requirement", "audit required above a turnover",
        ["accounts shall be audited where the turnover exceeds one crore rupees",
         "compulsory audit for businesses with turnover above Rs. 10 crore"], _audit),
    PolicyTemplate("advance_tax_installment", "advance tax payable in installments",
        ["advance tax shall be payable in four installments during the financial year",
         "fifteen per cent of advance tax by the fifteenth of June"], _advance_tax),
    PolicyTemplate("cess_on_tax", "cess levied as a % of the tax",
        ["a health and education cess of four per cent on the amount of income-tax",
         "cess of 3% shall be added to the tax computed"], _cess),
    PolicyTemplate("rebate_for_beneficiary", "rebate/relief for a protected group",
        ["a rebate shall be allowed to a resident individual whose income is low",
         "senior citizens are allowed a higher deduction"], _rebate),
    PolicyTemplate("minimum_commitment", "minimum payment or commitment obligation",
        ["the assessee shall pay a minimum alternate tax irrespective of profits",
         "a minimum commitment of purchases each year is required"], _fixed_offence),
]


# ─── Semantic matcher ───────────────────────────────────────────────────────────

_exemplar_matrix: Optional[np.ndarray] = None  # (T, 384) mean exemplar vectors


def _ensure_exemplars() -> np.ndarray:
    global _exemplar_matrix
    if _exemplar_matrix is None:
        from pipeline.embedder import embed_texts
        vecs = []
        for tpl in TEMPLATES:
            emb = embed_texts(tpl.exemplars)  # (k, 384) normalized
            vecs.append(emb.mean(axis=0))
        mat = np.vstack(vecs)
        # Renormalize the mean vectors so cosine == dot product.
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        _exemplar_matrix = mat / np.clip(norms, 1e-9, None)
    return _exemplar_matrix


def match_template(text: str) -> Optional[TemplateMatch]:
    """Return the best-matching template for a clause/rule text, or None when no
    template clears MATCH_THRESHOLD. Score is cosine similarity in [0, 1]."""
    if not text or not text.strip():
        return None
    from pipeline.embedder import embed_texts

    mat = _ensure_exemplars()
    q = embed_texts([text])[0]  # normalized (384,)
    sims = mat @ q  # (T,)
    idx = int(np.argmax(sims))
    score = float(sims[idx])
    if score < MATCH_THRESHOLD:
        return None
    tpl = TEMPLATES[idx]
    return TemplateMatch(key=tpl.key, score=round(score, 4), params=tpl.extract(text, {}))
