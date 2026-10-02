"""
Phase 3, Module E — instruction-tuning dataset builder.

Assembles an Alpaca-format dataset for QLoRA fine-tuning of Phi-3.5-mini from
three sources (all free / already on disk):

  1. Synthetic PRISM extractions — every clause where the Phase-2 LLM extracted a
     causal rule becomes a (clause → structured-JSON) example. This is the
     highest-value source: it distils PRISM's own pipeline into training data.
  2. Legal NER pairs — clauses with labeled entities become
     (clause → entity list) examples.
  3. LEDGAR provisions — public, expert-labeled contract clauses reused from the
     eval harness for an obligation-classification instruction.

Output: training/data/prism_instructions.jsonl (one {"text": ...} per line, the
full prompt already rendered in Phi-3.5 chat format) + a raw
prism_instructions.raw.json for inspection. Runs on CPU in seconds — no GPU.

Usage:
    python training/build_dataset.py [--limit-ledgar 400] [--max-per-doc 400]
"""
import argparse
import json
import sys
from pathlib import Path

# Make the sibling backend importable (store, config, eval loaders).
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT_DIR = Path(__file__).resolve().parent / "data"

_EXTRACT_INSTR = (
    "Extract the causal policy rule from the following legal clause. Return a "
    "JSON object with fields: condition, action, consequence, actors, thresholds."
)
_NER_INSTR = (
    "Identify all legal entities in this clause. Return a JSON list of "
    "{text, label} where label is one of OBLIGATION, RIGHT, PENALTY, THRESHOLD, "
    "ACTOR, BENEFICIARY."
)
_CLASSIFY_INSTR = (
    "Does the following contract clause impose a duty, penalty, or restriction? "
    'Answer with a JSON object {"is_obligation": true/false, "category": "..."}.'
)

# Phi-3.5 instruct chat template.
_CHAT = "<|system|>\n{system}<|end|>\n<|user|>\n{user}<|end|>\n<|assistant|>\n{assistant}<|end|>"
_SYSTEM = (
    "You are PRISM Legal AI, fine-tuned on Indian legal documents. You extract "
    "causal policy rules, identify legal entities, and classify clauses."
)


def _render(instruction: str, input_text: str, output_obj) -> dict:
    user = f"{instruction}\n\nClause:\n{input_text}"
    assistant = json.dumps(output_obj, ensure_ascii=False)
    return {
        "text": _CHAT.format(system=_SYSTEM, user=user, assistant=assistant),
        "instruction": instruction,
        "input": input_text,
        "output": assistant,
    }


def from_prism_extractions(max_per_doc: int = 400) -> list[dict]:
    """Source 1 + 2: synthetic extraction + NER examples from stored analyses."""
    from storage import store

    examples: list[dict] = []
    for meta in store.list_documents():
        result = store.get_result(meta.doc_id)
        if result is None:
            continue
        count = 0
        for clause in result.clauses:
            if count >= max_per_doc:
                break
            if clause.clause_type == "table" or len(clause.text.strip()) < 40:
                continue
            ex = clause.llm_extraction
            # Source 1: causal extraction (only confident, causal, parsed ones).
            if ex is not None and ex.is_causal:
                out = {
                    "condition": ex.condition, "action": ex.action,
                    "consequence": ex.consequence, "actors": ex.actors,
                    "thresholds": ex.thresholds,
                }
                examples.append(_render(_EXTRACT_INSTR, clause.text[:1000], out))
                count += 1
            # Source 2: NER pairs (any clause with labeled entities).
            if clause.entities:
                ents = [{"text": e.text, "label": e.label} for e in clause.entities][:12]
                examples.append(_render(_NER_INSTR, clause.text[:1000], ents))
                count += 1
    return examples


def from_ledgar(limit: int = 400) -> list[dict]:
    """Source 3: public LEDGAR obligation-classification examples."""
    try:
        from eval.datasets_cuad import load_eval_set
    except Exception:
        return []
    items, _source = load_eval_set(limit=limit)
    out = []
    for it in items:
        out.append(_render(
            _CLASSIFY_INSTR, it["text"],
            {"is_obligation": bool(it["is_causal"]), "category": it.get("category", "")},
        ))
    return out


def build(max_per_doc: int, limit_ledgar: int) -> dict:
    prism = from_prism_extractions(max_per_doc=max_per_doc)
    ledgar = from_ledgar(limit=limit_ledgar)
    all_examples = prism + ledgar

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl = OUT_DIR / "prism_instructions.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps({"text": ex["text"]}, ensure_ascii=False) + "\n")
    (OUT_DIR / "prism_instructions.raw.json").write_text(
        json.dumps(all_examples, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {
        "total": len(all_examples),
        "from_prism_pipeline": len(prism),
        "from_ledgar": len(ledgar),
        "output_jsonl": str(jsonl),
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the PRISM QLoRA instruction dataset.")
    ap.add_argument("--max-per-doc", type=int, default=400)
    ap.add_argument("--limit-ledgar", type=int, default=400)
    args = ap.parse_args()

    summary = build(args.max_per_doc, args.limit_ledgar)
    print(json.dumps(summary, indent=2))
    if summary["total"] == 0:
        print("\n[warn] No examples produced. Run the Phase-2 LLM extraction on at "
              "least one document first (analyze → LLM extraction), then re-run.")
    else:
        print(f"\n[ok] Wrote {summary['total']} instruction examples.")


if __name__ == "__main__":
    main()
