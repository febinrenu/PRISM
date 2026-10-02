# PRISM — Module E: QLoRA Fine-Tuning

Fine-tunes `microsoft/Phi-3.5-mini-instruct` with 4-bit QLoRA into **PRISM-Legal**,
a legal-specialised model that serves the whole platform when
`LLM_BACKEND=ollama_finetuned`.

## Pipeline

```
build_dataset.py   →  data/prism_instructions.jsonl   (CPU, seconds)
finetune.py        →  prism-phi35-lora/               (GPU, ~overnight on 4GB)
export_ollama.py   →  Ollama model `prism-legal`      (merge + register)
```

## 1. Build the dataset (no GPU)

```bash
python training/build_dataset.py
```

Assembles Alpaca-format instructions from three free sources:
- **PRISM's own Phase-2 extractions** — every LLM-extracted causal rule becomes a
  `clause → structured JSON` example (the highest-value, in-domain source).
- **Legal NER pairs** — clauses with labeled entities → `clause → entity list`.
- **LEDGAR** — public expert-labeled contract provisions → obligation classification.

> Tip: run the Phase-2 LLM extraction on several documents first — the more
> analysed documents on disk, the larger and more in-domain the dataset.

## 2. Verify the wiring (fast smoke test)

```bash
pip install -r training/requirements-train.txt
python training/finetune.py --smoke        # 2 optimizer steps on a tiny subset
```

If this prints `Smoke test passed`, the full run below will work.

## 3. Train (overnight)

```bash
python training/finetune.py --epochs 3
```

RTX 3050 (4GB) settings are the defaults: 4-bit NF4, LoRA `r=8` on
`q/k/v/o_proj`, batch size 1 × grad-accum 8, paged 8-bit AdamW, `max_seq_len=768`.
Adapters land in `prism-phi35-lora/`.

## 4. Merge & serve via Ollama

```bash
python training/export_ollama.py           # merge → Modelfile → ollama create prism-legal
```

Then point the platform at it:

```bash
# backend/.env
LLM_BACKEND=ollama_finetuned
OLLAMA_FT_MODEL=prism-legal
```

RAG chat, deep reasoning, and the free-form path now use your fine-tuned model.
(The structured Phase-2 extractor stays pinned to base Phi-3.5 for reproducibility
of the published Phase-2 numbers — see `backend/pipeline/llm_backend.py`.)

## Evaluate the gain

The eval harness has a `--with-llm` path; run it once on base and once on the
fine-tuned backend to fill the "PRISM-Legal LoRA" row of the paper's Table 1/2:

```bash
LLM_BACKEND=ollama            python -m eval.run_benchmark --with-llm   # base
LLM_BACKEND=ollama_finetuned  python -m eval.run_benchmark --with-llm   # fine-tuned
```
