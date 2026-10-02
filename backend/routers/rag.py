"""
Phase 3, Module D — RAG assistant API.

POST /api/rag/ingest/{doc_id}   → (re)index one analysed doc into the corpus
POST /api/rag/ingest-all        → index every analysed doc
GET  /api/rag/corpus            → corpus stats (docs, clause counts)
DELETE /api/rag/corpus/{doc_id} → drop a doc from the corpus
POST /api/rag/query             → non-streaming cited answer
GET  /api/rag/stream            → SSE: retrieval → answer tokens → done
GET  /api/rag/backend           → active LLM backend descriptor
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pipeline import llm_backend
from rag import corpus_builder, query_engine
from storage import store

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


class QueryBody(BaseModel):
    question: str
    doc_ids: Optional[list[str]] = None
    strict: bool = True


@router.get("/rag/backend")
async def get_backend():
    return llm_backend.active_backend()


@router.get("/rag/corpus")
async def get_corpus():
    try:
        return corpus_builder.corpus_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Corpus unavailable: {e}")


@router.post("/rag/ingest/{doc_id}")
async def ingest(doc_id: str):
    if store.get_result(doc_id) is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")
    try:
        return corpus_builder.ingest_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rag/ingest-all")
async def ingest_all():
    results = []
    for meta in store.list_documents():
        if store.get_result(meta.doc_id) is None:
            continue
        try:
            results.append(corpus_builder.ingest_document(meta.doc_id))
        except Exception as e:
            results.append({"doc_id": meta.doc_id, "error": str(e)})
    return {"ingested": results, "corpus": corpus_builder.corpus_stats()}


@router.delete("/rag/corpus/{doc_id}")
async def remove(doc_id: str):
    corpus_builder.remove_document(doc_id)
    return {"removed": doc_id, "corpus": corpus_builder.corpus_stats()}


@router.post("/rag/query")
async def query(body: QueryBody):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question.")
    try:
        return await query_engine.answer(body.question, doc_ids=body.doc_ids, strict=body.strict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/stream")
async def stream(
    q: str = Query(..., min_length=1),
    docs: Optional[str] = Query(None, description="comma-separated doc_ids to filter"),
    strict: bool = Query(True),
):
    doc_ids = [d for d in docs.split(",") if d] if docs else None

    async def event_stream():
        try:
            async for event in query_engine.answer_stream(q, doc_ids=doc_ids, strict=strict):
                yield _sse(event)
        except Exception as e:
            yield _sse({"stage": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )
