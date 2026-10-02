"""
Phase 3, Module G — evaluate the live systems against the in-domain, human-
reviewed gold sets (Income Tax Bill), as opposed to the out-of-domain LEDGAR set.

This is what turns "the pipeline runs" into a results table: NER F1, causal
P/R/F1, and RAG retrieval@k measured on real Indian-statute clauses a human
confirmed. Only items with `reviewed: true` are scored — bootstrap candidates
that were never checked are excluded (and counted, so coverage is honest).

    python -m eval.gold_eval [--with-llm]
"""
from typing import Optional

from eval import causal_eval, ner_eval
from eval.gold_builder import load_gold


def _causal_to_eval_shape(items: list[dict]) -> list[dict]:
    return [{"text": it["text"], "is_causal": bool(it["gold_is_causal"])} for it in items]


def _ner_to_eval_shape(items: list[dict]) -> list[dict]:
    return [{"text": it["text"], "entities": it["gold_entities"]} for it in items]


def evaluate_causal_gold(with_llm: bool = False) -> dict:
    reviewed = load_gold("causal", reviewed_only=True)
    total = len(load_gold("causal"))
    if not reviewed:
        return {"note": "no reviewed causal gold — run eval.review_gold --set causal", "reviewed": 0, "total": total}
    gold = _causal_to_eval_shape(reviewed)
    out = {"reviewed": len(reviewed), "total": total, "rule_based": causal_eval.evaluate_rule_based(gold)}
    if with_llm:
        llm = causal_eval.evaluate_llm(gold)
        out["llm"] = llm if llm is not None else {"note": "Ollama unreachable"}
    return out


def evaluate_ner_gold() -> dict:
    reviewed = load_gold("ner", reviewed_only=True)
    total = len(load_gold("ner"))
    if not reviewed:
        return {"note": "no reviewed NER gold — run eval.review_gold --set ner", "reviewed": 0, "total": total}
    gold = _ner_to_eval_shape(reviewed)
    out = {
        "reviewed": len(reviewed), "total": total,
        "presence": ner_eval.evaluate_ner_presence(gold),
    }
    spans = ner_eval.evaluate_ner_spans(gold)
    out["spans"] = spans or {"note": "seqeval not installed"}
    return out


def evaluate_rag_retrieval(top_k: int = 8) -> dict:
    """retrieval@k: does the RAG retriever surface the clause each question was
    generated from? Reports recall@1 and recall@k over reviewed QA pairs."""
    reviewed = load_gold("rag_qa", reviewed_only=True)
    total = len(load_gold("rag_qa"))
    if not reviewed:
        return {"note": "no reviewed RAG QA — run eval.review_gold --set rag_qa", "reviewed": 0, "total": total}
    try:
        from rag import corpus_builder
        if corpus_builder.corpus_stats()["total_clauses"] == 0:
            return {"note": "corpus empty — ingest a document first", "reviewed": len(reviewed), "total": total}
    except Exception as e:
        return {"note": f"corpus unavailable: {e}", "reviewed": len(reviewed), "total": total}

    hit1 = hitk = 0
    for it in reviewed:
        hits = corpus_builder.semantic_search(it["question"], n_results=top_k)
        ids = [h.get("clause_id") for h in hits]
        gold_id = it["gold_clause_id"]
        if ids and ids[0] == gold_id:
            hit1 += 1
        if gold_id in ids:
            hitk += 1
    n = len(reviewed)
    return {
        "reviewed": n, "total": total, "top_k": top_k,
        "recall_at_1": round(hit1 / n, 4),
        "recall_at_k": round(hitk / n, 4),
    }


def run_gold_eval(with_llm: bool = False) -> dict:
    return {
        "causal": evaluate_causal_gold(with_llm=with_llm),
        "ner": evaluate_ner_gold(),
        "rag_retrieval": evaluate_rag_retrieval(),
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Evaluate against in-domain gold sets.")
    ap.add_argument("--with-llm", action="store_true")
    args = ap.parse_args()
    print(json.dumps(run_gold_eval(with_llm=args.with_llm), indent=2))
