# Independent coding of income-tax parameters

**Who:** the second coder, working alone. Don't look at
`backend/simulation/rac/gold/` or discuss values with the first coder until
both codings are finished.

**Time:** about 5–6 hours.

**Why it matters:** the paper compares rules extracted by language models
against these parameters, so they need independent confirmation. We report
how often two people reading the same Finance Acts arrive at the same numbers.

## What to code

Code each assessment year from AY 2020-21 to AY 2027-28. AY 2027-28 is tax
year 2026-27, the first year under the Income-tax Act, 2025.

Code everything for a **resident individual** whose income is taxed at
normal rates. Leave out special-rate capital gains, lotteries and
agricultural-income aggregation.

| Parameter | Where to find it |
|---|---|
| Old-regime slab rates for each age band (below 60, 60–80, 80+) | First Schedule, Part I, Paragraph A of that year's Finance Act. Part III of the previous year's Act prints the same rates. |
| New-regime (s.115BAC) slab rates, from AY 2021-22 | The section of the Finance Act that inserts or substitutes s.115BAC(1) / (1A). For AY 2027-28, s.202 of the Income-tax Act, 2025. |
| s.87A rebate: income limit, maximum rebate, marginal relief (yes/no), per regime | The Finance Act section amending s.87A. For AY 2027-28, s.156 of the 2025 Act. |
| Standard deduction on salary, per regime | s.16(ia) and its provisos. For AY 2027-28, the salary deductions Schedule of the 2025 Act. |
| Surcharge thresholds and rates, per regime, including any cap | Section 2 and the First Schedule. |
| Health and Education Cess rate | Section 2 of the Finance Act. |
| Default regime (old or new) | s.115BAC(1A) and (6). For AY 2027-28, s.202. |

All the Acts are in `backend/data/corpus/*/source.pdf`. Finance Act 2019
(No. 7), 2021, 2022 and the interim Finance Act 2024 are not in the corpus.
Find them on egazette.gov.in if you need them, and note that in the
`source` field.

## How to record it

1. Copy `docs/expert_coding_template.json` to `docs/coder2_pit.json`.
2. Fill in every `null`. Write amounts in rupees (`700000`, not "7 lakh") and
   rates as fractions (`0.05` for 5%).
3. Give each slab as `{"lower": …, "upper": …, "rate": …}`, starting from 0,
   with the last slab's `upper` set to `null`.
4. Next to each block, fill `"source"` with the statute and provision you
   read, e.g. `"FA2023 s.52, s.115BAC(1A) Table"`.
5. If the law is unclear, enter your best reading and explain it in
   `"note"`. Don't leave a value blank.

## When both codings are done

```bash
cd backend
python -m cli gold-agree --coder2 ../docs/coder2_pit.json
```

This lists every parameter where the two codings differ. Sit down together
and settle each difference by reading the statute; don't take an average.
The command also reports agreement before you reconcile (the number that
goes in the paper) and records which coder's reading the statute supported.
