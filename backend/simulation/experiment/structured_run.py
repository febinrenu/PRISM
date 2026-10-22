"""
The headline experiment under the structured extraction condition
(pipeline.extraction.structured): rebuilt rate tables in the prompt,
schema-constrained decoding, and one repair round after a failed
structural check.

Each run is scored twice by the headline's own scoring
(harness.evaluate): after the first pass and after the repair round. Both
are kept, with a log of every repair asked for and its outcome. Results go
to data/experiments/structured/, apart from the headline runs, which stay
as they are.

Only the greedy extraction is used (temperature 0, as in the headline,
whose self-consistency samples measure stability and never change the
extraction that is scored).
"""
import json
from pathlib import Path
from typing import Optional

from pipeline.extraction import structured
from pipeline.extraction.units import build_units
from simulation.experiment.harness import RESULTS_DIR, evaluate
from simulation.experiment.provision_sets import PROVISION_SETS, units_for
from simulation.experiment.provision_sets import spec as provision_spec

STRUCTURED_DIR = RESULTS_DIR / "structured"


def _log(target: str, path: str, units: list, records: list, stats: list) -> dict:
    return {
        "target": target, "path": path, "units": [u.unit_id for u in units],
        "status": [rec.status for rec in records],
        "rules": sum(len(rec.rules) for rec in records),
        "effects": sum(len(r.effects) for rec in records for r in rec.rules),
        "hallucinated_fields": sum(rec.hallucinated_fields for rec in records),
        "span_fields": sum(rec.total_span_fields for rec in records),
        "grounded_via_table": sum(st.get("grounded_via_table", 0) for st in stats),
        "table_rows": sum(st.get("tables", 0) for st in stats),
        "decoding": sorted({st.get("decoding", "rules") for st in stats}),
        "rule_confidence": [], "effect_confidence": [],
    }


def run_set(set_name: str, system: str, *, use_schema: bool = True, repair: bool = True,
            use_cache: bool = True) -> dict:
    spec = provision_spec(set_name)
    statute, version = spec["statute"]
    units = build_units(statute, version)

    rules_by_target: dict[str, list] = {}
    log: list[dict] = []
    attempts: dict[str, list] = {}           # path -> [(unit, Attempt)]
    for target, path in spec["targets"].items():
        target_units = units_for(path, units)
        if not target_units:
            raise ValueError(f"{set_name}: no units at {path}")
        out = [structured.extract_unit(u, system, use_schema=use_schema, use_cache=use_cache) for u in target_units]
        failed = [rec.error for rec, _, _ in out if rec.status == "error"]
        if failed:
            # as in the headline: a failed call is not a reading; not scored
            raise RuntimeError(f"{set_name}/{system}: model call failed at {path}: {failed[0]}")
        rules_by_target[path] = [r for rec, _, _ in out for r in rec.rules]
        attempts[path] = [(u, a) for u, (_, _, a) in zip(target_units, out)]
        log.append(_log(target, path, target_units, [o[0] for o in out], [o[1] for o in out]))

    first = evaluate(set_name, system, rules_by_target, log)
    repaired: Optional[dict] = None
    repair_log: list[dict] = []
    todo = [r for r in first["review"] if structured.repairable(r["reason"])]
    if repair and not system.startswith("rules") and todo:
        new_rules = dict(rules_by_target)
        new_log = [dict(entry) for entry in log]
        for item in todo:
            path = item["provision"]
            recs, stats = [], []
            for unit, attempt in attempts.get(path, []):
                if attempt is None:
                    continue
                rec, st, _ = structured.repair_unit(unit, system, attempt, item["target"], item["reason"],
                                                    use_schema=use_schema, use_cache=use_cache)
                if rec.status == "error":
                    raise RuntimeError(f"{set_name}/{system}: repair call failed at {path}: {rec.error}")
                recs.append(rec)
                stats.append(st)
            if not recs:
                continue
            new_rules[path] = [r for rec in recs for r in rec.rules]
            for i, entry in enumerate(new_log):
                if entry["path"] == path:
                    new_log[i] = {**_log(item["target"], path, [u for u, _ in attempts[path]], recs, stats),
                                  "repaired": True}
            repair_log.append({"target": item["target"], "path": path, "reason": item["reason"],
                               "status": [rec.status for rec in recs],
                               "effects": sum(len(r.effects) for rec in recs for r in rec.rules)})
        repaired = evaluate(set_name, system, new_rules, new_log)
        for entry in repair_log:
            entry["fixed"] = not any(r["target"] == entry["target"] for r in repaired["review"])

    final = repaired or first
    return {
        "set": set_name, "system": system, "condition": "structured",
        "variant": variant_name(system, use_schema), "use_schema": use_schema and not system.startswith("rules"),
        "repair": repair and not system.startswith("rules"),
        "complete_first_pass": first["complete"], "complete": final["complete"],
        "first_pass": first, "repaired": repaired, "repair_log": repair_log,
    }


def variant_name(system: str, use_schema: bool) -> str:
    """tables+schema (constrained decoding) or tables+json (JSON mode), both
    with the repair round, whose first pass is kept; "tables" for the rule
    baseline, which neither decodes nor repairs."""
    if system.startswith("rules"):
        return "tables"
    return "tables+schema" if use_schema else "tables+json"


def save(result: dict) -> Path:
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    path = STRUCTURED_DIR / f"{result['set']}__{result['system']}__{result['variant']}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path


def load_runs() -> list[dict]:
    if not STRUCTURED_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(STRUCTURED_DIR.glob("*__*.json"))
            if p.stem.split("__")[0] in PROVISION_SETS]


def summary(headline: list[dict], runs: list[dict]) -> list[dict]:
    """Per system, for systems run on every reform: the headline and each
    variant's first pass and repaired result, as counts of reforms that
    assemble and that keep every pre-registered conclusion."""
    from collections import defaultdict
    n = len(PROVISION_SETS)
    by: dict = defaultdict(dict)
    for r in runs:
        by[(r["system"], r["variant"])][r["set"]] = r
    head: dict = defaultdict(dict)
    for r in headline:
        head[r["system"]][r["set"]] = r

    def counts(results: list[dict]) -> dict:
        return {"assembled": sum(1 for x in results if x["complete"]),
                "no_flip": sum(1 for x in results if x["population"]["flip_rate"] == 0), "reforms": n}

    order = ["rules", "gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "phi3.5", "gemma2-2b"]
    out = []
    for system in sorted({s for s, _ in by}, key=lambda x: (order.index(x) if x in order else 99, x)):
        variants = sorted(v for (s, v) in by if s == system and len(by[(s, v)]) == n)
        if not variants:
            continue
        entry = {"system": system, "headline": counts(list(head[system].values())) if len(head[system]) == n else None,
                 "variants": []}
        for v in variants:
            rs = [by[(system, v)][k] for k in PROVISION_SETS]
            item = {"variant": v, "first_pass": counts([r["first_pass"] for r in rs]), "repaired": None}
            if any(r["repair"] for r in rs):
                item["repaired"] = counts([r["repaired"] or r["first_pass"] for r in rs])
                item["repairs_asked"] = sum(1 for r in rs if r["repair_log"])
                item["assembled_by_repair"] = sum(1 for r in rs if r["repair_log"] and r["complete"]
                                                  and not r["complete_first_pass"])
                item["repaired_but_flipped"] = sum(1 for r in rs if r["repaired"] and r["complete"]
                                                   and not r["complete_first_pass"]
                                                   and r["repaired"]["population"]["flip_rate"] > 0)
            logs = [e for r in rs for e in r["first_pass"].get("extraction", [])]
            item["targets"] = len(logs)
            item["empty_targets"] = sum(1 for e in logs if e["rules"] == 0)
            item["reforms"] = [{"set": r["set"], "first_complete": r["complete_first_pass"],
                                "first_flip_rate": r["first_pass"]["population"]["flip_rate"],
                                "complete": r["complete"],
                                "flip_rate": (r["repaired"] or r["first_pass"])["population"]["flip_rate"],
                                "repairs": len(r["repair_log"]),
                                "review": (r["repaired"] or r["first_pass"]).get("review", [])} for r in rs]
            entry["variants"].append(item)
        out.append(entry)
    return out


def interleaved_sets() -> list[str]:
    """Provision sets with a rate table whose canonical text does not hold
    some row in its printed order (the rebuilt row is not a substring of
    the provision text, whitespace aside)."""
    from pipeline.statute import tables as statute_tables

    def squash(s: str) -> str:
        return " ".join(s.replace("|", " ").split())

    out = []
    for name, spec in PROVISION_SETS.items():
        units = build_units(*spec["statute"])
        hit = False
        for path in spec["targets"].values():
            for u in units_for(path, units):
                body = squash(u.text)
                for t in statute_tables.tables_in(u.statute, u.start, u.end):
                    if any(squash(r.text) not in body for r in t.rows):
                        hit = True
        if hit:
            out.append(name)
    return out


def number_grounding(systems: Optional[list[str]] = None, sets: Optional[dict] = None) -> list[dict]:
    """For each system and condition whose extractions are all cached: how
    many numeric fields of its effects are stated in the quote they cite, only
    elsewhere in the provision, or nowhere (pipeline.extraction.numbers).
    Never calls a model."""
    import os
    from collections import Counter

    from pipeline.extraction import structured
    from pipeline.extraction.backends import OfflineCacheMiss
    from pipeline.extraction.extractor import cached_record
    from pipeline.extraction.numbers import check_record
    from pipeline.extraction.rule_based import extract_unit as rule_unit

    systems = systems or ["rules", "gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "phi3.5", "gemma2-2b"]
    units = []
    for spec in (sets or PROVISION_SETS).values():
        built = build_units(*spec["statute"])
        for path in spec["targets"].values():
            units += units_for(path, built)

    def readers(system: str):
        if system.startswith("rules"):
            from pipeline.extraction.rule_based import RULE_VERSIONS
            yield "headline", lambda u: rule_unit(u, version=RULE_VERSIONS[system])[0]
            yield "tables", lambda u: structured.extract_unit(u, system)[0]
            return
        yield "headline", lambda u: cached_record(u, system)
        for schema in (False, True):
            yield ("tables+schema" if schema else "tables+json"), \
                lambda u, s=schema: structured.extract_unit(u, system, use_schema=s)[0]

    rows = []
    prev = os.environ.get("PRISM_OFFLINE")
    os.environ["PRISM_OFFLINE"] = "1"
    try:
        for system in systems:
            for condition, read in readers(system):
                c: Counter = Counter()
                examples = []
                complete = True
                for u in units:
                    try:
                        rec = read(u)
                    except OfflineCacheMiss:
                        rec = None
                    if rec is None or rec.status == "error":
                        complete = False
                        break
                    effects = [e for r in rec.rules for e in r.effects]
                    for e, chk in zip(effects, check_record(rec, u.text)):
                        c["effects"] += 1
                        c[f"effects_{chk.status}"] += 1
                        for f in chk.fields:
                            c[f.found] += 1
                            if f.found == "missing" and len(examples) < 6:
                                examples.append({"provision": u.path, "kind": e.kind, "field": f.field, "value": f.value})
                if not complete:
                    continue
                n = c["quote"] + c["provision"] + c["missing"]
                rows.append({"system": system, "condition": condition, "fields": n,
                             "in_quote": c["quote"], "in_provision": c["provision"], "missing": c["missing"],
                             "effects": c["effects"], "effects_unsupported": c["effects_unsupported"],
                             "missing_examples": examples})
    finally:
        if prev is None:
            os.environ.pop("PRISM_OFFLINE", None)
        else:
            os.environ["PRISM_OFFLINE"] = prev
    return rows
