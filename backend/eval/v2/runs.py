"""
Run extraction systems over the frozen evaluation sets, and score them.

    data/eval/v2/runs/{system}/{split}.jsonl     one ExtractionRecord per item
    data/annotations/{annotator}/{item}.json     human annotations
    data/annotations/adjudicated/{item}.json     agreed gold after adjudication
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from config import BASE_DIR
from eval.v2 import sampling, scoring
from models.rules import ExtractionRecord

RUNS_DIR = sampling.EVAL_DIR / "runs"
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"


def split_items(split: str) -> list[dict]:
    m = sampling.load()
    if split == "pilot":
        dev = {it["item_id"]: it for it in m["dev"]}
        return [dev[i] for i in m["pilot"]]
    return m[split]


@lru_cache(maxsize=16)
def _units(statute_key: str) -> dict:
    from pipeline.extraction.units import build_units
    statute, version = statute_key.split("/")
    return {u.unit_id: u for u in build_units(statute, version)}


def run(system: str, split: str, limit: Optional[int] = None, progress=print) -> Path:
    items = split_items(split)[:limit] if limit else split_items(split)
    out = RUNS_DIR / system / f"{split}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done[rec["item_id"]] = rec
    if system == "rules":
        from pipeline.extraction.rule_based import extract_unit as rb_extract
    else:
        from pipeline.extraction.extractor import extract_unit
    with open(out, "a", encoding="utf-8") as fh:
        for n, it in enumerate(items, 1):
            if it["item_id"] in done and done[it["item_id"]]["record"]["status"] != "error":
                continue
            unit = _units(it["statute"]).get(it["unit_id"])
            if unit is None:
                progress(f"{it['item_id']}: unit {it['unit_id']} no longer in the corpus")
                continue
            rec, stats = rb_extract(unit) if system == "rules" else extract_unit(unit, system)
            fh.write(json.dumps({"item_id": it["item_id"], "record": rec.model_dump(), "stats": stats}) + "\n")
            fh.flush()
            if n % 10 == 0:
                progress(f"{system} {split}: {n}/{len(items)}")
    return out


def load_run(system: str, split: str) -> dict[str, ExtractionRecord]:
    path = RUNS_DIR / system / f"{split}.jsonl"
    recs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        recs[row["item_id"]] = ExtractionRecord.model_validate(row["record"])  # last one wins
    return recs


def load_annotations(annotator: str, items: list[dict], done_only: bool = True) -> dict[str, dict]:
    d = ANNOTATION_DIR / annotator
    out = {}
    for it in items:
        p = d / f"{it['item_id']}.json"
        if p.exists():
            a = json.loads(p.read_text(encoding="utf-8"))
            if not done_only or a.get("status") == "done":
                out[it["item_id"]] = a
    return out


def annotators() -> list[str]:
    if not ANNOTATION_DIR.exists():
        return []
    return sorted(p.name for p in ANNOTATION_DIR.iterdir() if p.is_dir() and p.name != "adjudicated")


def agreement(split: str) -> dict:
    """Pairwise agreement between annotators on items both have finished."""
    items = split_items(split)
    names = annotators()
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ann_a, ann_b = load_annotations(a, items), load_annotations(b, items)
            common = [it for it in items if it["item_id"] in ann_a and it["item_id"] in ann_b]
            if not common:
                continue
            ga = [scoring.from_annotation(ann_a[it["item_id"]], it) for it in common]
            gb = [scoring.from_annotation(ann_b[it["item_id"]], it) for it in common]
            out[f"{a} vs {b}"] = scoring.compare(ga, gb)
    return out


def score(system: str, split: str, gold: str = "adjudicated") -> dict:
    items = split_items(split)
    gold_ann = load_annotations(gold, items)
    covered = [it for it in items if it["item_id"] in gold_ann]
    recs = load_run(system, split)
    g = [scoring.from_annotation(gold_ann[it["item_id"]], it) for it in covered]
    p = [scoring.from_record(recs[it["item_id"]], it["item_id"]) for it in covered if it["item_id"] in recs]
    res = scoring.compare(g, p)
    res["gold"] = gold
    res["system"] = system
    res["coverage"] = {"gold_items": len(covered), "system_items": len(p), "split_items": len(items)}
    halluc = [recs[it["item_id"]] for it in covered if it["item_id"] in recs]
    tot = sum(r.total_span_fields for r in halluc)
    res["hallucination_rate"] = round(sum(r.hallucinated_fields for r in halluc) / tot, 4) if tot else None
    return res
