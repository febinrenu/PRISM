"""
The rule baseline with its two held-out defects fixed ("rules-v2"),
reported separately and as post-hoc.

The held-out check exposed two defects of the rule baseline (version 1, as
reported throughout): a figure printed with a space before its comma
("Rs. 10 ,00,000", FA 2020 Part III) read as Rs. 10, and a schedule printed
without row labels (FA 2024 (No. 2) Part III item (III)) that the table
rebuilder did not find. Version 2 fixes both (pipeline.extraction.rule_based,
pipeline.statute.tables.load_v2). Version 1 and every reported result are
left as they were.

Version 2 is run on the ten headline reforms and the five held-out reforms,
with and without rebuilt tables, and written to data/experiments/rules_v2/.
Its fixes were designed after the held-out results were seen, so on those
five reforms its results are not a held-out test; this module says so in
everything it writes.

    python -m cli rules-v2
"""
import json
from pathlib import Path

from simulation.experiment import heldout, structured_run
from simulation.experiment.harness import RESULTS_DIR, run_set
from simulation.experiment.provision_sets import HELD_OUT_SETS, PROVISION_SETS

OUT_DIR = RESULTS_DIR / "rules_v2"
SYSTEM = "rules-v2"
NOTE = ("post-hoc: version 2 fixes two defects the held-out check exposed; designed after those results "
        "were seen, so on the held-out reforms it is not a held-out test")


def _wrap(scope: str, set_name: str, condition: str, r: dict) -> dict:
    first = r["first_pass"] if "first_pass" in r else r
    final = (r.get("repaired") or first) if "first_pass" in r else r
    return {"scope": scope, "set": set_name, "system": SYSTEM, "condition": condition, "note": NOTE,
            "complete": final["complete"], "flip_rate": final["population"]["flip_rate"],
            "review": final.get("review", []), "result": r}


def run_all(progress=print) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    jobs = [("headline", s, c) for s in PROVISION_SETS for c in ("headline", "tables")] + \
           [("heldout", s, c) for s in HELD_OUT_SETS for c in ("headline", "tables")]
    for scope, set_name, condition in jobs:
        if condition == "headline":
            r = run_set(set_name, SYSTEM, k=0)
        else:
            r = structured_run.run_set(set_name, SYSTEM)
        w = _wrap(scope, set_name, condition, r)
        path = OUT_DIR / f"{scope}__{set_name}__{condition}.json"
        path.write_text(json.dumps(w, indent=2), encoding="utf-8")
        written.append(path)
        progress(f"{scope:8s} {set_name:28s} {condition:9s} complete={w['complete']!s:5s} flip={w['flip_rate']:.2f}")
    return written


def load() -> list[dict]:
    if not OUT_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT_DIR.glob("*__*__*.json"))]


def _v1() -> dict:
    """Version 1's results, as reported: {(scope, set, condition): (complete, flip_rate)}."""
    from simulation.experiment.stats import load_runs
    out = {}
    for r in load_runs():
        if r["system"] == "rules":
            out[("headline", r["set"], "headline")] = (r["complete"], r["population"]["flip_rate"])
    for r in structured_run.load_runs():
        if r["system"] == "rules":
            f = r["first_pass"]
            out[("headline", r["set"], "tables")] = (f["complete"], f["population"]["flip_rate"])
    for r in heldout.load():
        if r["system"] == "rules":
            f = r["first_pass"]
            out[("heldout", r["set"], r["condition"])] = (f["complete"], f["population"]["flip_rate"])
    return out


def summary() -> dict:
    v2 = {(r["scope"], r["set"], r["condition"]): (r["complete"], r["flip_rate"]) for r in load()}
    v1 = _v1()
    rows, changes = [], []
    for scope, sets in (("headline", PROVISION_SETS), ("heldout", HELD_OUT_SETS)):
        for condition in ("headline", "tables"):
            keys = [(scope, s, condition) for s in sets]
            if not all(k in v1 and k in v2 for k in keys):
                continue
            rows.append({"scope": scope, "condition": condition, "reforms": len(keys),
                         "v1_no_flip": sum(1 for k in keys if v1[k][1] == 0),
                         "v2_no_flip": sum(1 for k in keys if v2[k][1] == 0)})
            for k in keys:
                if v1[k] != v2[k]:
                    changes.append({"scope": scope, "set": k[1], "condition": condition,
                                    "v1": {"complete": v1[k][0], "flip_rate": v1[k][1]},
                                    "v2": {"complete": v2[k][0], "flip_rate": v2[k][1]}})
    return {"note": NOTE, "rows": rows, "changes": changes}
