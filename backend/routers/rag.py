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

from auth.deps import can_list, can_manage, filter_corpus_stats, optional_user, readable_scope
from fastapi import Depends, APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pipeline import llm_backend
from rag import corpus_builder, query_engine, statute_index
from storage import store

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


class Turn(BaseModel):
    role: str
    content: str


class QueryBody(BaseModel):
    question: str = Field(..., max_length=2000)
    doc_ids: Optional[list[str]] = None
    strict: bool = True
    history: list[Turn] = Field(default_factory=list, max_length=20)

    def turns(self) -> list[dict]:
        return [t.model_dump() for t in self.history]


@router.get("/rag/backend")
async def get_backend():
    return llm_backend.active_backend()


@router.get("/rag/corpus")
async def get_corpus(user: dict | None = Depends(optional_user)):
    try:
        stats = filter_corpus_stats(corpus_builder.corpus_stats(), user)
        for d in stats["documents"]:
            d["kind"] = "statute" if statute_index.is_statute_doc(d["doc_id"]) else "document"
        # statutes still being indexed at startup: the UI shows a progress note
        return {**stats, "indexing": statute_index.pending()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Corpus unavailable: {e}")


@router.post("/rag/ingest/{doc_id}")
def ingest(doc_id: str, user: dict | None = Depends(optional_user)):
    if not can_list(store.get_meta(doc_id), user):
        raise HTTPException(status_code=403, detail="Only the owner can add a private document to the corpus.")
    if store.get_result(doc_id) is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")
    try:
        return corpus_builder.ingest_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rag/ingest-all")
def ingest_all(user: dict | None = Depends(optional_user)):
    """Index every analysed document the caller may see: shared ones and their own."""
    results = []
    for meta in store.list_documents():
        if not can_list(meta, user) or store.get_result(meta.doc_id) is None:
            continue
        try:
            results.append(corpus_builder.ingest_document(meta.doc_id))
        except Exception as e:
            results.append({"doc_id": meta.doc_id, "error": str(e)})
    return {"ingested": results, "corpus": corpus_builder.corpus_stats()}


@router.delete("/rag/corpus/{doc_id}")
def remove(doc_id: str, user: dict | None = Depends(optional_user)):
    from storage import store
    if statute_index.is_statute_doc(doc_id):
        raise HTTPException(status_code=400, detail="The statutes are part of PRISM; they cannot be removed from the corpus.")
    meta = store.get_meta(doc_id)
    if meta is not None and not can_manage(meta, user):
        raise HTTPException(status_code=403, detail="Only the document's owner can remove it.")
    corpus_builder.remove_document(doc_id)
    return {"removed": doc_id, "corpus": corpus_builder.corpus_stats()}


@router.post("/rag/query")
async def query(body: QueryBody, user: dict | None = Depends(optional_user)):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question.")
    scope = readable_scope(body.doc_ids, user)
    try:
        return await query_engine.answer(body.question, doc_ids=scope, strict=body.strict, history=body.turns())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _stream_response(question: str, doc_ids: Optional[list[str]], strict: bool, history: list[dict]):
    async def event_stream():
        try:
            async for event in query_engine.answer_stream(question, doc_ids=doc_ids, strict=strict,
                                                          history=history):
                yield _sse(event)
        except Exception as e:
            yield _sse({"stage": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.get("/rag/stream")
async def stream(
    q: str = Query(..., min_length=1, max_length=2000),
    docs: Optional[str] = Query(None, description="comma-separated doc_ids to filter"),
    strict: bool = Query(True),
    user: dict | None = Depends(optional_user),
):
    doc_ids = readable_scope([d for d in docs.split(",") if d] if docs else None, user)
    return _stream_response(q, doc_ids, strict, [])


@router.post("/rag/stream")
async def stream_with_history(body: QueryBody, user: dict | None = Depends(optional_user)):
    """The streaming answer with the earlier turns, so a follow-up is understood."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question.")
    return _stream_response(body.question, readable_scope(body.doc_ids, user), body.strict, body.turns())
