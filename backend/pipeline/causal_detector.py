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

    # WHERE-clause: "where X, Y shall" — the action must actually reach a
    # modal verb; without the "|$" fallback the old regex used, this no
    # longer matches trailing boilerplate that never states a consequence.
    ("IF_THEN", re.compile(
        r"(?i)\b(where)\b"
        r"(.{10,200}?)"
        r",\s*"
        r"(.{5,300}?)"
        r"(?=\bshall\b|\bmust\b|\bwill\b)",
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
_HIGH_KEYWORDS = re.compile(
    r"(?i)\b("
    r"penalty|fine|liable|forfeiture|surcharge|interest|"
    r"Rs\.|lakh|crore|percent|%"
    r")\b"
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
                groups = m.groups()
                condition = ""
                action = ""

                if group_mode == "4group":
                    condition = (groups[0] + " " + groups[1]).strip()
                    action = (groups[2] + " " + groups[3]).strip()

                elif group_mode == "3group":
                    condition = (groups[0] + " " + groups[1]).strip()
                    action = groups[2].strip()

                elif group_mode == "3group_where":
                    condition = (groups[0] + " " + groups[1]).strip()
                    action = groups[2].strip()

                elif group_mode == "3group_failing":
                    condition = groups[0].strip()
                    action = (groups[1] + " " + groups[2]).strip()

                elif group_mode == "penalty":
                    condition = (groups[0] + " " + groups[1]).strip()
                    action = (groups[2] + " " + (groups[3] if len(groups) > 3 else "")).strip()

                condition = _clean_span(condition)
                action = _clean_span(action)

                if not condition or not action:
                    continue
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
                    "risk_tier": risk_tier,
                    "impact_score": impact_score,
                })

    survivors = _remove_overlapping_candidates(candidates)

    return [
        CausalPattern(
            pattern_type=c["pattern_type"],  # type: ignore
            condition_span=c["condition"][:400],
            action_span=c["action"][:400],
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


def _clean_span(text: str) -> str:
    """Remove leading/trailing whitespace, commas, and connectors."""
    text = text.strip()
    text = re.sub(r"^[,;\s]+", "", text)
    text = re.sub(r"[,;\s]+$", "", text)
    return text.strip()
