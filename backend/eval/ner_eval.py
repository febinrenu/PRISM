"""
NER benchmark — entity-level F1 of the Phase-1 rule/spaCy NER via seqeval.

Gold format: [{text, entities: [{label, start, end}]}]. When a gold set with
explicit spans isn't available (e.g. CUAD only gives a coarse category → entity
label per clause), use `presence_eval` instead, which scores whether the
pipeline finds *at least one* entity of the expected label in the clause — a
weaker but honest signal for an out-of-domain set.
"""
from pipeline.legal_ner import extract_entities
from eval.metrics import binary_prf1, ner_f1, to_bio


def evaluate_ner_spans(gold: list[dict]) -> dict | None:
    """Full entity-level F1 (seqeval) against span-annotated gold. Returns None
    if seqeval isn't installed."""
    gold_bio, pred_bio = [], []
    for item in gold:
        text = item["text"]
        gold_ents = item.get("entities", [])
        pred_ents = [
            {"label": e.label, "start": e.start, "end": e.end}
            for e in extract_entities(text)
        ]
        gold_bio.append(to_bio(text, gold_ents))
        pred_bio.append(to_bio(text, pred_ents))
    return ner_f1(gold_bio, pred_bio)


def evaluate_ner_presence(gold: list[dict]) -> dict:
    """Weaker check for coarsely-labeled sets (e.g. CUAD): per expected entity
    label, did the pipeline surface that label anywhere in the clause? Reports
    per-label and macro binary P/R/F1. Items with entity_label=None are treated
    as 'expect no strong entity' negatives for all labels."""
    labels = ["OBLIGATION", "PENALTY", "THRESHOLD", "RIGHT", "ACTOR", "BENEFICIARY"]
    per_label: dict[str, dict] = {}
    for label in labels:
        g, p = [], []
        for item in gold:
            expected = item.get("entity_label") == label
            found = any(e.label == label for e in extract_entities(item["text"]))
            g.append(expected)
            p.append(found)
        # Only score labels that actually appear in the gold set.
        if any(g):
            per_label[label] = binary_prf1(g, p)
    macro_f1 = round(sum(v["f1"] for v in per_label.values()) / len(per_label), 4) if per_label else 0.0
    return {"macro_f1": macro_f1, "per_label": per_label}
