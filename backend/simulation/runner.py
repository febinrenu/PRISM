"""
Phase 2/3, Module C — simulation runner: per-step metric generator, narrative
construction, and final verdict persistence.
"""
import uuid
from typing import Iterator, Optional

from models.schemas import (
    SimulationConfig,
    SimulationResult,
    SimulationStep,
)
from simulation.model import PRISMSimulationModel
from simulation.params import GINI_PROGRESSIVE_DELTA, GINI_REGRESSIVE_DELTA
from simulation.rules import SimulationRule
from storage import store

_TYPE_LABELS = {
    "low_income": "low-income households",
    "middle_income": "middle-income households",
    "high_income": "high-income households",
    "small_business": "small businesses",
    "large_corporate": "large corporates",
}


def new_simulation_id() -> str:
    return "sim_" + uuid.uuid4().hex[:8]


def iter_simulation(
    model: PRISMSimulationModel, n_steps: int
) -> Iterator[SimulationStep]:
    """Advance the model one step at a time, yielding per-step metrics."""
    for step_idx in range(n_steps):
        model.step()
        # Read the just-collected values directly. get_model_vars_dataframe()
        # rebuilds the entire history into a DataFrame every call — O(n²) over
        # a run; the raw model_vars lists give the last row in O(1).
        mv = model.datacollector.model_vars
        frame = {k: mv[k][-1] for k in mv}

        def _f(x) -> float:
            try:
                v = float(x)
            except (TypeError, ValueError):
                return 0.0
            return v if v == v and v not in (float("inf"), float("-inf")) else 0.0

        yield SimulationStep(
            step=step_idx,
            compliance_rate=round(_f(frame["compliance_rate"]), 4),
            gini_coefficient=round(_f(frame["gini_coefficient"]), 4),
            avg_burden_by_type={
                "low_income": round(_f(frame["avg_burden_low"]), 2),
                "middle_income": round(_f(frame["avg_burden_middle"]), 2),
                "high_income": round(_f(frame["avg_burden_high"]), 2),
                "small_business": round(_f(frame["avg_burden_sme"]), 2),
                "large_corporate": round(_f(frame["avg_burden_corp"]), 2),
            },
            policy_burden_index=round(_f(frame["policy_burden_index"]), 6),
            compliance_by_type={
                k: round(_f(v), 4) for k, v in frame["compliance_by_type"].items()
            },
            effective_rate_by_type={
                k: round(_f(v), 6) for k, v in frame["effective_rate_by_type"].items()
            },
            revenue_total=round(_f(frame["revenue_total"]), 2),
            revenue_compliance=round(_f(frame["revenue_compliance"]), 2),
            revenue_penalty=round(_f(frame["revenue_penalty"]), 2),
            revenue_by_type={
                k: round(_f(v), 2) for k, v in frame["revenue_by_type"].items()
            },
            mean_q_gap=round(_f(frame.get("mean_q_gap", 0.0)), 4),
        )


def verdict_for(steps: list[SimulationStep]) -> str:
    """Fallback verdict on the Gini trajectory — used only when the caller
    supplies no effective-rate incidence verdict (the preferred one)."""
    if len(steps) < 2:
        return "neutral"
    delta = steps[-1].gini_coefficient - steps[0].gini_coefficient
    if delta > GINI_REGRESSIVE_DELTA:
        return "regressive"
    if delta < GINI_PROGRESSIVE_DELTA:
        return "progressive"
    return "neutral"


def _fmt_rupees(x: float) -> str:
    """Compact ₹ formatting (lakh/crore) for narrative prose."""
    x = float(x)
    if x >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    if x >= 1e3:
        return f"₹{x / 1e3:.1f}k"
    return f"₹{x:.0f}"


def build_narrative(
    rules: list[SimulationRule],
    rules_source: str,
    steps: list[SimulationStep],
    verdict: str,
    eff_low: float,
    eff_high: float,
) -> str:
    """A deterministic, data-grounded explanation of the run — no LLM, so it is
    always available and never hallucinates. Cites the actual verdict basis
    (low- vs high-income effective rate), revenue, the heaviest rules, and
    per-class compliance, and states the modelling limits."""
    if not steps:
        return "No simulation steps were produced."

    last = steps[-1]
    n_rules = len(rules)
    src = "LLM-extracted" if rules_source == "llm" else "rule-based"

    # Which rules drove the most revenue this run.
    rev_by_type = last.revenue_by_type or {}
    total_rev = last.revenue_total

    eff_lines = []
    for t in ("low_income", "middle_income", "high_income"):
        r = last.effective_rate_by_type.get(t, 0.0)
        eff_lines.append(f"{_TYPE_LABELS[t]} {r * 100:.2f}%")
    eff_summary = ", ".join(eff_lines)

    if verdict == "regressive":
        verdict_clause = (
            f"This is **regressive**: {_TYPE_LABELS['low_income']} face an effective rate of "
            f"{eff_low * 100:.2f}% of gross income versus {eff_high * 100:.2f}% for "
            f"{_TYPE_LABELS['high_income']} — the levy takes a larger share from those least "
            f"able to bear it."
        )
    elif verdict == "progressive":
        verdict_clause = (
            f"This is **progressive**: {_TYPE_LABELS['low_income']} face {eff_low * 100:.2f}% "
            f"versus {eff_high * 100:.2f}% for {_TYPE_LABELS['high_income']}, so the burden "
            f"rises with income."
        )
    else:
        verdict_clause = (
            f"This is **broadly neutral**: effective rates are similar across income bands "
            f"({eff_low * 100:.2f}% low vs {eff_high * 100:.2f}% high)."
        )

    low_comp = round(last.compliance_by_type.get("low_income", 1.0) * 100)
    corp_comp = round(last.compliance_by_type.get("large_corporate", 1.0) * 100)

    revenue_clause = (
        f"Over {len(steps)} simulated months the {n_rules} {src} policy rule"
        f"{'s' if n_rules != 1 else ''} collect {_fmt_rupees(total_rev)} in total government "
        f"revenue"
    )
    if rev_by_type:
        top_type = max(rev_by_type, key=rev_by_type.get)
        revenue_clause += (
            f", most of it from {_TYPE_LABELS.get(top_type, top_type)} "
            f"({_fmt_rupees(rev_by_type[top_type])})."
        )
    else:
        revenue_clause += "."

    incidence_clause = (
        f"Effective tax rates by band: {eff_summary}. {verdict_clause}"
    )

    compliance_clause = (
        f"Compliance settles at {corp_comp}% for large corporates and {low_comp}% for "
        f"low-income households."
    )

    limits_clause = (
        "Figures are illustrative: incomes are drawn from calibrated log-normal "
        "distributions and behavioural/compliance parameters are documented in the "
        "model-assumptions panel, not fitted to microdata."
    )

    return " ".join([revenue_clause, incidence_clause, compliance_clause, limits_clause])


def finalize(
    simulation_id: str,
    doc_id: str,
    rules: list[SimulationRule],
    rules_source: str,
    config: SimulationConfig,
    steps: list[SimulationStep],
    n_agents: int,
    verdict: Optional[str] = None,
    eff_low: float = 0.0,
    eff_high: float = 0.0,
) -> SimulationResult:
    # Prefer the effective-rate incidence verdict (computed from final agent
    # state) when supplied; otherwise fall back to the Gini-trajectory rule.
    policy_verdict = verdict or verdict_for(steps)
    narrative = build_narrative(rules, rules_source, steps, policy_verdict, eff_low, eff_high)

    result = SimulationResult(
        simulation_id=simulation_id,
        doc_id=doc_id,
        n_agents=n_agents,
        n_steps=len(steps),
        active_rules=[r.clause_id for r in rules],
        rules_source=rules_source,  # type: ignore[arg-type]
        steps=steps,
        final_gini=steps[-1].gini_coefficient if steps else 0.0,
        final_compliance_rate=steps[-1].compliance_rate if steps else 1.0,
        policy_verdict=policy_verdict,  # type: ignore[arg-type]
        effective_rate_low=round(eff_low, 6),
        effective_rate_high=round(eff_high, 6),
        final_revenue=steps[-1].revenue_total if steps else 0.0,
        narrative=narrative,
        config=config,
    )
    store.save_simulation(result)
    return result
