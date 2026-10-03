"""
Global sensitivity of the simulated outcomes to the modelling assumptions.

Inputs (uniform ranges):
    optimal_share     share of taxpayers choosing the cheaper regime      0.25 – 1.0
    via_scale         Chapter VI-A deductions × this                       0.5 – 1.5
    top_alpha         Pareto shape of the open top income band             1.5 – 3.0
    senior_share      share of taxpayers aged 60–80                        0.0 – 0.2
    growth            nominal income growth after FY 2023-24               0.07 – 0.12

Outputs:
    cost_fa2023, cost_fa2025   simulated revenue cost of the reforms (₹ crore)
    kakwani_2026_27            progressivity of AY 2026-27 law
    insample_ratio_2023_24     simulated / reported tax payable, AY 2023-24

Morris elementary effects screen all inputs cheaply; Sobol first-order and
total indices (Saltelli sampling) quantify each input's share of output
variance. Expert-vs-extracted comparisons hold every one of these inputs
fixed, so the assumptions they vary cancel in paired differences.
"""
from typing import Callable

import numpy as np
from SALib.analyze import morris as morris_analyze
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import morris as morris_sample
from SALib.sample import sobol as sobol_sample

from simulation.backtest.run import age, income_year, macro
from simulation.engine.outcomes import concentration, gini
from simulation.engine.static import simulate
from simulation.population.cbdt import load_targets
from simulation.population.taxpayers import build
from simulation.rac import gold

PROBLEM = {
    "num_vars": 5,
    "names": ["optimal_share", "via_scale", "top_alpha", "senior_share", "growth"],
    "bounds": [[0.25, 1.0], [0.5, 1.5], [1.5, 3.0], [0.0, 0.2], [0.07, 0.12]],
}
OUTPUTS = ["cost_fa2023", "cost_fa2025", "kakwani_2026_27", "insample_ratio_2023_24"]


def model(x: np.ndarray) -> np.ndarray:
    optimal_share, via_scale, top_alpha, senior_share, growth = x
    G = gold.build_gold()
    M = macro()
    pop = build("2023-24", via_scale=via_scale, top_alpha=top_alpha)
    base_fy = income_year("2023-24")

    def aged(target_ay: str):
        fy = income_year(target_ay)
        if fy in M:
            f = M[fy]["gdp"] / M[base_fy]["gdp"]
        else:
            last = max(M)
            f = M[last]["gdp"] / M[base_fy]["gdp"] * (1 + growth) ** (int(fy[:4]) - int(last[:4]))
        return age(pop, f, 1.0, target_ay)

    def rev(law: str, p) -> float:
        return simulate(G[law], p, optimal_share, senior_share=senior_share).revenue()

    p24 = aged("2024-25")
    cost23 = (rev("2023-24", p24) - rev("2024-25", p24)) / 1e7
    p26 = aged("2026-27")
    cost25 = (rev("2025-26", p26) - rev("2026-27", p26)) / 1e7
    r26 = simulate(G["2026-27"], p26, optimal_share, senior_share=senior_share)
    kak = concentration(r26.tax, r26.weight, r26.gti) - gini(r26.gti, r26.weight)
    insample = simulate(G["2023-24"], pop, optimal_share, senior_share=senior_share).revenue()
    observed = sum(r.total_inr for r in load_targets("2023-24", "tax"))
    return np.array([cost23, cost25, kak, insample / observed])


def _evaluate(X: np.ndarray, progress: Callable[[str], None]) -> np.ndarray:
    Y = np.empty((len(X), len(OUTPUTS)))
    for i, x in enumerate(X):
        Y[i] = model(x)
        if (i + 1) % 100 == 0:
            progress(f"  {i + 1}/{len(X)} evaluations")
    return Y


def run(n_sobol: int = 128, n_morris: int = 20, seed: int = 11, progress=print) -> dict:
    progress(f"Morris screening ({n_morris} trajectories)")
    Xm = morris_sample.sample(PROBLEM, n_morris, num_levels=4, seed=seed)
    Ym = _evaluate(Xm, progress)
    morris = {}
    for k, name in enumerate(OUTPUTS):
        res = morris_analyze.analyze(PROBLEM, Xm, Ym[:, k], num_levels=4, seed=seed)
        morris[name] = {p: {"mu_star": float(res["mu_star"][i]), "sigma": float(res["sigma"][i])}
                        for i, p in enumerate(PROBLEM["names"])}
    progress(f"Sobol (Saltelli, N={n_sobol})")
    Xs = sobol_sample.sample(PROBLEM, n_sobol, calc_second_order=False, seed=seed)
    Ys = _evaluate(Xs, progress)
    sobol = {}
    for k, name in enumerate(OUTPUTS):
        res = sobol_analyze.analyze(PROBLEM, Ys[:, k], calc_second_order=False, seed=seed)
        sobol[name] = {p: {"S1": float(res["S1"][i]), "S1_conf": float(res["S1_conf"][i]),
                           "ST": float(res["ST"][i]), "ST_conf": float(res["ST_conf"][i])}
                       for i, p in enumerate(PROBLEM["names"])}
    ranges = {name: {"min": float(Ys[:, k].min()), "p5": float(np.percentile(Ys[:, k], 5)),
                     "median": float(np.median(Ys[:, k])), "p95": float(np.percentile(Ys[:, k], 95)),
                     "max": float(Ys[:, k].max())} for k, name in enumerate(OUTPUTS)}
    return {"problem": PROBLEM, "n_sobol": n_sobol, "n_morris": n_morris, "seed": seed,
            "evaluations": int(len(Xm) + len(Xs)), "morris": morris, "sobol": sobol, "output_ranges": ranges}
