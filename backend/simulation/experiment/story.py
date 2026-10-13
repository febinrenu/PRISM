"""
The data behind the web app's landing story, built only from results that
already exist: the paper's generated numbers (paper/tables/numbers.tex), the
experiment runs, the error-injection and behaviour results, the expert law
and the parsed statute corpus. Nothing here calls a model.

    python -m cli story-export          # write the snapshot files
    python -m cli story-export --check  # exit 1 if any file is stale

Every value the story prints carries its source (file and key), so the page
can show where a number comes from. Output is deterministic: no timestamps,
sorted keys, rounded floats.

Files written:
    frontend/src/content/story.core.json    bundled with the page (text, numbers, small series)
    frontend/public/story/population.json   the simulated taxpayers (fetched by the scene)
    frontend/public/story/constellation.json  statute structure for the provenance scene
    backend/data/experiments/story.json     the core file, served at /api/research/story
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from config import BASE_DIR
from simulation.experiment.harness import RESULTS_DIR

ROOT = BASE_DIR.parent
NUMBERS_TEX = ROOT / "paper" / "tables" / "numbers.tex"
FRONTEND = ROOT / "frontend"
CORE_OUT = FRONTEND / "src" / "content" / "story.core.json"
POP_OUT = FRONTEND / "public" / "story" / "population.json"
CONST_OUT = FRONTEND / "public" / "story" / "constellation.json"
API_OUT = RESULTS_DIR / "story.json"

# The reform the story follows from text to population: Finance Act 2025's
# Rs. 12 lakh rebate, read by the system with the largest revenue error.
FOCUS_SET = "FA2025_rebate_12L"
FOCUS_SYSTEM = "qwen3.8-27b"
FOCUS_TARGET = "new.rebate"
# The constellation: the consolidated Income-tax Act 2025, with the thread
# through its rebate section (s.156) and its default-regime table (s.202).
CONST_STATUTE = ("ITA2025", "amended_fa2026")
CONST_THREAD = ("156", "202")

SYSTEMS = [
    {"id": "gpt-oss-120b", "label": "gpt-oss-120b", "kind": "open-weight, hosted", "params_b": 120},
    {"id": "qwen3.8-27b", "label": "Qwen 3.8 27B", "kind": "open-weight, hosted", "params_b": 27},
    {"id": "gpt-oss-20b", "label": "gpt-oss-20b", "kind": "open-weight, hosted", "params_b": 20},
    {"id": "phi3.5", "label": "Phi-3.5 mini", "kind": "small, runs locally", "params_b": 3.8},
    {"id": "gemma2-2b", "label": "Gemma 2 2B", "kind": "small, runs locally", "params_b": 2},
    {"id": "rules", "label": "Rule-based", "kind": "regular expressions, no model", "params_b": 0},
]


def _rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT.resolve()).as_posix()


def _r(x, nd=4):
    if x is None:
        return None
    return round(float(x), nd)


def read_numbers(path: Path = NUMBERS_TEX) -> dict[str, dict]:
    """Every \\res{key} the paper prints, with its source."""
    pat = re.compile(r"\\csname res@(.+?)\\endcsname\{(.*)\}\s*$")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pat.search(line)
        if m:
            out[m.group(1)] = {"value": m.group(2), "source": {"file": _rel(path), "key": m.group(1)}}
    return out


def _run(set_name: str, system: str) -> dict | None:
    p = RESULTS_DIR / f"{set_name}__{system}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def matrix() -> dict:
    """Reform × system: did the extraction assemble, did any conclusion flip,
    how far off was the revenue change, and why it could not assemble."""
    from simulation.experiment.provision_sets import PROVISION_SETS
    reforms, cells = [], []
    for set_name, spec in PROVISION_SETS.items():
        reforms.append({"id": set_name, "ay": spec["ay"], "statute": "/".join(spec["statute"]),
                        "description": spec.get("description", ""), "targets": spec["targets"]})
        for s in SYSTEMS:
            run = _run(set_name, s["id"])
            if run is None:
                cells.append({"set": set_name, "system": s["id"], "status": "missing"})
                continue
            pop = run["population"]
            n_conc = len(pop["conclusions_expert"])
            cell = {"set": set_name, "system": s["id"], "complete": run["complete"],
                    "source": {"file": _rel(RESULTS_DIR / f"{set_name}__{s['id']}.json")}}
            if run["complete"]:
                err = abs(pop["revenue_change_system_crore"] - pop["revenue_change_expert_crore"])
                cell.update(status="assembled", flips=int(round(pop["flip_rate"] * n_conc)), conclusions=n_conc,
                            revenue_error_crore=_r(err, 1), decile_rate_l1=_r(pop["decile_rate_l1"], 5),
                            param_diff=run.get("param_diff", []))
            else:
                cell.update(status="no conclusion",
                            reasons=sorted({x["reason"].split(":")[0].split(" between")[0] for x in run["review"]}))
            cells.append(cell)
    return {"reforms": reforms, "systems": SYSTEMS, "cells": cells}


def focus_provision() -> dict:
    """The rebate provision as the focus system read it: text, quoted span,
    extracted values against the expert's (from the extraction cache)."""
    from routers.research import inspect
    view = inspect(FOCUS_SET, FOCUS_SYSTEM)
    tgt = next(t for t in view["targets"] if t["target"] == FOCUS_TARGET)
    unit = tgt["units"][0]
    effects = [{k: e.get(k) for k in ("kind", "regime", "max_income", "max_rebate", "marginal_relief", "quote",
                                       "span", "modality") if k in e} for e in unit["effects"]]
    run = _run(FOCUS_SET, FOCUS_SYSTEM)
    return {"set": FOCUS_SET, "system": FOCUS_SYSTEM, "target": FOCUS_TARGET, "provision": tgt["provision"],
            "path": unit["path"], "text": unit["text"], "effects": effects,
            "expert": tgt["expert"], "extracted": tgt["system"], "param_diff": run.get("param_diff", []),
            "revenue_error_crore": _r(run["attribution"]["total"]["revenue_error_crore"], 1),
            "source": {"file": _rel(RESULTS_DIR / f"{FOCUS_SET}__{FOCUS_SYSTEM}.json"),
                       "inspect": f"/research?set={FOCUS_SET}&inspect={FOCUS_SYSTEM}"}}


def _params(run_or_ay):
    from simulation.rac import gold
    from simulation.rac.types import PITParams
    if isinstance(run_or_ay, str):
        return gold.build_gold()[run_or_ay]
    return PITParams.model_validate(run_or_ay["params"])


def tax_curve() -> dict:
    """New-regime tax on a salary, AY 2025-26 law, AY 2026-27 expert law and
    the focus system's reading of it."""
    from simulation.rac.pit import liability
    salary = np.arange(0, 2_500_001, 5_000, dtype=float)
    out = {"salary": salary.astype(int).tolist(), "series": {}}
    for key, p in (("before", _params("2025-26")), ("expert", _params("2026-27")),
                   ("system", _params(_run(FOCUS_SET, FOCUS_SYSTEM)))):
        out["series"][key] = liability(p, "new", salary).total_tax.astype(int).tolist()
    exp, sysv = np.array(out["series"]["expert"]), np.array(out["series"]["system"])
    diff = sysv - exp
    i = int(np.argmax(diff))
    out["largest_gap"] = {"salary": int(salary[i]), "expert": int(exp[i]), "system": int(sysv[i]),
                          "difference": int(diff[i])}
    out["source"] = {"engine": "backend/simulation/rac/pit.py",
                     "expert": "backend/simulation/rac/gold (AY 2025-26, 2026-27)",
                     "system": _rel(RESULTS_DIR / f"{FOCUS_SET}__{FOCUS_SYSTEM}.json")}
    return out


@lru_cache(maxsize=32)
def ay_deciles(ay: str, set_name: str | None = None, system: str | None = None) -> dict:
    """Effective tax rate by income decile on one population: the previous
    year's law, the expert law for `ay` and (optionally) a system's reading
    of a reform."""
    from simulation.backtest.run import population_for
    from simulation.engine.outcomes import decile_rates
    from simulation.engine.static import simulate
    from simulation.experiment.harness import baseline
    pop = population_for(ay)
    expert = _params(ay)
    after = simulate(expert, pop)
    before = baseline(expert, ay, pop, after)
    rows = {"before": decile_rates(before), "expert": decile_rates(after)}
    run = _run(set_name, system) if (set_name and system) else None
    if run is not None and run["complete"]:
        rows["system"] = decile_rates(simulate(_params(run), pop))
    return {"ay": ay, "set": set_name, "system": system if "system" in rows else None,
            "deciles": [{"decile": d["decile"], "income_upper": _r(d["income_upper"], 0),
                         **{k: _r(v[i]["effective_rate"], 5) for k, v in rows.items()}}
                        for i, d in enumerate(rows["expert"])]}


def decile_view(set_name: str, system: str | None = None) -> dict:
    from simulation.experiment.provision_sets import PROVISION_SETS
    return ay_deciles(PROVISION_SETS[set_name]["ay"], set_name, system)


def population_points() -> dict:
    """The representative taxpayers of the simulated population (AY 2026-27):
    income, how many returns each stands for, decile, and tax under the
    previous law, the expert law and the focus system's reading."""
    from simulation.backtest.run import population_for
    from simulation.engine.static import simulate
    from simulation.experiment.harness import baseline
    ay = "2026-27"
    pop = population_for(ay)
    expert = _params(ay)
    after = simulate(expert, pop)
    before = baseline(expert, ay, pop, after)
    system = simulate(_params(_run(FOCUS_SET, FOCUS_SYSTEM)), pop)
    o = np.argsort(pop.gti, kind="stable")
    cum = np.cumsum(pop.weight[o]) / pop.weight.sum()
    dec = np.empty(len(o), dtype=int)
    dec[o] = np.minimum((cum * 10 - 1e-9).astype(int), 9) + 1
    rows = [[int(round(pop.gti[i])), _r(pop.weight[i], 1), int(dec[i]), int(round(before.tax[i])),
             int(round(after.tax[i])), int(round(system.tax[i]))] for i in o]
    return {"ay": ay, "columns": ["income", "returns", "decile", "tax_before", "tax_expert", "tax_system"],
            "rows": rows, "returns_total": _r(pop.weight.sum(), 0),
            "source": {"population": "backend/simulation/population/taxpayers.py (CBDT returns by income range)",
                       "engine": "backend/simulation/engine/static.py",
                       "system": _rel(RESULTS_DIR / f"{FOCUS_SET}__{FOCUS_SYSTEM}.json")}}


def injection() -> dict:
    path = RESULTS_DIR / "error_injection.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    kinds = {}
    for r in rows:
        k = kinds.setdefault(r["error"], {"error": r["error"], "injections": 0, "flipping": 0,
                                         "max_flip_rate": 0.0, "max_revenue_error_crore": 0.0})
        k["injections"] += 1
        k["flipping"] += int(r["flip_rate"] > 0)
        k["max_flip_rate"] = max(k["max_flip_rate"], r["flip_rate"])
        k["max_revenue_error_crore"] = max(k["max_revenue_error_crore"], abs(r["revenue_error_crore"]))
    for k in kinds.values():
        k["max_flip_rate"] = _r(k["max_flip_rate"], 4)
        k["max_revenue_error_crore"] = _r(k["max_revenue_error_crore"], 0)
    return {"kinds": sorted(kinds.values(), key=lambda k: -k["max_flip_rate"]),
            "rows": [{"set": r["set"], "target": r["target"], "error": r["error"],
                      "flip_rate": _r(r["flip_rate"], 4), "revenue_error_crore": _r(r["revenue_error_crore"], 0)}
                     for r in rows],
            "source": {"file": _rel(path)}}


def behaviour() -> dict:
    path = RESULTS_DIR / "behaviour.json"
    b = json.loads(path.read_text(encoding="utf-8"))
    st = {n: _r(v["ST"], 3) for n, v in b["sobol"]["indices"]["tax_gap"].items() if n != "range"}
    return {"expert_penalty": b["expert_penalty"], "misread_penalty": b["misread_penalty"],
            "sobol_total": dict(sorted(st.items(), key=lambda kv: -kv[1])),
            "systems": {k: {"penalty_rate": v.get("penalty_rate"), "matches_expert": v.get("matches_expert")}
                        for k, v in b["systems"].items()},
            "source": {"file": _rel(path)}}


def constellation() -> dict:
    """Chapters, sections and schedules of the consolidated 2025 Act, plus
    every node under the thread sections."""
    from pipeline.statute.corpus import CORPUS_DIR
    statute, version = CONST_STATUTE
    path = CORPUS_DIR / statute / version / "ast.json"
    ast = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n["node_id"]: n for n in ast["nodes"]}
    keep: dict[str, dict] = {}
    thread_ids = []
    for n in ast["nodes"]:
        if n.get("quoted"):
            continue
        if n["kind"] in ("chapter", "schedule", "part") or n["kind"] == "section":
            keep[n["node_id"]] = n
        if n["kind"] == "section" and n.get("number") in CONST_THREAD:
            thread_ids.append(n["node_id"])
            stack = list(n.get("children", []))
            while stack:
                c = nodes.get(stack.pop())
                if c and c["kind"] in ("subsection", "clause", "subclause", "item", "table_row"):
                    keep[c["node_id"]] = c
                    stack.extend(c.get("children", []))

    def kept_parent(n):
        p = n.get("parent")
        while p and p not in keep:
            p = nodes[p].get("parent") if p in nodes else None
        return p

    order = [n["node_id"] for n in ast["nodes"] if n["node_id"] in keep]
    index = {nid: i for i, nid in enumerate(order)}
    out = []
    for nid in order:
        n = keep[nid]
        p = kept_parent(n)
        out.append({"k": n["kind"], "l": n.get("number") or n.get("label") or "",
                    "h": (n.get("heading") or "")[:80], "p": index.get(p, -1) if p else -1})
    return {"statute": f"{statute}/{version}", "title": ast.get("title", statute), "nodes": out,
            "thread": [index[t] for t in thread_ids], "source": {"file": _rel(path)}}


def build() -> tuple[dict, dict, dict]:
    nums = read_numbers()
    core = {
        "version": 1,
        "numbers": nums,
        "matrix": matrix(),
        "focus": focus_provision(),
        "curve": tax_curve(),
        "deciles": decile_view(FOCUS_SET, FOCUS_SYSTEM),
        "injection": injection(),
        "behaviour": behaviour(),
        "corpus": _corpus_counts(),
    }
    return core, population_points(), constellation()


def _corpus_counts() -> dict:
    from routers.corpus import statutes
    s = statutes()["statutes"]
    return {"statutes": [{"key": x["key"], "title": x["title"], "sections": x["sections"], "chapters": x["chapters"]}
                         for x in s],
            "sections_total": sum(x["sections"] for x in s), "characters_total": sum(x["characters"] for x in s),
            "source": {"file": "backend/data/corpus/*/*/ast.json", "route": "/api/corpus/statutes"}}


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def export(check: bool = False) -> list[tuple[Path, bool]]:
    """Write (or, with check, compare) every story file. Returns (path, fresh)."""
    core, pop, const = build()
    files = [(CORE_OUT, _dump(core)), (API_OUT, _dump(core)), (POP_OUT, _dump(pop)), (CONST_OUT, _dump(const))]
    out = []
    for path, text in files:
        fresh = path.exists() and path.read_text(encoding="utf-8") == text
        if not check and not fresh:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        out.append((path, fresh))
    return out
