"""
Read-only access to the research results for the web app.

    GET /api/research/experiments          expert-vs-extracted runs (summary)
    GET /api/research/experiments/{set}    every system's run for one provision set
    GET /api/research/backtest             microsimulation validation
    GET /api/research/sensitivity          Sobol / Morris indices
    GET /api/research/stats                flip robustness and system comparisons
    GET /api/research/error-injection      typed errors injected into the expert law
    GET /api/research/provision-sets       the experimental design
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
