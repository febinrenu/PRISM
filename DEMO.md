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
| `ollama list` | `phi3.5:3.8b` present (the Ask view and live model readings use it; everything else works without it). If `GROQ_API_KEYS` is set, the hosted model backs it up automatically |
| First start | the server indexes the parsed statutes once (about 4 minutes, in the background) and loads the models; Ask works meanwhile and says how many statutes are left |

Optional, to show the checks are green:

```bash
cd backend && python -m pytest -q          # 525 tests
cd frontend && npx vitest run              # 38 tests
cd frontend && node scripts/e2e.mjs        # 12-step walk through the running app
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
  - *Rates*: the rate tables the document's text lets PRISM read (the demo has one complete schedule, on page 247), read row by row into bands
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

## 5. Policy sandbox (4 min) - document bar → "Policy sandbox"

Two modes; it opens in **Statute mode**.

**Statute mode** prices a change to the law itself. The rate table on page 247 of the demo document is read and
checked, and becomes the baseline (the page says it matches the expert coding of AY 2027-28, with the provisions
cited under "Where the baseline law comes from").

- Click **"Make income up to ₹15 lakh tax-free"** (or edit any rate, limit, the rebate, the standard deduction or
  the cess). The result updates as you type.
- **Revenue effect** with the range across the population assumptions the data cannot fix, and whether the
  direction ever changes.
- **Who pays more and who pays less**, by the law's own income bands. Point out what a clause-by-clause model cannot
  show: with the ₹60,000 rebate, cutting a band below ₹12 lakh changes nobody's tax under ₹12 lakh.
- **What drove the revenue change**: each change's exact share (Shapley); the parts add up to the whole.
- **Which assumption matters** (tornado): usually only income growth does.
- Tick **Include a behavioural response** to run the compliance model under both laws.
- Open **How far to trust it**: in-sample the simulated tax is 1.04-1.09 times the reported tax payable; of two
  held-out forecasts one beats a naive forecast and one does not; the reform costs are 1.9 and 2.9 times the Budget
  figures, with the caveat that those cover all direct-tax proposals. Say these out loud: the model's limits are shown,
  not hidden.

**Clause dynamics** is the earlier agent model: five groups of agents respond to the rules extracted from the document,
month by month. Each clause is a separate levy, so overlapping clauses add up; the page says so, and warns when a
household would pay over half its income. Its effective rate is per year (it was once cumulative over the run).

## 6. Report (1 min) - document bar → "Report"

The whole analysis as one printable page.

## 7. The statutes (2 min) - `/statutes`

Twelve parsed statute texts (eleven Acts; the Income-tax Act 2025 both as enacted and as amended), each section with its exact text. Show:

- **The Income-tax Act, 1961**: its India Code PDF uses fonts with no text
  map (a plain extractor returns control characters); PRISM decodes the text
  exactly from the fonts' glyph names. Open s.87A.
- **The Income-tax Act, 2025**, s.156 or s.202.

## 8. Ask (4 min) - `/chat`

Searches the twelve parsed statutes and any analysed document. Try, in this order:

1. **"What is the rebate under section 156 of the Income-tax Act, 2025?"**: a section the question names is fetched
   exactly (tag "exact section match"), not searched for. The answer cites it; the line under the answer says what
   was checked: every amount, rate, quotation and named Act in each statement is matched to the cited text.
2. **"And for senior citizens?"**: the follow-up is rewritten with the earlier turn ("Understood as: ...") and
   searched as such.
3. **"Compare the rebate in section 87A of the old Income-tax Act with the new Act"**: passages are retrieved per Act.
4. **"How do I register a trademark in India?"**: declined in about a second, without calling the model, with the reason
   ("the corpus does not discuss trademark"); the closest passages are still shown.

The model is the local Phi-3.5 with the hosted one as a backup, and the answer says which answered. The checks
catch an invented figure or Act and trigger one rewrite; they cannot tell whether a paraphrase is faithful, and the
page says so. Click a `[1]` marker to open its source; the source card links to the statute reader.

Measured on 89 hand-written questions (lookup, fact, compare, follow-up, unanswerable, injection), 15 of them written
before the out-of-scope checks existed (`python -m eval.v2.chat_eval`; `paper/tables/chat.csv`):

| | Phi-3.5 3.8B (local) | gpt-oss-120b (hosted) |
|---|---|---|
| Answerable questions answered correctly (95% CI) | 77% (67-88%) | 91% (83-98%) |
| Cites the section that answers it | 67% | 93% |
| Unanswerable questions declined | 94% (29 of 31) | 100% (31 of 31) |
| of which the 15 written before the checks existed | 13 of 15 | 15 of 15 |
| Injection attempts resisted | 2 of 2 | 2 of 2 |
| Median / 95th percentile time to an answer | 8.3 s / 31 s | 2.7 s / 4.9 s |

Retrieval alone (no model) puts the section that answers a question first for 83% of answerable questions and in the top
five for 98%. The samples are small (57 answerable, 31 unanswerable) and the questions are the authors' draft: each gold
section and fact is checked against the statute text by the harness, but no second reader has signed them off. The
local model's failures are mostly rambling or garbled answers and follow-ups it loses; its cited provision is exact
regardless.

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
python -m eval.v2.chat_eval validate   # the 89 Ask questions: every gold section and fact checked against the statute text
python ../paper/check_manuscript.py  # every number cited in the manuscript is generated
```
