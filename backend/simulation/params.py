"""
Phase 3, Module C — single source of truth for every simulation parameter.

Previously these constants were scattered across agents.py / rules.py /
model.py / templates.py, which made the model's assumptions impossible to
audit and easy for a reviewer to dismiss as "uncited magic numbers". This
module gathers all of them in one place, each annotated with a plain-language
rationale and an honesty tag:

    "sourced"      → grounded in a published figure / standard definition
    "illustrative" → a defensible modelling choice, NOT a measured value

`PARAM_REGISTRY` (bottom) exposes the whole set as structured metadata so the
API / UI can render a "Model assumptions" table — nothing about the economics
is hidden from the user.

Nothing here samples randomness or holds state; it is pure configuration.
"""
from dataclasses import dataclass
from enum import Enum


# ─── Agent taxonomy (kept here so params can key off it without importing
#     agents.py, which imports this module) ──────────────────────────────────
class AgentType(str, Enum):
    LOW_INCOME_HOUSEHOLD = "low_income"        # annual income < ₹3L
    MIDDLE_INCOME_HOUSEHOLD = "middle_income"  # ₹3L – ₹15L
    HIGH_INCOME_HOUSEHOLD = "high_income"      # ₹15L – ₹1Cr
    SMALL_BUSINESS = "small_business"          # SME, turnover < ₹5Cr
    LARGE_CORPORATE = "large_corporate"        # turnover > ₹100Cr


HOUSEHOLD_TYPES = (
    AgentType.LOW_INCOME_HOUSEHOLD,
    AgentType.MIDDLE_INCOME_HOUSEHOLD,
    AgentType.HIGH_INCOME_HOUSEHOLD,
)
FIRM_TYPES = (AgentType.SMALL_BUSINESS, AgentType.LARGE_CORPORATE)


def is_household(agent_type: AgentType) -> bool:
    return agent_type in HOUSEHOLD_TYPES


# ─── Ability to pay ────────────────────────────────────────────────────────
# Annual ₹ needed for basic subsistence (food, shelter, essentials). Subtracted
# from HOUSEHOLD income to get disposable income (ability to pay). Held constant
# in absolute terms, so the same flat levy consumes a larger share of a poor
# household's disposable income than a rich one's — this is the *affordability*
# lens, kept SEPARATE from the statutory-incidence verdict (see model.py).
SUBSISTENCE_FLOOR = 1.5e5  # illustrative — a single national figure

# Floor on disposable income as a fraction of gross, so the poorest never hit
# zero (which would make burden ratios explode).
DISPOSABLE_FLOOR_FRACTION = 0.10  # illustrative

# Firms have no "subsistence floor"; their capacity to bear a levy is a share of
# turnover representing margin/profit. Subtracting a household subsistence figure
# from a ₹400Cr corporation was meaningless, so firms use these margins instead.
PROFIT_MARGIN = {
    AgentType.SMALL_BUSINESS: 0.08,    # illustrative — thin SME net margin
    AgentType.LARGE_CORPORATE: 0.12,   # illustrative — listed-firm net margin
}


# ─── Tax base ──────────────────────────────────────────────────────────────
# For a percent rule WITHOUT an explicit above-threshold structure, the rate is
# applied to this fraction of income, approximating the effective taxable base
# after slabs/deductions/exemptions. Marginal rules (rate + amount threshold)
# ignore this and tax income *above* the threshold directly (see rules.py).
TAXABLE_SLICE = 0.25  # illustrative — effective-base approximation

# Hard cap on any parsed percent rate, so a mis-parsed "200%" can't blow up.
MAX_RATE_PERCENT = 40.0  # illustrative safety cap


# ─── Compliance behaviour ──────────────────────────────────────────────────
# Mean compliance tendency per type. Households with fewer resources have lower
# capacity to absorb compliance overhead; larger/formal entities comply more.
# Directionally consistent with tax-morale / ABM compliance literature; the
# specific values are illustrative.
COMPLIANCE_TENDENCY_MEAN = {
    AgentType.LOW_INCOME_HOUSEHOLD: 0.55,
    AgentType.MIDDLE_INCOME_HOUSEHOLD: 0.70,
    AgentType.HIGH_INCOME_HOUSEHOLD: 0.80,
    AgentType.SMALL_BUSINESS: 0.65,
    AgentType.LARGE_CORPORATE: 0.90,
}

# Beta(4,2) is used to draw a skewed tendency; its mean (=4/(4+2)) rescales the
# draw so the population mean lands on COMPLIANCE_TENDENCY_MEAN.
BETA_A, BETA_B = 4.0, 2.0
BETA_MEAN = BETA_A / (BETA_A + BETA_B)  # 0.667

COMPLIANCE_TENDENCY_MIN = 0.05
COMPLIANCE_TENDENCY_MAX = 0.98

# Months of financial buffer (savings) per type, drawn uniformly.
BUFFER_RANGES = {
    AgentType.LOW_INCOME_HOUSEHOLD: (0.0, 2.0),
    AgentType.MIDDLE_INCOME_HOUSEHOLD: (1.0, 6.0),
    AgentType.HIGH_INCOME_HOUSEHOLD: (6.0, 24.0),
    AgentType.SMALL_BUSINESS: (1.0, 4.0),
    AgentType.LARGE_CORPORATE: (12.0, 36.0),
}  # illustrative

# Static decision rule: comply iff (tendency + noise) > burden_score * stress.
# stress = 1 / (1 + STRESS_BUFFER_COEFF * buffer) — a larger buffer softens the
# felt weight of the burden.
STRESS_BUFFER_COEFF = 0.05  # illustrative
DECISION_NOISE = 0.15       # ± uniform noise on the comply decision, illustrative

# Buffer dynamics (makes the adaptive model a genuine MDP): paying burden
# depletes the buffer; it recovers slowly toward its starting level each month.
BUFFER_DEPLETION_PER_BURDEN = 1.0   # months of buffer lost per (burden/monthly-capacity)
BUFFER_RECOVERY_PER_STEP = 0.15     # months recovered toward baseline each step
BUFFER_MIN = 0.0
BUFFER_MAX = 60.0


# ─── Costs & penalties ─────────────────────────────────────────────────────
BASE_COMPLIANCE_COST = 2000.0  # flat ₹ fallback when a rule has no rate, illustrative
BASE_PENALTY_AMOUNT = 5000.0   # flat ₹ fallback penalty, illustrative
DEFAULT_PENALTY_PROBABILITY = 0.3  # illustrative baseline enforcement intensity

# Flat costs scale gently with income so corporates aren't billed household-sized
# fees: cost = base * max(1, (income / COST_SCALE_PIVOT) ** COST_SCALE_EXPONENT).
COST_SCALE_PIVOT = 5.0e5
COST_SCALE_EXPONENT = 0.5  # illustrative — sub-linear scaling

# A defaulting agent's expected penalty is this multiple of the compliance cost.
PENALTY_COST_MULTIPLE = 2.0  # illustrative


# ─── Verdict thresholds ────────────────────────────────────────────────────
# The verdict is an incidence test on the EFFECTIVE TAX RATE (burden / gross
# income) of low- vs high-income households — the textbook definition of a
# regressive tax (effective rate falls as income rises). Ratio = low / high.
EFFECTIVE_RATE_REGRESSIVE_RATIO = 1.15   # low pays ≥15% higher effective rate → regressive
EFFECTIVE_RATE_PROGRESSIVE_RATIO = 0.87  # low pays ≤13% lower effective rate → progressive

# Secondary Gini-trajectory fallback (only used when no incidence signal exists).
GINI_REGRESSIVE_DELTA = 0.03
GINI_PROGRESSIVE_DELTA = -0.02


# ─── Q-learning ────────────────────────────────────────────────────────────
Q_ALPHA = 0.15          # learning rate
Q_GAMMA = 0.90          # discount — meaningful now that buffer dynamics couple steps
Q_EPSILON_START = 0.30  # initial exploration
Q_EPSILON_DECAY = 0.93  # per-step decay
Q_EPSILON_MIN = 0.02


# ─── Registry for the transparency panel ───────────────────────────────────
@dataclass(frozen=True)
class ParamInfo:
    key: str
    label: str
    value: object
    rationale: str
    tag: str  # "sourced" | "illustrative"
    group: str


def _fmt(value) -> object:
    """Make dict/enum-keyed values JSON-friendly for the API."""
    if isinstance(value, dict):
        return {(k.value if isinstance(k, AgentType) else k): v for k, v in value.items()}
    return value


PARAM_REGISTRY: list[ParamInfo] = [
    ParamInfo("SUBSISTENCE_FLOOR", "Household subsistence floor (₹/yr)", SUBSISTENCE_FLOOR,
              "Income below this is deemed unavailable to bear a levy; drives the affordability lens.",
              "illustrative", "Ability to pay"),
    ParamInfo("DISPOSABLE_FLOOR_FRACTION", "Min disposable income (fraction of gross)", DISPOSABLE_FLOOR_FRACTION,
              "Keeps the poorest households' disposable income above zero so burden ratios stay finite.",
              "illustrative", "Ability to pay"),
    ParamInfo("PROFIT_MARGIN", "Firm ability-to-pay (share of turnover)", _fmt(PROFIT_MARGIN),
              "Firms bear levies out of margin, not a household subsistence figure.",
              "illustrative", "Ability to pay"),
    ParamInfo("TAXABLE_SLICE", "Effective taxable base (fraction of income)", TAXABLE_SLICE,
              "Approximates the post-deduction base for percent rules that lack an explicit threshold.",
              "illustrative", "Tax base"),
    ParamInfo("MAX_RATE_PERCENT", "Max parsed rate (%)", MAX_RATE_PERCENT,
              "Caps a mis-parsed rate so one bad clause can't dominate the run.",
              "illustrative", "Tax base"),
    ParamInfo("COMPLIANCE_TENDENCY_MEAN", "Mean compliance tendency by type", _fmt(COMPLIANCE_TENDENCY_MEAN),
              "Direction (poorer/informal comply less) follows tax-morale literature; magnitudes are illustrative.",
              "illustrative", "Behaviour"),
    ParamInfo("BUFFER_RANGES", "Financial buffer by type (months)", _fmt(BUFFER_RANGES),
              "Savings cushion that softens the felt weight of a burden; wider for richer agents/firms.",
              "illustrative", "Behaviour"),
    ParamInfo("STRESS_BUFFER_COEFF", "Buffer→stress coefficient", STRESS_BUFFER_COEFF,
              "How much a month of buffer reduces perceived stress in the static decision rule.",
              "illustrative", "Behaviour"),
    ParamInfo("DECISION_NOISE", "Decision noise (±)", DECISION_NOISE,
              "Random slack on the comply/defect boundary so identical agents don't act identically.",
              "illustrative", "Behaviour"),
    ParamInfo("BASE_COMPLIANCE_COST", "Flat compliance cost fallback (₹)", BASE_COMPLIANCE_COST,
              "Used when a rule carries no rate; scales sub-linearly with income.",
              "illustrative", "Costs"),
    ParamInfo("PENALTY_COST_MULTIPLE", "Penalty ÷ compliance cost", PENALTY_COST_MULTIPLE,
              "Expected penalty for defaulting, relative to the cost of complying.",
              "illustrative", "Costs"),
    ParamInfo("DEFAULT_PENALTY_PROBABILITY", "Baseline enforcement probability", DEFAULT_PENALTY_PROBABILITY,
              "Chance a defaulting agent is caught and penalised in a month.",
              "illustrative", "Costs"),
    ParamInfo("EFFECTIVE_RATE_REGRESSIVE_RATIO", "Regressive threshold (low/high eff. rate)", EFFECTIVE_RATE_REGRESSIVE_RATIO,
              "Verdict = regressive when low-income households face ≥15% higher effective rate than high-income.",
              "sourced", "Verdict"),
    ParamInfo("EFFECTIVE_RATE_PROGRESSIVE_RATIO", "Progressive threshold (low/high eff. rate)", EFFECTIVE_RATE_PROGRESSIVE_RATIO,
              "Verdict = progressive when low-income households face ≤13% lower effective rate than high-income.",
              "sourced", "Verdict"),
    ParamInfo("Q_GAMMA", "Q-learning discount γ", Q_GAMMA,
              "Meaningful because buffer dynamics couple steps into a real MDP.",
              "illustrative", "Adaptive agents"),
]


def param_table() -> list[dict]:
    """Structured assumptions table for the API / UI transparency panel."""
    return [
        {"key": p.key, "label": p.label, "value": p.value,
         "rationale": p.rationale, "tag": p.tag, "group": p.group}
        for p in PARAM_REGISTRY
    ]
