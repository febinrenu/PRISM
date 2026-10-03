"""Taxpayer population, distributional outcomes and back-test plumbing."""
from pathlib import Path

import numpy as np
import pytest

from simulation.engine.outcomes import concentration, gini, suits
from simulation.population.taxpayers import _pareto_quantiles, _tilted_quantiles

TARGETS = Path(__file__).parent.parent / "simulation" / "population" / "targets"


@pytest.mark.parametrize("mean", [1.0, 3.0, 5.0, 7.0, 9.0])
def test_tilted_band_density_hits_its_mean(mean):
    q = _tilted_quantiles(0.0, 10.0, mean, 4000)
    assert q.min() >= 0 and q.max() <= 10
    assert abs(q.mean() - mean) < 0.01


def test_pareto_tail_mean():
    q = _pareto_quantiles(100.0, 250.0, 20000)
    assert q.min() >= 100 and abs(q.mean() - 250.0) / 250.0 < 0.05


def test_inequality_measures():
    w = np.ones(4)
    assert gini(np.array([1.0, 1, 1, 1]), w) == pytest.approx(0.0, abs=1e-12)
    assert gini(np.array([0.0, 0, 0, 4]), w) == pytest.approx(0.75)
    inc = np.array([1.0, 2, 3, 4])
    proportional = 0.1 * inc
    # A flat-rate tax has the income distribution's own concentration.
    assert concentration(proportional, w, inc) - gini(inc, w) == pytest.approx(0.0, abs=1e-12)
    assert suits(proportional, inc, w) == pytest.approx(0.0, abs=1e-12)
    progressive = np.array([0.0, 0, 0.3, 1.0])
    assert suits(progressive, inc, w) > 0
    assert concentration(progressive, w, inc) - gini(inc, w) > 0


@pytest.mark.skipif(not (TARGETS / "cbdt_individuals_ay2023_24.csv").exists(), reason="CBDT targets not built")
def test_population_reproduces_published_totals():
    from simulation.population.cbdt import load_targets
    from simulation.population.taxpayers import build

    pop = build("2023-24")
    rows = [r for r in load_targets("2023-24", "gti") if r.returns > 0 and r.total_inr > 0]
    assert pop.returns == pytest.approx(sum(r.returns for r in rows), rel=1e-9)
    assert pop.total_gti() == pytest.approx(sum(r.total_inr for r in rows), rel=1e-9)
    # Deductions by rank matching reproduce the gross-to-returned income gap.
    ded = float((pop.gti * pop.via_share * pop.weight).sum()) / pop.total_gti()
    published_gap = 1 - sum(r.total_inr for r in load_targets("2023-24", "returned")) / sum(
        r.total_inr for r in load_targets("2023-24", "gti"))
    assert abs(ded - published_gap) < 0.02


@pytest.mark.skipif(not (TARGETS / "cbdt_individuals_ay2023_24.csv").exists(), reason="CBDT targets not built")
def test_flat_rate_law_is_neutral():
    from simulation.engine.outcomes import summarise
    from simulation.engine.static import simulate
    from simulation.population.taxpayers import build
    from simulation.rac import gold
    from simulation.rac.types import RegimeSchedule, Slab

    flat = gold.build_gold()["2023-24"].model_copy(deep=True)
    flat.regimes = {"old": RegimeSchedule(slabs={"below_60": [Slab(lower=0, rate=0.1)]}, same_for_all_ages=True,
                                          allows_chapter_via_deductions=False)}
    flat.cess_rate = 0.0
    pop = build("2023-24")
    pop.via_share[:] = 0
    s = summarise(simulate(flat, pop))
    assert abs(s["kakwani"]) < 0.002 and abs(s["suits"]) < 0.002
