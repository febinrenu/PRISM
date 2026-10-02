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

## Official statistics (redistributed as extracted tables)

Back-test targets are transcribed from published government sources (CBDT
income-tax return statistics, Union Budget receipt documents and revenue
impact statements, and NIPFP Working Paper 403 for GST incidence). Each CSV in
`backend/simulation/backtest/targets/` names its source document and table.

## Benchmarks

`backend/data/_quarantine_v1/ledgar_eval.json` contains 120 provisions derived
from LEDGAR as packaged in LexGLUE (Chalkidis et al., 2022); see the LexGLUE
dataset card for its licence. It is retained only as a record of the v1
evaluation and is not used.

## Annotations (released)

Human annotations produced for this project (`backend/data/annotations/` and
the frozen sets in `backend/data/eval/v2/`) are released under CC BY 4.0.
