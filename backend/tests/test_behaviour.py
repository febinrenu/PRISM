"""Compliance model: basic properties."""
from dataclasses import replace

import pytest

from simulation.behaviour.compliance import BehaviourParams, run


@pytest.fixture(scope="module")
def setup():
    from simulation.backtest.run import population_for
    from simulation.rac import gold
    return gold.build_gold()["2026-27"], population_for("2026-27")


def _run(setup, **kw):
    law, pop = setup
    return run(law, pop, replace(BehaviourParams(steps=30, burn_in=15), **kw), n_agents=800, seed=3)


def test_same_seed_same_result(setup):
    assert _run(setup)["tax_gap"] == _run(setup)["tax_gap"]


def test_a_higher_penalty_never_raises_the_gap(setup):
    gaps = [_run(setup, penalty_rate=t)["tax_gap"] for t in (0.5, 1.0, 2.0, 4.0)]
    assert all(b <= a + 1e-12 for a, b in zip(gaps, gaps[1:]))
    assert gaps[-1] < gaps[0]


def test_salaried_income_that_cannot_be_concealed_is_not(setup):
    assert _run(setup, salaried_evadable=0.0)["gap_salaried"] == 0.0


def test_strong_intrinsic_morale_removes_evasion(setup):
    r = _run(setup, morale=0.999, norm_weight=0.0, morale_concentration=1000.0, audit_rate=0.03)
    assert r["tax_gap"] < 0.01
