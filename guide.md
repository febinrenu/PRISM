# PRISM — Complete User & Feature Guide

**PRISM** (Policy & Rule Intelligence for Statutory Materials) is a local-first legal-intelligence
platform. You give it a legal PDF (an Act, a bill, a regulation, an annual report) and it turns the
raw document into structured, explainable intelligence:

- **Parses** the PDF, cleans the text, and detects tables.
- **Segments** it into clauses and tags each one.
- **Extracts** legal entities (obligations, penalties, rights, thresholds, actors, beneficiaries).
- **Detects causal rules** ("if X then Y") with a fast rule engine and, optionally, a local LLM.
- **Explains** any clause token-by-token (LIME).
- **Simulates** the socioeconomic impact of the extracted rules on a synthetic population.
- **Compares** two versions of a law clause-by-clause.
- **Visualises** the whole thing as a knowledge graph and a semantic map.

Everything runs on your machine. No cloud, no data leaves the box.

---

## Table of contents

1. [Architecture at a glance](#1-architecture-at-a-glance)
2. [Prerequisites](#2-prerequisites)
3. [Launching the app](#3-launching-the-app)
4. [Step-by-step walkthrough (with examples)](#4-step-by-step-walkthrough-with-examples)
   - [Step 1 — Landing page: upload or demo](#step-1--landing-page-upload-or-demo)
   - [Step 2 — Analysis pipeline (live)](#step-2--analysis-pipeline-live)
   - [Step 3 — The Workspace](#step-3--the-workspace)
   - [Step 4 — Analytics tabs](#step-4--analytics-tabs)
   - [Step 5 — LLM extraction](#step-5--llm-extraction)
   - [Step 6 — Explainability Studio](#step-6--explainability-studio)
   - [Step 7 — Simulation Theater](#step-7--simulation-theater)
   - [Step 8 — Policy Diff Arena (Compare)](#step-8--policy-diff-arena-compare)
   - [Step 9 — Provenance graph](#step-9--provenance-graph)
   - [Step 10 — Export a report](#step-10--export-a-report)
5. [Complete feature reference](#5-complete-feature-reference)
6. [Data & persistence](#6-data--persistence)
7. [Troubleshooting](#7-troubleshooting)
8. [How to make PRISM better (roadmap)](#8-how-to-make-prism-better-roadmap)

---

## 1. Architecture at a glance

```
┌─────────────────────────────┐         ┌──────────────────────────────────────┐
│  Frontend (Next.js 14)      │  HTTP/  │  Backend (FastAPI, Python)             │
│  http://localhost:3000      │  SSE    │  http://localhost:8000                 │
│                             │ ──────► │                                        │
│  • Upload / demo            │         │  Pipeline:  PDF → clauses → NER →      │
│  • Workspace + analytics    │ ◄────── │             causal → embeddings → graph│
│  • Explainability Studio    │  events │  Modules:   LLM (Ollama phi3.5),       │
│  • Simulation Theater       │         │             LIME, Mesa simulation,     │
│  • Compare / Provenance     │         │             semantic search, compare   │
└─────────────────────────────┘         └───────────────┬────────────────────────┘
                                                         │
                                          ┌──────────────▼───────────────┐
                                          │ Ollama (localhost:11434)      │
                                          │ phi3.5:3.8b  (LLM reasoning)  │
                                          └───────────────────────────────┘
```

- **Backend** exposes a REST + Server-Sent-Events (SSE) API. Long jobs (analysis, LLM extraction,
  LIME, simulation) stream progress as SSE events so the UI updates live.
- **Ollama** is only needed for the LLM-powered features (LLM extraction tab, LIME "faithful" mode,
  and the highest-quality simulation rules). Everything else — parsing, NER, rule-based causal
  detection, search, compare, rule-based simulation — works **without** Ollama.
- **Persistence**: every analysed document is written to `backend/data/store/{doc_id}/` so results
  survive restarts and reload instantly (see [§6](#6-data--persistence)).

---

## 2. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| **Python 3.10+** | backend | `python --version` |
| **Node.js 18+** | frontend | `node --version` |
| **Ollama** + `phi3.5:3.8b` | LLM extraction, LIME-faithful, best simulation rules | `ollama list` |
| ~4 GB free VRAM (or CPU) | running phi3.5 locally | — |

Install the model once:

```bash
ollama pull phi3.5:3.8b
```

> **You can use PRISM without Ollama.** Parsing, entities, rule-based causal detection, search,
> compare, the knowledge graph, and rule-based simulation all work. The **LLM tab**, **LIME
> "faithful" mode**, and LLM-sourced simulation rules simply won't be available and the UI will say
> so instead of crashing.

---

## 3. Launching the app

From the project root (`C:\Users\fkr77\Downloads\prism-p1`), double-click **`start.bat`** (or run
it in a terminal).

**What it does, in order:**

1. Checks Python and Node are installed.
2. Frees ports 8000, 3000, 3001, 3002 of any stale PRISM processes.
3. Opens a **"PRISM Backend"** window → runs `backend\run_backend.bat`, which installs Python deps,
   ensures the spaCy model, and starts uvicorn on `http://localhost:8000`.
4. Installs frontend deps (first run only) and opens a **"PRISM Frontend"** window → `npm run dev`
   on `http://localhost:3000`.

**What to expect:**

- Two terminal windows appear. The backend window ends with:
  `Uvicorn running on http://127.0.0.1:8000` and `PRISM ready — API docs at /docs`.
- The frontend window ends with `✓ Ready in Xs`.
- Open **http://localhost:3000** in your browser.
- First launch is slower (dependency install + model downloads). Subsequent launches are quick.

**Useful URLs:**

- App: `http://localhost:3000`
- API docs (interactive Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health` → `{"status":"ok",...}`

> If the frontend loads forever showing "missing required error components", delete
> `frontend\.next` and relaunch — that's a corrupted dev cache, not a code problem.

---

## 4. Step-by-step walkthrough (with examples)

We'll use two running examples:

- **Example A — the bundled demo**: `income_tax_2025.pdf` (a large, 624-page statute). Good for
  showing scale.
- **Example B — a small Act**: a one-page "Micro Enterprises Levy Act 2026" with sections 1–6
  (short title, levy, filing obligation, exemption, penalty, audit). Good for showing the full
  pipeline end-to-end quickly.

### Step 1 — Landing page: upload or demo

**Where:** `http://localhost:3000/` (`frontend/src/app/page.tsx`)

**What you see:** a hero with a drag-and-drop **upload zone** and a **"Try the demo"** button.

**Two ways in:**

- **Upload**: drag a `.pdf` (≤ 50 MB) onto the zone, or click to browse.
  → `POST /api/upload` stores the file, returns a `doc_id`, and routes you to
  `/analyze/{doc_id}`.
- **Demo**: click the demo button.
  → `POST /api/demo` loads `income_tax_2025.pdf` under the stable id `demo_income_tax_2025` and
  routes you to its workspace.

**Example (B):** upload `micro_enterprises_act.pdf`. Within a second you land on
`/analyze/<new-uuid>` and the analysis pipeline starts automatically.

**What to expect:** only PDFs are accepted; a non-PDF returns a clear "Only PDF files are
supported" error. Files over 50 MB are rejected with a size message.

---

### Step 2 — Analysis pipeline (live)

**Where:** `/analyze/{docId}` (`frontend/src/app/analyze/[docId]/page.tsx`), driven by
`GET /api/analyze/{docId}` (SSE).

The pipeline runs **5 stages**, streamed live with a progress overlay:

| Stage | What happens | Example B output |
|---|---|---|
| 1. **Parsing** | Opens the PDF, extracts text per page, **normalises** it (collapses layout line-breaks, joins hyphenated words, fixes `` ` ``→₹ and smart quotes), and **detects tables**. | "Extracted 1 page" |
| 2. **Segmentation** | Splits text into clauses on section numbers (`1.`, `1.2`) and legal markers ("Provided that", "Where any…"). Tables become one clause each, tagged `table`. | "Identified **8 clauses**" |
| 3. **NER + Causal** | For each prose clause: tags legal **entities** and detects **causal patterns**. Streams one event per clause. | 31 entities, 4 causal patterns |
| 4. **Embeddings + UMAP** | Encodes every clause into a 384-d vector (sentence-transformers) and projects to 2D for the semantic map. | 8 vectors → 8 points |
| 5. **Knowledge graph** | Builds a provenance graph (document → sections → clauses → entities/causal nodes). | 45 nodes, 47 edges |

**What to expect:**

- A progress overlay shows each stage with a percentage and live clause counter.
- If you re-open a document that's already analysed, it **replays from disk in <1 s** (same
  visuals, no recompute). To force a fresh re-analysis, the app calls `?force=true`.
- Large documents take longer at Stage 1 because table detection scans every page (e.g. the CWC
  188-page report ≈ 2 min; a 624-page statute proportionally more). This is a one-time cost —
  results are cached.
- **Tables are no longer shredded into garbage.** A capacity/net-worth table now appears as one
  clean, tagged clause (e.g. `Chapter | Title | Page No. …`) instead of fragmented noise.

---

### Step 3 — The Workspace

**Where:** `/analyze/{docId}` — a three-column layout.

| Column | Component | What it does |
|---|---|---|
| **Left — PDF viewer** | `PDFViewerPanel.tsx` (served by `GET /api/pdf/{docId}`) | Renders the original PDF. Selecting a clause highlights its bounding box on the page. Zoom / page controls. |
| **Middle — Clause feed** | `ClauseFeed.tsx` / `ClauseCard.tsx` | A scrollable list of every clause with its section number, entity pills, and causal badges. Click a clause to select it everywhere. |
| **Right — Analytics tabs** | `AnalyticsTabs.tsx` | Six tabs (next section). |

**Example (B):** click clause **§5 "Penalty for concealment"** in the feed → the PDF pane jumps to
that clause and highlights it; the entity pills show `PENALTY`, `THRESHOLD` (e.g. "Rs. 2,00,000"),
`ACTOR`.

---

### Step 4 — Analytics tabs

**Where:** right column of the workspace (`frontend/src/components/workspace/analytics/`).

| Tab | Component | Backend | What it shows |
|---|---|---|---|
| **Overview** | `OverviewTab.tsx` | `GET /api/stats/{docId}` | Document domain, clause/entity/pattern counts, risk distribution, confidence breakdown. |
| **Causal** | `CausalTab.tsx` | `GET /api/causal/{docId}` | Every detected causal rule as a card: **condition → consequence**, risk tier (CRITICAL/HIGH/MEDIUM/LOW), impact bar. Click a risk chip to filter. |
| **LLM** | `LLMCompareTab.tsx` | `POST /api/analyze/{docId}/llm` (SSE), `GET /api/clauses/{docId}/llm` | Runs / shows the local-LLM extraction and compares it to the rule engine (see Step 5). |
| **Search** | `SearchTab.tsx` | `POST /api/search/{docId}` | **Semantic search** over the document + a short synthesized answer. |
| **Entities** | `EntityNetworkTab.tsx` | `GET /api/entities/{docId}` | A force-directed **co-occurrence network** of legal entities. |
| **UMAP** | `EmbeddingTab.tsx` | `GET /api/embeddings/{docId}` | A **2D semantic scatter** of clauses; nearby dots = semantically similar clauses. Lasso-select to multi-select. |

**Example — Search (A):** in the demo, type *"What happens if I file my return late?"* →
`POST /api/search/demo_income_tax_2025` returns the most relevant clauses (ranked by cosine
similarity on the stored embeddings) plus a one-paragraph answer stitched from the top hits.

**Example — Overview (B):** domain "General Legislation", 8 clauses, 31 entities, 4 causal
patterns, risk mix 1 CRITICAL / 2 HIGH / 1 LOW.

**What to expect for the UMAP tab:** if a document's 2D projection didn't complete (rare,
non-fatal), the tab now says **"2D projection unavailable for this document"** instead of spinning
forever. Table clauses and tiny clauses may cluster oddly — that's expected.

---

### Step 5 — LLM extraction

**Where:** the **LLM** tab (`LLMCompareTab.tsx`). Needs **Ollama running** with `phi3.5:3.8b`.

**What it does:** picks the highest-impact clauses (those with an **obligation or penalty**
entity), sends each to phi3.5 with a strict JSON prompt, and extracts a structured causal rule:
`is_causal, condition, action, consequence, actors[], thresholds[], confidence, reasoning`. It then
labels each clause by **agreement**: `both` (rule engine + LLM agree), `llm only`, `rules only`, or
`conflict`.

**How to run it:** open the LLM tab → click **"Run LLM Extraction"**. Progress streams clause by
clause.

**Example (B):** 6 candidate clauses selected → phi3.5 extracts **5 causal rules, 0 parse
failures** in ~60 s. Example output for §5:

```
condition:   concealing turnover with intent to evade the levy
consequence: imprisonment for up to three years or a fine of Rs. 2,00,000
is_causal:   true    confidence: 0.9
```

**What to expect / good to know:**

- Only **candidate** clauses are extracted (default cap 40, configurable via `LLM_MAX_CANDIDATES`).
  A clause that wasn't a candidate is honestly labelled **"not run for this clause"** — not
  "failed".
- Table clauses are **excluded** and shown as "tabular data".
- Speed: ~5–7 s per clause on a 4 GB GPU. Re-runs are near-instant (results cached by content hash).
- phi3.5 is a small model — expect the occasional imperfect extraction. Genuine parse failures
  (rare now that the token budget is 800) show as **"failed to parse"** with the raw output, and
  are **not** cached, so re-running retries them.

---

### Step 6 — Explainability Studio

**Where:** `/explain/{docId}/{clauseId}` (`frontend/src/app/explain/[docId]/[clauseId]/page.tsx`).
Reach it from any clause's **"Explain this"** link.

**What it does:** runs **LIME** (Local Interpretable Model-agnostic Explanations) — it perturbs the
clause hundreds of ways and watches the classifier react, producing per-token weights:

- **Green tokens** push the clause *toward* a causal reading; **red** push away.
- A bar chart ranks the **most influential tokens**.
- A **Rule-vs-LLM table** compares the rule engine and phi3.5 side by side.

**Two modes (toggle top-right):**

| Mode | Speed | Explains | Use when |
|---|---|---|---|
| **Fast preview** (`proxy`) | ~1 s | the rule-based classifier | quick, always-available preview |
| **LLM faithful** (`llm`) | ~1–3 min | phi3.5 itself (≈50 Ollama calls) | you want the true model explanation |

**Example (B):** open §5, Fast preview → the tokens **"Whoever"**, **"conceals"**, **"punishable"**
light up green (they drive the causal/penalty reading); a progress bar shows perturbations being
classified.

**What to expect:**

- Token highlighting now aligns to **whole words** (e.g. "tax" won't highlight inside "taxation").
- For a **table** clause, the Studio shows **"Tabular data — not analyzed as a prose clause"**
  instead of meaningless token noise.
- The Rule-vs-LLM table distinguishes four honest states: *causal*, *not causal*, *failed to
  parse*, *not run* — and only flags a real **disagreement** (one says causal, the other doesn't),
  not a mere missing field.

---

### Step 7 — Simulation Theater

**Where:** `/simulate/{docId}` (`frontend/src/app/simulate/[docId]/page.tsx`). Uses a **Mesa**
agent-based model.

**What it does:** builds executable rules from the document's extractions (LLM rules preferred,
rule-based as fallback) and runs them against a **synthetic society** of five agent types:

`low_income · middle_income · high_income · small_business · large_corporate`

Each agent, each month, decides whether to comply with each applicable rule based on its income,
financial buffer, compliance tendency, and the rule's **burden relative to its disposable income**.
The theater streams live metrics.

**How to run it:** open the page → it lists the available rules → set the population and number of
steps in the controls → **Run**. Charts animate as each step streams in.

**Live metrics & charts:**

- **Compliance rate** (overall and per agent type)
- **Gini coefficient** of burden inequality
- **Average burden** per agent type (₹)
- **Policy burden index**
- **Verdict:** `progressive` · `neutral` · `regressive`

**Example (B):** run the micro-Act's 6 rules for 40 steps →

```
final compliance ≈ 0.70    final Gini ≈ 0.68    verdict: REGRESSIVE
low_income compliance ≈ 0.30   vs   large_corporate ≈ 1.00
```

The verdict reads **regressive** because the flat levy/fees consume a far larger share of a
low-income household's *disposable* income — so the poor are pushed into non-compliance while
corporates comply comfortably. (A flat percent levy that used to wrongly read "neutral" now
correctly reads "regressive".)

**What to expect:**

- If a document has **no causal rules to simulate** (e.g. it imposes no duties/levies), you get a
  calm **empty state** explaining why — not a red error.
- The verdict is an **incidence** measure (do low-income agents bear a higher burden share than
  high-income?), which is the textbook definition of regressivity.
- Results are deterministic for a fixed seed (default 42), so runs are reproducible.

---

### Step 8 — Policy Diff Arena (Compare)

**Where:** `/compare` (`frontend/src/app/compare/page.tsx`). Backend: `POST /api/compare`.

**What it does:** puts two analysed documents (e.g. **v1 vs v2** of a bill) side by side and shows:

- **Clause-level diff** — matched / modified / added / removed, using the stored embeddings
  (≥ 0.92 similarity = matched, 0.75–0.92 = modified).
- **Entity delta** — which obligations/penalties/actors appear only in A, only in B, or both.
- **Risk comparison** — how the risk profile shifted.
- **Comparative simulation** — runs both versions through the simulator to show who bears the
  difference.

**How to use it:** go to `/compare` → the **DocPicker** shows all analysed documents → pick
**Document A** (baseline) and **Document B** (revision) → the arena opens.

**Example:** compare `mini_act_v1.pdf` vs `mini_act_v2.pdf` → the arena flags a threshold that
changed (e.g. a rate 12% → 18%) as a **modified** clause at ~0.90 similarity, and the comparative
sim shows the revision is more regressive.

**What to expect:**

- You need **at least two analysed documents**. If the list can't load, you get a clear backend
  error (distinct from "no documents yet").
- If the two documents are too dissimilar to align (or embeddings are missing), a **banner**
  explains that the clause-level diff is unavailable while the entity/risk deltas still show — the
  arena won't just render blank.

---

### Step 9 — Provenance graph

**Where:** `/provenance/{docId}` (`frontend/src/app/provenance/[docId]/page.tsx`). Backend:
`GET /api/graph/{docId}`.

**What it does:** renders the knowledge graph — **document → chapters/sections → clauses →
entity/causal nodes** — as an interactive node-link diagram (React Flow / d3). Click a node to see
its details; trace how a penalty connects back to the clause and section that created it. You can
export the graph as a PNG.

**Example (A):** in the demo, expand a chapter node to see its sections, then a section to its
clauses, then a clause to the obligations and penalties it contains.

---

### Step 10 — Export a report

**Where:** the **Export report** button in the workspace analytics header. Backend:
`GET /api/report/{docId}?fmt=html`.

**What it does:** opens a formatted report in a new tab — executive summary (clause/entity/pattern
counts, critical & high risks, domain), a causal-analysis section grouped by risk tier, and a
compliance checklist. Useful for sharing findings without the interactive UI.

> Tip: if nothing opens, your browser likely blocked the pop-up — allow pop-ups for localhost.

---

## 5. Complete feature reference

**Frontend routes**

| Route | Page file | Purpose |
|---|---|---|
| `/` | `app/page.tsx` | Landing: upload / demo |
| `/analyze/{docId}` | `app/analyze/[docId]/page.tsx` | Workspace (PDF + clauses + analytics) |
| `/explain/{docId}/{clauseId}` | `app/explain/[docId]/[clauseId]/page.tsx` | Explainability Studio (LIME) |
| `/simulate/{docId}` | `app/simulate/[docId]/page.tsx` | Simulation Theater (Mesa ABM) |
| `/compare` | `app/compare/page.tsx` | Policy Diff Arena |
| `/provenance/{docId}` | `app/provenance/[docId]/page.tsx` | Knowledge-graph explorer |

**Backend endpoints** (all prefixed `/api`; interactive docs at `/docs`)

| Method & path | Router file | What it does |
|---|---|---|
| `POST /upload` | `routers/upload.py` | Upload a PDF → `doc_id` |
| `POST /demo`, `GET /demo` | `routers/data.py` | Load the bundled demo statute |
| `GET /analyze/{docId}` | `routers/analyze.py` | **SSE** 5-stage analysis (`?force=true` to re-run) |
| `GET /clauses/{docId}` | `routers/data.py` | All clauses + metadata |
| `GET /entities/{docId}` | `routers/data.py` | Entities + co-occurrence matrix |
| `GET /causal/{docId}` | `routers/data.py` | Rule-based causal patterns |
| `GET /embeddings/{docId}` | `routers/data.py` | 2D UMAP points |
| `GET /graph/{docId}` | `routers/data.py` | Knowledge-graph nodes/edges |
| `GET /stats/{docId}` | `routers/data.py` | Aggregate stats for Overview |
| `GET /documents` | `routers/data.py` | List all analysed documents |
| `GET /pdf/{docId}` | `routers/pdf.py` | Stream the original PDF |
| `POST /search/{docId}` | `routers/intelligence.py` | Semantic search + answer |
| `GET /report/{docId}` | `routers/intelligence.py` | HTML/JSON report |
| `POST /compare` | `routers/intelligence.py` | Two-document diff |
| `GET /domain/{docId}` | `routers/intelligence.py` | Detected legal domain |
| `POST /analyze/{docId}/llm` | `routers/llm.py` | **SSE** LLM extraction (`?scope=auto|all`) |
| `GET /clauses/{docId}/llm` | `routers/llm.py` | Stored LLM extractions |
| `GET /explain/{docId}/{clauseId}` | `routers/explain.py` | LIME result (202 while running) |
| `GET /explain/{docId}/{clauseId}/stream` | `routers/explain.py` | **SSE** LIME progress |
| `GET /simulate/{docId}/rules` | `routers/simulate.py` | List executable rules (no run created) |
| `POST /simulate/{docId}` | `routers/simulate.py` | Create a simulation run |
| `GET /simulate/{docId}/stream` | `routers/simulate.py` | **SSE** per-step metrics |
| `GET /simulate/{docId}/results` | `routers/simulate.py` | Stored simulation result |

**Backend pipeline modules** (`backend/pipeline/`)

| File | Responsibility |
|---|---|
| `pdf_parser.py` | Extract + normalise text; detect & linearise tables |
| `clause_segmenter.py` | Split into clauses; tag `prose`/`table` |
| `legal_ner.py` | Legal entity recognition (spaCy Matcher + regex) |
| `causal_detector.py` | Rule-based "if→then" pattern detection |
| `embedder.py` | Sentence-transformer embeddings + UMAP |
| `graph_builder.py` | Provenance knowledge graph |
| `llm_extractor.py` | phi3.5 causal extraction (Ollama) |
| `lime_explainer.py` | LIME token attribution (proxy + llm modes) |

**Simulation** (`backend/simulation/`): `agents.py` (agent types, income, disposable-income burden),
`model.py` (Mesa model, Gini, regressivity verdict), `rules.py` (extraction → executable rules),
`runner.py` (per-step metrics, finalize).

---

## 6. Data & persistence

Everything lives under `backend/data/store/{doc_id}/`:

```
result.json                 # clauses, graph, stats (the analysed document)
embeddings.npy              # 384-d clause vectors (semantic search + compare)
llm/extractions.json        # cached LLM causal rules (keyed by content hash)
lime/{clause}.{mode}.json   # cached LIME explanations
simulations/                # saved simulation results
```

- Writes are atomic; in-memory caches are write-through. **Analyses survive restarts** and reload
  instantly.
- Uploaded PDFs are kept in `backend/data/uploads/{doc_id}.pdf`.
- Re-analysing with `?force=true` recomputes and overwrites `result.json`. Because clause IDs can be
  reassigned on re-segmentation, stale LIME caches are auto-invalidated by content fingerprint (they
  recompute on next view) and LLM caches are keyed by clause text (so changed text re-extracts).
- To wipe a document, delete its folder under `data/store/` (and its PDF under `data/uploads/`).

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Frontend shows "Failed to fetch" / `ERR_CONNECTION_REFUSED` on `:8000` | Backend not running | Check the "PRISM Backend" window is up; it should say `Uvicorn running…`. |
| Frontend stuck on "missing required error components" | Corrupted `.next` dev cache | Delete `frontend\.next`, relaunch. |
| LLM tab shows "Extraction failed — is Ollama running?" | Ollama down or model missing | `ollama list` → `ollama pull phi3.5:3.8b`; ensure `ollama serve` is up. |
| A clause shows "not run for this clause" | It wasn't an LLM candidate (no obligation/penalty) | Run LLM extraction with **scope = all**, or it's simply not a causal clause. |
| Analysis is slow on a big PDF | Table detection scans every page | One-time cost; result is cached. Reopen = instant replay. |
| Simulation says "No causal rules to simulate" | Document imposes no duties/levies/thresholds | Expected — try a statute with obligations, or run LLM extraction first. |
| UMAP tab: "2D projection unavailable" | UMAP step was skipped/failed (non-fatal) | Other analysis is unaffected; re-run with `?force=true` if needed. |
| Backend window closed instantly with no error | Dependency install failed | Open `backend\run_backend.bat` manually to read the error; it pauses on failure. |

---

## 8. How to make PRISM better (roadmap)

Concrete, high-value improvements, grouped by effort and impact. These are *additions* — the current
app already works end-to-end.

### A. Correctness & trust (highest value)
1. **Gold-standard evaluation set.** Hand-label ~100 clauses (is_causal, condition, consequence,
   entities) and add a `backend/eval/` harness that reports precision/recall for the rule engine and
   the LLM. Without this you can't *prove* the extractions are good — you can only show them. This is
   the single biggest credibility upgrade (and the basis for an IEEE-style paper).
2. **Confidence calibration.** phi3.5's self-reported confidence is not calibrated. Compare it
   against the gold set and remap, so a "0.9" actually means 90%.
3. **Citations in search answers.** The semantic-search answer should cite the specific clause IDs
   it drew from (footnote-style), so users can verify rather than trust.

### B. Retrieval & reasoning (Phase 3, already planned)
4. **RAG chat over the document** (`ChromaDB` + a `/chat` page): ask free-form questions and get
   answers grounded in cited clauses. This turns PRISM from an analyser into an assistant.
5. **Cross-document RAG**: ask questions spanning your whole corpus ("which of my uploaded acts
   impose a penalty above ₹1 lakh?").
6. **Fine-tune phi3.5 (QLoRA)** on legal causal-extraction examples to cut parse errors further and
   improve consequence extraction quality.

### C. Simulation realism
7. **Editable rule parameters** in the Simulation Theater — let the user tweak a rate/threshold and
   see the verdict shift live (policy what-if). The model already supports it; expose sliders.
8. **Behavioural realism**: add enforcement intensity, evasion cost, and multi-year horizons; report
   confidence bands from multiple seeds instead of one deterministic run.
9. **Named populations**: let users define their own agent mix (e.g. a specific sector) instead of
   the fixed five types.

### D. Usability & robustness
10. **OCR fallback** for scanned/image PDFs (currently text-only). Detect a text-less page and route
    it through Tesseract.
11. **Table structure preservation**: render detected tables as real HTML tables in the UI (the data
    is already captured), rather than linearised text.
12. **Progress persistence for long jobs**: if the browser tab closes mid-analysis, let it reattach
    to the running job on reload (the backend already runs jobs independently).
13. **Multi-file & bulk upload** with a corpus dashboard.

### E. Deployment & collaboration (Phase 3, already planned)
14. **Auth + hosted deployment** (NextAuth + a Postgres/Neon store + Vercel/Railway) so it's not just
    localhost. Move the file store from disk to object storage.
15. **Shareable analysis links** and PDF/DOCX report export (beyond the current HTML report).
16. **Audit log**: record who analysed what and when — important for any real legal-ops use.

### F. Quality-of-life
17. **Keyboard navigation** through clauses; **saved views**/bookmarks for important clauses.
18. **Diff across >2 documents** (version history of a bill through readings).
19. **Configurable risk thresholds** so an organisation can encode its own risk appetite.

**Suggested next three, in order:** (1) the gold-standard eval harness — it makes everything else
measurable; (4) RAG chat — the biggest new user-facing capability; (7) editable simulation
parameters — turns the simulator from a demo into a decision tool.

---

*Generated for PRISM v2.0 — Phase 1 (cognition engine) + Phase 2 (LLM / LIME / simulation / compare),
all repaired and verified end-to-end. Phase 3 (RAG, fine-tuning, deployment, evaluation) is the
planned next milestone.*
