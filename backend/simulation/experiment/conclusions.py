"""
Pre-registered policy conclusions and flip rates.

For a reform year, each parameter set (expert or extracted) is compared with
the previous year's expert law on the same population. The conclusions are
fixed in advance (this list is not tuned to results):

    revenue_direction        sign of the revenue change
    revenue_within_10pct     revenue change within ±10% of the expert's change
    progressivity_direction  sign of the change in the Kakwani index
    top_gaining_decile       decile with the largest fall in effective rate
    decile_k_direction       sign of the effective-rate change, deciles 1–10
    regime_p50 / p90 / p99   regime chosen by the taxpayer at that percentile

A system's flip rate is the share of conclusions that differ from the
expert's. If its parameters could not be assembled, every conclusion is
"no conclusion" (counted as a flip and reported separately).

Materiality (amendment of 2026-10-03). Directions are read with thresholds:
revenue ₹500 crore, decile effective rate 0.01 percentage points, Kakwani
0.001. The top gaining decile is named only when some decile gains by more
than the rate threshold (0 = none). The controlled error-injection study,
which uses no system output, showed that the original near-exact sign tests
let a one-rupee shift of a band boundary flip "direction" conclusions on
reforms whose true change is zero. The original definitions remain available
(`material=False`) and are reported alongside.
"""
import numpy as np

from simulation.engine.outcomes import concentration, decile_rates, gini
from simulation.engine.static import StaticResult


def _kakwani(r: StaticResult) -> float:
    return concentration(r.tax, r.weight, r.gti) - gini(r.gti, r.weight)


def _sign(x: float, tol: float = 1e-9) -> int:
    return 0 if abs(x) <= tol else (1 if x > 0 else -1)


def _regime_at(r: StaticResult, q: float) -> str:
    o = np.argsort(r.gti, kind="stable")
    cum = np.cumsum(r.weight[o]) / r.weight.sum()
    i = int(np.searchsorted(cum, q))
    return str(r.regime[o][min(i, len(o) - 1)])


# (revenue in rupees, effective rate as a fraction, Kakwani index)
MATERIAL = {"revenue": 500 * 1e7, "rate": 1e-4, "kakwani": 1e-3}
ORIGINAL = {"revenue": 1e5, "rate": 1e-7, "kakwani": 1e-6}


def conclusions(before: StaticResult, after: StaticResult, expert_after: StaticResult = None,
                material: bool = True) -> dict:
    tol = MATERIAL if material else ORIGINAL
    d_before = decile_rates(before)
    d_after = decile_rates(after)
    rate_change = [a["effective_rate"] - b["effective_rate"] for a, b in zip(d_after, d_before)]
    d_rev = after.revenue() - before.revenue()
    top = int(np.argmin(rate_change)) + 1
    if material and min(rate_change) > -tol["rate"]:
        top = 0                                  # no decile gains materially
    out = {
        "revenue_direction": _sign(d_rev, tol=tol["revenue"]),
        "progressivity_direction": _sign(_kakwani(after) - _kakwani(before), tol=tol["kakwani"]),
        "top_gaining_decile": top,
        **{f"decile_{k + 1}_direction": _sign(c, tol=tol["rate"]) for k, c in enumerate(rate_change)},
        "regime_p50": _regime_at(after, 0.50),
        "regime_p90": _regime_at(after, 0.90),
        "regime_p99": _regime_at(after, 0.99),
    }
    if expert_after is not None:
        expert_change = expert_after.revenue() - before.revenue()
        if abs(expert_change) > tol["revenue"]:
            out["revenue_within_10pct"] = bool(abs(d_rev - expert_change) <= 0.10 * abs(expert_change))
        else:
            out["revenue_within_10pct"] = bool(abs(d_rev) <= tol["revenue"])
    else:
        out["revenue_within_10pct"] = True
    return out


def flips(expert: dict, system: dict | None) -> dict:
    keys = sorted(expert)
    if system is None:
        return {"flip_rate": 1.0, "no_conclusion": True, "flipped": keys}
    flipped = [k for k in keys if expert[k] != system.get(k)]
    return {"flip_rate": len(flipped) / len(keys), "no_conclusion": False, "flipped": flipped}
