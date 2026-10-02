# Quarantined v1 artefacts

These files were produced before the October 2026 rebuild. They are kept for
traceability only. Nothing in the current evaluation, training or paper reads
from this folder, and none of it is valid evidence.

| Path | What it is | Why it is invalid |
|---|---|---|
| `eval_gold/` | NER (200), causal (100) and RAG-QA (50) "gold" sets | Every label is identical to the system's own candidate output (bulk-accepted, no human edits). Causal positives were seeded from the LLM's own extractions. |
| `ledgar_eval.json` | 120 LEDGAR contract provisions mapped to causal / non-causal | Contract-category classification is a different task, and every item also appears in the v1 fine-tuning data. |
| `eval_results/` | v1 benchmark outputs and figures | Computed on the sets above. The simulation KL compares each sampler with its own target distribution. |
| `training_data/` | v1 fine-tuning set (1,167 examples) | Self-distilled from rule-NER and LLM output, overlaps the eval sets, and includes extractions attached to the wrong clause. |
| `demo_store/llm_extractions.json` | v1 Phi-3.5 extraction cache for the demo statute | Keyed by positional clause ID; 39 of 78 entries were attached to the wrong clause after re-segmentation. Generated with a prompt that silently truncated clauses at 1,200 characters. |
| `demo_store/lime/`, `demo_store/deep_reasoning/` | Cached explanations | Their fingerprints no longer match the clause text; the LIME files used 50 samples. |
| `demo_store/simulations/` | Stored simulation runs | Produced by the v1 engine, which divides annual cost by monthly ability-to-pay and accumulates effective rates over the run length. |

The replacement data lives under `backend/data/eval/v2/` (frozen evaluation
sets), `backend/data/annotations/` (human annotation) and `backend/data/runs/`
(run manifests).
