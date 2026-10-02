"""Economic-correctness tests for the simulation — assert *why* the model
behaves as it does, not just that metrics fall in range.

These lock in the rigour changes:
  - flat levy → regressive for the RIGHT reason (effective rate falls with income)
  - marginal above-threshold levy → progressive
  - an above-threshold rule collects ZERO from agents below the threshold
  - government revenue is conserved (revenue == aggregate burden)
  - firms are not charged a household subsistence floor
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.agents import AgentType, PolicyAgent
from simulation.model import PRISMSimulationModel
from simulation.params import PROFIT_MARGIN, SUBSISTENCE_FLOOR
from simulation.rules import SimulationRule
from simulation.runner import build_narrative, iter_simulation

HOUSEHOLDS = {"low_income": 300, "middle_income": 200, "high_income": 100}
FULL = {**HOUSEHOLDS, "small_business": 60, "large_corporate": 15}


def _final_model(rules, agents, seed=42, n_steps=24, adaptive=False):
    model = PRISMSimulationModel(rules, agents, seed=seed, adaptive=adaptive)
    steps = list(iter_simulation(model, n_steps))
    return model, steps


def test_fixed_fee_is_regressive_by_effective_rate():
    """A flat FIXED fee (same-ish ₹ regardless of income) is the textbook
    regressive instrument: it takes a larger share of a poor household's income
    than a rich one's, so the effective rate falls as income rises. A small fee
    with no penalty keeps every household complying, isolating the incidence."""
    rules = [SimulationRule(clause_id="fee", description="fixed filing fee",
                            base_compliance_cost=500.0, penalty_probability=0.0)]
    model, _ = _final_model(rules, HOUSEHOLDS)
    low, high = model.effective_rate_gap()
    assert low > high, f"expected falling effective rate, got low={low} high={high}"
    assert model.regressivity_verdict() == "regressive"


def test_proportional_levy_is_not_baked_regressive():
    """A proportional percent levy on gross income has a ~constant effective
    rate, so it must NOT automatically read regressive — proving regressivity is
    a finding, not an artefact of the model (the old disposable-income Gini made
    every flat levy look regressive)."""
    rules = [SimulationRule(clause_id="prop", description="proportional levy",
                            rate_percent=10.0, full_base=True, penalty_probability=0.0)]
    model, _ = _final_model(rules, HOUSEHOLDS)
    # Everyone who complies pays the same fraction of gross income → the verdict
    # is not regressive (it is neutral, or progressive if the poor comply less).
    assert model.regressivity_verdict() != "regressive"


def test_marginal_high_threshold_is_progressive():
    """A levy that applies only to income ABOVE a high threshold barely touches
    low-income households (effective rate ≈ 0) while biting high-income ones —
    the effective rate rises with income → progressive."""
    rules = [SimulationRule(
        clause_id="marg", description="30% above ₹15L",
        rate_percent=30.0, threshold_value=1.5e6, threshold_kind="amount",
        marginal=True, penalty_probability=0.0,
    )]
    model, _ = _final_model(rules, HOUSEHOLDS)
    low, high = model.effective_rate_gap()
    assert high > low, f"expected rising effective rate, got low={low} high={high}"
    assert model.regressivity_verdict() == "progressive"


def test_above_threshold_collects_zero_below_threshold():
    """Directly: the rule charges nothing to an agent whose income is below the
    threshold, and a positive amount to one above it."""
    rule = SimulationRule(
        clause_id="marg", description="20% above ₹10L",
        rate_percent=20.0, threshold_value=1.0e6, threshold_kind="amount", marginal=True,
    )
    assert rule.compliance_cost_for(5.0e5) == 0.0        # below threshold → nothing
    assert rule.compliance_cost_for(2.0e6) == (2.0e6 - 1.0e6) * 0.20  # only the excess


def test_revenue_conservation():
    """Government revenue must equal the aggregate burden borne by agents
    (compliance + penalties), exactly — no money created or lost."""
    rules = [
        SimulationRule(clause_id="c1", description="levy", rate_percent=8.0),
        SimulationRule(clause_id="c2", description="fee", base_compliance_cost=1200.0,
                       penalty_probability=0.5),
    ]
    model, steps = _final_model(rules, FULL)
    agent_total = sum(a.cumulative_burden for a in model.agents)
    last = steps[-1]
    # Conservation, within the 2-decimal rounding applied to the streamed step.
    assert abs(last.revenue_total - agent_total) < 1.0
    assert abs(last.revenue_compliance + last.revenue_penalty - last.revenue_total) < 0.05
    # Per-type revenue sums to the total.
    assert abs(sum(last.revenue_by_type.values()) - last.revenue_total) < 1.0


def test_firms_not_charged_household_subsistence_floor():
    """A firm's ability-to-pay is a margin on turnover, NOT turnover minus a
    household subsistence figure (which would be a rounding error on ₹400Cr)."""
    model = PRISMSimulationModel(
        [SimulationRule(clause_id="c", description="probe", rate_percent=1.0)],
        {"large_corporate": 20}, seed=1,
    )
    for a in model.agents:
        expected = a.income * PROFIT_MARGIN[AgentType.LARGE_CORPORATE]
        assert abs(a.ability_to_pay - expected) < 1e-6
        # The household subsistence path would give ~income - 1.5e5; ensure we
        # are NOT doing that.
        assert abs(a.ability_to_pay - (a.income - SUBSISTENCE_FLOOR)) > 1.0


def test_narrative_is_populated_and_grounded():
    """The narrative must be non-trivial and cite the verdict basis + revenue
    (built deterministically, no disk write)."""
    rules = [SimulationRule(clause_id="fee", description="fixed filing fee",
                            base_compliance_cost=500.0, penalty_probability=0.0)]
    model, steps = _final_model(rules, HOUSEHOLDS)
    low, high = model.effective_rate_gap()
    verdict = model.regressivity_verdict()
    narrative = build_narrative(rules, "rule_based", steps, verdict, low, high)
    assert len(narrative) > 80
    assert "revenue" in narrative.lower()
    assert verdict in narrative.lower()
