"""
PRISM — Legal Intelligence Platform
FastAPI application entry point (Phase 1 pipeline + Phase 2 LLM/LIME/simulation).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from routers import (upload, analyze, data, pdf, intelligence, llm, explain,
                     simulate, rag, auth_routes, public_api, admin, annotate)
from storage import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("PRISM starting up...")
    indexed = store.load_index()
    print(f"[ok] Document index loaded ({indexed} documents)")

    try:
        from pipeline.legal_ner import _get_nlp
        _get_nlp()
        print("[ok] spaCy model loaded")
    except Exception as e:
        print(f"[warn] spaCy load failed: {e}")
        print("  Run: python -m spacy download en_core_web_sm")

    try:
        from pipeline.embedder import _get_model
        _get_model()
        print("[ok] Sentence transformer loaded (all-MiniLM-L6-v2)")
    except Exception as e:
        print(f"[warn] Sentence transformer load failed: {e}")

    # Phase 3: warm the RAG corpus so the first chat query is fast.
    try:
        from rag import corpus_builder
        n = corpus_builder.corpus_stats()["total_clauses"]
        print(f"[ok] RAG corpus ready ({n} clauses indexed)")
    except Exception as e:
        print(f"[warn] RAG corpus unavailable: {e}")

    # Phase 3: ensure the auth/usage tables exist (SQLite fallback if no DATABASE_URL).
    try:
        from db.database import init_db
        print(f"[ok] Database ready ({init_db()})")
    except Exception as e:
        print(f"[warn] Database init failed: {e}")

    print("PRISM ready — API docs at /docs")
    yield


app = FastAPI(
    title="PRISM Legal Intelligence API",
    description=(
        "Legal Cognition Engine — PDF parsing, clause segmentation, legal NER, "
        "causal pattern detection, semantic embeddings, LLM causal extraction, "
        "LIME explainability, and agent-based policy simulation."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 3, Module F: per-API-key rate limiting for the public /v1 surface.
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from auth.rate_limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(store.InvalidDocId)
async def _invalid_doc_id(request: Request, exc: store.InvalidDocId):
    return JSONResponse(status_code=404, content={"detail": "Document not found."})

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(data.router, prefix="/api", tags=["data"])
app.include_router(pdf.router, prefix="/api", tags=["pdf"])
app.include_router(intelligence.router, prefix="/api", tags=["intelligence"])
app.include_router(llm.router, prefix="/api", tags=["llm"])
app.include_router(explain.router, prefix="/api", tags=["explain"])
app.include_router(simulate.router, prefix="/api", tags=["simulate"])
app.include_router(rag.router, prefix="/api", tags=["rag"])
app.include_router(auth_routes.router, prefix="/api", tags=["auth"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(annotate.router, prefix="/api", tags=["annotate"])
app.include_router(public_api.router, tags=["public-v1"])  # /v1/... (no /api prefix)


@app.get("/health")
async def health():
    from pipeline import llm_backend
    return {
        "status": "ok",
        "service": "PRISM Legal Intelligence API",
        "phase": 3,
        "llm_backend": llm_backend.active_backend(),
    }


@app.get("/")
async def root():
    return {
        "message": "PRISM — Legal Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }
