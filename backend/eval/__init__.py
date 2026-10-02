"""
PRISM evaluation harness (Module G).

Turns PRISM's claims into measurable numbers for the IEEE paper:
  - NER entity-level F1 (seqeval)              → ner_eval.py
  - causal-extraction precision/recall/F1      → causal_eval.py
  - template-matching precision@1              → causal_eval.py / templates
  - LIME local-surrogate fidelity + agreement  → lime_fidelity.py
  - simulation validity (KL vs calibrated ref) → sim_validity.py

`run_benchmark.py` orchestrates everything and writes results/ tables + charts.
The metric functions in `metrics.py` are dependency-light and unit-tested
offline; dataset loading (CUAD) and the LLM path require network/services and
are guarded so the harness degrades gracefully.
"""
