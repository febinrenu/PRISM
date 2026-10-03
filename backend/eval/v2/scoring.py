"""
Scoring rules against rules — one module for inter-annotator agreement and
for system evaluation.

Both sides are normalised to NormRule (spans as offsets into the statute's
canonical text). Rules are matched one-to-one by the overlap of their
action / consequence / subject spans (greedy on the best pair, minimum
overlap MATCH_MIN). On top of the matching:

    detection      provision has a rule? (P/R/F1, Cohen's kappa)
    rules          matched / unmatched rules → rule-level P/R/F1
    modality       accuracy and Cohen's kappa over matched rules
    spans          per field, strict (exact offsets) and relaxed (IoU ≥ 0.5) F1
    effects        effect-kind F1 per matched rule pair; numeric exact match
                   of each field on effects of the same kind
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

MATCH_MIN = 0.2
RELAXED_IOU = 0.5
SPAN_FIELDS = ("subject", "action", "consequence", "conditions", "exceptions", "cross_refs")
NUMERIC_TOL = 1e-6


@dataclass
class NormRule:
    modality: str
    spans: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    effects: list[tuple[str, dict]] = field(default_factory=list)


@dataclass
class NormItem:
    item_id: str
    no_rule: bool
    rules: list[NormRule]


def from_annotation(ann: dict, item: dict) -> NormItem:
    base = item["start"]

    def sp(s):
        return (base + s["start"], base + s["end"])

    rules = []
    for r in ann.get("rules", []):
        spans = {
            "subject": [sp(r["subject"])] if r.get("subject") else [],
            "action": [sp(r["action"])] if r.get("action") else [],
            "consequence": [sp(r["consequence"])] if r.get("consequence") else [],
            "conditions": [sp(c) for c in r.get("conditions", [])],
            "exceptions": [sp(c) for c in r.get("exceptions", [])],
            "cross_refs": [sp(c) for c in r.get("cross_refs", [])],
        }
        effects = [(e["kind"], dict(e.get("fields", {}))) for e in r.get("effects", [])]
        rules.append(NormRule(r["modality"], spans, effects))
    return NormItem(item["item_id"], bool(ann.get("no_rule")) or not rules, rules)


def from_record(rec, item_id: str) -> NormItem:
    """A system ExtractionRecord (models.rules) → NormItem."""
    rules = []
    for r in rec.rules:
        def one(s):
            return [(s.start, s.end)] if s is not None else []
        spans = {
            "subject": one(r.subject.span),
            "action": one(r.action),
            "consequence": one(r.consequence),
            "conditions": [(c.span.start, c.span.end) for c in r.conditions if c.span],
            "exceptions": [(e.span.start, e.span.end) for e in r.exceptions if e.span],
            "cross_refs": [(c.span.start, c.span.end) for c in r.cross_refs if c.span],
        }
        effects = []
        for e in r.effects:
            d = e.model_dump(exclude={"source_span", "operation", "taxpayer"})
            effects.append((d.pop("kind"), d))
        rules.append(NormRule(r.modality, spans, effects))
    return NormItem(item_id, not rules, rules)


def _iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0


def _anchor(r: NormRule) -> list[tuple[int, int]]:
    return r.spans.get("action", []) + r.spans.get("consequence", []) + r.spans.get("subject", [])


def match_rules(a: list[NormRule], b: list[NormRule]) -> list[tuple[int, int]]:
    """One-to-one pairs (i, j), greedy on the best anchor-span overlap.
    Rules without spans (e.g. rate tables) pair by effect kinds instead."""
    scores = []
    for i, ra in enumerate(a):
        for j, rb in enumerate(b):
            sa, sb = _anchor(ra), _anchor(rb)
            if sa and sb:
                s = max(_iou(x, y) for x in sa for y in sb)
            else:
                ka, kb = Counter(k for k, _ in ra.effects), Counter(k for k, _ in rb.effects)
                s = (sum((ka & kb).values()) / max(sum((ka | kb).values()), 1)) if (ka or kb) else 0.0
            if s >= MATCH_MIN:
                scores.append((s, i, j))
    pairs, used_a, used_b = [], set(), set()
    for s, i, j in sorted(scores, reverse=True):
        if i not in used_a and j not in used_b:
            pairs.append((i, j))
            used_a.add(i)
            used_b.add(j)
    return pairs


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def cohen_kappa(pairs: Iterable[tuple[str, str]]) -> Optional[float]:
    pairs = list(pairs)
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else 1.0


def _span_counts(gold: list[tuple[int, int]], pred: list[tuple[int, int]], relaxed: bool) -> tuple[int, int, int]:
    used = set()
    tp = 0
    for g in gold:
        for k, p in enumerate(pred):
            if k in used:
                continue
            if (relaxed and _iou(g, p) >= RELAXED_IOU) or (not relaxed and g == p):
                used.add(k)
                tp += 1
                break
    return tp, len(pred) - tp, len(gold) - tp


def _num_equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= NUMERIC_TOL * max(1.0, abs(float(a)))
    return a == b


def compare(gold_items: list[NormItem], pred_items: list[NormItem]) -> dict:
    """Score `pred` against `gold` (or annotator B against A for agreement)."""
    pred_by_id = {p.item_id: p for p in pred_items}
    det = Counter()
    det_pairs = []
    rule_tp = rule_fp = rule_fn = 0
    mod_pairs = []
    span = {f: {"strict": [0, 0, 0], "relaxed": [0, 0, 0]} for f in SPAN_FIELDS}
    eff = [0, 0, 0]
    num_checked = num_equal = 0
    per_kind = defaultdict(lambda: [0, 0, 0])
    for g in gold_items:
        p = pred_by_id.get(g.item_id, NormItem(g.item_id, True, []))
        gh, ph = not g.no_rule, not p.no_rule
        det_pairs.append((str(gh), str(ph)))
        det["tp" if gh and ph else "fp" if ph else "fn" if gh else "tn"] += 1
        pairs = match_rules(g.rules, p.rules)
        rule_tp += len(pairs)
        rule_fp += len(p.rules) - len(pairs)
        rule_fn += len(g.rules) - len(pairs)
        for i, j in pairs:
            gr, pr = g.rules[i], p.rules[j]
            mod_pairs.append((gr.modality, pr.modality))
            for f in SPAN_FIELDS:
                for mode in ("strict", "relaxed"):
                    tp, fp, fn = _span_counts(gr.spans.get(f, []), pr.spans.get(f, []), mode == "relaxed")
                    c = span[f][mode]
                    c[0] += tp
                    c[1] += fp
                    c[2] += fn
            gk, pk = Counter(k for k, _ in gr.effects), Counter(k for k, _ in pr.effects)
            inter = sum((gk & pk).values())
            eff[0] += inter
            eff[1] += sum(pk.values()) - inter
            eff[2] += sum(gk.values()) - inter
            for k in set(gk) | set(pk):
                pk_tp = min(gk[k], pk[k])
                per_kind[k][0] += pk_tp
                per_kind[k][1] += pk[k] - pk_tp
                per_kind[k][2] += gk[k] - pk_tp
            # Numeric fields: pair effects of the same kind in order of their
            # first numeric field.
            for k in set(gk) & set(pk):
                ge = sorted([d for kk, d in gr.effects if kk == k], key=_sort_key)
                pe = sorted([d for kk, d in pr.effects if kk == k], key=_sort_key)
                for gd, pd in zip(ge, pe):
                    for fname, gv in gd.items():
                        if gv in (None, "") or fname in ("regime", "age_band", "applies_to_ay", "trigger", "description"):
                            continue
                        num_checked += 1
                        num_equal += int(_num_equal(gv, pd.get(fname)))
    return {
        "items": len(gold_items),
        "detection": {**prf(det["tp"], det["fp"], det["fn"]), "kappa": cohen_kappa(det_pairs)},
        "rules": prf(rule_tp, rule_fp, rule_fn),
        "modality": {"accuracy": round(sum(a == b for a, b in mod_pairs) / len(mod_pairs), 4) if mod_pairs else None,
                     "kappa": cohen_kappa(mod_pairs), "pairs": len(mod_pairs)},
        "spans": {f: {m: prf(*c) for m, c in modes.items()} for f, modes in span.items()},
        "effects": {"kinds": prf(*eff), "per_kind": {k: prf(*v) for k, v in sorted(per_kind.items())},
                    "numeric_exact": round(num_equal / num_checked, 4) if num_checked else None,
                    "numeric_fields": num_checked},
    }


def _sort_key(d: dict):
    for k in ("lower", "threshold", "max_income", "amount", "per_day", "rate", "max_rate"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0
