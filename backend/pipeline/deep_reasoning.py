"""
Phase 3 — on-demand deep reasoning for a single clause.

The bulk LLM extraction (llm_extractor.py) deliberately asks for a one-sentence
`reasoning` so it can process dozens of candidates quickly on a 4GB GPU. This
module is the opposite: for the ONE clause a user is looking at in the
Explainability Studio, it generates a rich, multi-paragraph, statute-grounded
rationale — reading the FULL clause (not the 1200-char extraction truncation)
and the already-computed structured rule.

Results are cached on disk keyed by sha1(clause_text)+model, so re-opening the
same clause is instant. This keeps overall analysis fast while making the
explanation deep exactly where the user is paying attention.
"""
import hashlib
import json
import time
from typing import Optional

from config import LLM_TEMPERATURE
from pipeline import llm_backend
from storage import store


def _active_model() -> str:
    return llm_backend.active_backend()["model"]

# A single clause can be long; cap generously (far above the bulk 1200) while
# staying within the small local model's context budget.
_MAX_DEEP_CHARS = 4000
_DEEP_NUM_PREDICT = 700

_DEEP_PROMPT = """You are a senior legal analyst explaining a statutory clause to a policy audience. Ground every statement in the clause's actual wording — do not invent facts not present in the text.

Explain the clause in clear prose (a few short paragraphs, no JSON, no bullet markup), covering:
1. Trigger — the condition or event that activates this provision.
2. Obligation / action — what must be done, and by whom.
3. Consequence — the penalty, benefit, or outcome, and how significant it is.
4. Thresholds & figures — how any monetary limits, rates, or time periods apply.
5. Affected parties — who bears the obligation and who benefits, and why.
6. Ambiguities — any edge cases or unclear language a practitioner should note.

Clause:
{clause_text}

A structured extraction has already been computed for reference (you may correct it if the text disagrees):
{extraction}

Write the explanation now:"""


def _fingerprint(clause_text: str) -> str:
    return hashlib.sha1(f"{clause_text}::{_active_model()}::deep".encode("utf-8")).hexdigest()


def _extraction_summary(extraction: Optional[dict]) -> str:
    if not extraction:
        return "(none available)"
    keep = {k: extraction.get(k) for k in ("condition", "action", "consequence", "actors", "thresholds")}
    return json.dumps({k: v for k, v in keep.items() if v}, ensure_ascii=False)


async def generate_deep_reasoning(
    doc_id: str,
    clause_id: str,
    clause_text: str,
    extraction: Optional[dict] = None,
    force: bool = False,
) -> dict:
    """Generate (or replay from cache) a deep rationale for one clause."""
    fp = _fingerprint(clause_text)
    if not force:
        cached = store.load_deep_reasoning(doc_id, clause_id)
        if cached is not None and cached.get("fingerprint") == fp:
            return {**cached, "cached": True}

    prompt = _DEEP_PROMPT.format(
        clause_text=clause_text[:_MAX_DEEP_CHARS],
        extraction=_extraction_summary(extraction),
    )
    started = time.perf_counter()
    # Free-form prose via the active backend (Ollama local or Groq cloud) —
    # multi-paragraph, so temperature is nudged up and no JSON format is forced.
    text = (await llm_backend.generate(
        prompt,
        temperature=min(0.4, LLM_TEMPERATURE + 0.15),
        num_predict=_DEEP_NUM_PREDICT,
    )).strip()
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    payload = {
        "clause_id": clause_id,
        "reasoning": text,
        "model": _active_model(),
        "fingerprint": fp,
        "generation_time_ms": elapsed_ms,
        "cached": False,
    }
    # Only persist a non-empty result so a transient failure isn't cached forever.
    if text:
        store.save_deep_reasoning(doc_id, clause_id, payload)
    return payload
