"""
Statute-faithful personal income-tax liability, vectorised over taxpayers.

For each taxpayer and regime, in the order the law applies them:

  1. standard deduction on salary          (s.16(ia) / 2025 Act Sch. salary)
  2. Chapter VI-A deductions, old regime    (claimed amount, capped at income)
  3. round total income to ₹10              (s.288A / 2025 Act s.537)
  4. tax on the slab schedule for the age band
  5. rebate (s.87A / 2025 Act s.156), with marginal relief where the law
     grants it: tax payable never exceeds income above the rebate limit
  6. surcharge for the band the income falls in, with marginal relief:
     tax + surcharge never exceeds the amount at the band threshold plus
     the income above that threshold
  7. health and education cess on tax + surcharge
  8. round the total to ₹10                 (s.288B)

Scope: resident individuals, income at normal rates (no special-rate
capital gains, no agricultural-income aggregation). Every component is
returned so a difference between two parameter sets can be traced to the
step that produced it.
"""
from dataclasses import dataclass

import numpy as np

from simulation.rac.types import AGE_BANDS, PITParams, RegimeSchedule

AGE_INDEX = {band: i for i, band in enumerate(AGE_BANDS)}


def round_to_10(x: np.ndarray) -> np.ndarray:
    """Nearest multiple of ten rupees; exact halves (…5) round up."""
    return np.floor(np.asarray(x, dtype=np.float64) / 10.0 + 0.5) * 10.0


def slab_tax(income: np.ndarray, slabs) -> np.ndarray:
    income = np.asarray(income, dtype=np.float64)
    tax = np.zeros_like(income)
    for s in slabs:
        top = np.inf if s.upper is None else s.upper
        tax += s.rate * np.clip(income - s.lower, 0.0, top - s.lower)
    return tax


@dataclass
class Liability:
    regime: str
    gross_income: np.ndarray
    standard_deduction: np.ndarray
    deductions: np.ndarray
    total_income: np.ndarray
    tax_on_income: np.ndarray
    rebate: np.ndarray
    surcharge: np.ndarray
    cess: np.ndarray
    total_tax: np.ndarray

    def as_dict(self) -> dict:
        return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.__dict__.items()}


def _surcharge(total_income, tax_after_rebate, sched: RegimeSchedule, slabs, age_mask_tax_at):
    """Surcharge with marginal relief at the threshold of the applicable band."""
    bands = sorted(sched.surcharge, key=lambda b: b.threshold)
    sur = np.zeros_like(total_income)
    if not bands:
        return sur
    rate = np.zeros_like(total_income)
    threshold = np.zeros_like(total_income)
    prev_rate = np.zeros_like(total_income)
    for i, b in enumerate(bands):
        hit = total_income > b.threshold
        prev_rate = np.where(hit, rate, prev_rate)
        rate = np.where(hit, b.rate, rate)
        threshold = np.where(hit, b.threshold, threshold)
    sur = rate * tax_after_rebate
    applies = rate > 0
    if np.any(applies):
        tax_at_t = age_mask_tax_at(threshold)
        cap = tax_at_t * (1.0 + prev_rate) + (total_income - threshold)
        over = applies & (tax_after_rebate + sur > cap)
        sur = np.where(over, np.maximum(cap - tax_after_rebate, 0.0), sur)
    return sur


def liability(params: PITParams, regime: str, salary, other_income=0.0, deductions=0.0,
              age="below_60", round_tax: bool = True) -> Liability:
    """Tax for arrays of taxpayers under one regime. `age` is a band name or
    an array of band names; scalars broadcast."""
    sched = params.regimes[regime]
    shape = np.broadcast_shapes(np.shape(salary), np.shape(other_income), np.shape(deductions),
                                np.shape(age), (1,))
    salary = np.broadcast_to(np.asarray(salary, dtype=np.float64), shape).astype(np.float64)
    other = np.broadcast_to(np.asarray(other_income, dtype=np.float64), shape).astype(np.float64)
    claimed = np.broadcast_to(np.asarray(deductions, dtype=np.float64), shape).astype(np.float64)
    ages = np.broadcast_to(np.asarray(age), shape)

    gross = salary + other
    std = np.minimum(salary, sched.standard_deduction)
    if regime == "old" and sched.allows_chapter_via_deductions:
        via = np.minimum(np.maximum(claimed, 0.0), np.maximum(gross - std, 0.0))
    else:
        via = np.zeros_like(gross)
    total_income = round_to_10(np.maximum(gross - std - via, 0.0))

    tax = np.zeros_like(total_income)
    masks = {}
    for band in AGE_BANDS:
        m = ages == band
        masks[band] = m
        if np.any(m):
            tax[m] = slab_tax(total_income[m], sched.slabs_for(band))

    def tax_at(income: np.ndarray) -> np.ndarray:
        out = np.zeros_like(income)
        for band, m in masks.items():
            if np.any(m):
                out[m] = slab_tax(income[m], sched.slabs_for(band))
        return out

    rebate = np.zeros_like(tax)
    r = sched.rebate
    if r is not None:
        within = total_income <= r.max_income
        rebate = np.where(within, np.minimum(tax, r.max_rebate), 0.0)
        if r.marginal_relief:
            excess = total_income - r.max_income
            relief = (~within) & (tax > excess)
            rebate = np.where(relief, tax - excess, rebate)
    tax_after = tax - rebate

    sur = _surcharge(total_income, tax_after, sched, None, tax_at)
    cess = params.cess_rate * (tax_after + sur)
    total = tax_after + sur + cess
    if round_tax:
        total = round_to_10(total)
    return Liability(regime=regime, gross_income=gross, standard_deduction=std, deductions=via,
                     total_income=total_income, tax_on_income=tax, rebate=rebate,
                     surcharge=sur, cess=cess, total_tax=total)


def optimal_regime(params: PITParams, salary, other_income=0.0, deductions=0.0,
                   age="below_60", round_tax: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(regime choice per taxpayer, tax under that choice). Where the law
    offers only one regime, that regime. Ties go to the default regime."""
    if len(params.regimes) == 1:
        only = next(iter(params.regimes))
        lia = liability(params, only, salary, other_income, deductions, age, round_tax)
        return np.full(lia.total_tax.shape, only), lia.total_tax
    old = liability(params, "old", salary, other_income, deductions, age, round_tax).total_tax
    new = liability(params, "new", salary, other_income, deductions, age, round_tax).total_tax
    if params.default_regime == "new":
        choose_new = new <= old
    else:
        choose_new = new < old
    return np.where(choose_new, "new", "old"), np.where(choose_new, new, old)
