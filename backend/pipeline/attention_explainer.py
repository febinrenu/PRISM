"""
Phase 3 (bonus XAI) — transformer attention-weight extraction.

A second, complementary explanation to LIME. Where LIME perturbs inputs and fits
a local surrogate, this reads the model's *internal* self-attention directly:
per-token salience = mean attention received across all heads and layers.

Important honesty note: this explains the **sentence-embedding transformer**
(all-MiniLM-L6-v2), which is already loaded for search/UMAP/templates — NOT the
Phi-3.5 generator. Extracting Phi-3.5's attention would require loading the raw
`transformers` model weights on the GPU (out of scope here). So attention here
is "what the encoder attends to when representing this clause", surfaced
alongside LIME as a distinct lens. Cached like LIME under mode="attention".

CPU-only, ~50-150ms per clause; no extra model download.
"""
import hashlib
import re
import time
from typing import Optional

from config import OLLAMA_MODEL  # noqa: F401  (kept for parity; not used)
from storage import store

_WORD_RE = re.compile(r"\S+")

# The encoder must use the *eager* attention implementation — PyTorch's default
# SDPA backend fuses attention and returns no per-token weights (output_attentions
# yields an empty tuple). We load a dedicated eager copy once (CPU, ~90MB, same
# weights as the embedder) so attention extraction is reliable.
_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
_enc_model = None
_enc_tokenizer = None


def _get_eager_encoder():
    global _enc_model, _enc_tokenizer
    if _enc_model is None:
        from transformers import AutoModel, AutoTokenizer
        _enc_tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        _enc_model = AutoModel.from_pretrained(
            _MODEL_ID, attn_implementation="eager", output_attentions=True
        )
        _enc_model.eval()
    return _enc_model, _enc_tokenizer


def _word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def explain_attention(doc_id: str, clause_id: str, clause_text: str) -> dict:
    """Extract per-word attention salience from the MiniLM encoder. Returns the
    same token shape as LIME ({token, weight, normalized_weight, position}) so
    the frontend heatmap can render it directly. Cached on disk."""
    cached = store.load_lime(doc_id, clause_id, "attention")
    text_sha = hashlib.sha1(clause_text.encode("utf-8")).hexdigest()
    if cached is not None and cached.get("text_sha1") == text_sha:
        return {**cached, "cached": True}

    started = time.perf_counter()
    import numpy as np
    import torch

    transformer, tokenizer = _get_eager_encoder()

    enc = tokenizer(
        clause_text, return_tensors="pt", truncation=True, max_length=256,
        return_offsets_mapping=True,
    )
    offsets = enc.pop("offset_mapping")[0].tolist()

    with torch.no_grad():
        out = transformer(**enc, output_attentions=True)

    # attentions: tuple over layers, each (batch=1, heads, seq, seq).
    # Mean over layers and heads → (seq, seq); salience of token j = mean
    # attention it *receives* across all query positions.
    att = torch.stack(out.attentions).mean(dim=0).mean(dim=1)[0]  # (seq, seq)
    received = att.mean(dim=0).cpu().numpy()  # (seq,)

    # Aggregate subword salience into whitespace words via char offsets.
    spans = _word_spans(clause_text)
    word_weight = [0.0] * len(spans)
    for tok_idx, (cs, ce) in enumerate(offsets):
        if cs == ce:  # special token ([CLS]/[SEP]/pad) → offset (0,0)
            continue
        for wi, (ws, we) in enumerate(spans):
            if cs < we and ce > ws:  # subword overlaps this word
                word_weight[wi] += float(received[tok_idx])
                break

    max_w = max(word_weight, default=1.0) or 1.0
    tokens = []
    for (ws, we), w in zip(spans, word_weight):
        tokens.append({
            "token": clause_text[ws:we],
            "weight": round(w, 6),
            "normalized_weight": round(w / max_w, 4),
            "position": ws,
        })

    top = sorted(tokens, key=lambda t: t["weight"], reverse=True)[:12]
    payload = {
        "clause_id": clause_id,
        "mode": "attention",
        "model": "all-MiniLM-L6-v2",
        "explains": "sentence-embedding encoder (not the Phi-3.5 generator)",
        "text_len": len(clause_text),
        "text_sha1": text_sha,
        "lime_tokens": tokens,
        "top_tokens": [[t["token"], t["weight"]] for t in top],
        "prediction": None,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "cached": False,
    }
    store.save_lime(doc_id, clause_id, "attention", payload)
    return payload
