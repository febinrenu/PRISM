"""
The shared rule representation (schema v1).

Every extractor (rule-based, any LLM, a human annotator) emits LegalRule
objects; one deterministic assembler turns them into engine parameters, so a
difference in simulated outcomes can only come from a difference in the rules.

A LegalRule describes one deontic statement in one provision of a statute:

    modality      obligation | prohibition | permission | power | deeming | definition
    subject       who it binds              (grounded span + agent class)
    conditions    when it applies           (grounded spans, possibly negated)
    action        what is required/allowed
    consequence   what follows
    exceptions    provisos / "unless" carve-outs (spans or rule references)
    cross_refs    "section 80C(2)" → resolved node ids
    quantities    typed amounts, rates, durations with exact offsets
    effects       the machine-executable reading (tax rate rows, rebates,
                  penalties, deadlines …) — the part the engines consume

Spans always point into the canonical statute text (pipeline.statute), so
every rule is traceable to page and bounding box.
"""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

Modality = Literal["obligation", "prohibition", "permission", "power", "deeming", "definition"]
Regime = Literal["old", "new", "both"]
AgeBand = Literal["below_60", "60_to_80", "80_plus", "all"]
Operation = Literal["set", "substitute", "insert", "omit"]


class Span(BaseModel):
    node_id: str
    start: int            # offsets into the statute's canonical text
    end: int
    text: str


class Quantity(BaseModel):
    kind: Literal["amount_inr", "rate_pct", "duration_days", "count", "date"]
    value: float
    comparator: Optional[Literal["gt", "ge", "lt", "le", "eq", "range"]] = None
    upper: Optional[float] = None          # for comparator == "range"
    per: Optional[Literal["day", "month", "year", "instance"]] = None
    basis: Optional[str] = None            # "of the income-tax", "of total income" …
    span: Optional[Span] = None


class Subject(BaseModel):
    span: Optional[Span] = None
    agent_class: Optional[str] = None      # "individual", "company", "employer", "registered_person" …


class Condition(BaseModel):
    span: Optional[Span] = None
    negated: bool = False
    # Machine-readable form over the fact vocabulary (policy/facts.py), e.g.
    # {"op": "gt", "var": "aggregate_turnover", "value": 2e7}. None when the
    # condition needs a fact outside the vocabulary (rule not executable).
    expr: Optional[dict] = None


class Exception_(BaseModel):
    span: Optional[Span] = None
    rule_ref: Optional[str] = None         # rule_id of a defeating rule


class CrossRef(BaseModel):
    span: Optional[Span] = None
    target_node_id: Optional[str] = None   # None = unresolved


class Temporal(BaseModel):
    effective_from: Optional[str] = None   # ISO date
    assessment_year: Optional[str] = None  # "2024-25" (AY) or tax year under the 2025 Act
    deadline: Optional[str] = None


# ─── executable effects ─────────────────────────────────────────────────────

class _EffectBase(BaseModel):
    operation: Operation = "set"
    applies_to_ay: Optional[str] = None    # assessment year the effect governs
    regime: Regime = "both"
    taxpayer: str = "individual"           # individual | huf | company | firm | any
    age_band: AgeBand = "all"
    source_span: Optional[Span] = None


class SlabRow(_EffectBase):
    kind: Literal["slab_row"] = "slab_row"
    lower: float                           # income above this…
    upper: Optional[float] = None          # …up to this (None = no upper bound)
    rate: float                            # fraction, 0.05 = 5%


class Rebate(_EffectBase):
    kind: Literal["rebate"] = "rebate"
    max_income: float                      # available when total income ≤ this
    max_rebate: float
    marginal_relief: bool = False          # tax capped at income above max_income
    excludes_special_rate_income: bool = False


class StandardDeduction(_EffectBase):
    kind: Literal["standard_deduction"] = "standard_deduction"
    amount: float
    applies_to: str = "salary"


class SurchargeBand(_EffectBase):
    kind: Literal["surcharge_band"] = "surcharge_band"
    threshold: float                       # total income exceeding this
    rate: float                            # fraction of income-tax
    marginal_relief: bool = True


class SurchargeCap(_EffectBase):
    kind: Literal["surcharge_cap"] = "surcharge_cap"
    max_rate: float


class Cess(_EffectBase):
    kind: Literal["cess"] = "cess"
    rate: float
    base: Literal["tax_plus_surcharge"] = "tax_plus_surcharge"


class DeductionCap(_EffectBase):
    kind: Literal["deduction_cap"] = "deduction_cap"
    section: str
    max_amount: float


class RegimeOption(_EffectBase):
    kind: Literal["regime_option"] = "regime_option"
    default_regime: Literal["old", "new"]
    opt_out_allowed: bool = True


class TimingRule(_EffectBase):
    """TDS, advance tax and due dates change *when* tax is paid, never how
    much is owed, so the assembler routes them away from annual liability."""
    kind: Literal["tds", "advance_tax", "due_date"]
    rate: Optional[float] = None
    days: Optional[int] = None
    description: str = ""


class Penalty(_EffectBase):
    kind: Literal["penalty", "fee", "interest"]
    amount: Optional[float] = None         # fixed rupee amount
    per_day: Optional[float] = None
    rate: Optional[float] = None           # fraction (of tax / of amount)
    rate_per_month: Optional[float] = None
    max_amount: Optional[float] = None
    trigger: str = ""                      # "late filing", "failure to register" …


class OutOfScope(_EffectBase):
    kind: Literal["out_of_scope"] = "out_of_scope"
    reason: str = ""


Effect = Annotated[
    Union[SlabRow, Rebate, StandardDeduction, SurchargeBand, SurchargeCap, Cess,
          DeductionCap, RegimeOption, TimingRule, Penalty, OutOfScope],
    Field(discriminator="kind"),
]


class Provenance(BaseModel):
    extractor: str                         # "expert", "rule_based", "phi3.5", "gpt-oss-120b" …
    model: Optional[str] = None
    model_digest: Optional[str] = None
    prompt_version: Optional[int] = None
    schema_version: int = 1
    run_id: Optional[str] = None
    samples: int = 1                       # self-consistency k
    agreement: Optional[float] = None      # vote share across samples


class LegalRule(BaseModel):
    rule_id: str
    statute: str                           # "FA2023/enacted"
    provision: str                         # statute node_id
    modality: Modality
    subject: Subject = Subject()
    conditions: list[Condition] = []
    action: Optional[Span] = None
    consequence: Optional[Span] = None
    exceptions: list[Exception_] = []
    cross_refs: list[CrossRef] = []
    temporal: Temporal = Temporal()
    quantities: list[Quantity] = []
    effects: list[Effect] = []
    defeats: list[str] = []                # rule_ids this rule overrides
    executable: bool = True                # False when it needs facts outside the vocabulary
    provenance: Provenance


class ExtractionRecord(BaseModel):
    """What an extractor returned for one provision, including failure."""
    provision: str
    statute: str
    status: Literal["ok", "parse_error", "schema_invalid", "grounding_rejected", "timeout", "error"]
    rules: list[LegalRule] = []
    hallucinated_fields: int = 0           # span fields rejected by grounding
    total_span_fields: int = 0
    raw_ref: Optional[str] = None          # cache key of the raw model output
    error: Optional[str] = None
