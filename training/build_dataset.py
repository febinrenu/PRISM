"""
Silver training data for fine-tuning a small local extractor.

Two strong teacher systems extract rules from the same statute provisions
with the production prompt. A provision becomes a training example only when
the teachers agree after grounding: same rules (matched on their spans), same
modalities, same effect kinds and the same numbers. The target is the first
teacher's grounded record, rendered back into the prompt's JSON format, so
every quoted string in a target is verbatim statute text.

Leakage control:
  - every provision in the frozen evaluation sets (test, dev, pilot) is excluded;
  - so is any provision sharing more than MAX_OVERLAP of its word 8-grams with
    an evaluation provision (Finance Acts quote the Acts they amend);
  - so is every provision the headline experiment extracts (provision_sets.py),
    and everything below it;
  - one statute (DPDP2023 by default) is held out entirely to measure transfer.

Output (training/data/):
  sft.jsonl          {"prompt": [...], "completion": [...], "unit_id", "statute"} per line
  sft_report.json    pool, exclusions, teacher agreement, label mix

    python training/build_dataset.py --pool 800
    python training/build_dataset.py --pool 800 --dry-run   # sample and dedupe only
"""
import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

OUT_DIR = Path(__file__).resolve().parent / "data"
SEED = 20261003
MAX_OVERLAP = 0.2
TEACHERS = ("gpt-oss-120b", "gemini-3.8-flash")
TRAIN_STATUTES = ["ITA2025/amended_fa2026", "CGST2017/consolidated", "COW2019/enacted",
                  "FA2019N2/enacted", "FA2020/enacted", "FA2023/enacted", "FA2024N2/enacted",
                  "FA2025/enacted", "FA2026/enacted"]
HELD_OUT = ["DPDP2023/enacted"]
MIN_CHARS = 60

_WORD = re.compile(r"[a-z0-9]+")


def ngrams(text: str, n: int = 8) -> set[int]:
    w = _WORD.findall(text.lower())
    return {hash(" ".join(w[i:i + n])) for i in range(max(0, len(w) - n + 1))}


def overlap(text: str, eval_grams: set[int]) -> float:
    g = ngrams(text)
    return len(g & eval_grams) / len(g) if g else 0.0


def eval_exclusions() -> tuple[set[str], set[int]]:
    from eval.v2 import sampling
    m = sampling.load()
    items = m["test"] + m["dev"]
    grams: set[int] = set()
    for it in items:
        grams |= ngrams(sampling.item_text(it))
    return {it["unit_id"] for it in items}, grams


def pool(statutes: list[str], size: int, seed: int = SEED) -> tuple[list, dict]:
    """Stratified random sample of provisions (by statute and kind), with the
    evaluation provisions and their near-duplicates removed."""
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import PROVISION_SETS
    eval_ids, eval_grams = eval_exclusions()
    experiment_paths = [p for spec in PROVISION_SETS.values() for p in spec["targets"].values()]
    candidates, dropped = [], Counter()
    for key in statutes:
        statute, version = key.split("/")
        try:
            units = build_units(statute, version)
        except FileNotFoundError:
            dropped[f"{key}: not parsed"] += 1
            continue
        for u in units:
            if len(u.text.strip()) < MIN_CHARS:
                dropped["too short"] += 1
            elif u.unit_id in eval_ids:
                dropped["in evaluation sets"] += 1
            elif any(u.path == p or u.path.startswith(p + "/") for p in experiment_paths):
                dropped["in headline experiment"] += 1
            elif overlap(u.text, eval_grams) > MAX_OVERLAP:
                dropped["8-gram overlap with evaluation sets"] += 1
            else:
                candidates.append(u)
    strata: dict[tuple, list] = {}
    for u in candidates:
        strata.setdefault((u.statute, u.kind), []).append(u)
    rng = random.Random(seed)
    for v in strata.values():
        v.sort(key=lambda u: u.unit_id)
        rng.shuffle(v)
    # Proportional allocation, at least one per stratum.
    total = len(candidates)
    picked = []
    for k in sorted(strata):
        n = max(1, round(size * len(strata[k]) / total)) if total else 0
        picked.extend(strata[k][:n])
    rng.shuffle(picked)
    return picked[:size], {"candidates": total, "dropped": dict(dropped),
                           "strata": {f"{a}|{b}": len(v) for (a, b), v in sorted(strata.items())}}


def teachers_agree(a, b, unit_id: str) -> bool:
    from eval.v2.scoring import compare, from_record
    if a.status != "ok" or b.status != "ok" or a.hallucinated_fields or b.hallucinated_fields:
        return False
    c = compare([from_record(a, unit_id)], [from_record(b, unit_id)])
    d, r, e = c["detection"], c["rules"], c["effects"]["kinds"]
    if d["fp"] or d["fn"] or r["fp"] or r["fn"] or e["fp"] or e["fn"]:
        return False
    if c["modality"]["accuracy"] not in (None, 1.0):
        return False
    return c["effects"]["numeric_exact"] in (None, 1.0)


def _txt(span):
    return span.text if span is not None else None


def target_json(record) -> dict:
    """A grounded record in the prompt's output format (quotes = statute text)."""
    rules = []
    for r in record.rules:
        effects = []
        for e in r.effects:
            d = e.model_dump(exclude={"source_span", "operation", "taxpayer"}, exclude_none=True)
            d["quote"] = _txt(e.source_span)
            effects.append(d)
        rules.append({
            "modality": r.modality,
            "subject": _txt(r.subject.span),
            "agent_class": r.subject.agent_class,
            "conditions": [{"quote": _txt(c.span), "negated": c.negated} for c in r.conditions if c.span],
            "action": _txt(r.action),
            "consequence": _txt(r.consequence),
            "exceptions": [_txt(x.span) for x in r.exceptions if x.span],
            "cross_refs": [_txt(x.span) for x in r.cross_refs if x.span],
            "effects": effects,
        })
    return {"rules": rules}


def example(unit, record) -> dict:
    from pipeline.extraction.prompts import render
    return {
        "prompt": [{"role": "user", "content": render(unit.text, unit.context)}],
        "completion": [{"role": "assistant", "content": json.dumps(target_json(record), ensure_ascii=False)}],
        "unit_id": unit.unit_id, "statute": unit.statute,
    }


def build(size: int, teachers: tuple[str, str] = TEACHERS, dry_run: bool = False,
          max_negative_share: float = 0.25) -> dict:
    from pipeline.extraction.extractor import extract_unit
    units, pool_report = pool(TRAIN_STATUTES, size)
    report = {"seed": SEED, "teachers": list(teachers), "held_out": HELD_OUT,
              "max_overlap": MAX_OVERLAP, "pool": pool_report, "sampled": len(units)}
    if dry_run:
        return report

    kept, negatives, outcome = [], [], Counter()
    for i, u in enumerate(units, 1):
        try:
            a = extract_unit(u, teachers[0])[0]
            b = extract_unit(u, teachers[1])[0]
        except Exception as exc:  # a quota or network failure stops the build; cached work is kept
            report["stopped_at"] = {"index": i, "error": str(exc)[:300]}
            break
        if not teachers_agree(a, b, u.unit_id):
            outcome["disagree"] += 1
            continue
        outcome["agree"] += 1
        (negatives if not a.rules else kept).append(example(u, a))
        if i % 25 == 0:
            print(f"{i}/{len(units)}  agree={outcome['agree']} disagree={outcome['disagree']}")

    cap = int(max_negative_share * len(kept) / (1 - max_negative_share)) if kept else 0
    rows = kept + negatives[:cap]
    random.Random(SEED).shuffle(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "sft.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    effect_kinds = Counter(e["kind"] for r in rows for rule in json.loads(r["completion"][0]["content"])["rules"]
                           for e in rule["effects"])
    report.update({
        "teacher_outcomes": dict(outcome),
        "agreement_rate": round(outcome["agree"] / max(1, sum(outcome.values())), 4),
        "examples": len(rows), "with_rules": len(kept), "no_rule": min(len(negatives), cap),
        "per_statute": dict(Counter(r["statute"] for r in rows)),
        "effect_kinds": dict(effect_kinds),
        "sha256": hashlib.sha256((OUT_DIR / "sft.jsonl").read_bytes()).hexdigest(),
    })
    (OUT_DIR / "sft_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pool", type=int, default=800)
    ap.add_argument("--teachers", default=",".join(TEACHERS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    report = build(args.pool, tuple(args.teachers.split(",")), args.dry_run)
    print(json.dumps({k: v for k, v in report.items() if k != "pool"} | {"pool": {
        "candidates": report["pool"]["candidates"], "dropped": report["pool"]["dropped"]}}, indent=2))


if __name__ == "__main__":
    main()
