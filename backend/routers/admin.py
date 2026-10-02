"""
Phase 3, Module F — admin dashboard API (role: admin only).

GET  /api/admin/metrics        → users, docs, sims, api-call counts, backend status
GET  /api/admin/users          → all registered users + their usage
POST /api/admin/backend        → switch the active LLM backend at runtime
POST /api/admin/corpus/reindex → re-index the whole shared RAG corpus
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import users
from auth.deps import require_admin
from db import database
from pipeline import llm_backend
from rag import corpus_builder
from storage import r2, store

router = APIRouter()


@router.get("/admin/metrics")
async def metrics(_admin: dict = Depends(require_admin)):
    return {
        "users": database.scalar("SELECT COUNT(*) FROM users") or 0,
        "documents": len(store.list_documents()),
        "user_documents": database.scalar("SELECT COUNT(*) FROM user_documents") or 0,
        "simulations": database.scalar("SELECT COUNT(*) FROM simulations") or 0,
        "api_calls_total": database.scalar("SELECT COUNT(*) FROM api_usage") or 0,
        "llm_backend": llm_backend.active_backend(),
        "storage": r2.status(),
        "corpus": corpus_builder.corpus_stats(),
    }


@router.get("/admin/users")
async def all_users(_admin: dict = Depends(require_admin)):
    return {"users": users.list_users()}


class BackendBody(BaseModel):
    backend: str  # ollama | ollama_finetuned | groq


@router.post("/admin/backend")
async def switch_backend(body: BackendBody, _admin: dict = Depends(require_admin)):
    """Switch the active generation backend for this process at runtime. Persist
    it to backend/.env for restarts is a manual step (documented in the UI)."""
    if body.backend not in ("ollama", "ollama_finetuned", "groq"):
        raise HTTPException(status_code=400, detail="Unknown backend.")
    import config
    config.LLM_BACKEND = body.backend
    llm_backend.LLM_BACKEND = body.backend  # module-level copy used by _resolve()
    return {"active": llm_backend.active_backend()}


@router.post("/admin/corpus/reindex")
def reindex(_admin: dict = Depends(require_admin)):
    results = []
    for meta in store.list_documents():
        if store.get_result(meta.doc_id) is None:
            continue
        try:
            results.append(corpus_builder.ingest_document(meta.doc_id))
        except Exception as e:
            results.append({"doc_id": meta.doc_id, "error": str(e)})
    return {"reindexed": results, "corpus": corpus_builder.corpus_stats()}
