# Data sources

Every external dataset PRISM uses, where it comes from, and whether it is
redistributed in this repository.

## Statutes (redistributed)

| File | Source | Notes |
|---|---|---|
| `backend/data/demo/income_tax_2025.pdf` | The Income-tax Bill, 2025, as introduced in Lok Sabha (Government of India) | Public legislative document, included so the demo works offline. |

The multi-statute corpus (Income-tax Act 1961, Finance Acts 2019–2025, CGST
Act 2017, Code on Wages 2019, DPDP Act 2023) is downloaded by
`python -m cli ingest` from India Code (indiacode.nic.in) and the e-Gazette
(egazette.gov.in). The exact URL and SHA-256 of each file are recorded in
`backend/data/corpus/{statute}/{version}/source.json`.

## Survey microdata (not redistributed)

PLFS and HCES unit-level records are distributed by the Ministry of Statistics
and Programme Implementation through microdata.gov.in to registered users
only. They are never committed. Place downloaded files under
`backend/data/raw/mospi/` (git-ignored and excluded from Docker images).
Derived aggregates published in the paper are released.

## Scope decision: GST incidence

Simulating GST incidence by income group needs spending on each GST rate
category for each consumption fractile. That breakdown exists only in
unit-level HCES microdata (not available to this project) and in the CMIE
household data behind NIPFP Working Paper 403 (not public). The published
HCES 2022-23 report and factsheet give MPCE by fractile and item shares by
state, not item shares by fractile. GST incidence is therefore outside the
simulation. The CGST Act remains in the extraction evaluation and in the
rule engine (late fees and penalties).

## Official statistics (redistributed as extracted tables)

Back-test targets come from published government sources:

- Income Tax Return Statistics for AY 2019-20, 2020-21, 2022-23 and 2023-24
  (Income Tax Department), individual tables 2.1, 2.10 and 2.11, parsed into
  `backend/simulation/population/targets/cbdt_individuals_ay*.csv` with the
  table and page of every row (`python -m cli cbdt-targets`).
- Nominal GDP and the number of individual return filers by financial year
  from the Income Tax Department Time Series Data FY 2000-01 to 2023-24
  (tables 1.4 and 1.8): `targets/macro.csv`.
- Revenue forgone announced in the Budget Speeches 2023-24 and 2025-26
  (indiabudget.gov.in), quoted in `simulation/backtest/run.py`.

The source PDFs stay in `backend/data/raw/` (git-ignored).

## Benchmarks

`backend/data/_quarantine_v1/ledgar_eval.json` contains 120 provisions derived
from LEDGAR as packaged in LexGLUE (Chalkidis et al., 2022); see the LexGLUE
dataset card for its licence. It is retained only as a record of the v1
evaluation and is not used.

## Annotations (released)

Human annotations produced for this project (`backend/data/annotations/` and
the frozen sets in `backend/data/eval/v2/`) are released under CC BY 4.0.
