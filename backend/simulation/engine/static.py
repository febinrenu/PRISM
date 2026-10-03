"""
Static microsimulation of personal income tax.

Applies a parameter set (expert or extracted) to a weighted taxpayer
population: each taxpayer files under the regime that minimises their tax
(when both are available) or the default regime, with a configurable share
choosing optimally. Outcomes are weighted aggregates and distributional
measures computed in engine/outcomes.py.

Scope (stated in the paper): normal-rate income of resident individuals.
Special-rate capital gains, surcharge on special-rate income and
non-resident cases are outside the calculator, so simulated totals are
expected to fall short of reported tax payable at the very top.
"""
from dataclasses import dataclass

import numpy as np

from simulation.population.taxpayers import Population
from simulation.rac.pit import liability
from simulation.rac.types import PITParams


@dataclass
class StaticResult:
    ay: str
    tax: np.ndarray            # per representative taxpayer
    regime: np.ndarray         # "old" / "new"
    total_income: np.ndarray
    weight: np.ndarray
    gti: np.ndarray

    def revenue(self) -> float:
        return float((self.tax * self.weight).sum())

    def taxpayers_with_tax(self) -> float:
        return float(self.weight[self.tax > 0].sum())


def simulate(params: PITParams, pop: Population, optimal_share: float = 1.0, age: str = "below_60") -> StaticResult:
    gti = pop.gti
    deductions = pop.gti * pop.via_share
    results = {}
    for regime in params.regimes:
        lia = liability(params, regime, 0.0, gti, deductions, age)
        results[regime] = lia
    if len(results) == 1:
        (regime, lia), = results.items()
        return StaticResult(pop.ay, lia.total_tax, np.full(gti.shape, regime), lia.total_income, pop.weight, gti)
    old, new = results["old"].total_tax, results["new"].total_tax
    default = params.default_regime
    chooses_new_if_optimal = new < old if default == "old" else new <= old
    # A share `optimal_share` of taxpayers picks the cheaper regime; the rest
    # stay on the default. Represented by splitting each taxpayer's weight.
    default_tax = new if default == "new" else old
    opt_tax = np.where(chooses_new_if_optimal, new, old)
    tax = optimal_share * opt_tax + (1 - optimal_share) * default_tax
    regime = np.where(chooses_new_if_optimal, "new", "old")
    ti = np.where(chooses_new_if_optimal, results["new"].total_income, results["old"].total_income)
    return StaticResult(pop.ay, tax, regime, ti, pop.weight, gti)
