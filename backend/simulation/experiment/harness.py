"""
Expert vs extracted: does a system's reading of the statute give the same
taxes, and which provisions cause the differences?

For one provision set and one extraction system:
  1. extract rules from the target provisions (cached, grounded)
  2. assemble parameters (expert parameters for everything else)
  3. compute tax on a fixed synthetic taxpayer grid for every targeted regime
  4. compare with the expert parameters: exact-match rate (within Rs. 10),
     mean and maximum absolute error, and whether assembly was complete

The population-weighted outcomes (deciles, progressivity, revenue) are added
on top of this by the microsimulation; this module is the direct,
taxpayer-level check.
"""
import json
from dataclasses import asdict
from typing import Optional

import numpy as np

from config import BASE_DIR
from pipeline.extraction.units import build_units
from simulation.experiment.provision_sets import PROVISION_SETS, units_for
from simulation.rac import gold
from simulation.rac.pit import liability
from simulation.translate.assemble import assemble

RESULTS_DIR = BASE_DIR / "data" / "experiments"


def taxpayer_grid(n_random: int = 6000, seed: int = 7) -> np.ndarray:
    """Incomes from 0 to Rs. 10 crore: log-uniform draws plus dense points
    around every bound in the expert schedules (where errors bite)."""
    rng = np.random.default_rng(seed)
    pts = list(10 ** rng.uniform(4, 8, n_random))
    G = gold.build_gold()
    kinks = set()
    for p in G.values():
        for sched in p.regimes.values():
            for slabs in sched.slabs.values():
                for s in slabs:
                    for b in (s.lower, s.upper):
                        if b:
                            kinks.add(b)
            if sched.rebate:
                kinks.add(sched.rebate.max_income)
            for sb in sched.surcharge:
                kinks.add(sb.threshold)
    for k in sorted(kinks):
        for d in (-1000, -100, -10, -1, 0, 1, 10, 100, 1000, 25_000, 75_000):
            pts.append(k + d)
    return np.clip(np.array(sorted(set(pts)), dtype=np.float64), 0, None)


def _extract(system: str, units: list, use_cache: bool = True):
    if system == "rules":
        from pipeline.extraction.rule_based import extract_unit as rb
        return [rb(u)[0] for u in units]
    from pipeline.extraction.extractor import extract_unit
    return [extract_unit(u, system, use_cache=use_cache)[0] for u in units]


def run_set(set_name: str, system: str, use_cache: bool = True) -> dict:
    spec = PROVISION_SETS[set_name]
    ay = spec["ay"]
    statute, version = spec["statute"]
    units = build_units(statute, version)
    G = gold.build_gold()
    expert = G[ay]

    rules_by_target: dict[str, list] = {}
    extraction_log = []
    for target, path in spec["targets"].items():
        target_units = units_for(path, units)
        if not target_units:
            raise ValueError(f"{set_name}: no units at {path}")
        records = _extract(system, target_units, use_cache)
        rules_by_target[path] = [r for rec in records for r in rec.rules]
        extraction_log.append({
            "target": target, "path": path, "units": [u.unit_id for u in target_units],
            "status": [rec.status for rec in records],
            "rules": sum(len(rec.rules) for rec in records),
            "effects": sum(len(r.effects) for rec in records for r in rec.rules),
            "hallucinated_fields": sum(rec.hallucinated_fields for rec in records),
            "span_fields": sum(rec.total_span_fields for rec in records),
        })

    result = assemble(rules_by_target, spec["targets"], expert, ay)
    grid = taxpayer_grid()
    regimes = sorted({t.split(".")[0] for t in spec["targets"] if t.split(".")[0] in ("old", "new")})
    comparisons = {}
    failed = {r.target for r in result.review}
    for regime in regimes:
        ages = ["below_60", "60_to_80", "80_plus"] if regime == "old" else ["below_60"]
        for age in ages:
            # A target the system could not fill keeps the expert value inside
            # the assembled parameters; scoring that regime would credit the
            # system with the expert's answer. It is reported as no result.
            regime_failed = [t for t in failed if t.startswith(regime + ".")
                             and (t.count(".") < 2 or t.endswith(age) or ".slabs." not in t)]
            if regime_failed:
                comparisons[f"{regime}:{age}"] = {"no_result": True, "failed_targets": sorted(regime_failed)}
                continue
            exp_tax = liability(expert, regime, 0.0, grid, 0.0, age).total_tax
            sys_tax = liability(result.params, regime, 0.0, grid, 0.0, age).total_tax
            err = np.abs(sys_tax - exp_tax)
            comparisons[f"{regime}:{age}"] = {
                "taxpayers": int(len(grid)),
                "exact_match_rate": float(np.mean(err <= 10)),
                "mae": float(np.mean(err)),
                "max_error": float(np.max(err)),
                "mean_signed_error": float(np.mean(sys_tax - exp_tax)),
            }
    return {
        "set": set_name, "system": system, "ay": ay,
        "complete": result.complete,
        "review": [asdict(r) for r in result.review],
        "param_diff": expert.diff(result.params),
        "extraction": extraction_log,
        "comparisons": comparisons,
        "params_hash": result.params.canonical_hash(),
        "expert_hash": expert.canonical_hash(),
    }


def save(result: dict, run_id: Optional[str] = None) -> str:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{result['set']}__{result['system']}.json"
    path = RESULTS_DIR / name
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return str(path)
