"""
Statistics for the headline experiment.

1. Population robustness. The conclusions are computed on one calibrated
   taxpayer population. Here the modelling assumptions are re-drawn (the
   ranges of the sensitivity analysis: regime-choice share, Chapter VI-A
   deductions, top-tail shape, senior share, income growth) and the
   conclusions recomputed for the expert law and each system's law on every
   draw. Two numbers per run:
     - persistence of each flip: the share of draws in which the system's
       conclusion still differs from the expert's on the same draw;
     - the noise floor: how often the expert's own conclusion on a draw
       differs from its conclusion on the calibrated population. A flip
       caused by extraction should persist far above the noise floor.

2. Paired comparison of systems. Each (provision set, conclusion) is a
   paired binary outcome (agrees with the expert or not). Systems are
   compared with exact McNemar tests, Holm-corrected across all pairs.
"""
import json
from functools import lru_cache
from itertools import combinations
from math import comb
from typing import Optional

import numpy as np
from scipy.stats import qmc

from simulation.backtest.run import age, income_year, macro
from simulation.engine.sensitivity import PROBLEM
from simulation.engine.static import StaticResult, simulate
from simulation.experiment.conclusions import conclusions, flips
from simulation.experiment.harness import RESULTS_DIR, _previous_ay
from simulation.experiment.provision_sets import PROVISION_SETS
from simulation.population.taxpayers import build
from simulation.rac import gold
from simulation.rac.types import PITParams

SEED = 20261003


@lru_cache(maxsize=4)
def draws(n: int, seed: int = SEED) -> tuple[tuple[float, ...], ...]:
    """Scrambled Sobol points over the sensitivity ranges."""
    lo = np.array([b[0] for b in PROBLEM["bounds"]])
    hi = np.array([b[1] for b in PROBLEM["bounds"]])
    m = int(np.ceil(np.log2(max(n, 2))))
    pts = qmc.Sobol(d=len(lo), scramble=True, seed=seed).random_base2(m)[:n]
    return tuple(tuple(float(v) for v in lo + p * (hi - lo)) for p in pts)


@lru_cache(maxsize=512)
def _population(ay: str, via_scale: float, top_alpha: float, growth: float, base_ay: str = "2023-24"):
    M = macro()
    base_fy, fy = income_year(base_ay), income_year(ay)
    if fy in M:
        f = M[fy]["gdp"] / M[base_fy]["gdp"]
    else:
        last = max(M)
        f = M[last]["gdp"] / M[base_fy]["gdp"] * (1 + growth) ** (int(fy[:4]) - int(last[:4]))
    return age(build(base_ay, via_scale=via_scale, top_alpha=top_alpha), f, 1.0, ay)


def _conclusions_on(draw, expert: PITParams, system: Optional[PITParams], ay: str):
    optimal_share, via_scale, top_alpha, senior_share, growth = draw
    pop = _population(ay, round(via_scale, 6), round(top_alpha, 6), round(growth, 6))

    def run(p):
        return simulate(p, pop, optimal_share, senior_share=senior_share)

    exp_after = run(expert)
    if _previous_ay(ay) != ay:
        before = run(gold.build_gold()[_previous_ay(ay)])
    else:
        rate = exp_after.revenue() / float((pop.gti * pop.weight).sum())
        before = StaticResult(ay, pop.gti * rate, exp_after.regime, pop.gti, pop.weight, pop.gti)
    exp_c = conclusions(before, exp_after, exp_after)
    sys_c = conclusions(before, run(system), exp_after) if system is not None else None
    return exp_c, sys_c


def robustness(run: dict, n: int = 64) -> dict:
    """Population robustness of one saved experiment run (needs run['params'])."""
    ay = run["ay"]
    expert = gold.build_gold()[ay]
    system = PITParams.model_validate(run["params"]) if run.get("complete") and run.get("params") else None
    calibrated = run["population"]["conclusions_expert"]
    keys = sorted(calibrated)
    flip_counts = dict.fromkeys(keys, 0)
    noise_counts = dict.fromkeys(keys, 0)
    rates = []
    for d in draws(n):
        exp_c, sys_c = _conclusions_on(d, expert, system, ay)
        for k in keys:
            noise_counts[k] += int(exp_c[k] != calibrated[k])
        f = flips(exp_c, sys_c)
        rates.append(f["flip_rate"])
        for k in f["flipped"]:
            flip_counts[k] += 1
    flipped_here = run["population"]["flipped"]
    return {
        "set": run["set"], "system": run["system"], "draws": n, "complete": run["complete"],
        "flip_rate_calibrated": run["population"]["flip_rate"],
        "flip_rate_mean": float(np.mean(rates)), "flip_rate_range": [float(np.min(rates)), float(np.max(rates))],
        "persistence": {k: flip_counts[k] / n for k in flipped_here},
        "flips_on_some_draw_only": sorted(k for k in keys if flip_counts[k] and k not in flipped_here),
        "noise_floor": {k: noise_counts[k] / n for k in keys},
        "noise_floor_mean": float(np.mean([noise_counts[k] / n for k in keys])),
    }


def _exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def holm(pvals: dict) -> dict:
    order = sorted(pvals, key=pvals.get)
    m = len(order)
    adj, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        adj[k] = running
    return adj


def agreement_vectors(runs: list[dict]) -> dict[str, dict[tuple[str, str], int]]:
    """system → {(set, conclusion): 1 if it agrees with the expert}."""
    out: dict[str, dict] = {}
    for r in runs:
        keys = r["population"]["conclusions_expert"]
        flipped = set(r["population"]["flipped"])
        out.setdefault(r["system"], {}).update({(r["set"], k): int(k not in flipped) for k in keys})
    return out


def compare_systems(runs: list[dict]) -> dict:
    vec = agreement_vectors(runs)
    systems = sorted(vec)
    tests, pvals = {}, {}
    for a, b in combinations(systems, 2):
        common = sorted(set(vec[a]) & set(vec[b]))
        if not common:
            continue
        only_a = sum(1 for k in common if vec[a][k] and not vec[b][k])
        only_b = sum(1 for k in common if vec[b][k] and not vec[a][k])
        key = f"{a} vs {b}"
        pvals[key] = _exact_mcnemar(only_a, only_b)
        tests[key] = {"pairs": len(common), f"{a}_only_correct": only_a, f"{b}_only_correct": only_b,
                      "p_exact": pvals[key]}
    for k, p in holm(pvals).items():
        tests[k]["p_holm"] = p
    return {
        "agreement_rate": {s: float(np.mean(list(v.values()))) for s, v in vec.items()},
        "conclusions": {s: len(v) for s, v in vec.items()},
        "tests": tests,
    }


def load_runs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS_DIR.glob("*__*.json"))
            if p.stem.split("__")[0] in PROVISION_SETS]


def report(n_draws: int = 64, progress=print) -> dict:
    runs = load_runs()
    rob = []
    for r in runs:
        if "params" not in r and r.get("complete"):
            progress(f"{r['set']}/{r['system']}: no saved parameters; re-run the experiment")
            continue
        rob.append(robustness(r, n_draws))
        progress(f"{r['set']:20s} {r['system']:16s} flips {rob[-1]['flip_rate_calibrated']:.2f} "
                 f"(draws {rob[-1]['flip_rate_mean']:.2f}), noise floor {rob[-1]['noise_floor_mean']:.3f}")
    out = {"draws": n_draws, "robustness": rob, "systems": compare_systems(runs)}
    (RESULTS_DIR / "stats.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
