"""
Phase 2, Module B — structured causal rule extraction with a local LLM
(Phi-3.5-mini via Ollama).

Design notes:
- Candidates are clauses with at least one OBLIGATION or PENALTY entity,
  priority-ranked and capped at LLM_MAX_CANDIDATES (a 600-page bill has
  hundreds of candidates; at ~5-10s/clause on a 4GB GPU that would be
  30-60+ minutes uncapped). scope="all" or explicit clause_ids override.
- Results are cached on disk keyed by sha1(clause_text) + model, so
  re-runs and resumed jobs are instant.
- Ollama serializes GPU inference (OLLAMA_NUM_PARALLEL=1 by default);
  batching overlaps HTTP/queueing, not compute.
"""
import asyncio
import hashlib
import json
import re
import time
from typing import Callable, Optional

import httpx

from config import (
    LLM_BATCH_SIZE,
    LLM_MAX_CANDIDATES,
    LLM_NUM_PREDICT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_S,
    OLLAMA_MODEL,
    OLLAMA_URL,
)
from models.schemas import Clause, LLMCausalRule
from storage import store

_PROMPT_TEMPLATE = """You are a legal AI. Extract causal policy rules from legal text.
Return ONLY a JSON object with exactly these fields:
{{
  "is_causal": true/false,
  "condition": "the triggering condition text or null",
  "action": "the required action/obligation text or null",
  "consequence": "the penalty/benefit/outcome text or null",
  "actors": ["list of affected parties"],
  "thresholds": ["list of numeric thresholds mentioned"],
  "confidence": 0.0-1.0,
  "reasoning": "one sentence explaining your extraction"
}}
Return nothing else. No markdown. No explanation outside the JSON.

Legal clause: {clause_text}"""

_REPAIR_SUFFIX = "\n\nYour previous answer was not valid JSON. Return ONLY the JSON object."

_MAX_CLAUSE_CHARS = 1200


def _cache_key(clause_text: str) -> str:
    digest = hashlib.sha1(clause_text.encode("utf-8")).hexdigest()
    return f"{digest}:{OLLAMA_MODEL}"


async def call_ollama(
    prompt: str,
    client: httpx.AsyncClient,
    num_predict: int = LLM_NUM_PREDICT,
) -> str:
    """Single Ollama generate call. Returns the raw response text."""
    response = await client.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": LLM_TEMPERATURE, "num_predict": num_predict},
        },
        timeout=LLM_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json().get("response", "")


def parse_llm_json(raw: str) -> Optional[dict]:
    """Parse (possibly messy) LLM output into a dict, or None."""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_rule(parsed: dict, elapsed_ms: int) -> LLMCausalRule:
    """Coerce loosely-typed LLM output into a valid LLMCausalRule."""
    def _str_or_none(v) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s and s.lower() not in ("null", "none", "n/a") else None

    def _str_list(v) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()][:12]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    condition = _str_or_none(parsed.get("condition"))
    action = _str_or_none(parsed.get("action"))
    consequence = _str_or_none(parsed.get("consequence"))

    is_causal = parsed.get("is_causal")
    if isinstance(is_causal, str):
        is_causal = is_causal.strip().lower() in ("true", "yes", "1")
    elif not isinstance(is_causal, bool):
        # The JSON parsed fine but the flag was missing/garbled. Don't discard
        # a good extraction: infer causality from the content it returned.
        if condition and (consequence or action):
            is_causal = True
        elif "is_causal" in parsed:
            is_causal = False  # explicitly present but unrecognized value
        else:
            is_causal = None

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return LLMCausalRule(
        is_causal=is_causal,
        condition=condition,
        action=action,
        consequence=consequence,
        actors=_str_list(parsed.get("actors")),
        thresholds=_str_list(parsed.get("thresholds")),
        confidence=confidence,
        # Bulk reasoning stays one sentence by prompt design, but don't hard-clip
        # a model that returns a fuller justification (deep reasoning is separate).
        reasoning=str(parsed.get("reasoning", "")).strip()[:2000],
        extraction_time_ms=elapsed_ms,
        model=OLLAMA_MODEL,
    )


async def extract_clause(clause_text: str, client: httpx.AsyncClient) -> LLMCausalRule:
    """Extract one clause: prompt → parse → one repair retry → fallback record."""
    prompt = _PROMPT_TEMPLATE.format(clause_text=clause_text[:_MAX_CLAUSE_CHARS])
    started = time.perf_counter()

    raw = await call_ollama(prompt, client)
    parsed = parse_llm_json(raw)
    if parsed is None:
        raw = await call_ollama(prompt + _REPAIR_SUFFIX, client)
        parsed = parse_llm_json(raw)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if parsed is None:
        return LLMCausalRule(
            is_causal=None,
            confidence=0.0,
            reasoning="",
            extraction_time_ms=elapsed_ms,
            model=OLLAMA_MODEL,
            parse_error=raw[:200] if raw else "empty response",
        )
    return _coerce_rule(parsed, elapsed_ms)


def select_candidates(
    clauses: list[Clause],
    scope: str = "auto",
    clause_ids: Optional[list[str]] = None,
) -> tuple[list[Clause], int]:
    """
    Pick clauses for LLM extraction.
    Returns (selected, total_candidates). Filter: has OBLIGATION or PENALTY
    entity. Priority: penalty signals > obligations, weighted by rule-based
    impact and entity density.
    """
    if clause_ids:
        wanted = set(clause_ids)
        selected = [c for c in clauses if c.clause_id in wanted]
        return selected, len(selected)

    def _is_candidate(c: Clause) -> bool:
        if c.clause_type == "table":
            return False
        return any(e.label in ("OBLIGATION", "PENALTY") for e in c.entities)

    candidates = [c for c in clauses if _is_candidate(c)]
    total = len(candidates)

    if scope == "all":
        return candidates, total

    def _priority(c: Clause) -> float:
        has_penalty_entity = any(e.label == "PENALTY" for e in c.entities)
        has_penalty_trigger = any(
            p.pattern_type == "PENALTY_TRIGGER" for p in c.causal_patterns
        )
        has_obligation = any(e.label == "OBLIGATION" for e in c.entities)
        max_impact = max((p.impact_score for p in c.causal_patterns), default=0.0)
        return (
            3.0 * has_penalty_entity
            + 2.0 * has_penalty_trigger
            + 1.0 * has_obligation
            + max_impact
            + c.complexity_score
        )

    candidates.sort(key=_priority, reverse=True)
    return candidates[:LLM_MAX_CANDIDATES], total


def compute_extraction_method(
    has_rule_pattern: bool, llm_is_causal: Optional[bool]
) -> str:
    if llm_is_causal is True:
        return "both" if has_rule_pattern else "llm"
    if llm_is_causal is False:
        return "conflict" if has_rule_pattern else "rule_based"
    return "rule_based"  # LLM extraction failed to parse


async def warmup(client: httpx.AsyncClient) -> None:
    """1-token generate so cold model load doesn't eat the first clause's timeout."""
    try:
        await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": "ok",
                "stream": False,
                "options": {"num_predict": 1},
            },
            timeout=max(LLM_TIMEOUT_S, 120),
        )
    except httpx.HTTPError:
        pass  # extraction calls will surface real connectivity errors


async def extract_document(
    doc_id: str,
    scope: str = "auto",
    clause_ids: Optional[list[str]] = None,
    force: bool = False,
    publish: Callable[[dict], None] = lambda ev: None,
) -> dict:
    """
    Run LLM extraction over a document's candidate clauses.
    Emits SSE-shaped events via `publish`; persists a cache after every
    batch (resume-safe) and merges extractions into the stored result.
    """
    result = store.get_result(doc_id)
    if result is None:
        raise ValueError(f"No analysis results for {doc_id}")

    cache = (store.load_llm_extractions(doc_id) or {}) if not force else {}
    entries: dict[str, dict] = cache.get("entries", {})

    selected, total_candidates = select_candidates(result.clauses, scope, clause_ids)
    cached_count = sum(
        1 for c in selected if entries.get(c.clause_id, {}).get("key") == _cache_key(c.text)
    )

    publish({
        "stage": "llm_started",
        "doc_id": doc_id,
        "total_candidates": total_candidates,
        "selected": len(selected),
        "capped": scope == "auto" and not clause_ids and total_candidates > len(selected),
        "cached": cached_count,
        "model": OLLAMA_MODEL,
    })

    summary = {"selected": len(selected), "causal_found": 0, "failed": 0,
               "agreement": {"both": 0, "llm_only": 0, "rule_only": 0, "neither": 0, "conflict": 0}}
    started = time.perf_counter()
    done_count = 0

    async with httpx.AsyncClient() as client:
        await warmup(client)

        async def _process(clause: Clause) -> tuple[Clause, LLMCausalRule, bool]:
            key = _cache_key(clause.text)
            cached_entry = entries.get(clause.clause_id)
            if cached_entry is not None and cached_entry.get("key") == key:
                return clause, LLMCausalRule(**cached_entry["extraction"]), True
            publish({"stage": "llm_clause", "clause_id": clause.clause_id, "status": "processing"})
            rule = await extract_clause(clause.text, client)
            return clause, rule, False

        for batch_start in range(0, len(selected), LLM_BATCH_SIZE):
            batch = selected[batch_start:batch_start + LLM_BATCH_SIZE]
            outcomes = await asyncio.gather(*(_process(c) for c in batch), return_exceptions=True)

            for clause, outcome in zip(batch, outcomes):
                done_count += 1
                if isinstance(outcome, BaseException):
                    summary["failed"] += 1
                    publish({
                        "stage": "llm_clause",
                        "clause_id": clause.clause_id,
                        "status": "error",
                        "error": str(outcome)[:200],
                        "current": done_count,
                        "total": len(selected),
                        "progress": done_count / max(len(selected), 1),
                    })
                    continue

                clause_obj, rule, from_cache = outcome
                has_rule_pattern = len(clause_obj.causal_patterns) > 0
                method = compute_extraction_method(has_rule_pattern, rule.is_causal)

                if rule.is_causal is True:
                    summary["causal_found"] += 1
                if rule.is_causal is None:
                    summary["failed"] += 1
                    summary["agreement"]["neither"] += 1
                elif method == "both":
                    summary["agreement"]["both"] += 1
                elif method == "llm":
                    summary["agreement"]["llm_only"] += 1
                elif method == "conflict":
                    summary["agreement"]["conflict"] += 1
                elif has_rule_pattern:
                    summary["agreement"]["rule_only"] += 1
                else:
                    summary["agreement"]["neither"] += 1

                # Don't persist a parse failure as a terminal result — otherwise
                # the sha1(text)+model cache replays it forever and the clause is
                # never re-attempted. Live SSE still shows it this run.
                if rule.is_causal is not None:
                    entries[clause_obj.clause_id] = {
                        "key": _cache_key(clause_obj.text),
                        "extraction": rule.model_dump(),
                        "extraction_method": method,
                    }

                publish({
                    "stage": "llm_clause",
                    "clause_id": clause_obj.clause_id,
                    "status": "done",
                    "current": done_count,
                    "total": len(selected),
                    "progress": done_count / max(len(selected), 1),
                    "from_cache": from_cache,
                    "extraction_method": method,
                    "extraction": rule.model_dump(),
                })

            # Persist after every batch — resume-safe.
            store.save_llm_extractions(doc_id, {"model": OLLAMA_MODEL, "entries": entries})

    # Merge into the stored analysis result (single-writer via store lock).
    def _merge(analysis):
        for clause in analysis.clauses:
            entry = entries.get(clause.clause_id)
            if entry is not None:
                clause.llm_extraction = LLMCausalRule(**entry["extraction"])
                clause.extraction_method = entry["extraction_method"]

    store.update_result(doc_id, _merge)

    summary["total_time_ms"] = int((time.perf_counter() - started) * 1000)
    publish({"stage": "llm_complete", "doc_id": doc_id, "summary": summary})
    return summary
