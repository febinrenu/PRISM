"""
Read-only access to the research results for the web app.

    GET /api/research/experiments          expert-vs-extracted runs (summary)
    GET /api/research/experiments/{set}    every system's run for one provision set
    GET /api/research/backtest             microsimulation validation
    GET /api/research/sensitivity          Sobol / Morris indices
    GET /api/research/stats                flip robustness and system comparisons
    GET /api/research/inspect/{set}/{system}  per provision: text, extracted effects with
                                           their quoted spans, review reason (cache only)
    GET /api/research/error-injection      typed errors injected into the expert law
    GET /api/research/provision-sets       the experimental design
    GET /api/research/story                the landing story's data snapshot
    GET /api/research/population/{ay}      effective tax rate by decile: previous vs expert law
    GET /api/research/population/{set}/{system}  the same, plus a system's reading of the reform
"""
import json

from fastapi import APIRouter, HTTPException

from simulation.experiment.harness import RESULTS_DIR
from simulation.experiment.provision_sets import PROVISION_SETS

router = APIRouter()


def _load(name: str):
    p = RESULTS_DIR / name
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{name} has not been produced yet.")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/research/provision-sets")
def provision_sets():
    return {k: {kk: vv for kk, vv in v.items() if kk != "statute"} | {"statute": "/".join(v["statute"])}
            for k, v in PROVISION_SETS.items()}


@router.get("/research/experiments")
def experiments():
    runs = []
    for p in sorted(RESULTS_DIR.glob("*__*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        pop = r.get("population", {})
        runs.append({
            "set": r["set"], "system": r["system"], "ay": r["ay"], "complete": r["complete"],
            "samples": r.get("samples", 0),
            "flip_rate": pop.get("flip_rate"), "flipped": pop.get("flipped", []),
            "revenue_change_expert_crore": pop.get("revenue_change_expert_crore"),
            "revenue_change_system_crore": pop.get("revenue_change_system_crore"),
            "kakwani_expert": pop.get("kakwani_expert"), "kakwani_system": pop.get("kakwani_system"),
            "decile_rate_l1": pop.get("decile_rate_l1"),
            "review": r.get("review", []), "param_diff": r.get("param_diff", []),
            "hallucinated_fields": sum(e["hallucinated_fields"] for e in r.get("extraction", [])),
            "span_fields": sum(e["span_fields"] for e in r.get("extraction", [])),
            "attribution": r.get("attribution"),
        })
    return {"runs": runs}


@router.get("/research/experiments/{set_name}")
def experiment_set(set_name: str):
    if set_name not in PROVISION_SETS:
        raise HTTPException(status_code=404, detail="Unknown provision set")
    return {"set": set_name, "design": provision_sets()[set_name],
            "runs": [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS_DIR.glob(f"{set_name}__*.json"))]}


@router.get("/research/backtest")
def backtest():
    return _load("backtest.json")


@router.get("/research/sensitivity")
def sensitivity():
    return _load("sensitivity.json")


@router.get("/research/stats")
def stats():
    return _load("stats.json")


@router.get("/research/error-injection")
def error_injection():
    return {"rows": _load("error_injection.json")}


def _target_value(params: dict, target: str):
    """The parameter a target sets, for display (expert vs system)."""
    if target == "cess":
        return params.get("cess_rate")
    parts = target.split(".")
    sched = params.get("regimes", {}).get(parts[0])
    if sched is None:
        return None
    if parts[1] == "slabs":
        slabs = sched["slabs"]
        if sched.get("same_for_all_ages") or len(parts) == 2:
            return slabs.get("below_60")
        return slabs.get(parts[2])
    return sched.get(parts[1])


@router.get("/research/inspect/{set_name}/{system}")
def inspect(set_name: str, system: str):
    """What a system read from each provision of a reform. Extractions come
    from the cache only: this view never calls a model."""
    from pipeline.extraction.backends import SYSTEMS
    from pipeline.extraction.extractor import cached_record
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import units_for
    from simulation.rac import gold

    if set_name not in PROVISION_SETS or (system not in SYSTEMS and system != "rules"):
        raise HTTPException(status_code=404, detail="Unknown provision set or system")
    path = RESULTS_DIR / f"{set_name}__{system}.json"
    run = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    spec = PROVISION_SETS[set_name]
    units = build_units(*spec["statute"])
    expert = gold.build_gold()[spec["ay"]].model_dump(mode="json")
    review = {r["target"]: r["reason"] for r in (run or {}).get("review", [])}
    targets = []
    for target, prov in spec["targets"].items():
        provs = []
        for u in units_for(prov, units):
            if system == "rules":
                from pipeline.extraction.rule_based import extract_unit as rb
                rec = rb(u)[0]
            else:
                rec = cached_record(u, system)
            effects = []
            for r in (rec.rules if rec else []):
                for e in r.effects:
                    d = e.model_dump(exclude={"source_span", "operation", "taxpayer"}, exclude_none=True)
                    sp = e.source_span
                    effects.append({**d, "span": [sp.start - u.start, sp.end - u.start] if sp else None,
                                    "quote": sp.text if sp else None, "modality": r.modality})
            provs.append({"path": u.path, "text": u.text, "status": rec.status if rec else "not cached",
                          "rules": len(rec.rules) if rec else 0,
                          "hallucinated_fields": rec.hallucinated_fields if rec else 0, "effects": effects})
        targets.append({"target": target, "provision": prov, "review": review.get(target),
                        "expert": _target_value(expert, target),
                        "system": _target_value(run["params"], target) if run and run.get("params") else None,
                        "units": provs})
    return {"set": set_name, "system": system, "ay": spec["ay"], "statute": "/".join(spec["statute"]),
            "complete": run["complete"] if run else None,
            "attribution": (run or {}).get("attribution"), "targets": targets}


@router.get("/research/story")
def story():
    """The snapshot written by `python -m cli story-export` (experiment
    results are not in the repository; the copy bundled with the frontend
    is the fallback)."""
    from simulation.experiment.story import CORE_OUT
    if not (RESULTS_DIR / "story.json").exists() and CORE_OUT.exists():
        return json.loads(CORE_OUT.read_text(encoding="utf-8"))
    return _load("story.json")


@router.get("/research/population/{ay}")
def population(ay: str):
    from simulation.experiment.story import ay_deciles
    from simulation.rac import gold
    if ay not in gold.build_gold():
        raise HTTPException(status_code=404, detail="No expert law for that assessment year")
    return ay_deciles(ay)


@router.get("/research/population/{set_name}/{system}")
def population_for_system(set_name: str, system: str):
    from simulation.experiment.story import decile_view
    if set_name not in PROVISION_SETS:
        raise HTTPException(status_code=404, detail="Unknown provision set")
    if not (RESULTS_DIR / f"{set_name}__{system}.json").exists():
        raise HTTPException(status_code=404, detail="No run for that system")
    return decile_view(set_name, system)
