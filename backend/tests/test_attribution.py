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
