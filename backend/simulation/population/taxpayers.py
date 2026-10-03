"""
A weighted population of individual taxpayers reproducing the published
Income Tax Return Statistics exactly.

For each gross-total-income band (lower, upper] with N returns and total
income S, taxpayers are placed at K deterministic quantiles of the
maximum-entropy density on the band with mean S/N:

    finite band     f(x) ∝ exp(λx) on [lower, upper], λ solved for the mean
    open top band   Pareto with scale `lower` and α = m / (m − lower)

Each point carries weight N/K, and the points are shifted so the band's
weighted total equals S. Weighted counts and incomes therefore match the
statistics by construction; what the population adds is a defensible shape
inside each band.

Gross total income is income after the standard deduction and before
Chapter VI-A deductions. Deductions come from rank matching the gross-total-
income and returned-income distributions (the taxpayer at a given rank of
one is placed at the same rank of the other); `via_scale` varies them in the
sensitivity analysis.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import brentq

from simulation.population.cbdt import BandRow, load_targets

POINTS_PER_BAND = 60


def _tilted_quantiles(a: float, b: float, mean: float, k: int) -> np.ndarray:
    """K quantiles of f(x) ∝ exp(λx) on [a, b] with the given mean."""
    mid = (a + b) / 2
    mean = min(max(mean, a + 1e-6 * (b - a)), b - 1e-6 * (b - a))
    u = (np.arange(k) + 0.5) / k
    if abs(mean - mid) < 1e-9 * (b - a):
        return a + u * (b - a)
    w = b - a

    def mean_of(lam: float) -> float:
        t = lam * w
        if abs(t) < 1e-8:
            return mid
        # Mean of the density ∝ exp(t s) on s ∈ [0, 1] (valid for either sign of t).
        m = 1.0 / (-np.expm1(-t)) - 1.0 / t
        return a + w * m

    lo, hi = -500.0 / w, 500.0 / w
    lam = brentq(lambda l: mean_of(l) - mean, lo, hi, xtol=1e-14 / w, maxiter=500)
    t = lam * w
    if abs(t) < 1e-8:
        return a + u * w
    # inverse CDF of exp(t s) on [0,1]: s = log(1 + u (e^t - 1)) / t
    s = np.log1p(u * np.expm1(t)) / t
    return a + s * w


def _pareto_quantiles(lower: float, mean: float, k: int) -> np.ndarray:
    alpha = mean / (mean - lower) if mean > lower else 3.0
    alpha = max(alpha, 1.05)
    u = (np.arange(k) + 0.5) / k
    return lower * (1.0 - u) ** (-1.0 / alpha)


@dataclass
class Population:
    ay: str
    gti: np.ndarray            # gross total income (after standard deduction)
    weight: np.ndarray         # number of returns represented
    via_share: np.ndarray      # Chapter VI-A deductions as a share of GTI
    band: np.ndarray           # index of the source band
    bands: list[BandRow]
    # Share of each point's weight that is salaried (table 2.2 returns with
    # salary income ÷ table 2.1 returns, same income range), and the
    # standard deduction already netted out of the reported GTI.
    salaried_share: Optional[np.ndarray] = None
    embedded_standard_deduction: float = 0.0

    @property
    def returns(self) -> float:
        return float(self.weight.sum())

    def total_gti(self) -> float:
        return float((self.gti * self.weight).sum())


def _band_points(rows: list[BandRow], points_per_band: int, top_alpha: Optional[float]):
    xs, ws, bs = [], [], []
    for bi, row in enumerate(rows):
        mean = row.total_inr / row.returns
        lower = max(row.lower, 0.0)
        if row.upper is None:
            pts = (lower * (1.0 - (np.arange(points_per_band) + 0.5) / points_per_band) ** (-1.0 / top_alpha)
                   if top_alpha is not None else _pareto_quantiles(lower, mean, points_per_band))
        else:
            pts = _tilted_quantiles(lower, row.upper, mean, points_per_band)
        w = np.full(points_per_band, row.returns / points_per_band)
        pts = pts * (row.total_inr / float((pts * w).sum()))
        if row.upper is not None:
            pts = np.clip(pts, lower, row.upper)
        xs.append(pts)
        ws.append(w)
        bs.append(np.full(points_per_band, bi))
    return np.concatenate(xs), np.concatenate(ws), np.concatenate(bs).astype(int)


def _rank_matched_deduction_share(gti: np.ndarray, w: np.ndarray, ret_rows: list[BandRow],
                                  points_per_band: int, top_alpha: Optional[float]) -> np.ndarray:
    """Chapter VI-A share by rank matching: the taxpayer at cumulative share u
    of the gross-total-income distribution is placed at the same u of the
    returned-income distribution, so deduction = GTI(u) − returned(u)."""
    rows = [r for r in ret_rows if r.returns > 0 and r.total_inr > 0]
    rx, rw, _ = _band_points(rows, points_per_band, top_alpha)
    order = np.argsort(rx)
    rx, rw = rx[order], rw[order]
    r_cum = (np.cumsum(rw) - rw / 2) / rw.sum()
    g_order = np.argsort(gti)
    g_cum = np.empty_like(gti)
    g_cum[g_order] = (np.cumsum(w[g_order]) - w[g_order] / 2) / w.sum()
    returned = np.interp(g_cum, r_cum, rx)
    share = 1.0 - returned / np.maximum(gti, 1.0)
    return np.clip(share, 0.0, 0.5)


def build(ay: str, points_per_band: int = POINTS_PER_BAND, via_scale: float = 1.0,
          top_alpha: Optional[float] = None) -> Population:
    gti_rows = [r for r in load_targets(ay, "gti") if r.returns > 0 and r.total_inr > 0]
    gti, weight, band = _band_points(gti_rows, points_per_band, top_alpha)
    via = _rank_matched_deduction_share(gti, weight, load_targets(ay, "returned"), points_per_band, top_alpha)
    return Population(ay=ay, gti=gti, weight=weight, via_share=via * via_scale, band=band, bands=gti_rows,
                      salaried_share=salaried_share(ay, gti_rows)[band],
                      embedded_standard_deduction=embedded_standard_deduction(ay))


def salaried_share(ay: str, gti_rows: list[BandRow]) -> np.ndarray:
    """Per GTI band: returns reporting salary income in the same income range
    ÷ returns in the band. The two tables share their range edges; ranking by
    salary and by GTI differ for taxpayers with large non-salary income, so
    this is an approximation (stated in the paper). 0 when the year has no
    salary table."""
    sal = {(r.lower, r.upper): r.returns for r in load_targets(ay, "salary")}
    return np.array([min(1.0, sal.get((r.lower, r.upper), 0.0) / r.returns) if r.returns else 0.0
                     for r in gti_rows])


def embedded_standard_deduction(ay: str) -> float:
    """Standard deduction (s.16(ia)) already deducted in reported GTI: Rs. 40,000
    for AY 2019-20 under the Finance Act 2018, Rs. 50,000 from AY 2020-21. The
    statistics do not split returns by regime; new-regime returns (no
    deduction before AY 2024-25) were a small minority in the data years."""
    return 40_000.0 if ay <= "2019-20" else 50_000.0
