"""
Phase 2 — LIME token-level explainability for causal classification.

Two classifier modes:
  mode="llm"   — faithful: each LIME perturbation is classified by the local
                 LLM (short prompt, is_causal + confidence only). ~50 Ollama
                 calls ≈ 1.5–3 minutes on a 4GB GPU. Runs in a worker thread
                 with per-sample progress callbacks.
  mode="proxy" — fast (~1s): the Phase 1 rule-based causal detector serves as
                 the classifier. This explains the RULE-BASED model, not the
                 LLM — an interactive preview, labeled as such in the API/UI.

Explanations are cached on disk keyed by sha1(text) + mode + num_samples.
"""
import hashlib
import re
import time
from typing import Callable, Optional

import httpx
import numpy as np
from lime.lime_text import LimeTextExplainer

from config import (
    LIME_NUM_FEATURES,
    LIME_NUM_SAMPLES,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_S,
    OLLAMA_MODEL,
    OLLAMA_URL,
)
from pipeline.causal_detector import detect_causal_patterns
from pipeline.llm_extractor import parse_llm_json
from storage import store

_CLASSIFY_PROMPT = """You are a legal AI. Does the following legal text describe a causal rule
(a condition that triggers an action, obligation, penalty, or consequence)?
Return ONLY a JSON object: {{"is_causal": true/false, "confidence": 0.0-1.0}}

Legal text: {text}"""


def _cache_fingerprint(text: str, mode: str, num_samples: int) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"{digest}:{mode}:{num_samples}:{OLLAMA_MODEL if mode == 'llm' else 'rules'}"


def _proxy_proba(texts: list[str]) -> np.ndarray:
    """P(causal) from the Phase 1 rule-based detector."""
    rows = []
    for text in texts:
        try:
            patterns = detect_causal_patterns(text, "lime_probe")
        except Exception:
            patterns = []
        if not patterns:
            p_causal = 0.05
        else:
            p_causal = min(0.95, 0.5 + 0.45 * max(p.confidence for p in patterns))
        rows.append([1.0 - p_causal, p_causal])
    return np.array(rows)


def _llm_proba_factory(progress: Callable[[int, int], None], expected_total: int):
    """Sequential sync Ollama classifier for LIME perturbations."""
    counter = {"done": 0}

    def _classify(texts: list[str]) -> np.ndarray:
        rows = []
        with httpx.Client(timeout=LLM_TIMEOUT_S) as client:
            for text in texts:
                p_causal = 0.5
                try:
                    response = client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": OLLAMA_MODEL,
                            "prompt": _CLASSIFY_PROMPT.format(text=text[:1200]),
                            "stream": False,
                            "format": "json",
                            "options": {"temperature": LLM_TEMPERATURE, "num_predict": 48},
                        },
                    )
                    response.raise_for_status()
                    parsed = parse_llm_json(response.json().get("response", ""))
                    if parsed is not None:
                        conf = float(parsed.get("confidence", 0.5) or 0.5)
                        conf = max(0.0, min(1.0, conf))
                        is_causal = parsed.get("is_causal")
                        if isinstance(is_causal, str):
                            is_causal = is_causal.strip().lower() in ("true", "yes", "1")
                        p_causal = conf if is_causal else 1.0 - conf
                except Exception:
                    pass  # keep the uninformative 0.5 prior for failed samples
                rows.append([1.0 - p_causal, p_causal])
                counter["done"] += 1
                progress(counter["done"], expected_total)
        return np.array(rows)

    return _classify


def _token_positions(clause_text: str, tokens: list[str]) -> dict[str, list[int]]:
    """Char positions of each whole-word token occurrence (LIME reports unique
    words). Word-boundary matching prevents a token like "tax" from
    highlighting inside "taxation", which misaligned the heatmap overlay."""
    positions: dict[str, list[int]] = {}
    for token in tokens:
        needle = token.strip()
        found: list[int] = []
        if needle:
            pattern = re.compile(r"\b" + re.escape(needle) + r"\b", re.IGNORECASE)
            found = [m.start() for m in pattern.finditer(clause_text)]
        positions[token] = found
    return positions


def _fidelity_score(explanation) -> Optional[float]:
    """Extract LIME's local-surrogate R² (``explanation.score``) robustly across
    lime versions: it may be a float or a dict keyed by label. Returns a float
    in [0, 1]-ish (R² can dip slightly negative) or None if unavailable."""
    score = getattr(explanation, "score", None)
    if score is None:
        return None
    try:
        if isinstance(score, dict):
            if not score:
                return None
            # Prefer the "causal" label (1) if present, else the first entry.
            val = score.get(1, next(iter(score.values())))
        else:
            val = score
        return round(float(val), 4)
    except (TypeError, ValueError):
        return None


def explain_clause(
    doc_id: str,
    clause_id: str,
    clause_text: str,
    mode: str = "proxy",
    num_samples: Optional[int] = None,
    progress: Callable[[int, int], None] = lambda done, total: None,
) -> dict:
    """
    Run LIME on one clause (synchronous / CPU+network bound — call from a
    worker thread). Returns the cacheable payload dict.
    """
    num_samples = num_samples or LIME_NUM_SAMPLES
    fingerprint = _cache_fingerprint(clause_text, mode, num_samples)

    cached = store.load_lime(doc_id, clause_id, mode)
    if cached is not None and cached.get("fingerprint") == fingerprint:
        return {**cached, "cached": True}

    started = time.perf_counter()
    explainer = LimeTextExplainer(class_names=["non_causal", "causal"], random_state=42)

    if mode == "llm":
        classifier = _llm_proba_factory(progress, num_samples + 1)
    else:
        classifier = _proxy_proba

    explanation = explainer.explain_instance(
        clause_text,
        classifier,
        num_features=LIME_NUM_FEATURES,
        num_samples=num_samples,
    )

    token_weights = explanation.as_list()  # [(token, weight), ...]
    max_abs = max((abs(w) for _, w in token_weights), default=1.0) or 1.0
    positions = _token_positions(clause_text, [t for t, _ in token_weights])

    # Local-surrogate fidelity: R² of the linear model LIME fits to the
    # perturbation samples. Higher = the token weights explain the classifier's
    # local behavior more faithfully. LIME discards this by default; we keep it
    # so the UI/eval can report explanation quality.
    fidelity = _fidelity_score(explanation)

    lime_tokens = []
    for token, weight in token_weights:
        for pos in positions.get(token, [-1]) or [-1]:
            lime_tokens.append({
                "token": token,
                "weight": round(float(weight), 6),
                "normalized_weight": round(abs(float(weight)) / max_abs, 4),
                "position": pos,
            })

    proba = classifier([clause_text])[0]
    payload = {
        "fingerprint": fingerprint,
        "clause_id": clause_id,
        "mode": mode,
        "num_samples": num_samples,
        "model": OLLAMA_MODEL if mode == "llm" else "rule_based_proxy",
        "prediction": {
            "is_causal": bool(proba[1] >= 0.5),
            "p_causal": round(float(proba[1]), 4),
        },
        "lime_tokens": lime_tokens,
        "top_tokens": [[t, round(float(w), 4)] for t, w in token_weights],
        "fidelity": fidelity,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "cached": False,
    }

    store.save_lime(doc_id, clause_id, mode, payload)

    # Flag the clause so the UI can show "explanation available".
    def _mark(analysis):
        for clause in analysis.clauses:
            if clause.clause_id == clause_id:
                clause.lime_available = True
                break

    store.update_result(doc_id, _mark)
    return payload
