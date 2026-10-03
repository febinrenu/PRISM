# PRISM — Policy Rule Interpretation & Socioeconomic Impact Modelling

PRISM reads Indian statutes and asks a precise question: **when a language
model extracts the rules of a tax law, does simulating those rules lead to the
same policy conclusions as an expert's coding of the same law — and when it
doesn't, which clause is responsible?**

It parses statutes into their legal structure, extracts grounded rules with
local and hosted language models, turns them into executable tax parameters,
simulates them on a taxpayer population reproduced from official statistics,
and traces every divergence back to the provision, page and words it came
from. A web workspace exposes the same pipeline for any uploaded statute.

---

## Pipeline

| Stage | What it does | Code |
|---|---|---|
| Corpus | Downloads official statute PDFs, records URL and SHA-256 | `pipeline/statute/corpus.py`, `data/corpus/sources.json` |
| Structure | Layout cleaning (running heads, margin line numbers, marginal notes, footnotes), then a statute AST: Part / Chapter / Section / Sub-section / Clause / Proviso / Explanation / Schedule / tables, quoted Finance Act insertions, exact offsets and page boxes, content-addressed node ids | `pipeline/statute/layout.py`, `parser.py` |
| Rule schema | `LegalRule`: modality, subject, conditions, action, consequence, exceptions, cross-references, typed quantities and executable effects, all grounded to statute spans | `models/rules.py` |
| Extraction | Rule-based baseline and language models (Ollama Phi-3.5 / Gemma-2B; Groq GPT-OSS-120B / 20B, Qwen3.8-27B; Gemini Flash) behind one JSON interface; every quoted span is verified against the statute or rejected; self-consistency sampling gives calibrated confidence | `pipeline/extraction/` |
| Engines | Statute-faithful personal income-tax calculator (slabs by age, s.87A rebate with marginal relief, surcharge with marginal relief and caps, cess, statutory rounding); a generic rule engine for fees and penalties with defeasible exceptions | `simulation/rac/`, `policy/` |
| Expert coding | Income-tax parameters AY 2020-21 to tax year 2026-27, every value cited; slab tables checked row by row against the parsed statutes | `simulation/rac/gold/` |
| Assembly | One deterministic assembler from any system's rules to engine parameters; unfillable targets become review items, never defaults | `simulation/translate/assemble.py` |
| Population | Weighted taxpayer population reproducing the Income Tax Return Statistics exactly, with Chapter VI-A deductions by rank matching | `simulation/population/` |
| Microsimulation | Regime choice, revenue, decile effective rates, Gini, Kakwani, Reynolds–Smolensky and Suits indices | `simulation/engine/` |
| Validation | In-sample reproduction of reported tax, held-out forecasts against a naive baseline, reform costs against Budget speeches, Morris + Sobol sensitivity | `simulation/backtest/`, `simulation/engine/sensitivity.py` |
| Experiment | Five Finance Act reforms × systems: outcome divergence and pre-registered conclusion flips | `simulation/experiment/` |
| Evaluation | Frozen stratified evaluation sets (300 test / 102 dev / 30 pilot), blind double annotation tool, agreement and system scoring | `eval/v2/`, `routers/annotate.py`, `frontend/src/app/annotate/` |

## Reproducing the results

All commands run from `backend/` with the project virtual environment.

```bash
pip install -r requirements.txt          # exact versions: requirements.lock
python -m spacy download en_core_web_sm

python -m cli ingest                     # statute PDFs (some sites need a browser; see DATA.md)
python -m cli parse                      # statute ASTs
python -m cli cbdt-targets               # Income Tax Return Statistics → population targets
python -m cli gold-export                # expert income-tax parameters

python -m cli backtest                   # microsimulation validation
python -m cli sensitivity                # Morris + Sobol indices
python -m cli experiment                 # expert vs extracted (needs GROQ_API_KEY / GEMINI_API_KEY)

python -m cli eval-run --system rules --split test
python -m cli eval-agree --split pilot   # annotator agreement
python -m cli eval-score --system gpt-oss-120b --split test
```

Every run writes a manifest (git commit, package versions, model digests,
seeds, configuration) to `data/runs/`. Model outputs are cached
content-addressed in `data/cache/llm/`, so a rerun calls no model twice.

## Annotation

Two annotators label the frozen evaluation sets independently in the web app
(`/annotate`), following [`docs/annotation_guidelines.md`](docs/annotation_guidelines.md).
Expert tax parameters are coded independently by a second coder using
[`docs/expert_coding_form.md`](docs/expert_coding_form.md) and compared with
`python -m cli gold-agree`.

## Web application

```bash
# backend
cd backend && uvicorn main:app --port 8000
# frontend
cd frontend && npm install && npm run dev      # http://localhost:3000
```

or `start.bat` on Windows, or `docker compose up --build`.

- **Workspace** (`/analyze/[docId]`): upload a statute; it is segmented by its
  legal structure, annotated, and linked to the PDF.
- **Explainability** (`/explain/...`) and **provenance graph** (`/provenance/...`).
- **Research** (`/research`): expert-vs-extracted results, validation and
  sensitivity.
- **Annotate** (`/annotate`): the blind annotation tool.
- **Chat** (`/chat`): retrieval-augmented questions over the corpus, answers
  marked grounded only when they cite real sources.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Language-model keys
(`GROQ_API_KEY`, `GEMINI_API_KEY`) are only needed for the hosted systems;
everything else runs locally (Ollama for local models).

## Tests

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Data and licence

Sources, licences and scope decisions are listed in [`DATA.md`](DATA.md).
Code is released under the Apache-2.0 licence ([`LICENSE`](LICENSE)); cite
with [`CITATION.cff`](CITATION.cff).
