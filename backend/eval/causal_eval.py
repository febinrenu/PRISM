"""
Causal-extraction benchmark — binary "is this clause causal/obligation-bearing?"
precision/recall/F1 for each system:
  - rule_based : Phase-1 regex causal detector (offline, always available)
  - llm        : Phi-3.5-mini zero-shot via Ollama (optional — needs the service)

Gold format: [{text, is_causal: bool, ...}]. Span-level quality (condition/action)
is scored with embedding cosine when the gold provides spans; CUAD does not, so
that path is exercised only by in-domain gold sets.
"""
import asyncio
from typing import Optional

from pipeline.causal_detector import detect_causal_patterns
from eval.metrics import binary_prf1


def _rule_based_pred(text: str) -> bool:
    try:
        return len(detect_causal_patterns(text, "eval")) > 0
    except Exception:
        return False


def evaluate_rule_based(gold: list[dict]) -> dict:
    g = [bool(item["is_causal"]) for item in gold]
    p = [_rule_based_pred(item["text"]) for item in gold]
    return binary_prf1(g, p)


def evaluate_llm(gold: list[dict], timeout_s: float = 60.0) -> Optional[dict]:
    """Zero-shot LLM causal classification. Returns None if Ollama is
    unreachable (so the harness can skip this system cleanly)."""
    import httpx
    from pipeline.llm_extractor import extract_clause

    async def _run() -> list[bool]:
        preds: list[bool] = []
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            for item in gold:
                rule = await extract_clause(item["text"], client)
                preds.append(bool(rule.is_causal))
        return preds

    try:
        # Fail fast if the service isn't up.
        import httpx as _httpx
        from config import OLLAMA_URL
        _httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0).raise_for_status()
    except Exception:
        return None

    g = [bool(item["is_causal"]) for item in gold]
    p = asyncio.run(_run())
    return binary_prf1(g, p)


def span_similarity(pred_spans: list[str], gold_spans: list[str]) -> Optional[float]:
    """Mean best-match cosine similarity between predicted and gold spans, using
    the MiniLM embedder (normalized → dot product = cosine). None if no spans."""
    pred_spans = [s for s in pred_spans if s]
    gold_spans = [s for s in gold_spans if s]
    if not pred_spans or not gold_spans:
        return None
    from pipeline.embedder import embed_texts
    import numpy as np

    pe = embed_texts(pred_spans)
    ge = embed_texts(gold_spans)
    sims = pe @ ge.T  # (P, G)
    return round(float(np.mean(np.max(sims, axis=1))), 4)
