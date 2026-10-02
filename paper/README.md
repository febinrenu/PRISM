# PRISM — IEEE Paper (Module G)

`PRISM_IEEE.tex` is an IEEEtran conference draft pre-filled with the numbers the
evaluation harness already produces. Items marked `[RUN]` in red need one more
command (they require the LLM / fine-tuned backend).

## Build

```bash
python paper/make_figures.py          # collect eval charts + draw architecture.png
cd paper
pdflatex PRISM_IEEE.tex && pdflatex PRISM_IEEE.tex
```

(Any LaTeX distro with `IEEEtran.cls`, or upload the `.tex` to Overleaf.)

## Reproduce every number

```bash
cd backend
# Out-of-domain + simulation + template + LIME (offline where possible):
python -m eval.run_benchmark --limit 120 --doc demo_income_tax_2025

# In-domain gold sets (build → human-review → score):
python -m eval.gold_builder --doc demo_income_tax_2025 --llm-questions
python -m eval.review_gold --set causal      # confirm/correct, then ner, rag_qa
python -m eval.run_benchmark --gold --with-llm --doc demo_income_tax_2025
```

## Filling the `[RUN]` rows in Table 1/2

The cross-system comparison (rule-based vs Phi-3.5 vs fine-tuned LoRA) is the
paper's headline table. Produce it by scoring each backend on the reviewed
in-domain causal gold:

```bash
LLM_BACKEND=ollama            python -m eval.gold_eval --with-llm   # Phi-3.5 zero-shot
# ...after training/finetune.py + export_ollama.py:
LLM_BACKEND=ollama_finetuned  python -m eval.gold_eval --with-llm   # PRISM-Legal LoRA
```

Paste the resulting precision/recall/F1 into Table~\ref{tab:causal}.

## Numbers already in the draft (measured on this machine)

| Metric | Value |
|---|---|
| Clauses indexed (Income Tax Bill) | 2,755 |
| RAG recall@1 / recall@8 (50 LLM-gen, reviewed QA) | 0.66 / 0.94 |
| Causal F1, rule-based, LEDGAR (out-of-domain) | 0.18 |
| Causal, Phi-3.5 zero-shot, in-domain gold (P/R/F1) | 0.54 / 0.98 / 0.70 |
| Causal, rule-based, in-domain gold (P/R/F1)† | 1.00 / 0.92 / 0.96 |
| Sim income KL — NSSO vs uncalibrated | 0.068 vs 0.234 (3.4× better) |
| Top-decile share — modelled vs WIR-2022 | 0.495 vs 0.57 |
| Template mean top-match cosine | 0.47 |

## Honesty notes (keep these in the paper)

- Gold sets are LLM-assisted **bootstrap → human review**, not independent
  from-scratch annotation. Scoring a system against gold it seeded is an
  *agreement upper bound*; the meaningful signal is **between** systems and on
  the out-of-domain set.
- Simulation parameters are documented baselines, not fitted to microdata.
