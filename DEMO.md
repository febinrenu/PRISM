# PRISM demo script

A walk through the whole application for a live review, about 20 minutes.
Each step names the screen, what to do, and what to point out. Every number
on screen comes from a generated result; none is typed into the interface.

## Before the review

```bat
start.bat
```

`start.bat` installs anything missing, builds the frontend when the code
changed, starts the backend (http://127.0.0.1:8000), the frontend
(http://localhost:3000) and Ollama, and waits until both answer. Then open
http://localhost:3000 in the browser. `start.bat stop` stops them.

Pre-flight (5 minutes before):

| Check | Expect |
|---|---|
| http://127.0.0.1:8000/health | `"status": "ok"` |
| http://localhost:3000/start | the start page, no error banner |
| Close heavy apps | the backend needs about 2 GB of free memory; on a full machine the first analysis is slow |
| `ollama list` | `phi3.5:3.8b` present (the Ask view and live model readings use it; everything else works without it) |

Optional, to show the checks are green:

```bash
cd backend && python -m pytest -q          # 296 tests
cd frontend && npx vitest run              # 26 tests
cd frontend && node scripts/e2e.mjs        # 10-step walk through the running app
cd frontend && node scripts/delete-check.mjs <a small PDF>   # upload and delete, workspace and dashboard
```

## 1. The landing story (2 min) - `/`

Scroll slowly. The landing is one 3D scene driven by the scroll: statute
text flows into a prism and comes out as the six kinds of legal entity, then
the story goes through reading, simulating, the case where a model misreads a
rebate, the verdict board and the limits.

Point out: every figure in the story is drawn from the research results (a
build check fails if a number is typed into the copy). The sound toggle
(top right) is off by default.

## 2. Open the demo document (3 min) - `/start` → "Open the demo"

The Income-tax Bill, 2025 (624 pages), already analysed.

- **Clause feed** (middle): 2,757 clauses, each with its section, page and
  tagged entities (obligation, penalty, right, threshold, actor, beneficiary).
  Search a word, filter by an entity chip.
- **PDF** (left): click a clause, the page jumps there and the clause is
  highlighted.
- **Analysis tabs** (right):
  - *Overview*: entity and risk counts.
  - *Causal*: condition → consequence structures with risk tiers.
  - *LLM*: a local model's reading of each clause next to the rule-based
    one. One reading is marked **"Needs review: fifty crore rupees is not in
    the clause"**. Every amount and rate a model states is checked against
    the clause's own text.
  - *Rates*: every rate table in the document, read row by row into bands
    and checked (starts at zero, no gaps, open top band, rates do not fall),
    each band next to the row as printed. Click "p.247" to jump to it.
  - *Search*, *Entities* (co-occurrence network), *UMAP* (semantic map;
    lasso a cluster).

## 3. One clause, explained (2 min) - click "Explain this" on a clause

LIME token weights (which words drive the "causal" reading), the rule-based
reading against the model's, and the clause's place in the document.

## 4. Provenance (1 min) - document bar → "Provenance"

The document's structure as a graph and as 3D strata (Part → Chapter →
Section → clause). Click a node to open its clause.

## 5. Policy sandbox (2 min) - document bar → "Policy sandbox"

Pick rules extracted from the document, run an agent-based simulation of
compliance (adaptive agents learn to comply or defect), watch it converge.
Past runs are kept below.

## 6. Report (1 min) - document bar → "Report"

The whole analysis as one printable page.

## 7. The statutes (2 min) - `/statutes`

Twelve parsed statute texts (eleven Acts; the Income-tax Act 2025 both as enacted and as amended), each section with its exact text. Show:

- **The Income-tax Act, 1961**: its India Code PDF uses fonts with no text
  map (a plain extractor returns control characters); PRISM decodes the text
  exactly from the fonts' glyph names. Open s.87A.
- **The Income-tax Act, 2025**, s.156 or s.202.

## 8. Ask (2 min) - `/chat`

Ask "What is the rebate under section 156?". Retrieval (BM25 + embeddings +
a re-ranker) finds the sections; the answer cites them, and each citation
opens the section. When nothing in the corpus answers, it says so.

## 9. The research (4 min) - `/research`

The question: do rules a language model reads from the statute lead to the
same policy conclusions as an expert's coding?

- **Reforms × readers**: ten income-tax reforms, six readers. A dark tile =
  every pre-registered conclusion agrees with the expert; hatched = the
  reading could not be assembled into a law.
- **One reform**: click a reform, then "Inspect" on a reader: the provision,
  the spans the reader quoted, its extracted bands, and for every number
  whether it is in the words it cites.
- **Structured reading**: rate tables rebuilt from the PDF, schema-constrained
  decoding and one repair round. The **held-out check** below it was fixed in
  the code before any run: no reader did worse, and their numbers are found
  in their own quotes more often.
- Further down: injected errors (which mistakes change a conclusion),
  robustness to population assumptions, validation of the microsimulation
  against published tax statistics, sensitivity, retrieval and faithfulness.

Point out what the research does *not* claim (the "Read with care" note and
the paper's threats to validity): the structured condition was designed on
the same reforms; the held-out check shows it does no harm more than the size
of its gain.

## 10. Upload a document (optional, 2 min) - `/start` → "Analyse a PDF"

Any statute PDF. Analysis streams stage by stage. A scanned page is read by
OCR, and the workspace then names the OCR'd pages and their confidence; a
clause from such a page carries an "OCR" tag, and the Rates tab reads the
rate schedules of scanned pages too (from the recognised lines). Analysis of
a scanned page takes about 15-45 seconds per page on a laptop CPU.

"Delete" next to "Re-analyse" removes the document after a confirmation:
its analysis, model readings, explanations, saved sandbox runs and the
uploaded PDF. Only the owner (or an admin) can delete a signed-in upload;
the shared demo cannot be deleted.

## 11. Accounts and the public API (1 min) - `/login`, `/dashboard`, `/api-docs`

Register, see your documents (each row has a delete button) and an API key; the API docs show the `/v1`
endpoints.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Pages say the API is offline | `start.bat stop`, then `start.bat`; another server on port 8000 (Docker, WSL) can answer instead, so the frontend uses 127.0.0.1 |
| Ask or model readings do not answer | Ollama is not running: `ollama serve`, or set `LLM_BACKEND=groq` in `backend/.env` |
| Everything is slow | free memory (close browsers with many tabs); the first request after start loads the models |
| A page looks stale after a code change | `start.bat` rebuilds when sources changed; or `cd frontend && npm run build` |

## Reproducing the paper

```bash
cd backend
python -m cli reproduce          # every table and number in paper/tables, from the cache, no model calls
python ../paper/check_manuscript.py  # every number cited in the manuscript is generated
```
