# Fine-tuning a local extractor

Can a 3.8B model that runs on a laptop (Phi-3.5-mini, 4-bit) approach the
hosted models at statutory rule extraction after fine-tuning on statute
provisions? This directory builds the training data, trains QLoRA adapters
on a Kaggle/Colab GPU, and turns the result into an Ollama model that the
evaluation and the headline experiment use as system `prism-legal`.

## 1. Silver data (local, needs `GROQ_API_KEY` and `GEMINI_API_KEY`)

```bash
python training/build_dataset.py --pool 800 --dry-run   # sample + leakage report only
python training/build_dataset.py --pool 800
```

- Two teachers (GPT-OSS-120B and Gemini Flash) extract every sampled
  provision with the production prompt. Only provisions where they agree
  after grounding (same rules, modalities, effect kinds and numbers) are kept;
  the target is the grounded record, so every quoted string is statute text.
- Excluded: every provision in the frozen evaluation sets, any provision
  sharing more than 20% of its word 8-grams with one, every provision the
  headline experiment extracts, and the whole DPDP Act (held out for transfer).
- Outputs `data/sft.jsonl` and `data/sft_report.json` (pool, exclusions,
  agreement rate, label mix, data hash). Teacher calls are cached, so an
  interrupted build resumes where it stopped (free-tier quotas).

## 2. Train (Kaggle)

Upload `data/sft.jsonl` as a Kaggle dataset named `prism-sft`, open
`kaggle_qlora.ipynb`, enable a GPU and internet, and run all cells. It:

- trains QLoRA adapters (NF4, r=16) on `qkv_proj, o_proj, gate_up_proj,
  down_proj` with loss on the assistant turn only;
- fails unless every one of those module types received an update
  (`train_summary.json` records the norms);
- merges, converts to GGUF and quantises to Q4_K_M (~2.4 GB).

## 3. Serve and evaluate (local)

```bash
python training/export_ollama.py register --gguf prism-legal-q4_k_m.gguf
cd backend
python -m cli eval-run --system prism-legal --split test
python -m cli eval-score --system prism-legal --split test
python -m cli experiment --systems prism-legal,phi3.5
```

Compare against the base `phi3.5` system on the same items; the DPDP items in
the test set measure transfer to a statute the model never saw.
