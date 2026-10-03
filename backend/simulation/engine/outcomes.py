"""
Distributional outcomes of a static simulation (all population-weighted).

    revenue, taxpayers with positive tax
    effective rate by decile of gross total income
    Gini of pre-tax and post-tax income
    Kakwani index        concentration(tax) − Gini(pre-tax income); > 0 progressive
    Reynolds–Smolensky   Gini(pre) − concentration(post) by pre-tax ranking
    Suits index          1 − 2·∫ L_tax(L_income); > 0 progressive
"""
import numpy as np

from simulation.engine.static import StaticResult


def _sorted(x: np.ndarray, w: np.ndarray, key: np.ndarray):
    o = np.argsort(key, kind="stable")
    return x[o], w[o]


def concentration(values: np.ndarray, weights: np.ndarray, rank_by: np.ndarray) -> float:
    """Concentration coefficient of `values` with units ranked by `rank_by`
    (equals the Gini when values == rank_by)."""
    v, w = _sorted(values.astype(float), weights.astype(float), rank_by)
    total_w, total_v = w.sum(), (v * w).sum()
    if total_w <= 0 or total_v == 0:
        return 0.0
    cum_w = np.cumsum(w) / total_w
    cum_v = np.cumsum(v * w) / total_v
    prev_w = np.concatenate([[0.0], cum_w[:-1]])
    prev_v = np.concatenate([[0.0], cum_v[:-1]])
    area = np.sum((cum_w - prev_w) * (cum_v + prev_v) / 2.0)
    return float(1.0 - 2.0 * area)


def gini(values: np.ndarray, weights: np.ndarray) -> float:
    return concentration(values, weights, values)


def suits(tax: np.ndarray, income: np.ndarray, weights: np.ndarray) -> float:
    """Suits index: 1 − 2·area under the tax-share curve plotted against
    cumulative income share (units ranked by income)."""
    o = np.argsort(income, kind="stable")
    inc, t, w = income[o] * weights[o], tax[o] * weights[o], weights[o]
    if inc.sum() <= 0 or t.sum() <= 0:
        return 0.0
    x = np.concatenate([[0.0], np.cumsum(inc) / inc.sum()])
    y = np.concatenate([[0.0], np.cumsum(t) / t.sum()])
    area = np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1]) / 2.0)
    return float(1.0 - 2.0 * area)


def decile_rates(result: StaticResult, n: int = 10) -> list[dict]:
    o = np.argsort(result.gti, kind="stable")
    gti, tax, w = result.gti[o], result.tax[o], result.weight[o]
    cum = np.cumsum(w) / w.sum()
    out = []
    for d in range(n):
        lo, hi = d / n, (d + 1) / n
        m = (cum > lo) & (cum <= hi + 1e-12)
        inc = float((gti[m] * w[m]).sum())
        t = float((tax[m] * w[m]).sum())
        out.append({"decile": d + 1, "taxpayers": float(w[m].sum()), "income": inc, "tax": t,
                    "effective_rate": t / inc if inc > 0 else 0.0,
                    "income_upper": float(gti[m].max()) if m.any() else None})
    return out


def summarise(result: StaticResult) -> dict:
    w, gti, tax = result.weight, result.gti, result.tax
    post = gti - tax
    g_pre = gini(gti, w)
    return {
        "ay": result.ay,
        "revenue": result.revenue(),
        "taxpayers_with_tax": result.taxpayers_with_tax(),
        "returns": float(w.sum()),
        "gini_pre": g_pre,
        "gini_post": gini(post, w),
        "kakwani": concentration(tax, w, gti) - g_pre,
        "reynolds_smolensky": g_pre - concentration(post, w, gti),
        "suits": suits(tax, gti, w),
        "new_regime_share": float(w[result.regime == "new"].sum() / w.sum()),
        "deciles": decile_rates(result),
    }


def band_counts(result: StaticResult, bands: list[tuple[float, float | None]]) -> list[float]:
    """Weighted number of taxpayers whose tax falls in each (lower, upper] band."""
    out = []
    for lo, hi in bands:
        m = result.tax > lo if hi is None else (result.tax > lo) & (result.tax <= hi)
        out.append(float(result.weight[m].sum()))
    return out
