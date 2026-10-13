"""
Experiments with the compliance model (paper Appendix B).

The behavioural parameters (audit rate as perceived and enforced, risk
aversion, tax morale and its social share, the evadable share of salaries)
are not identified by any published Indian data, so the model's levels are
not predictions. What the appendix measures is relative: does reading the
penalty provision wrongly move the predicted tax gap by more or less than
the uncertainty in those parameters?

    sobol        Sobol indices of the tax gap over the eight inputs, the
                 penalty rate included (its range spans s.439(9) 50% to
                 s.439(10) 200%)
    paired       the same behavioural draws run with the expert's penalty
                 (200%, misreporting) and with the under-reporting rate
                 applied to deliberate concealment (50%)
    convergence  agent count and seeds at the default parameters
    systems      the penalty rate each extraction system reads from s.439(10)
                 (cached outputs only); a system that reads none leaves the
                 behavioural model without a penalty, i.e. no conclusion

Every run is stored as it finishes (data/experiments/behaviour_runs.jsonl),
so a long experiment resumes where it stopped.
"""
import hashlib
import json
from dataclasses import asdict, replace
from typing import Callable

import numpy as np

from simulation.behaviour.compliance import BehaviourParams, run
from simulation.experiment.harness import RESULTS_DIR

AY = "2026-27"
EXPERT_PENALTY = 2.0      # s.439(10): misreporting (deliberate concealment)
MISREAD_PENALTY = 0.5     # s.439(9): under-reporting
PROBLEM = {
    "num_vars": 8,
    "names": ["audit_rate", "initial_belief", "belief_weight", "risk_aversion", "morale", "norm_weight",
              "salaried_evadable", "penalty_rate"],
    "bounds": [[0.002, 0.03], [0.005, 0.10], [0.05, 0.5], [1.0, 4.0], [0.0, 0.95], [0.0, 1.0],
               [0.0, 0.15], [0.5, 2.0]],
}
STORE = RESULTS_DIR / "behaviour_runs.jsonl"


def _key(params: BehaviourParams, n_agents: int, seed: int) -> str:
    blob = json.dumps({**asdict(params), "n": n_agents, "seed": seed, "ay": AY}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def _load_store() -> dict:
    out = {}
    if STORE.exists():
        for line in STORE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[row["key"]] = row
    return out


class Runner:
    """Runs the model once per (parameters, agents, seed), remembering results."""

    def __init__(self, progress: Callable[[str], None] = print):
        from simulation.backtest.run import population_for
        from simulation.rac import gold
        self.law = gold.build_gold()[AY]
        self.pop = population_for(AY)
        self.done = _load_store()
        self.progress = progress
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def __call__(self, params: BehaviourParams, n_agents: int = 3000, seed: int = 0) -> dict:
        k = _key(params, n_agents, seed)
        if k not in self.done:
            r = run(self.law, self.pop, params, n_agents, seed)
            row = {"key": k, "params": asdict(params), "n": n_agents, "seed": seed,
                   **{m: r[m] for m in ("tax_gap", "evaders", "gap_salaried", "gap_other", "revenue_crore")},
                   "gap_by_decile": r["gap_by_decile"]}
            with open(STORE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            self.done[k] = row
        return self.done[k]


def _params(x) -> BehaviourParams:
    return replace(BehaviourParams(), **{n: float(v) for n, v in zip(PROBLEM["names"], x)})


def sobol(runner: Runner, n_base: int = 64, seed: int = 11) -> dict:
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample
    X = sobol_sample.sample(PROBLEM, n_base, calc_second_order=False, seed=seed)
    Y = {"tax_gap": [], "gap_other": []}
    for i, x in enumerate(X):
        r = runner(_params(x))
        for m in Y:
            Y[m].append(r[m])
        if (i + 1) % 100 == 0:
            runner.progress(f"  sobol {i + 1}/{len(X)}")
    out = {}
    for m, ys in Y.items():
        s = sobol_analyze.analyze(PROBLEM, np.array(ys), calc_second_order=False, seed=seed)
        out[m] = {n: {"S1": float(s["S1"][i]), "ST": float(s["ST"][i]), "ST_conf": float(s["ST_conf"][i])}
                  for i, n in enumerate(PROBLEM["names"])}
        out[m]["range"] = {"p5": float(np.percentile(ys, 5)), "median": float(np.median(ys)),
                           "p95": float(np.percentile(ys, 95))}
    return {"n_base": n_base, "runs": len(X), "indices": out}


def paired(runner: Runner, n_draws: int = 64, seed: int = 20261003) -> dict:
    from scipy.stats import qmc
    names, bounds = PROBLEM["names"][:-1], PROBLEM["bounds"][:-1]
    lo, hi = np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds])
    draws = lo + qmc.LatinHypercube(d=len(names), seed=seed).random(n_draws) * (hi - lo)
    rows = []
    for x in draws:
        base = replace(BehaviourParams(), **{n: float(v) for n, v in zip(names, x)})
        expert = runner(replace(base, penalty_rate=EXPERT_PENALTY))
        misread = runner(replace(base, penalty_rate=MISREAD_PENALTY))
        rows.append({"expert": expert["tax_gap"], "misread": misread["tax_gap"],
                     "difference": misread["tax_gap"] - expert["tax_gap"]})
    d = np.array([r["difference"] for r in rows])
    e = np.array([r["expert"] for r in rows])
    return {"draws": n_draws,
            "difference": {"mean": float(d.mean()), "p5": float(np.percentile(d, 5)),
                           "p95": float(np.percentile(d, 95)), "share_positive": float((d > 0).mean())},
            "expert_gap_across_draws": {"p5": float(np.percentile(e, 5)), "median": float(np.median(e)),
                                        "p95": float(np.percentile(e, 95))}}


def convergence(runner: Runner, sizes=(1000, 3000, 10_000), seeds: int = 10) -> dict:
    out = {}
    for n in sizes:
        gaps = [runner(BehaviourParams(), n_agents=n, seed=s)["tax_gap"] for s in range(seeds)]
        out[str(n)] = {"mean": float(np.mean(gaps)), "sd": float(np.std(gaps, ddof=1))}
    return out


PENALTY_PROVISION = ("ITA2025", "amended_fa2026", "ITA2025/s439/(10)")
SYSTEMS = ["gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "phi3.5", "gemma2-2b", "rules"]


def system_penalties() -> dict:
    """The penalty rate each system extracts from s.439(10), from the cache."""
    from pipeline.extraction.extractor import cached_record
    from pipeline.extraction.rule_based import extract_unit as rule_based
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import units_for
    statute, version, path = PENALTY_PROVISION
    unit = units_for(path, build_units(statute, version))[0]
    out = {}
    for system in SYSTEMS:
        rec = rule_based(unit)[0] if system == "rules" else cached_record(unit, system)
        if rec is None:
            out[system] = {"status": "not run", "penalty_rate": None}
            continue
        rates = [e.rate for r in rec.rules for e in r.effects
                 if e.kind == "penalty" and getattr(e, "rate", None) is not None]
        out[system] = {"status": rec.status, "penalty_rate": rates[0] if len(set(rates)) == 1 else None,
                       "rates_found": rates,
                       "matches_expert": bool(rates) and len(set(rates)) == 1 and abs(rates[0] - EXPERT_PENALTY) < 1e-9}
    return out


def report(progress: Callable[[str], None] = print) -> dict:
    runner = Runner(progress)
    progress("convergence")
    conv = convergence(runner)
    progress("paired expert vs misread penalty")
    pair = paired(runner)
    progress("sobol")
    sob = sobol(runner)
    out = {"ay": AY, "expert_penalty": EXPERT_PENALTY, "misread_penalty": MISREAD_PENALTY,
           "convergence": conv, "paired": pair, "sobol": sob, "problem": PROBLEM,
           "systems": system_penalties()}
    (RESULTS_DIR / "behaviour.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
