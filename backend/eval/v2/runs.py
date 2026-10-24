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


def item_unit(it: dict):
    """The extraction unit of a frozen item. The item is defined by its text
    (offsets into the canonical statute text, checked by eval-verify); if a
    later parser fix gave its node a new identifier, the unit is rebuilt from
    the frozen text, with the context of the current node at the same path."""
    from dataclasses import replace
    units = _units(it["statute"])
    unit = units.get(it["unit_id"])
    if unit is not None:
        return unit
    same_path = next((u for u in units.values() if u.path == it["path"]), None)
    text = sampling.item_text(it)
    if same_path is not None:
        return replace(same_path, unit_id=it["unit_id"], start=it["start"], end=it["end"], text=text)
    from pipeline.extraction.units import Unit
    return Unit(unit_id=it["unit_id"], statute=it["statute"], path=it["path"], kind=it["kind"],
                start=it["start"], end=it["end"], text=text)


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
            unit = item_unit(it)
            rec, stats = rb_extract(unit) if system == "rules" else extract_unit(unit, system)
            # the context goes with the record: the unit's context comes from the
            # current parse, and a later parser fix must not change what a stored
            # reading is compared against (faithfulness re-reads the same unit)
            fh.write(json.dumps({"item_id": it["item_id"], "record": rec.model_dump(), "stats": stats,
                                "context": unit.context}) + "\n")
            fh.flush()
            if n % 10 == 0:
                progress(f"{system} {split}: {n}/{len(items)}")
    return out


def stale_items(system: str, split: str) -> list[str]:
    """Items whose stored reading was made from a prompt the item no longer
    gives (its unit context changed in a later parser fix): the record's
    cache key is not the key of the item's current prompt."""
    from pipeline.extraction import cache, prompts
    from pipeline.extraction.backends import SYSTEMS, request_options
    s = SYSTEMS[system]
    originals = load_run(system, split)
    contexts = load_contexts(system, split)
    out = []
    for it in split_items(split):
        rec = originals.get(it["item_id"])
        if rec is None or not rec.raw_ref or it["item_id"] in contexts:
            continue
        unit = item_unit(it)
        key = cache.key(provider=s.provider, model=s.model, prompt=prompts.render(unit.text, unit.context),
                        temperature=0.0, seed=0, prompt_version=prompts.EXTRACTION_PROMPT_VERSION,
                        options=request_options(s, None))
        if key != rec.raw_ref:
            out.append(it["item_id"])
    return out


def refresh(system: str, split: str, progress=print) -> list[str]:
    """Re-read the stale items with their current context and append the new
    records (with the context) to the run; the last record of an item is the
    one used. Writes a log of what was refreshed, when and why."""
    import datetime
    from pipeline.extraction.extractor import extract_unit
    stale = stale_items(system, split)
    items = {it["item_id"]: it for it in split_items(split)}
    out = RUNS_DIR / system / f"{split}.jsonl"
    with open(out, "a", encoding="utf-8") as fh:
        for n, item_id in enumerate(stale, 1):
            unit = item_unit(items[item_id])
            rec, stats = extract_unit(unit, system)
            if rec.status == "error":
                raise RuntimeError(f"{system} {item_id}: model call failed: {rec.error}")
            fh.write(json.dumps({"item_id": item_id, "record": rec.model_dump(), "stats": stats,
                                 "context": unit.context}) + "\n")
            fh.flush()
            progress(f"{system} {split}: refreshed {n}/{len(stale)} ({item_id})")
    log = RUNS_DIR / system / f"{split}.refresh.json"
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    if stale:
        entries.append({"date": datetime.date.today().isoformat(), "items": stale,
                        "reason": "unit context changed in a parser fix after the first run; the reading "
                                  "was re-made with the current context"})
        log.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    return stale


def load_contexts(system: str, split: str) -> dict[str, str]:
    """The unit context each stored reading was made with (runs written
    before contexts were recorded have none)."""
    path = RUNS_DIR / system / f"{split}.jsonl"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if "context" in row:
            out[row["item_id"]] = row["context"]
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
