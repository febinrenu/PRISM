"""
LIME evaluation:
  - fidelity : mean local-surrogate R² across cached explanations (now that
    lime_explainer persists explanation.score).
  - agreement: for clauses explained in BOTH proxy and llm mode, the Jaccard
    overlap of their top-token sets — how well the fast rule-based preview
    approximates the faithful LLM explanation.

Reads only what's already cached on disk; never runs LIME itself.
"""
from eval.metrics import jaccard
from storage import store


def evaluate_lime(doc_id: str, clause_ids: list[str], top_k: int = 8) -> dict:
    proxy_fid, llm_fid = [], []
    agreements = []

    for clause_id in clause_ids:
        proxy = store.load_lime(doc_id, clause_id, "proxy")
        llm = store.load_lime(doc_id, clause_id, "llm")

        if proxy and isinstance(proxy.get("fidelity"), (int, float)):
            proxy_fid.append(float(proxy["fidelity"]))
        if llm and isinstance(llm.get("fidelity"), (int, float)):
            llm_fid.append(float(llm["fidelity"]))

        if proxy and llm:
            pt = [t for t, _ in proxy.get("top_tokens", [])[:top_k]]
            lt = [t for t, _ in llm.get("top_tokens", [])[:top_k]]
            agreements.append(jaccard(pt, lt))

    def _mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "n_clauses": len(clause_ids),
        "proxy_fidelity_mean": _mean(proxy_fid),
        "llm_fidelity_mean": _mean(llm_fid),
        "proxy_vs_llm_agreement_mean": _mean(agreements),
        "n_with_both_modes": len(agreements),
    }
