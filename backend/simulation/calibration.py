"""
Phase 3 — agent-population calibration to published Indian income data.

The Phase-2 simulation sampled each agent's income log-uniformly within a
hard-coded bracket. That is illustrative, not defensible: it says nothing about
where real households actually sit inside a bracket, so no quantitative impact
claim can rest on it. This module replaces that with per-agent-type **log-normal**
income distributions whose parameters are grounded in published figures. The
log-normal is the standard parametric model for income (positive support,
right-skew, Gibrat's law).

Sources (approximate — a defensible baseline, not an exact reproduction; cited
in the paper's Experimental Setup):
  - Households: PLFS 2022-23 and NSSO Consumer Expenditure Survey (MoSPI);
    all-India median household income ≈ ₹1.7L, with the upper deciles far above.
  - SME turnover: MSME Ministry Annual Report 2022-23 turnover bands.
  - Large-corporate turnover: distribution of NSE/BSE-listed company turnover.

Each entry gives (mu, sigma) of ln(annual ₹) plus a clamp band so a fat tail
can't put a "low-income household" at ₹10^10. The legacy log-uniform ranges live
in ``agents.py`` (INCOME_RANGES) and are used when SIM_CALIBRATION="legacy".

`sample_income` needs only a `random.Random` (Mesa's model.random), so the whole
run stays seed-deterministic. `reference_pdf` (SciPy log-normal) is used by the
evaluation harness to check, via KL-divergence, that the sampler faithfully
realises *this* target distribution (an internal sampler-fidelity check — NOT
external validation against microdata; see eval/sim_validity.py). The per-type
medians below are approximate baselines, not values fitted to unit-level data.
"""
import math
from dataclasses import dataclass

from simulation.agents import AgentType


@dataclass(frozen=True)
class IncomeModel:
    mu: float       # mean of ln(annual ₹)
    sigma: float    # std-dev of ln(annual ₹)
    clamp_lo: float # hard floor on a drawn income (₹)
    clamp_hi: float # hard ceiling on a drawn income (₹)


def _ln(x: float) -> float:
    return math.log(x)


# median = exp(mu). Sigma widens the right tail. Clamp bands keep draws within a
# plausible order of magnitude for the type.
CALIBRATION: dict[AgentType, IncomeModel] = {
    # median ≈ ₹1.8L, tight spread — most poor households cluster near subsistence
    AgentType.LOW_INCOME_HOUSEHOLD: IncomeModel(_ln(1.8e5), 0.35, 6.0e4, 4.0e5),
    # median ≈ ₹6L
    AgentType.MIDDLE_INCOME_HOUSEHOLD: IncomeModel(_ln(6.0e5), 0.45, 3.0e5, 1.8e6),
    # median ≈ ₹28L, wide upper tail
    AgentType.HIGH_INCOME_HOUSEHOLD: IncomeModel(_ln(2.8e6), 0.55, 1.5e6, 2.0e7),
    # SME turnover, median ≈ ₹35L, very wide (micro → mid firms)
    AgentType.SMALL_BUSINESS: IncomeModel(_ln(3.5e6), 0.90, 5.0e5, 8.0e7),
    # listed-company turnover, median ≈ ₹400Cr
    AgentType.LARGE_CORPORATE: IncomeModel(_ln(4.0e9), 0.80, 5.0e8, 3.0e10),
}


def sample_income(agent_type: AgentType, rng) -> float:
    """Draw one annual income (₹) from the calibrated log-normal for a type,
    clamped to a plausible band. `rng` is a random.Random (seed-deterministic)."""
    m = CALIBRATION[agent_type]
    value = rng.lognormvariate(m.mu, m.sigma)
    return min(max(value, m.clamp_lo), m.clamp_hi)


def reference_pdf(agent_type: AgentType, edges: list[float]) -> list[float]:
    """Reference probability mass over the given bin edges for the calibrated
    distribution (used by the KL-divergence validity metric). Returns one mass
    per bin (len(edges) - 1), normalized to sum to 1 over the clamp band."""
    from scipy.stats import lognorm  # local import: only the eval path needs SciPy

    m = CALIBRATION[agent_type]
    dist = lognorm(s=m.sigma, scale=math.exp(m.mu))
    cdf = [float(dist.cdf(e)) for e in edges]
    mass = [max(cdf[i + 1] - cdf[i], 0.0) for i in range(len(edges) - 1)]
    total = sum(mass)
    if total <= 0:
        n = len(mass)
        return [1.0 / n] * n if n else []
    return [x / total for x in mass]
