"""
Are the quoted spans the evidence the extraction actually rests on?

Every extracted field is grounded to a span of the provision; together the
spans are the system's rationale. Following ERASER (DeYoung et al., 2020),
the provision is re-extracted twice more:

    without the rationale   → comprehensiveness = 1 − F1(original, re-extraction)
    with only the rationale → sufficiency       = F1(original, re-extraction)

and once with random spans of the same lengths deleted, the baseline that
comprehensiveness must beat. Outputs are compared on what they mean, not on
offsets: the multiset of rule modalities and of effects with their numbers.

    data/eval/v2/faithfulness/{system}_{split}.json
"""
import json
import random
import re
from collections import Counter
from dataclasses import replace
from typing import Callable, Optional

import numpy as np

from eval.v2 import runs, sampling

OUT_DIR = sampling.EVAL_DIR / "faithfulness"
SEED = 20261003
_NUMERIC = ("lower", "upper", "rate", "max_income", "max_rebate", "amount", "threshold", "max_rate",
            "per_day", "rate_per_month", "max_amount", "days")


def signature(record) -> Counter:
    sig = Counter()
    for r in record.rules:
        sig[("rule", r.modality)] += 1
        for e in r.effects:
            d = e.model_dump()
            sig[("effect", d["kind"], tuple(round(float(d[k]), 6) if isinstance(d.get(k), (int, float)) else None
                                             for k in _NUMERIC))] += 1
    return sig


def f1(ref: Counter, pred: Counter) -> float:
    if not ref and not pred:
        return 1.0
    tp = sum((ref & pred).values())
    p = tp / sum(pred.values()) if pred else 0.0
    r = tp / sum(ref.values()) if ref else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def rationale(record, unit_start: int, unit_len: int) -> list[tuple[int, int]]:
    """Union of every grounded span, as merged offsets relative to the unit."""
    spans = []
    for r in record.rules:
        for s in [r.subject.span, r.action, r.consequence, *[c.span for c in r.conditions],
                  *[x.span for x in r.exceptions], *[x.span for x in r.cross_refs],
                  *[e.source_span for e in r.effects]]:
            if s is not None:
                spans.append((max(0, s.start - unit_start), min(unit_len, s.end - unit_start)))
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if a >= b:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def _clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


def delete(text: str, spans: list[tuple[int, int]]) -> str:
    out, last = [], 0
    for a, b in spans:
        out.append(text[last:a])
        last = b
    out.append(text[last:])
    return _clean(" ".join(out))


def keep(text: str, spans: list[tuple[int, int]]) -> str:
    return _clean(" … ".join(text[a:b] for a, b in spans))


def random_spans(spans: list[tuple[int, int]], n: int, rng: random.Random) -> list[tuple[int, int]]:
    """Non-overlapping spans with the same lengths as `spans`, placed at random."""
    lengths = [b - a for a, b in spans]
    free = n - sum(lengths)
    if free < 0:
        return list(spans)
    # Distribute the free characters into len+1 gaps.
    cuts = sorted(rng.randint(0, free) for _ in lengths)
    order = lengths[:]
    rng.shuffle(order)
    out, pos, prev = [], 0, 0
    for cut, ln in zip(cuts, order):
        pos += cut - prev
        prev = cut
        out.append((pos, pos + ln))
        pos += ln
    return out


def evaluate(system: str, split: str, limit: Optional[int] = None,
             extract: Optional[Callable] = None, progress=print) -> dict:
    """`extract(unit) -> ExtractionRecord`; defaults to the system's extractor."""
    if extract is None:
        from pipeline.extraction.extractor import extract_unit
        extract = lambda u: extract_unit(u, system)[0]  # noqa: E731
    originals = runs.load_run(system, split)
    items = [it for it in runs.split_items(split) if it["item_id"] in originals]
    rows = []
    for it in items:
        rec = originals[it["item_id"]]
        if rec.status != "ok" or not rec.rules:
            continue
        unit = runs._units(it["statute"]).get(it["unit_id"])
        if unit is None:
            continue
        spans = rationale(rec, unit.start, len(unit.text))
        if not spans:
            continue
        rng = random.Random(f"{SEED}|{it['item_id']}")
        ref = signature(rec)

        def variant(text: str):
            return extract(replace(unit, text=text, end=unit.start + len(text)))

        without = variant(delete(unit.text, spans))
        only = variant(keep(unit.text, spans))
        rand = variant(delete(unit.text, random_spans(spans, len(unit.text), rng)))
        rows.append({
            "item_id": it["item_id"],
            "rationale_share": sum(b - a for a, b in spans) / len(unit.text),
            "comprehensiveness": 1 - f1(ref, signature(without)),
            "sufficiency": f1(ref, signature(only)),
            "random_comprehensiveness": 1 - f1(ref, signature(rand)),
            "status": [without.status, only.status, rand.status],
        })
        if limit and len(rows) >= limit:
            break
        if len(rows) % 10 == 0:
            progress(f"{system} {split}: {len(rows)} items")

    def ci(key: str) -> dict:
        v = np.array([r[key] for r in rows], dtype=float)
        if not len(v):
            return {"mean": None}
        boots = np.random.default_rng(SEED).choice(v, size=(2000, len(v))).mean(axis=1)
        return {"mean": round(float(v.mean()), 4), "ci95": [round(float(np.percentile(boots, 2.5)), 4),
                                                             round(float(np.percentile(boots, 97.5)), 4)]}

    gap = np.array([r["comprehensiveness"] - r["random_comprehensiveness"] for r in rows], dtype=float)
    summary = {
        "system": system, "split": split, "items": len(rows),
        "comprehensiveness": ci("comprehensiveness"),
        "random_comprehensiveness": ci("random_comprehensiveness"),
        "sufficiency": ci("sufficiency"),
        "rationale_share": ci("rationale_share"),
        "comprehensiveness_minus_random": round(float(gap.mean()), 4) if len(gap) else None,
        "beats_random_share": round(float((gap > 0).mean()), 4) if len(gap) else None,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{system}_{split}.json").write_text(json.dumps({"summary": summary, "items": rows}, indent=2),
                                                    encoding="utf-8")
    return summary
