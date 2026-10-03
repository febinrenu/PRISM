"""Clause-level attribution of expert-vs-extracted divergence."""
import pytest

from simulation.experiment.attribution import attribute, check_efficiency
from simulation.experiment.harness import baseline
from simulation.rac import gold
from simulation.rac.types import Rebate, Slab

AY = "2026-27"
TARGETS = {"new.slabs": "FA2025/s25", "new.rebate": "FA2025/s20"}


@pytest.fixture(scope="module")
def setup():
    from simulation.backtest.run import population_for
    expert = gold.build_gold()[AY]
    pop = population_for(AY)
    return expert, pop, baseline(expert, AY, pop)


def test_expert_against_itself_is_zero(setup):
    expert, pop, before = setup
    r = attribute(expert, expert.model_copy(deep=True), TARGETS, before, pop)
    assert r["players"] == []
    assert r["total"] == {"revenue_error_crore": 0.0, "decile_rate_l1": 0.0, "flips": 0.0}
    assert sorted(r["identical_targets"]) == sorted(TARGETS)


def test_injected_rate_error_is_attributed_to_the_slab_table(setup):
    expert, pop, before = setup
    system = expert.model_copy(deep=True)
    slabs = system.regimes["new"].slabs_for("below_60")
    # A 10x misreading of the top rate (30% read as 300% would be rejected;
    # 3% read as 30% is the realistic form).
    system.regimes["new"].slabs["below_60"] = [Slab(lower=s.lower, upper=s.upper, rate=min(1.0, s.rate * 10) if s.upper is None else s.rate)
                                               for s in slabs]
    r = attribute(expert, system, TARGETS, before, pop)
    assert [p["target"] for p in r["players"]] == ["new.slabs"]
    assert r["total"]["revenue_error_crore"] > 0
    assert check_efficiency(r)


def test_two_errors_split_and_sum_to_total(setup):
    expert, pop, before = setup
    system = expert.model_copy(deep=True)
    slabs = system.regimes["new"].slabs_for("below_60")
    system.regimes["new"].slabs["below_60"] = [Slab(lower=s.lower, upper=s.upper, rate=s.rate + (0.05 if s.rate >= 0.3 else 0))
                                               for s in slabs]
    rb = system.regimes["new"].rebate
    system.regimes["new"].rebate = Rebate(max_income=rb.max_income, max_rebate=rb.max_rebate, marginal_relief=False)
    r = attribute(expert, system, TARGETS, before, pop)
    assert {p["target"] for p in r["players"]} == {"new.slabs", "new.rebate"}
    assert check_efficiency(r)
    total = sum(p["revenue_error_crore"] for p in r["players"])
    assert total == pytest.approx(r["total"]["revenue_error_crore"], abs=1e-6)
    if r["total"]["flips"] > 0:
        players = {p["target"] for p in r["players"]}
        assert r["minimal_restoring_set"] and set(r["minimal_restoring_set"]) <= players
    else:
        assert r["minimal_restoring_set"] is None


def test_failed_targets_are_not_attributed(setup):
    expert, pop, before = setup
    r = attribute(expert, expert.model_copy(deep=True), TARGETS, before, pop, failed={"new.rebate"})
    assert r["failed_targets"] == ["new.rebate"]
    assert all(p["target"] != "new.rebate" for p in r["players"])


def test_mcnemar_and_holm():
    from simulation.experiment.stats import _exact_mcnemar, holm
    assert _exact_mcnemar(0, 0) == 1.0
    assert _exact_mcnemar(10, 0) == pytest.approx(2 / 2 ** 10)
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}


def test_compare_systems_pairs_on_the_same_conclusions():
    from simulation.experiment.stats import compare_systems

    def run(system, set_name, flipped):
        return {"system": system, "set": set_name,
                "population": {"conclusions_expert": {"x": 1, "y": 1, "z": 1}, "flipped": flipped}}
    out = compare_systems([run("a", "s1", []), run("b", "s1", ["x", "y"]), run("a", "s2", ["z"]), run("b", "s2", [])])
    t = out["tests"]["a vs b"]
    assert t["pairs"] == 6 and t["a_only_correct"] == 2 and t["b_only_correct"] == 1
    assert out["agreement_rate"] == {"a": 5 / 6, "b": 4 / 6}


def test_injected_error_flips_persist_across_population_draws(setup):
    from simulation.experiment.stats import robustness
    from simulation.experiment.conclusions import conclusions, flips
    from simulation.engine.static import simulate
    expert, pop, before = setup
    system = expert.model_copy(deep=True)
    system.regimes["new"].rebate = None          # the Rs. 12 lakh rebate missed entirely
    exp_after, sys_after = simulate(expert, pop), simulate(system, pop)
    exp_c = conclusions(before, exp_after, exp_after)
    f = flips(exp_c, conclusions(before, sys_after, exp_after))
    run = {"set": "FA2025_rebate_12L", "system": "t", "ay": AY, "complete": True,
           "params": system.model_dump(mode="json"),
           "population": {"conclusions_expert": exp_c, **f}}
    out = robustness(run, 8)
    assert f["flipped"] and "revenue_within_10pct" in f["flipped"]
    assert out["persistence"]["revenue_within_10pct"] == 1.0
    assert out["noise_floor"]["revenue_within_10pct"] < 0.5
