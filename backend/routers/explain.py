"""
Phase 2 — LIME explainability endpoints.

GET /api/explain/{doc_id}/{clause_id}          → 200 cached result | 202 job started/running
GET /api/explain/{doc_id}/{clause_id}/stream   → SSE progress + final payload
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from config import LIME_NUM_SAMPLES
from pipeline.lime_explainer import explain_clause, _cache_fingerprint
from services import job_manager
from storage import store

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _table_payload(clause_id: str, mode: str) -> dict:
    """Explainability is not meaningful for tabular data — return a clean
    'not applicable' result instead of noise from perturbing table fragments."""
    return {
        "status": "complete",
        "clause_id": clause_id,
        "mode": mode,
        "not_applicable": "table",
        "message": "Tabular data — not analyzed as a prose clause.",
        "lime_tokens": [],
        "top_tokens": [],
        "prediction": None,
        "cached": True,
    }


def _find_clause(doc_id: str, clause_id: str):
    result = store.get_result(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")
    for clause in result.clauses:
        if clause.clause_id == clause_id:
            return clause
    raise HTTPException(status_code=404, detail=f"Clause {clause_id} not found.")


def _start_explain_job(doc_id: str, clause_id: str, clause_text: str, mode: str, num_samples: Optional[int]):
    job_key = f"lime:{doc_id}:{clause_id}:{mode}:{num_samples or LIME_NUM_SAMPLES}"
    job = job_manager.get_job(job_key)
    if job is not None and job.status == "running":
        return job_key, job

    async def _run():
        loop = asyncio.get_running_loop()

        def progress(done: int, total: int) -> None:
            loop.call_soon_threadsafe(
                job_manager.publish,
                job_key,
                {"stage": "explain_progress", "done": done, "total": total,
                 "progress": done / max(total, 1)},
            )

        payload = await loop.run_in_executor(
            None, explain_clause, doc_id, clause_id, clause_text, mode, num_samples, progress
        )
        job_manager.publish(job_key, {"stage": "explain_complete", **payload})
        return payload

    return job_key, job_manager.start(job_key, _run)


@router.get("/explain/{doc_id}/{clause_id}")
async def get_explanation(
    doc_id: str,
    clause_id: str,
    mode: str = Query("proxy", pattern="^(proxy|llm)$"),
    num_samples: Optional[int] = Query(None, ge=10, le=2000),
):
    clause = _find_clause(doc_id, clause_id)

    if clause.clause_type == "table":
        return _table_payload(clause_id, mode)

    from config import LIME_NUM_SAMPLES
    effective_samples = num_samples or LIME_NUM_SAMPLES
    cached = store.load_lime(doc_id, clause_id, mode)
    if cached is not None and cached.get("fingerprint") == _cache_fingerprint(
        clause.text, mode, effective_samples
    ):
        return {**cached, "status": "complete", "cached": True}

    job_key, job = _start_explain_job(doc_id, clause_id, clause.text, mode, num_samples)

    if job.status == "complete" and isinstance(job.result, dict):
        return {**job.result, "status": "complete"}
    if job.status == "error":
        raise HTTPException(status_code=500, detail=job.error or "Explanation failed.")

    return JSONResponse(
        status_code=202,
        content={
            "status": "running",
            "progress": round(job.progress, 4),
            "mode": mode,
            "num_samples": effective_samples,
            "stream": f"/api/explain/{doc_id}/{clause_id}/stream?mode={mode}",
        },
    )


@router.get("/explain/{doc_id}/{clause_id}/deep-reasoning")
async def get_deep_reasoning(doc_id: str, clause_id: str, force: bool = False):
    """Rich, on-demand LLM rationale for one clause. Returns 200 with the cached
    result when available; otherwise starts a background generation job and
    returns 202 with a stream URL (generation is a ~10-30s Ollama call)."""
    clause = _find_clause(doc_id, clause_id)
    if clause.clause_type == "table":
        return {
            "status": "complete", "clause_id": clause_id, "not_applicable": "table",
            "reasoning": "Tabular data — not analyzed as a prose clause.", "cached": True,
        }

    from pipeline.deep_reasoning import _fingerprint

    if not force:
        cached = store.load_deep_reasoning(doc_id, clause_id)
        if cached is not None and cached.get("fingerprint") == _fingerprint(clause.text):
            return {**cached, "status": "complete", "cached": True}

    job_key, job = _start_deep_reasoning_job(doc_id, clause_id, clause)
    if job.status == "complete" and isinstance(job.result, dict):
        return {**job.result, "status": "complete"}
    if job.status == "error":
        raise HTTPException(status_code=500, detail=job.error or "Deep reasoning failed.")

    return JSONResponse(
        status_code=202,
        content={
            "status": "running",
            "clause_id": clause_id,
            "stream": f"/api/explain/{doc_id}/{clause_id}/deep-reasoning/stream",
        },
    )


def _start_deep_reasoning_job(doc_id: str, clause_id: str, clause):
    job_key = f"deep:{doc_id}:{clause_id}"
    job = job_manager.get_job(job_key)
    if job is not None and job.status == "running":
        return job_key, job

    extraction = clause.llm_extraction.model_dump() if clause.llm_extraction else None

    async def _run():
        from pipeline.deep_reasoning import generate_deep_reasoning
        job_manager.publish(job_key, {"stage": "deep_progress", "message": "Generating rationale…"})
        payload = await generate_deep_reasoning(doc_id, clause_id, clause.text, extraction)
        job_manager.publish(job_key, {"stage": "deep_complete", **payload})
        return payload

    return job_key, job_manager.start(job_key, _run)


@router.get("/explain/{doc_id}/{clause_id}/deep-reasoning/stream")
async def stream_deep_reasoning(doc_id: str, clause_id: str):
    clause = _find_clause(doc_id, clause_id)
    if clause.clause_type == "table":
        async def table_stream():
            yield _sse({"stage": "deep_complete", "clause_id": clause_id,
                        "not_applicable": "table", "reasoning": "Tabular data.",
                        "status": "complete"})
        return StreamingResponse(
            table_stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                     "Connection": "keep-alive"},
        )

    job_key, _job = _start_deep_reasoning_job(doc_id, clause_id, clause)

    async def event_stream():
        async for event in job_manager.subscribe(job_key):
            if event is None:
                yield ": heartbeat\n\n"
            else:
                yield _sse(event)

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.get("/explain/{doc_id}/{clause_id}/attention")
async def get_attention(doc_id: str, clause_id: str):
    """Transformer attention salience for a clause — a second XAI lens beside
    LIME. Fast (CPU); computed off-loop and cached. Explains the MiniLM encoder,
    not the Phi-3.5 generator (see attention_explainer docstring)."""
    clause = _find_clause(doc_id, clause_id)
    if clause.clause_type == "table":
        return {**_table_payload(clause_id, "attention"), "mode": "attention"}

    from pipeline.attention_explainer import explain_attention
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(
        None, explain_attention, doc_id, clause_id, clause.text
    )
    return {**payload, "status": "complete"}


@router.get("/explain/{doc_id}/{clause_id}/stream")
async def stream_explanation(
    doc_id: str,
    clause_id: str,
    mode: str = Query("proxy", pattern="^(proxy|llm)$"),
    num_samples: Optional[int] = Query(None, ge=10, le=2000),
):
    clause = _find_clause(doc_id, clause_id)

    if clause.clause_type == "table":
        async def table_stream():
            yield _sse({"stage": "explain_complete", **_table_payload(clause_id, mode)})
        return StreamingResponse(
            table_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                     "Connection": "keep-alive"},
        )

    job_key, _job = _start_explain_job(doc_id, clause_id, clause.text, mode, num_samples)

    async def event_stream():
        async for event in job_manager.subscribe(job_key):
            if event is None:
                yield ": heartbeat\n\n"
            else:
                yield _sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
