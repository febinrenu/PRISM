"""
Simulation sampler-fidelity check — how well the sampled agent population
reproduces its OWN target (calibrated) income distribution, via KL-divergence
per agent type.

IMPORTANT (honesty): this is an *internal consistency* check, not external
validation. It confirms that the log-normal sampler faithfully realises the
distribution we asked it to draw from — i.e. the Monte-Carlo draw isn't biased
by clamping or too few agents. A low KL does NOT mean the population matches
published Indian microdata; that would require fitting to unit-level records,
which we do not do. The calibration *targets* themselves (the per-type medians)
are approximate baselines documented in calibration.py, not fitted values.

`external_anchor()` adds one genuinely outward-facing (but explicitly caveated)
comparison — the modelled top-decile household income share vs a published
reference — so the reader can see roughly where the synthetic population sits
relative to reality, with its limitations stated.
"""
from eval.metrics import histogram, kl_divergence, log_edges
from simulation.agents import AgentType
from simulation.calibration import CALIBRATION, reference_pdf
from simulation.model import PRISMSimulationModel
from simulation.params import HOUSEHOLD_TYPES
from simulation.rules import SimulationRule


def income_kl(
    agent_config: dict[str, int] | None = None,
    seed: int = 42,
    n_bins: int = 20,
    calibration_mode: str = "nsso",
) -> dict:
    """Per-type and mean KL(sim ‖ reference) of the sampled income population."""
    agent_config = agent_config or {
        "low_income": 800, "middle_income": 600, "high_income": 300,
        "small_business": 200, "large_corporate": 80,
    }
    # A trivial rule set — we only need the agents' sampled incomes, not dynamics.
    rules = [SimulationRule(clause_id="probe", description="probe", rate_percent=1.0)]
    model = PRISMSimulationModel(rules, agent_config, seed=seed, calibration_mode=calibration_mode)

    by_type: dict[str, list[float]] = {t.value: [] for t in AgentType}
    for agent in model.agents:
        by_type[agent.agent_type.value].append(agent.income)

    per_type: dict[str, dict] = {}
    kls = []
    for agent_type in AgentType:
        incomes = by_type[agent_type.value]
        if not incomes:
            continue
        model_income = CALIBRATION[agent_type]
        edges = log_edges(model_income.clamp_lo, model_income.clamp_hi, n_bins)
        emp = histogram(incomes, edges)
        ref = reference_pdf(agent_type, edges)
        kl = kl_divergence(emp, ref)
        kls.append(kl)
        per_type[agent_type.value] = {
            "n": len(incomes),
            "kl": kl,
            "median_income": round(sorted(incomes)[len(incomes) // 2], 2),
        }

    return {
        "calibration_mode": calibration_mode,
        "interpretation": (
            "Sampler-fidelity check (sim ‖ own target). Low KL = the Monte-Carlo "
            "draw faithfully realises the calibrated log-normal; NOT external "
            "validation against microdata."
        ),
        "mean_kl": round(sum(kls) / len(kls), 4) if kls else None,
        "per_type": per_type,
    }


# India top-10% share of pre-tax national income ≈ 57% (World Inequality
# Report 2022, wid.world). Household *income* is not identical to national
# income and our agent counts are illustrative (not census weights), so this is
# a rough order-of-magnitude comparator, not a fitted match.
_REFERENCE_TOP10_SHARE = 0.57
_REFERENCE_SOURCE = "World Inequality Report 2022 (top-10% pre-tax national income share, India)"


def external_anchor(agent_config: dict[str, int] | None = None, seed: int = 42) -> dict:
    """One outward-facing comparison: the modelled top-decile household income
    share vs a published reference. Explicitly caveated — a sanity indicator,
    not a validated calibration."""
    agent_config = agent_config or {
        "low_income": 800, "middle_income": 600, "high_income": 300,
        "small_business": 200, "large_corporate": 80,
    }
    rules = [SimulationRule(clause_id="probe", description="probe", rate_percent=1.0)]
    model = PRISMSimulationModel(rules, agent_config, seed=seed, calibration_mode="nsso")

    hh_values = {t.value for t in HOUSEHOLD_TYPES}
    incomes = sorted((a.income for a in model.agents if a.agent_type.value in hh_values), reverse=True)
    if not incomes:
        return {"note": "no household agents"}

    top_n = max(1, len(incomes) // 10)
    modelled_share = sum(incomes[:top_n]) / sum(incomes)
    return {
        "metric": "top_10pct_household_income_share",
        "modelled": round(modelled_share, 4),
        "reference": _REFERENCE_TOP10_SHARE,
        "reference_source": _REFERENCE_SOURCE,
        "gap": round(modelled_share - _REFERENCE_TOP10_SHARE, 4),
        "caveat": (
            "Agent counts are illustrative, not census weights, and household "
            "income ≠ national income — treat as an order-of-magnitude sanity "
            "check, not a fitted calibration."
        ),
    }
