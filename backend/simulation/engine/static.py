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


def simulate(params: PITParams, pop: Population, optimal_share: float = 1.0, age: str = "below_60",
             senior_share: float = 0.0) -> StaticResult:
    """`senior_share` of every taxpayer's weight is treated as aged 60-80
    (the published statistics carry no age breakdown); the result is the
    weight-averaged tax of the two age groups.

    Salaried taxpayers (the population's per-band salaried share) receive
    the simulated law's standard deduction: their salary is the reported GTI
    plus the deduction already netted out of it in the data year. The rest
    have no salary income. Each group chooses its regime separately; the
    result is the weight-averaged tax."""
    if senior_share > 0:
        young = simulate(params, pop, optimal_share, "below_60")
        old_age = simulate(params, pop, optimal_share, "60_to_80")
        tax = (1 - senior_share) * young.tax + senior_share * old_age.tax
        return StaticResult(pop.ay, tax, young.regime, young.total_income, pop.weight, pop.gti)
    share = pop.salaried_share
    if share is None or not np.any(share > 0):
        return _simulate_group(params, pop, optimal_share, age, 0.0, pop.gti)
    sal = _simulate_group(params, pop, optimal_share, age, pop.gti + pop.embedded_standard_deduction, 0.0)
    non = _simulate_group(params, pop, optimal_share, age, 0.0, pop.gti)
    tax = share * sal.tax + (1 - share) * non.tax
    regime = np.where(share >= 0.5, sal.regime, non.regime)
    ti = share * sal.total_income + (1 - share) * non.total_income
    return StaticResult(pop.ay, tax, regime, ti, pop.weight, pop.gti)


def _simulate_group(params: PITParams, pop: Population, optimal_share: float, age: str,
                    salary, other) -> StaticResult:
    gti = pop.gti
    deductions = pop.gti * pop.via_share
    results = {}
    for regime in params.regimes:
        results[regime] = liability(params, regime, salary, other, deductions, age)
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
