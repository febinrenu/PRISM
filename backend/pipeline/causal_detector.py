"""
Rule-based causal pattern detection for legal clauses.
Each pattern receives a risk_tier (CRITICAL/HIGH/MEDIUM/LOW) and
impact_score (0.0–1.0) based on linguistic content.

Phase 2 will replace/augment this with Phi-3.5-mini LLM extraction.

Matching is scoped to one sentence at a time (clauses are frequently
multi-sentence paragraphs) so a condition in one sentence can't pair with an
unrelated consequence in the next; overlapping matches from different
patterns are then collapsed to the single highest-confidence one.
"""
import re
from models.schemas import CausalPattern
from pipeline.clause_segmenter import _SENTENCE_BOUNDARY_RE


# ─── Pattern definitions ───────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # IF-THEN: "If X, (then/shall) Y" — allows a subject between the comma
    # and the modal ("If X, the Assessing Officer shall Y"), which is the
    # dominant formulation in statutes.
    ("IF_THEN", re.compile(
        r"(?i)\b(if|when|in\s+case)\b"
        r"(.{10,250}?)"
        r"(?:,\s*)"
        r"((?:[^,]{0,80}?\s)?(?:then|shall|must|will)\b)"
        r"(.{5,300})",
        re.DOTALL,
    ), "4group"),

    # WHERE-clause: "where X, Y shall [not] Z" — the action must reach a modal
    # verb and runs on through it to the end of the sentence, so the
    # consequence (and any negation: "shall not be allowed") stays in the span.
    ("IF_THEN", re.compile(
        r"(?i)\b(where)\b"
        r"(.{10,200}?)"
        r",\s*"
        r"(.{0,300}?\b(?:shall|must|will)\b.{3,300})",
        re.DOTALL,
    ), "3group_where"),

    # PROVIDED THAT / SUBJECT TO
    ("CONDITION_ACTION", re.compile(
        r"(?i)\b(provided\s+that|subject\s+to)"
        r"(.{10,300}?)"
        r",\s*"
        r"(.{5,300})",
        re.DOTALL,
    ), "3group"),

    # NOTWITHSTANDING
    ("CONDITION_ACTION", re.compile(
        r"(?i)\b(notwithstanding\s+(?:anything\s+)?(?:contained\s+in|to\s+the\s+contrary))"
        r"(.{0,150}?)"
        r",\s*"
        r"(.{5,300})",
        re.DOTALL,
    ), "3group"),

    # PENALTY TRIGGER: "whoever does X shall be liable/punishable"
    ("PENALTY_TRIGGER", re.compile(
        r"(?i)\b(whoever|any\s+person\s+who|any\s+(?:company|firm|individual)\s+that)"
        r"(.{5,200}?)"
        r"(shall\s+be\s+(?:liable|punishable|guilty)|is\s+guilty)"
        r"(.{5,200})",
        re.DOTALL,
    ), "penalty"),

    # FAILING WHICH
    ("IF_THEN", re.compile(
        r"(?i)(.{15,250}?)"
        r"\b(failing\s+which|in\s+default\s+thereof|failing\s+to\s+do\s+so)\b"
        r"(.{5,200})",
        re.DOTALL,
    ), "3group_failing"),
]

# ─── Keywords that escalate risk tier ─────────────────────────────────────────
_CRITICAL_KEYWORDS = re.compile(
    r"(?i)\b("
    r"imprisonment|punishable|rigorous|criminal|prosecution|"
    r"jail|arrest|seized|confiscated"
    r")\b"
)
# Money/rate markers sit outside the \b group: "Rs." ends in a non-word char
# and "₹"/"%" are non-word chars, so a trailing/leading \b would never match
# them next to whitespace.
_HIGH_KEYWORDS = re.compile(
    r"(?i)(\b(?:penalty|fine|liable|forfeiture|surcharge|interest|lakhs?|crores?|percent)\b"
    r"|\bRs\.?(?=\s*\d)|₹|\d\s*%|\bper\s+cent\b)"
)
_OBLIGATION_KEYWORDS = re.compile(
    r"(?i)\b(shall|must|required|obliged|mandatory)\b"
)


# Base confidence per group mode, ordered by pattern specificity: the
# PENALTY_TRIGGER regex anchors on explicit legal formulas (most reliable),
# while the WHERE-clause regex is the loosest and yields the most false
# positives. Spans that hit the 400-char truncation cap lose precision.
_GROUP_MODE_CONFIDENCE: dict[str, float] = {
    "penalty": 0.90,
    "4group": 0.85,
    "3group_failing": 0.80,
    "3group": 0.75,
    "3group_where": 0.65,
}


def _pattern_confidence(group_mode: str, condition: str, action: str) -> float:
    confidence = _GROUP_MODE_CONFIDENCE.get(group_mode, 0.60)
    if len(condition) >= 400 or len(action) >= 400:
        confidence -= 0.10
    return round(max(0.3, min(0.95, confidence)), 3)


def _score_pattern(
    pattern_type: str,
    condition: str,
    action: str,
) -> tuple[str, float]:
    """
    Compute (risk_tier, impact_score) for a causal pattern.
    """
    combined = condition + " " + action

    # PENALTY_TRIGGER base risk is always at least HIGH
    if pattern_type == "PENALTY_TRIGGER":
        if _CRITICAL_KEYWORDS.search(combined):
            return "CRITICAL", 0.95
        if _HIGH_KEYWORDS.search(combined):
            return "HIGH", 0.80
        return "HIGH", 0.70

    # IF_THEN with penalty/obligation consequences
    if pattern_type == "IF_THEN":
        if _CRITICAL_KEYWORDS.search(combined):
            return "CRITICAL", 0.90
        if _HIGH_KEYWORDS.search(combined):
            return "HIGH", 0.75
        if _OBLIGATION_KEYWORDS.search(action):
            return "MEDIUM", 0.55
        return "LOW", 0.35

    # CONDITION_ACTION (overriding / qualifying clauses)
    if pattern_type == "CONDITION_ACTION":
        if _CRITICAL_KEYWORDS.search(combined):
            return "HIGH", 0.70
        if _HIGH_KEYWORDS.search(combined):
            return "MEDIUM", 0.55
        return "LOW", 0.30

    return "LOW", 0.25


_PATTERN_PHRASING = {
    "IF_THEN": "a conditional (if/when/where ... then) structure linking a trigger to a consequence",
    "CONDITION_ACTION": "a qualifying clause (provided that / subject to / notwithstanding) that conditions an action",
    "PENALTY_TRIGGER": "an explicit penalty formula (whoever ... shall be liable/punishable)",
}


def _build_explanation(pattern_type: str, condition: str, action: str, risk_tier: str) -> str:
    """A deterministic, human-readable rationale for why this pattern was flagged
    and why it carries its risk tier — built from the structural match and the
    risk keywords that actually fired (no LLM, always available)."""
    combined = condition + " " + action
    crit = sorted({m.lower() for m in _CRITICAL_KEYWORDS.findall(combined)})
    high = sorted({m.lower() for m in _HIGH_KEYWORDS.findall(combined)})

    parts = [f"Flagged as {pattern_type.replace('_', ' ').lower()} because the clause contains "
             f"{_PATTERN_PHRASING.get(pattern_type, 'a causal structure')}."]
    if risk_tier == "CRITICAL" and crit:
        parts.append(f"Rated CRITICAL: it carries criminal/enforcement language ({', '.join(crit)}).")
    elif risk_tier == "HIGH" and (high or crit):
        parts.append(f"Rated HIGH: it references financial or liability consequences ({', '.join(high or crit)}).")
    elif risk_tier == "MEDIUM":
        parts.append("Rated MEDIUM: it imposes an obligation (shall/must/required) but no explicit penalty.")
    else:
        parts.append("Rated LOW: a conditional structure with no penalty or financial-consequence signal.")
    return " ".join(parts)


def _sentence_spans(clause_text: str) -> list[tuple[int, str]]:
    """Split clause text into (start_offset, sentence_text) spans using the
    same sentence-boundary heuristic clause_segmenter.py already trusts for
    prose (lookbehind-period + lookahead-uppercase, so it doesn't false-split
    on legal abbreviations like "Rs." / "S." / "No.")."""
    bounds = [m.end() for m in _SENTENCE_BOUNDARY_RE.finditer(clause_text)]
    starts = [0] + bounds
    ends = bounds + [len(clause_text)]
    return [(s, clause_text[s:e]) for s, e in zip(starts, ends) if clause_text[s:e].strip()]


def _remove_overlapping_candidates(candidates: list[dict]) -> list[dict]:
    """Collapse overlapping matches (from different patterns, or the same
    pattern matching the same text twice) to the single highest-confidence
    one. Confidence is the primary key — not span length — since
    _GROUP_MODE_CONFIDENCE already encodes which pattern type is more
    reliable (e.g. PENALTY_TRIGGER should win over the looser WHERE-clause
    pattern regardless of which span happens to be longer)."""
    order = sorted(
        candidates,
        key=lambda c: (-c["confidence"], -(c["end"] - c["start"]), c["start"]),
    )
    kept: list[dict] = []
    for c in order:
        if all(c["end"] <= k["start"] or c["start"] >= k["end"] for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["start"])


def detect_causal_patterns(clause_text: str, clause_id: str) -> list[CausalPattern]:
    """
    Detect causal patterns in a clause.
    Returns list of CausalPattern objects with risk_tier and impact_score.

    Each pattern is matched within a single sentence at a time (clauses are
    often multi-sentence paragraphs, and letting a condition span bleed
    across a full stop into an unrelated sentence produces nonsensical
    condition/action pairs). Overlapping matches across patterns/sentences
    are then collapsed to the single highest-confidence one.
    """
    candidates: list[dict] = []

    for sent_start, sentence in _sentence_spans(clause_text):
        for pattern_type, regex, group_mode in _PATTERNS:
            for m in regex.finditer(sentence):
                # Each mode names which capture groups make up the condition
                # and the action. Spans are sliced straight out of the source
                # sentence (never re-joined from groups), so they stay exact
                # substrings of the clause and their offsets can be stored.
                cond_groups, act_groups = _GROUP_LAYOUT[group_mode]
                cs, ce = _trim(sentence, m.start(cond_groups[0]), m.end(cond_groups[-1]))
                as_, ae = _trim(sentence, m.start(act_groups[0]), m.end(act_groups[-1]))
                condition = sentence[cs:ce]
                action = sentence[as_:ae]

                if len(condition) < 10 or len(action) < 5:
                    continue

                risk_tier, impact_score = _score_pattern(pattern_type, condition, action)
                confidence = _pattern_confidence(group_mode, condition, action)

                candidates.append({
                    "start": sent_start + m.start(),
                    "end": sent_start + m.end(),
                    "confidence": confidence,
                    "pattern_type": pattern_type,
                    "condition": condition,
                    "action": action,
                    "cond_off": (sent_start + cs, sent_start + ce),
                    "act_off": (sent_start + as_, sent_start + ae),
                    "risk_tier": risk_tier,
                    "impact_score": impact_score,
                })

    survivors = _remove_overlapping_candidates(candidates)

    return [
        CausalPattern(
            pattern_type=c["pattern_type"],  # type: ignore
            condition_span=c["condition"][:400],
            action_span=c["action"][:400],
            condition_start=c["cond_off"][0],
            condition_end=min(c["cond_off"][1], c["cond_off"][0] + 400),
            action_start=c["act_off"][0],
            action_end=min(c["act_off"][1], c["act_off"][0] + 400),
            confidence=c["confidence"],
            source_clause_id=clause_id,
            risk_tier=c["risk_tier"],  # type: ignore
            impact_score=round(c["impact_score"], 3),
            explanation=_build_explanation(
                c["pattern_type"], c["condition"], c["action"], c["risk_tier"]
            ),
        )
        for c in survivors
    ]


# Capture groups (1-based, contiguous range) forming the condition / action
# span for each group mode.
_GROUP_LAYOUT: dict[str, tuple[tuple[int, ...], tuple[int, ...]]] = {
    "4group": ((1, 2), (3, 4)),
    "3group": ((1, 2), (3,)),
    "3group_where": ((1, 2), (3,)),
    "3group_failing": ((1,), (2, 3)),
    "penalty": ((1, 2), (3, 4)),
}

_TRIM_CHARS = " \t\r\n,;"


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink [start, end) past leading/trailing whitespace and connectors
    (commas, semicolons) without changing what the offsets point at."""
    while start < end and text[start] in _TRIM_CHARS:
        start += 1
    while end > start and text[end - 1] in _TRIM_CHARS:
        end -= 1
    return start, end
