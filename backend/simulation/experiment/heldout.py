"""
The held-out check (provision_sets.HELD_OUT_SETS, fixed before any run).

Every system is run on every held-out reform under the headline condition
(the canonical text, JSON mode, greedy) and under the structured condition
(rebuilt tables, with and without schema decoding, one repair round), and
scored by the headline's own scoring. Results go to
data/experiments/heldout/{set}__{system}__{condition}.json.

    python -m cli experiment-heldout
"""
import json
from pathlib import Path

from simulation.experiment import structured_run
from simulation.experiment.harness import RESULTS_DIR, run_set
from simulation.experiment.provision_sets import HELD_OUT_SETS

HELDOUT_DIR = RESULTS_DIR / "heldout"
SYSTEMS = ["rules", "gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b"]


def conditions(system: str) -> list[str]:
    return ["headline", "tables"] if system == "rules" else ["headline", "tables+json", "tables+schema"]


def run(set_name: str, system: str, condition: str) -> dict:
    if condition == "headline":
        r = run_set(set_name, system, k=0)
        return {"set": set_name, "system": system, "condition": condition, "complete_first_pass": r["complete"],
                "complete": r["complete"], "first_pass": r, "repaired": None, "repair_log": []}
    r = structured_run.run_set(set_name, system, use_schema=condition == "tables+schema")
    return {**r, "condition": condition}


def save(r: dict) -> Path:
    HELDOUT_DIR.mkdir(parents=True, exist_ok=True)
    path = HELDOUT_DIR / f"{r['set']}__{r['system']}__{r['condition']}.json"
    path.write_text(json.dumps(r, indent=2), encoding="utf-8")
    return path


def load() -> list[dict]:
    if not HELDOUT_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HELDOUT_DIR.glob("*__*__*.json"))
            if p.stem.split("__")[0] in HELD_OUT_SETS]


def summary(runs: list[dict]) -> list[dict]:
    """Per system and condition, over every held-out reform: assembled and
    no-flip counts after the first pass and after the repair round, and
    where each number of the extracted effects is found."""
    from collections import defaultdict
    n = len(HELD_OUT_SETS)
    by: dict = defaultdict(dict)
    for r in runs:
        by[(r["system"], r["condition"])][r["set"]] = r
    grounding = {(g["system"], g["condition"]): g
                 for g in structured_run.number_grounding(sorted({s for s, _ in by}), sets=HELD_OUT_SETS)}

    def count(results):
        return {"assembled": sum(1 for x in results if x["complete"]),
                "no_flip": sum(1 for x in results if x["population"]["flip_rate"] == 0)}

    out = []
    order = SYSTEMS + ["phi3.5", "gemma2-2b"]
    for (system, condition), rs in sorted(by.items(), key=lambda kv: (order.index(kv[0][0]) if kv[0][0] in order else 99,
                                                                      conditions(kv[0][0]).index(kv[0][1])
                                                                      if kv[0][1] in conditions(kv[0][0]) else 9)):
        if len(rs) < n:
            continue
        runs_ = [rs[k] for k in HELD_OUT_SETS]
        g = grounding.get((system, condition))
        out.append({"system": system, "condition": condition, "reforms": n,
                    "first_pass": count([r["first_pass"] for r in runs_]),
                    "final": count([r["repaired"] or r["first_pass"] for r in runs_]),
                    "repairs": sum(1 for r in runs_ if r["repair_log"]),
                    "numbers": None if not g or not g["fields"] else
                    {"fields": g["fields"], "in_quote": g["in_quote"], "in_provision": g["in_provision"],
                     "missing": g["missing"]},
                    "per_reform": [{"set": r["set"], "complete": r["complete"],
                                    "flip_rate": (r["repaired"] or r["first_pass"])["population"]["flip_rate"],
                                    "first_complete": r["complete_first_pass"],
                                    "review": (r["repaired"] or r["first_pass"]).get("review", [])} for r in runs_]})
    return out
