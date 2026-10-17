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
| Reading PDFs | Each page's text is checked before use (empty, garbled, ok). Fonts without a Unicode map are decoded exactly from their glyph names, with bold read from glyph ink (how the India Code Income-tax Act 1961 is read); scanned or undecodable pages go to RapidOCR (PP-OCR, CPU), with glued words re-spaced from the corpus vocabulary. Every page records how it was read, and the app shows OCR pages | `pipeline/pdftext/` |
| Rate tables | Rate schedules rebuilt row by row from the PDF geometry (numbered two-column schedules, also across page breaks; boxed tables), each row cited to its span of the frozen canonical text; a derived view, never a change to the text | `pipeline/statute/tables.py`, `data/corpus/*/*/tables.json` |
| Rule schema | `LegalRule`: modality, subject, conditions, action, consequence, exceptions, cross-references, typed quantities and executable effects, all grounded to statute spans | `models/rules.py` |
| Extraction | Rule-based baseline and language models behind one JSON interface: local (Ollama Phi-3.5, Gemma-2B), hosted (Groq GPT-OSS-120B / 20B, Qwen3.8-27B; OpenRouter Gemma 4 31B, Nemotron-3-Super) and open-weight batch systems run on a GPU host (Llama-3.1-8B, Mistral-7B). Every quoted span is verified against the statute or rejected; self-consistency sampling gives confidence | `pipeline/extraction/` |
| Engines | Statute-faithful personal income-tax calculator (slabs by age, s.87A rebate with marginal relief, surcharge with marginal relief and caps, cess, statutory rounding); a generic rule engine for fees and penalties with defeasible exceptions | `simulation/rac/`, `policy/` |
| Expert coding | Income-tax parameters AY 2020-21 to tax year 2026-27, every value cited; slab tables checked row by row against the parsed statutes | `simulation/rac/gold/` |
| Assembly | One deterministic assembler from any system's rules to engine parameters; unfillable targets become review items, never defaults | `simulation/translate/assemble.py` |
| Population | Weighted taxpayer population reproducing the Income Tax Return Statistics exactly, with Chapter VI-A deductions by rank matching | `simulation/population/` |
| Microsimulation | Regime choice, revenue, decile effective rates, Gini, Kakwani, Reynolds–Smolensky and Suits indices | `simulation/engine/` |
| Validation | In-sample reproduction of reported tax, held-out forecasts against a naive baseline, reform costs against Budget speeches, Morris + Sobol sensitivity | `simulation/backtest/`, `simulation/engine/sensitivity.py` |
| Experiment | Ten personal income-tax reforms × systems: pre-registered conclusion flips, exact Shapley attribution to provisions, robustness to population assumptions, McNemar and sign tests; a controlled study injecting typed extraction errors | `simulation/experiment/` |
| Evaluation | Frozen stratified evaluation sets (300 test / 102 dev / 30 pilot), blind double annotation tool, agreement and system scoring | `eval/v2/`, `routers/annotate.py`, `frontend/src/app/annotate/` |

## Reproducing the results

All commands run from `backend/` with the project virtual environment.

```bash
pip install -r requirements.txt          # exact versions: requirements.lock
python -m spacy download en_core_web_sm

python -m cli ingest                     # statute PDFs (some sites need a browser; see DATA.md)
python -m cli parse                      # statute ASTs (and the rebuilt rate tables)
python -m cli parse --check              # reparse and confirm the frozen texts and node ids are unchanged
python -m cli tables                     # rebuild only the rate-table views
python -m cli ocr-vocab                  # corpus word frequencies for re-spacing OCR output
python -m cli ocr-eval                   # OCR word recall/precision; decoded fonts against OCR
python -m cli cbdt-targets               # Income Tax Return Statistics → population targets
python -m cli gold-export                # expert income-tax parameters

python -m cli backtest                   # microsimulation validation
python -m cli sensitivity                # Morris + Sobol indices
python -m cli experiment                 # expert vs extracted (hosted systems need API keys)
python -m cli experiment-stats           # robustness of flips, system comparisons
python -m cli experiment-structured      # rebuilt tables + schema decoding + one repair round
python -m cli experiment-structured --no-schema   # the same in JSON mode (decoding ablation)
python -m cli error-injection            # typed errors injected into the expert law

python -m cli eval-run --system rules --split test
python -m cli eval-agree --split pilot   # annotator agreement
python -m cli eval-score --system gpt-oss-120b --split test
python -m cli eval-faithfulness --system gpt-oss-120b --split dev

python -m cli reproduce                  # every paper table from the cache, no model calls
```

Every run writes a manifest (git commit, package versions, model digests,
seeds, configuration) to `data/runs/`. Model outputs are cached
content-addressed in `data/cache/llm/`, so a rerun calls no model twice;
`cli reproduce` regenerates every table in `paper/tables/` (and the numbers
cited in the manuscript) with model calls disabled.

**Structured condition.** `cli experiment-structured` reruns the headline
reforms with each provision's rate tables rebuilt from the PDF, decoding
constrained to the answer's JSON schema (strict for the GPT-OSS models), and
one repair round in which a reading that fails an assembler check is sent
back with the check in general terms (never a value). The first pass and the
repaired result are both scored by the headline's scoring and kept in
`data/experiments/structured/`; `cli reproduce` turns them into
`paper/tables/structured.tex`. The headline runs are left as they are.

**Open-weight systems in batch.** `cli batch-export --system mistral-7b`
writes every prompt the study needs; `training/kaggle_batch_extract.ipynb`
runs them on a free Kaggle GPU with vLLM; `cli batch-import` stores the
answers in the cache, after which the system runs like any other.

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

or `start.bat` on Windows (sets everything up and runs the full app; `start.bat dev` for hot
reload, `start.bat stop` to stop).

### Docker

```bash
docker compose up --build        # http://localhost  (nginx serves the app and the API on one origin)
```

The browser talks to nginx only and the app calls the API on the same origin, so no CORS
setup is needed. If another stack already uses the ports, move them:

```bash
HTTP_PORT=8088 BACKEND_PORT=8100 FRONTEND_PORT=3100 docker compose -p prism up --build
```

The first start copies the bundled demo analysis into the `prism-data` volume. Ollama runs
on the host and is reached through `host.docker.internal`; set `LLM_BACKEND=groq` and
`GROQ_API_KEY` to use a hosted model instead. Set `JWT_SECRET` before exposing it publicly.

### What is in the app

- **Workspace** (`/analyze/[docId]`): upload a statute; it is segmented by its
  legal structure, annotated, and linked to the PDF. Re-analyse runs the pipeline
  again (owner only; the demo is a fixed reference). The semantic map shows every
  clause's embedding in 2D.
- **Report** (`/report/[docId]`): summary figures, a compliance checklist, the risk
  matrix and key obligations, each linked to its clause; prints or downloads as HTML.
- **Explainability** (`/explain/...`) and **provenance graph** (`/provenance/...`),
  as a tree or as 3D strata.
- **Policy sandbox** (`/simulate/[docId]`): an illustrative agent-based simulation;
  every saved run can be reopened.
- **Research** (`/research`): expert-vs-extracted results, the effective tax rate by
  decile for any reform and reader, validation and sensitivity.
- **Annotate** (`/annotate`): the blind annotation tool.
- **Chat** (`/chat`): retrieval-augmented questions over the corpus (BM25 and
  dense retrieval fused and re-ranked), answers marked grounded only when they
  cite real sources.
- **Statutes** (`/statutes`): browse the parsed corpus by chapter and section.
- **Light or dark**: the app has both (top bar, mobile menu or Ctrl+K); the landing
  story is always dark.

Documents uploaded while signed in belong to the uploader: the document list
shows a user their own documents and the shared ones (the demo, anonymous
uploads), and only the owner or an admin can remove a document from the chat
corpus. A document is opened by its unguessable id, like an unlisted link.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Keys are only needed for the
hosted systems: `GROQ_API_KEY` (plus optional `GROQ_API_KEYS`, comma-separated)
and `OPENROUTER_API_KEYS`. Several keys are used in rotation: a per-minute
limit cools one key, a daily limit retires it for that model. Everything else
runs locally (Ollama for local models).

## Tests

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Data and licence

Sources, licences and scope decisions are listed in [`DATA.md`](DATA.md).
Code is released under the Apache-2.0 licence ([`LICENSE`](LICENSE)); cite
with [`CITATION.cff`](CITATION.cff).
