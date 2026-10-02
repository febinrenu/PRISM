"""
Legal Named Entity Recognition with per-pattern confidence scoring.

spaCy's Matcher does not report which pattern within a rule matched, so
confidence is encoded in the rule key itself ("RIGHT::MEDIUM") — each
(label, confidence) pair is registered as its own rule.

Entity types:
  OBLIGATION  - What must be done (shall file, required to pay)
  RIGHT       - What is permitted (entitled to, may claim)
  PENALTY     - Punishments (penalty, imprisonment, fine)
  THRESHOLD   - Numeric amounts/periods (Rs. 5,00,000, 30 days, 20%)
  ACTOR       - Who performs actions (Assessing Officer, taxpayer)
  BENEFICIARY - Who benefits (senior citizen, widow)
"""
import re
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from models.schemas import Entity


# ─── THRESHOLD regex patterns ─────────────────────────────────────────────────

_THRESHOLD_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Rs. with amount + optional unit → HIGH (very specific)
    (re.compile(
        r"(?i)\bRs\.\s*[\d,]+(?:\.\d+)?\s*"
        r"(?:lakh|lakhs|crore|crores|thousand|million|billion)?"
    ), "HIGH"),
    # INR/₹ + amount → HIGH
    (re.compile(
        r"(?i)\b(?:INR|₹)\s*[\d,]+(?:\.\d+)?\s*"
        r"(?:lakh|lakhs|crore|crores|thousand|million)?"
    ), "HIGH"),
    # digits + lakh/crore standalone → HIGH
    (re.compile(r"(?i)\b[\d,]+(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores)\b"), "HIGH"),
    # percentage → HIGH
    (re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:percent|per\s*cent|%)\b"), "HIGH"),
    # "exceeds/not exceeding/up to X" with amount → MEDIUM
    (re.compile(
        r"(?i)\b(?:exceeds?|not\s+exceeding|above|below|more\s+than|"
        r"less\s+than|up\s+to|at\s+least)\s+(?:Rs\.\s*)?[\d,]+(?:\.\d+)?"
        r"(?:\s*(?:lakh|lakhs|crore|crores))?"
    ), "MEDIUM"),
    # time thresholds → MEDIUM
    (re.compile(
        r"(?i)\b(?:within|before|after|not\s+later\s+than|"
        r"not\s+less\s+than|at\s+least)\s+\d+\s+(?:days?|months?|years?)\b"
    ), "MEDIUM"),
    # plain currency: "5,00,000 rupees" → HIGH
    (re.compile(r"(?i)\b\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\s*(?:rupees?)\b"), "HIGH"),
    # assessment year references → MEDIUM
    (re.compile(r"(?i)\bassessment\s+year\s+\d{4}[-–]\d{2,4}\b"), "MEDIUM"),
]

# ─── Matcher pattern groups: (label, confidence, patterns) ────────────────────
# Confidence is encoded in the rule key ("LABEL::CONF") because spaCy's basic
# Matcher API doesn't expose which pattern within a rule produced a match.

_MATCHER_GROUPS: list[tuple[str, str, list[list[dict]]]] = [
    ("OBLIGATION", "HIGH", [
        [{"LOWER": "shall"}, {"LOWER": "be", "OP": "?"}, {"POS": {"IN": ["VERB", "ADJ"]}}],
        [{"LOWER": "must"}, {"LOWER": "be", "OP": "?"}, {"POS": {"IN": ["VERB", "ADJ"]}}],
        [{"LOWER": "required"}, {"LOWER": "to"}, {"POS": "VERB"}],
        [{"LOWER": {"IN": ["obliged", "obligated", "directed", "mandated"]}},
         {"LOWER": "to"}, {"POS": "VERB"}],
        [{"LOWER": "is"}, {"LOWER": "required"}, {"LOWER": "to"}, {"POS": "VERB"}],
    ]),
    ("RIGHT", "HIGH", [
        [{"LOWER": "entitled"}, {"LOWER": "to"}],
        [{"LOWER": {"IN": ["has", "have"]}}, {"LOWER": "the"}, {"LOWER": "right"}, {"LOWER": "to"}],
        [{"LOWER": {"IN": ["permitted", "allowed", "authorised", "authorized"]}},
         {"LOWER": "to"}, {"POS": "VERB"}],
        [{"LOWER": "eligible"}, {"LOWER": {"IN": ["to", "for"]}}],
        [{"LOWER": "shall"}, {"LOWER": "be"},
         {"LOWER": {"IN": ["exempt", "exempted", "excluded", "entitled"]}}],
    ]),
    # "may VERB" is a broad modal — many false positives → MEDIUM
    ("RIGHT", "MEDIUM", [
        [{"LOWER": "may"}, {"POS": "VERB"}],
    ]),
    ("PENALTY", "HIGH", [
        [{"LOWER": "penalty"}],
        [{"LOWER": "imprisonment"}],
        [{"LOWER": "forfeiture"}],
        [{"LOWER": "surcharge"}],
        [{"LOWER": {"IN": ["offence", "offense"]}}],
        [{"LOWER": "prosecution"}],
        [{"LOWER": "a"}, {"LOWER": "fine"}],
        [{"LOWER": "fine"}, {"LOWER": "of"}],
        [{"LOWER": "shall"}, {"LOWER": "be"},
         {"LOWER": {"IN": ["liable", "punishable", "guilty"]}}],
        [{"LOWER": "is"}, {"LOWER": "guilty"}],
        [{"LOWER": "liable"}, {"LOWER": "to"}, {"LOWER": "pay"}],
        [{"LOWER": "punishable"}, {"LOWER": {"IN": ["with", "by"]}}],
    ]),
]

# ─── Specific ACTOR phrases ────────────────────────────────────────────────────
_ACTOR_PHRASES = [
    "Assessing Officer", "assessing officer",
    "Principal Commissioner", "Chief Commissioner",
    "Commissioner of Income-tax", "Income Tax Officer",
    "Tax Recovery Officer", "Deputy Commissioner",
    "Joint Commissioner", "Additional Commissioner",
    "Director General", "Director of Income-tax",
    "Appellate Authority", "Appellate Tribunal",
    "Income Tax Appellate Tribunal",
    "Central Board of Direct Taxes",
    "Central Government", "State Government",
    "Board",
    "taxpayer", "assessee", "declarant",
    "employer", "employee",
    "resident", "non-resident",
    "any person",
    "every person",
    "company", "firm", "partnership firm",
    "trust", "trustee",
    "cooperative society",
    "limited liability partnership",
    "Hindu undivided family",
]

# ─── Specific BENEFICIARY phrases ─────────────────────────────────────────────
_BENEFICIARY_PHRASES = [
    "senior citizen", "disabled person", "widow", "orphan",
    "minor", "minor child", "dependent", "nominee",
    "physically handicapped", "person with disability",
    "differently abled",
    "low income", "below poverty",
]

# Authority-level actors get HIGH confidence (official bodies)
_HIGH_CONFIDENCE_ACTORS = {
    "assessing officer", "principal commissioner", "chief commissioner",
    "commissioner of income-tax", "income tax officer", "tax recovery officer",
    "deputy commissioner", "joint commissioner", "additional commissioner",
    "director general", "director of income-tax", "appellate authority",
    "appellate tribunal", "income tax appellate tribunal",
    "central board of direct taxes", "central government", "state government",
    "board",
}

# ─── Lazy-loaded NLP objects ──────────────────────────────────────────────────

_nlp = None
_matcher = None
_phrase_matcher = None


def _init_nlp():
    global _nlp, _matcher, _phrase_matcher
    if _nlp is not None:
        return

    _nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    _matcher = Matcher(_nlp.vocab)
    _phrase_matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")

    for label, conf, patterns in _MATCHER_GROUPS:
        _matcher.add(f"{label}::{conf}", patterns)

    _phrase_matcher.add("ACTOR", list(_nlp.pipe(_ACTOR_PHRASES)))
    _phrase_matcher.add("BENEFICIARY", list(_nlp.pipe(_BENEFICIARY_PHRASES)))


def _get_nlp():
    _init_nlp()
    return _nlp, _matcher, _phrase_matcher


# ─── Main extraction function ─────────────────────────────────────────────────

def extract_entities(clause_text: str) -> list[Entity]:
    """
    Extract legal entities from clause text with confidence scoring.
    Returns deduplicated, overlap-free, position-sorted Entity list.
    """
    return extract_entities_batch([clause_text])[0]


def extract_entities_batch(clause_texts: list[str]) -> list[list[Entity]]:
    """
    Same extraction as extract_entities, but over many clauses at once via
    nlp.pipe() — spaCy amortizes tokenizer/pipeline overhead across texts
    instead of paying it per call, which matters when there are hundreds to
    thousands of clauses. Per-clause results are identical either way: the
    matchers here only look at the current Doc, no cross-document state.
    """
    if not clause_texts:
        return []
    nlp, matcher, phrase_matcher = _get_nlp()
    return [
        _entities_from_doc(doc, clause_text, nlp, matcher, phrase_matcher)
        for doc, clause_text in zip(nlp.pipe(clause_texts, batch_size=64), clause_texts)
    ]


def _entities_from_doc(doc, clause_text: str, nlp, matcher, phrase_matcher) -> list[Entity]:
    raw_entities: list[Entity] = []
    seen_spans: set[tuple[int, int]] = set()

    # ── Matcher (OBLIGATION, RIGHT, PENALTY) ─────────────────────────────────
    matches = matcher(doc)
    for match_id, start_tok, end_tok, *rest in matches:
        span = doc[start_tok:end_tok]
        char_start = span.start_char
        char_end = span.end_char
        entity_text = span.text.strip()

        if len(entity_text) < 4:
            continue
        if (char_start, char_end) in seen_spans:
            continue
        seen_spans.add((char_start, char_end))

        label, conf = nlp.vocab.strings[match_id].split("::")

        raw_entities.append(Entity(
            label=label,  # type: ignore[arg-type]
            text=entity_text,
            start=char_start,
            end=char_end,
            confidence=conf,  # type: ignore[arg-type]
        ))

    # ── PhraseMatcher (ACTOR, BENEFICIARY) ───────────────────────────────────
    phrase_matches = phrase_matcher(doc)
    for match_id, start_tok, end_tok in phrase_matches:
        span = doc[start_tok:end_tok]
        char_start = span.start_char
        char_end = span.end_char
        entity_text = span.text.strip()

        if len(entity_text) < 3:
            continue
        if (char_start, char_end) in seen_spans:
            continue
        seen_spans.add((char_start, char_end))

        rule_name = nlp.vocab.strings[match_id]

        # Actors that are official authorities → HIGH; generic roles → MEDIUM
        if rule_name == "ACTOR":
            conf = "HIGH" if entity_text.lower() in _HIGH_CONFIDENCE_ACTORS else "MEDIUM"
        else:  # BENEFICIARY
            conf = "HIGH"

        raw_entities.append(Entity(
            label=rule_name,  # type: ignore[arg-type]
            text=entity_text,
            start=char_start,
            end=char_end,
            confidence=conf,  # type: ignore[arg-type]
        ))

    # ── Threshold regex ───────────────────────────────────────────────────────
    for pattern, conf in _THRESHOLD_PATTERNS:
        for m in pattern.finditer(clause_text):
            entity_text = m.group().strip()
            if not any(c.isdigit() for c in entity_text):
                continue
            if len(entity_text) < 2:
                continue
            key = (m.start(), m.end())
            if key in seen_spans:
                continue
            seen_spans.add(key)
            raw_entities.append(Entity(
                label="THRESHOLD",
                text=entity_text,
                start=m.start(),
                end=m.end(),
                confidence=conf,  # type: ignore[arg-type]
            ))

    return _remove_overlaps(raw_entities)


def _remove_overlaps(entities: list[Entity]) -> list[Entity]:
    """
    Remove overlapping spans globally, preferring longer spans.
    Longest-first greedy selection: a span is kept only if it does not
    overlap any already-kept span (handles chains of 3+ overlaps that a
    previous-entity-only comparison would leak).
    """
    if not entities:
        return entities

    order = sorted(entities, key=lambda e: (-(e.end - e.start), e.start))
    kept: list[Entity] = []
    for entity in order:
        if all(entity.end <= k.start or entity.start >= k.end for k in kept):
            kept.append(entity)

    return sorted(kept, key=lambda e: e.start)
