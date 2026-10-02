"""
Phase 2 Module B — LLM causal extraction endpoints.

POST /api/analyze/{doc_id}/llm   → SSE stream (starts or attaches to a job)
GET  /api/clauses/{doc_id}/llm   → instant cache read with job status
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pipeline.llm_extractor import extract_document
from services import job_manager
from storage import store

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


class LLMExtractRequest(BaseModel):
    clause_ids: Optional[list[str]] = None


@router.post("/analyze/{doc_id}/llm")
async def run_llm_extraction(
    doc_id: str,
    scope: str = "auto",
    force: bool = False,
    body: Optional[LLMExtractRequest] = None,
):
    if store.get_result(doc_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results for {doc_id}. Run /api/analyze/{doc_id} first.",
        )
    if scope not in ("auto", "all"):
        raise HTTPException(status_code=422, detail="scope must be 'auto' or 'all'")

    clause_ids = body.clause_ids if body else None
    job_key = f"llm:{doc_id}"

    job = job_manager.get_job(job_key)
    if job is None or job.status != "running":
        job_manager.start(
            job_key,
            lambda: extract_document(
                doc_id,
                scope=scope,
                clause_ids=clause_ids,
                force=force,
                publish=lambda ev: job_manager.publish(job_key, ev),
            ),
        )

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


@router.get("/clauses/{doc_id}/llm")
async def get_llm_extractions(doc_id: str):
    if store.get_result(doc_id) is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")

    job = job_manager.get_job(f"llm:{doc_id}")
    status = "idle"
    progress = 0.0
    summary = None
    if job is not None:
        status = job.status if job.status != "complete" else "complete"
        progress = job.progress
        if job.status == "complete" and isinstance(job.result, dict):
            summary = job.result

    payload = store.load_llm_extractions(doc_id)
    extractions = []
    if payload:
        for clause_id, entry in payload.get("entries", {}).items():
            extractions.append({
                "clause_id": clause_id,
                "extraction": entry["extraction"],
                "extraction_method": entry["extraction_method"],
            })
        if status == "idle" and extractions:
            status = "complete"  # cached results from a previous server run

    return {
        "doc_id": doc_id,
        "status": status,
        "progress": round(progress, 4),
        "model": payload.get("model") if payload else None,
        "extractions": extractions,
        "summary": summary,
    }
