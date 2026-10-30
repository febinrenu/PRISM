"""
Policy scenarios on a document's own rate schedule (simulation/scenario.py).

GET  /api/policy/years        the expert-coded laws, for a document with no rate table
GET  /api/policy/law          the baseline law of a document (or of one assessment year),
                              with where every parameter came from
POST /api/policy/scenario     change the law and price the change
GET  /api/policy/validation   the model against published statistics and Budget speeches
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from auth.deps import ensure_readable, optional_user
from auth.rate_limiter import SCENARIO_LIMIT, limiter
from pipeline.schedules import schedules_for_doc
from simulation import scenario
from storage import store

router = APIRouter()


class AssumptionsBody(BaseModel):
    optimal_share: float = 1.0
    via_scale: float = 1.0
    top_alpha: Optional[float] = None
    senior_share: float = 0.0
    growth: float = scenario.DEFAULT_GROWTH


class BehaviourBody(BaseModel):
    audit_rate: Optional[float] = None
    penalty_rate: Optional[float] = None
    morale: Optional[float] = None


class ScenarioBody(BaseModel):
    doc_id: Optional[str] = None
    ay: Optional[str] = None
    schedule: Optional[int] = None
    changes: dict = Field(default_factory=dict)
    assumptions: AssumptionsBody = Field(default_factory=AssumptionsBody)
    behaviour: Optional[BehaviourBody] = None
    uncertainty: int = Field(0, ge=0, le=100)


def _prefer_law(filename: str) -> Optional[str]:
    """The Income-tax Act 2025 (or its Bill) is the law of the later expert-coded years."""
    n = filename.lower()
    return "ITA2025" if "income" in n and "tax" in n and "2025" in n else None


def _candidates(doc_id: str) -> tuple[list[dict], str]:
    meta = store.get_meta(doc_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        data = schedules_for_doc(doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No PDF is stored for this document.")
    return scenario.usable_schedules(data["schedules"]), meta.filename


def _baseline(doc_id: Optional[str], ay: Optional[str], schedule: Optional[int], user) -> tuple[scenario.Baseline, list[dict]]:
    """The baseline for the request, and the document's usable tables (for a choice)."""
    tables: list[dict] = []
    if doc_id:
        ensure_readable(doc_id, user)
        tables, filename = _candidates(doc_id)
        if tables:
            chosen = tables[0] if schedule is None else next((t for t in tables if t["index"] == schedule), None)
            if chosen is None:
                raise HTTPException(status_code=422, detail="That table is not a complete rate schedule.")
            try:
                return scenario.baseline_from_schedule(chosen, filename, _prefer_law(filename)), tables
            except scenario.ScenarioError as e:
                raise HTTPException(status_code=422, detail=str(e))
    if not ay:
        raise HTTPException(status_code=422, detail="This document has no complete rate table; choose a year's law instead.")
    try:
        return scenario.baseline_from_expert(ay), tables
    except scenario.ScenarioError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _table_info(t: dict) -> dict:
    return {"index": t["index"], "page": t["page"], "heading": t["heading"], "assessment_year": t.get("assessment_year"),
            "bands": len(t["rows"])}


@router.get("/policy/years")
def years():
    from simulation.rac import gold

    out = []
    for ay, p in sorted(gold.build_gold().items()):
        if "new" in p.regimes:
            s = p.regimes["new"].slabs["below_60"]
            out.append({"ay": ay, "law": p.law, "default_regime": p.default_regime,
                        "bands": len(s), "top_rate": s[-1].rate})
    return {"years": out}


@router.get("/policy/law")
def law(doc_id: Optional[str] = Query(None), ay: Optional[str] = Query(None), schedule: Optional[int] = Query(None),
        user: dict | None = Depends(optional_user)):
    if doc_id:
        ensure_readable(doc_id, user)
        tables, _ = _candidates(doc_id)
        if not tables and not ay:
            return {"available": False, "reason": "No complete rate table was found in this document.",
                    "tables": [], "bounds": scenario.BOUNDS}
    b, tables = _baseline(doc_id, ay, schedule, user)
    return {"available": True, **b.public(), "tables": [_table_info(t) for t in tables], "bounds": scenario.BOUNDS,
            "behaviour_limits": scenario.BEHAVIOUR_LIMITS, "selected_table": b.schedule["index"] if b.schedule else None}


@router.post("/policy/scenario")
@limiter.limit(SCENARIO_LIMIT)
def run_scenario(request: Request, body: ScenarioBody, user: dict | None = Depends(optional_user)):
    b, _ = _baseline(body.doc_id, body.ay, body.schedule, user)
    try:
        return scenario.run(
            b, body.changes, scenario.Assumptions(**body.assumptions.model_dump()),
            body.behaviour.model_dump() if body.behaviour else None, body.uncertainty)
    except scenario.ScenarioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/policy/validation")
def validation():
    return scenario.validation()
