# PRISM — Policy Rule Interpretation & Socioeconomic Impact Modeling

**"From Statute to Simulation"** — read the law, understand the intent, predict the impact.

PRISM is a local-first legal intelligence platform. Upload any legal PDF (Act, Bill, Policy) and it will parse, segment, and annotate the document with a legal NLP pipeline, extract structured causal rules with a **local LLM (Phi-3.5-mini via Ollama)**, explain every extraction token-by-token with **LIME**, and simulate the law's socioeconomic impact on a synthetic society with a **Mesa agent-based model** — all streamed live to a cinematic web interface.

---

## Phases

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1 — Legal Cognition Engine** | PDF parsing · clause segmentation · legal NER (6 entity types) · rule-based causal detection · MiniLM embeddings + UMAP · provenance graph · live SSE streaming | ✅ Complete |
| **Phase 2 — LLM + Simulation** | Phi-3.5-mini structured causal extraction (Module B) · LIME explainability · Mesa socioeconomic simulation (Module C) · Policy Diff Arena (Module D) | ✅ Complete |
| **Phase 3 — RAG, LoRA & Deployment** | ChromaDB RAG assistant (`/chat`) · QLoRA fine-tuning (PRISM-Legal) · multi-user auth + public `/v1` API · Docker/Vercel/Railway/Neon deploy · IEEE eval harness + gold sets + paper | ✅ Complete |

---

## Architecture

```
prism-p1/
├── backend/                       ← Python FastAPI
│   ├── main.py                    ← app entry (lifespan model preload)
│   ├── pipeline/                  ← pdf_parser · clause_segmenter · legal_ner
│   │                                causal_detector · embedder · graph_builder
│   │                                llm_extractor (Ollama) · lime_explainer
│   ├── simulation/                ← Mesa 3.x: agents · rules · model · runner
│   ├── services/job_manager.py    ← background jobs + SSE replay
│   ├── routers/                   ← upload · analyze (SSE) · data · pdf
│   │                                intelligence · llm · explain · simulate
│   ├── storage/store.py           ← disk-backed store (JSON + .npy per doc)
│   └── tests/                     ← 30 pytest tests
└── frontend/                      ← Next.js 14 App Router + TypeScript
    └── src/
        ├── app/                   ← / · /analyze/[docId] · /provenance/[docId]
        │                            /explain/[docId]/[clauseId]
        │                            /simulate/[docId] · /compare?a=&b=
        ├── components/            ← workspace · analytics · explain · simulate
        │                            compare · provenance · ui primitives
        ├── hooks/                 ← useAnalysisSession · useLLMExtraction
        │                            useExplanation · useSimulation · store
        └── lib/                   ← tokens.ts (design system) · api · sse
```

**Design system**: single source of truth in `frontend/src/lib/tokens.ts` — dark editorial theme (deep green `#06110D`, warm taupe `#C5A880`, ivory text), Playfair Display + Manrope + JetBrains Mono.

---

## Setup & Running

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Node.js | 18+ | `node --version` |
| Python | 3.10+ (3.13 tested) | `python --version` |
| Ollama | latest | `ollama --version` |

### 1. Ollama (Phase 2 LLM)

```bash
# Install from https://ollama.com, then pull the model (~2.2 GB):
ollama pull phi3.5:3.8b
# Ollama serves at http://localhost:11434 (started automatically on Windows)
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows  ·  source venv/bin/activate on Mac/Linux
pip install -r requirements.txt  # includes the spaCy model wheel
uvicorn main:app --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install                      # postinstall copies the pdf.js worker to public/
npm run dev
```

Open http://localhost:3000 — or run `start.bat` from the repo root to launch everything.

Optional env overrides: copy `backend/.env.example` → `backend/.env` (Ollama URL/model, LLM candidate cap, LIME samples).

---

## The Pipeline

1. **Parse** — PyMuPDF extracts text per page with block-level bounding boxes
2. **Segment** — structural markers split the document into clauses (offsets are exact — PDF overlays align)
3. **Legal NER** — spaCy rule pipes with per-pattern confidence: `OBLIGATION` `PENALTY` `RIGHT` `THRESHOLD` `ACTOR` `BENEFICIARY`
4. **Causal detection** — rule-based IF-THEN / CONDITION→ACTION / PENALTY_TRIGGER patterns with specificity-based confidence
5. **Embed** — all-MiniLM-L6-v2 (384-d, persisted) + UMAP 2-D projection
6. **Graph** — Document → Chapter → Section → Clause → Entity → Causal provenance graph
7. **LLM extraction** *(Phase 2)* — Phi-3.5-mini reads the highest-impact clauses and returns structured JSON rules (condition, action, consequence, actors, thresholds, confidence, reasoning); disk-cached, resumable, SSE-streamed
8. **Explain** *(Phase 2)* — LIME token attribution: fast proxy mode (~1 s) or faithful LLM mode (~1–3 min)
9. **Simulate** *(Phase 2)* — Mesa ABM: 5 socioeconomic agent types respond to extracted rules month-by-month; compliance, burden, and Gini stream live
10. **Compare** *(Phase 2)* — clause-level diff of two documents via embedding similarity + comparative simulation

All long-running stages stream over **Server-Sent Events** with heartbeats; every analysis persists to `backend/data/store/{doc_id}/` and survives restarts.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/upload` | Upload PDF → `doc_id` |
| GET/POST | `/api/demo` | Register the demo PDF (stable doc_id, cached) |
| GET | `/api/analyze/{doc_id}` | **SSE** — live pipeline (replays from cache if analyzed; `?force=true` re-runs) |
| GET | `/api/clauses/{doc_id}` · `/entities` · `/causal` · `/embeddings` · `/graph` · `/stats` | Analysis results |
| GET | `/api/pdf/{doc_id}` | Raw PDF for the in-browser viewer |
| POST | `/api/search/{doc_id}` | Semantic search (stored embeddings, <1 s) |
| GET | `/api/report/{doc_id}?fmt=json\|html` | Analysis report |
| POST | `/api/analyze/{doc_id}/llm?scope=auto\|all` | **SSE** — Phi-3.5 extraction (background job, re-attachable) |
| GET | `/api/clauses/{doc_id}/llm` | Cached LLM extractions + job status |
| GET | `/api/explain/{doc_id}/{clause_id}?mode=proxy\|llm` | LIME explanation (202 + `/stream` while running) |
| POST | `/api/simulate/{doc_id}` | Configure a simulation → `simulation_id` |
| GET | `/api/simulate/{doc_id}/stream` | **SSE** — per-step metrics |
| GET | `/api/simulate/{doc_id}/results` | Persisted simulation results |
| POST | `/api/compare` | Two-document diff (clause-level via embeddings) |
| POST | `/api/rag/ingest-all` · `/api/rag/ingest/{doc_id}` | Index documents into the ChromaDB corpus |
| GET | `/api/rag/corpus` · `/api/rag/backend` | Corpus stats · active LLM backend |
| GET | `/api/rag/stream?q=&docs=&strict=` | **SSE** — grounded, cited RAG answer |
| POST | `/api/auth/register` · `/api/auth/login` | Accounts (JWT) + per-user API key |
| GET | `/api/auth/dashboard` | User docs, simulations, API key, usage meter |
| GET | `/api/admin/metrics` · `/api/admin/users` | Admin dashboard (role: admin) |
| POST | `/v1/rag/query` · `/v1/simulate/{doc_id}` · `/v1/clauses/{doc_id}` … | Public API (Bearer `prism_sk_...`, rate-limited) |

---

## UI Tour

- **Landing (`/`)** — editorial hero, live pipeline diagram (Modules A–D), drag-and-drop upload, demo trigger
- **Analysis Workspace (`/analyze/[docId]`)** — cinematic SSE overlay → 3-column workspace: PDF viewer with clickable entity-tinted clause overlays · live clause feed with entity pills and UMAP-lasso filtering · analytics tabs (Overview, Causal, **LLM vs Rules**, Search, Entity network, UMAP scatter with lasso)
- **Explainability Studio (`/explain/[docId]/[clauseId]`)** — LIME token heatmap with hover attributions, top-token bar chart, structured LLM extraction card with radial confidence gauge and the model's own reasoning, rule-vs-LLM comparison table
- **Simulation Theater (`/simulate/[docId]`)** — agent population sliders, rule multi-select, live count-up metric cards, three streaming charts (compliance by stratum, burden distribution, Gini trajectory), verdict card with PDF export
- **Policy Diff Arena (`/compare?a=&b=`)** — side-by-side PDFs with diff-tinted overlays, word-level clause diffs, new-entity/rule detection, comparative simulation
- **Provenance Explorer (`/provenance/[docId]`)** — full-screen knowledge graph with node-type filters, causal-only mode, search, and PNG export

---

## Testing

```bash
cd backend
python -m pytest tests/ -q        # 30 tests: segmenter offsets · NER confidence
                                  # causal patterns · store persistence · LLM parsing
                                  # threshold translation · simulation determinism · diff
```

```bash
cd frontend
npx tsc --noEmit && npm run build # typecheck + production build
```

---

## Phase 3 — RAG, Fine-Tuning, Deployment & Research

### RAG Legal Assistant (`/chat`, Module D)
ChromaDB corpus built from stored clause embeddings (no re-embedding). Grounded,
source-cited answers stream from the active LLM backend; nothing outside the
corpus is invented.

```bash
# Index analysed documents, then open http://localhost:3000/chat
curl -X POST http://localhost:8000/api/rag/ingest-all
```

The LLM backend is switchable: `LLM_BACKEND=ollama` (local, default),
`ollama_finetuned` (your LoRA model), or `groq` (cloud — set `GROQ_API_KEY`).

### QLoRA Fine-Tuning (`training/`, Module E)
```bash
python training/build_dataset.py                 # distil instructions from PRISM's own extractions + LEDGAR
pip install -r training/requirements-train.txt
python training/finetune.py --smoke              # verify wiring (2 steps)
python training/finetune.py --epochs 3           # overnight on RTX 3050 (4GB)
python training/export_ollama.py                 # merge → Ollama model `prism-legal`
```

### Multi-user platform + public API (Module F)
- Auth: `/api/auth/register|login`, JWT sessions, per-user API keys, roles.
- Public API: `/v1/...` (Bearer `prism_sk_...`), rate-limited (100/hr).
- Pages: `/login` · `/dashboard` · `/corpus` · `/admin` · `/api-docs`.
- DB: Neon Postgres when `DATABASE_URL` is set, else a local SQLite file.
- Storage: Cloudflare R2 when configured, else local disk.

### Deploy
```bash
docker compose up --build        # full stack behind nginx (:80), local-parity
```
CI/CD in `.github/workflows/deploy.yml` (tests → Vercel frontend + Railway backend).
Fill secrets: `VERCEL_TOKEN`, `RAILWAY_TOKEN`, `GROQ_API_KEY`, `DATABASE_URL`, R2 keys.

### IEEE evaluation (`backend/eval/`, `paper/`, Module G)
```bash
cd backend
python -m eval.gold_builder --doc demo_income_tax_2025 --llm-questions   # 200 NER / 100 causal / 50 RAG-QA
python -m eval.review_gold --set causal                                  # human review (or --sample N / --accept-all)
python -m eval.run_benchmark --gold --with-llm --doc demo_income_tax_2025
python ../paper/make_figures.py                                          # figures for the paper
```
Draft paper: `paper/PRISM_IEEE.tex` (IEEEtran). Measured highlights: RAG
recall@1/@8 = 0.66/0.94, simulation KL 0.068 (NSSO) vs 0.234 (uncalibrated).

---

*PRISM — Final Year Project, 2026*
