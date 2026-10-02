"""Mesa simulation — determinism and metric sanity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.model import PRISMSimulationModel, _gini
from simulation.rules import SimulationRule
from simulation.runner import iter_simulation, verdict_for

AGENTS = {
    "low_income": 100,
    "middle_income": 60,
    "high_income": 30,
    "small_business": 20,
    "large_corporate": 5,
}

RULES = [
    SimulationRule(clause_id="c1", description="income levy", rate_percent=10.0),
    SimulationRule(
        clause_id="c2",
        description="flat filing fee",
        base_compliance_cost=1500.0,
        base_penalty_amount=4000.0,
        penalty_probability=0.4,
    ),
]


def _run(seed: int, n_steps: int = 20, adaptive: bool = False):
    model = PRISMSimulationModel(RULES, AGENTS, seed=seed, adaptive=adaptive)
    return list(iter_simulation(model, n_steps))


def test_deterministic_with_fixed_seed():
    a = _run(seed=42)
    b = _run(seed=42)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b]


def test_different_seeds_differ():
    a = _run(seed=1)
    b = _run(seed=2)
    assert [s.gini_coefficient for s in a] != [s.gini_coefficient for s in b]


def test_metric_ranges():
    steps = _run(seed=42)
    for step in steps:
        assert 0.0 <= step.compliance_rate <= 1.0
        assert 0.0 <= step.gini_coefficient <= 1.0
        for value in step.avg_burden_by_type.values():
            assert value >= 0.0


def test_cumulative_burden_monotone():
    steps = _run(seed=42)
    for agent_type in AGENTS:
        series = [s.avg_burden_by_type[agent_type] for s in steps]
        assert all(b >= a - 1e-6 for a, b in zip(series, series[1:]))


def test_gini_helper():
    assert _gini([]) == 0.0
    assert _gini([0.0, 0.0]) == 0.0
    assert _gini([5.0, 5.0, 5.0]) == 0.0  # perfectly equal
    assert _gini([0.0, 0.0, 0.0, 10.0]) > 0.6  # concentrated


def test_verdict_thresholds():
    steps = _run(seed=42)
    assert verdict_for(steps) in ("progressive", "neutral", "regressive")
    assert verdict_for([]) == "neutral"
    assert verdict_for(steps[:1]) == "neutral"


# ── Q-learning adaptive agents ────────────────────────────────────────────────

def test_adaptive_deterministic():
    a = _run(seed=7, adaptive=True)
    b = _run(seed=7, adaptive=True)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b]


def test_adaptive_differs_from_static():
    static = _run(seed=7, adaptive=False)
    adaptive = _run(seed=7, adaptive=True)
    assert [s.compliance_rate for s in static] != [s.compliance_rate for s in adaptive]


def test_adaptive_learns_and_q_gap_grows():
    """Q-tables populate and the population converges (mean_q_gap > 0 by the end
    of an adaptive run, but is 0 for a static run)."""
    model = PRISMSimulationModel(RULES, AGENTS, seed=7, adaptive=True)
    steps = list(iter_simulation(model, 30))
    assert steps[-1].mean_q_gap > 0.0
    # Q-values stay finite/bounded.
    for agent in model.agents:
        for q in agent.q_table.values():
            assert all(abs(v) < 100.0 for v in q)

    static_model = PRISMSimulationModel(RULES, AGENTS, seed=7, adaptive=False)
    static_steps = list(iter_simulation(static_model, 30))
    assert static_steps[-1].mean_q_gap == 0.0
