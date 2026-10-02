"""
Phase 3, Module F — public PRISM API (v1).

API-key authenticated, rate-limited endpoints for programmatic access. Every
request is metered (api_usage) for the dashboard meter. These wrap the same
pipeline the web app uses — no duplicate logic, just an authenticated surface.

    Authorization: Bearer prism_sk_...

POST /v1/documents/upload      GET /v1/documents/{doc_id}
GET  /v1/clauses/{doc_id}      GET /v1/causal/{doc_id}
GET  /v1/explain/{doc_id}/{clause_id}
POST /v1/simulate/{doc_id}     POST /v1/rag/query
GET  /v1/corpus/documents
"""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth import users
from auth.deps import api_key_user
from auth.rate_limiter import PUBLIC_RATE_LIMIT, limiter
from models.schemas import SimulationConfig
from rag import query_engine
from simulation.model import PRISMSimulationModel
from simulation.rules import build_simulation_rules
from simulation.runner import finalize, iter_simulation, new_simulation_id
from storage import store

router = APIRouter()


def _meter(user: dict, endpoint: str) -> None:
    try:
        users.log_usage(user["id"], endpoint)
    except Exception:
        pass  # metering must never break the request


def _require_result(doc_id: str):
    result = store.get_result(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")
    return result


@router.post("/v1/documents/upload")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_upload(request: Request, file: UploadFile = File(...), user: dict = Depends(api_key_user)):
    from routers.upload import ingest_pdf, read_capped  # reuse the app's ingest path

    data = await read_capped(file)
    doc_id, meta = await ingest_pdf(file.filename or "upload.pdf", data)
    users.record_document(user["id"], doc_id, meta.filename)
    _meter(user, "documents/upload")
    return {"doc_id": doc_id, "filename": meta.filename, "pages": meta.pages,
            "status": meta.status, "analyze": f"/api/analyze/{doc_id}"}


@router.post("/v1/analyze/{doc_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_analyze(request: Request, doc_id: str, force: bool = False, user: dict = Depends(api_key_user)):
    """Run the full analysis pipeline to completion (blocking) so the
    programmatic path is end-to-end: upload → analyze → clauses/causal.
    Returns the analysis stats. Replays instantly if already analysed."""
    import asyncio

    from routers.analyze import _pipeline_worker

    meta = store.get_meta(doc_id)
    pdf_path = store.get_path(doc_id)
    if not meta or not pdf_path:
        raise HTTPException(status_code=404, detail="Document not found.")

    existing = store.get_result(doc_id)
    if existing is not None and not force:
        _meter(user, "analyze")
        return {"doc_id": doc_id, "status": "complete", "cached": True, "stats": existing.stats}

    captured: dict = {}

    def emit(ev: dict) -> None:
        if ev.get("stage") == "complete":
            captured["stats"] = ev.get("stats")
        elif ev.get("stage") == "error":
            captured["error"] = ev.get("message")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _pipeline_worker, doc_id, pdf_path, meta.filename, emit)

    if "error" in captured:
        raise HTTPException(status_code=500, detail=captured["error"])
    _meter(user, "analyze")
    return {"doc_id": doc_id, "status": "complete", "cached": False, "stats": captured.get("stats")}


@router.get("/v1/documents/{doc_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_document(request: Request, doc_id: str, user: dict = Depends(api_key_user)):
    meta = store.get_meta(doc_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    _meter(user, "documents/get")
    return meta.model_dump()


@router.get("/v1/clauses/{doc_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_clauses(request: Request, doc_id: str, user: dict = Depends(api_key_user)):
    result = _require_result(doc_id)
    _meter(user, "clauses")
    return {"doc_id": doc_id, "clauses": [c.model_dump() for c in result.clauses]}


@router.get("/v1/causal/{doc_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_causal(request: Request, doc_id: str, user: dict = Depends(api_key_user)):
    result = _require_result(doc_id)
    rules = [
        {"clause_id": c.clause_id, "page": c.page, "extraction": c.llm_extraction.model_dump()}
        for c in result.clauses
        if c.llm_extraction and c.llm_extraction.is_causal
    ]
    _meter(user, "causal")
    return {"doc_id": doc_id, "count": len(rules), "causal_rules": rules}


@router.get("/v1/explain/{doc_id}/{clause_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_explain(request: Request, doc_id: str, clause_id: str, user: dict = Depends(api_key_user)):
    cached = store.load_lime(doc_id, clause_id, "proxy") or store.load_lime(doc_id, clause_id, "llm")
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached explanation. Generate it via the web app first.")
    _meter(user, "explain")
    return cached


class RAGQueryBody(BaseModel):
    question: str
    doc_ids: list[str] | None = None
    strict: bool = True


@router.post("/v1/rag/query")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_rag_query(request: Request, body: RAGQueryBody, user: dict = Depends(api_key_user)):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question.")
    _meter(user, "rag/query")
    return await query_engine.answer(body.question, doc_ids=body.doc_ids, strict=body.strict)


@router.get("/v1/corpus/documents")
@limiter.limit(PUBLIC_RATE_LIMIT)
async def v1_corpus(request: Request, user: dict = Depends(api_key_user)):
    from rag import corpus_builder

    _meter(user, "corpus")
    return corpus_builder.corpus_stats()


@router.post("/v1/simulate/{doc_id}")
@limiter.limit(PUBLIC_RATE_LIMIT)
def v1_simulate(request: Request, doc_id: str, config: SimulationConfig | None = None,
                      user: dict = Depends(api_key_user)):
    result = _require_result(doc_id)
    config = config or SimulationConfig()
    n_agents = sum(max(0, int(v)) for v in config.agent_config.values())
    if n_agents == 0:
        raise HTTPException(status_code=422, detail="Agent population is zero.")
    if n_agents > 5000 or config.n_steps > 200:
        raise HTTPException(status_code=422, detail="Exceeds public limits (≤5000 agents, ≤200 steps).")

    rules, rules_source = build_simulation_rules(result, config.rule_clause_ids)
    if not rules:
        raise HTTPException(status_code=422, detail="No executable policy rules for this document.")

    model = PRISMSimulationModel(rules, config.agent_config, config.seed,
                                 calibration_mode=config.calibration_mode, adaptive=config.adaptive)
    steps = list(iter_simulation(model, config.n_steps))
    eff_low, eff_high = model.effective_rate_gap()
    sim = finalize(new_simulation_id(), doc_id, rules, rules_source, config, steps, n_agents,
                   verdict=model.regressivity_verdict(), eff_low=eff_low, eff_high=eff_high)
    users.record_simulation(user["id"], doc_id, config.model_dump(),
                            {"final_gini": sim.final_gini, "verdict": sim.policy_verdict,
                             "final_revenue": sim.final_revenue})
    _meter(user, "simulate")
    return sim.model_dump()
