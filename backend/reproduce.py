"""
Regenerate every table of the paper from frozen inputs and cached model
outputs, without calling any model (PRISM_OFFLINE=1: a cache miss is an
error, never a silently failed extraction).

    python -m cli reproduce                  # tables from the cache
    python -m cli reproduce --sensitivity    # also re-run the Sobol analysis (slow)

Writes paper/tables/{name}.tex and {name}.csv. Every number in the paper
comes from one of these files.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Optional

from config import BASE_DIR

TABLES = BASE_DIR.parent / "paper" / "tables"
CORPUS = BASE_DIR / "data" / "corpus"


def _tex_escape(v) -> str:
    s = "--" if v is None else str(v)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"),
                 ("₹", r"Rs.~"), ("→", r"$\rightarrow$"), ("−", "-")):
        s = s.replace(a, b)
    return s


def write_table(name: str, header: list[str], rows: list[list], caption: str, align: Optional[str] = None) -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    with open(TABLES / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    align = align or "l" + "r" * (len(header) - 1)
    lines = [r"\begin{table}[t]", r"\centering\small", rf"\caption{{{caption}}}", rf"\label{{tab:{name}}}",
             rf"\begin{{tabular}}{{{align}}}", r"\toprule",
             " & ".join(_tex_escape(h) for h in header) + r" \\", r"\midrule"]
    lines += [" & ".join(_tex_escape(c) for c in r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    path = TABLES / f"{name}.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _f(x, nd=3):
    return None if x is None else f"{x:.{nd}f}"


def _cr(x):
    return None if x is None else f"{x:,.0f}"


# ── tables ───────────────────────────────────────────────────────────────────

def corpus_table() -> Path:
    def source_sha(d: Path) -> str:
        src = d / "source.json"
        return json.loads(src.read_text(encoding="utf-8")).get("sha256", "")[:12] if src.exists() else ""

    rows = []
    for ast_path in sorted(CORPUS.glob("*/*/ast.json")):
        key = f"{ast_path.parent.parent.name}/{ast_path.parent.name}"
        ast = json.loads(ast_path.read_text(encoding="utf-8"))
        nodes = ast["nodes"]
        secs = {n["number"] for n in nodes if n["kind"] == "section" and not n["quoted"]}
        text = (ast_path.parent / "text.txt").read_text(encoding="utf-8")
        rows.append([key, len(secs), sum(n["kind"] == "chapter" for n in nodes), len(nodes), len(text),
                     source_sha(ast_path.parent), hashlib.sha256(text.encode()).hexdigest()[:12]])
    return write_table("corpus", ["Statute", "Sections", "Chapters", "Nodes", "Characters", "PDF SHA-256",
                                  "Text SHA-256"], rows, "Statute corpus parsed into abstract syntax trees.")


def eval_sets_table() -> Path:
    from eval.v2 import sampling
    m = sampling.load()
    from collections import Counter
    rows = []
    for split in ("test", "dev"):
        c = Counter(it["statute"] for it in m[split])
        for st, n in sorted(c.items()):
            rows.append([split, st, n])
    rows.append(["pilot (from dev)", "all", len(m["pilot"])])
    return write_table("eval_sets", ["Split", "Statute", "Provisions"], rows,
                       f"Frozen evaluation sets (seed {m['seed']}), stratified by statute, provision kind and length.")


def backtest_tables(res_dir: Path) -> list[Path]:
    b = json.loads((res_dir / "backtest.json").read_text(encoding="utf-8"))
    out = [write_table("backtest_in_sample", ["AY", "Simulated (cr)", "Reported (cr)", "Ratio", "Tax-band L1"],
                       [[r["ay"], _cr(r["simulated_revenue_crore"]), _cr(r["reported_tax_payable_crore"]),
                         _f(r["ratio"]), _f(r["tax_band_share_l1"])] for r in b["in_sample"]],
                       "In-sample reproduction of reported tax payable (individuals).")]
    f = b["forecast"]
    out.append(write_table("backtest_forecast", ["Base AY", "Target AY", "APE model", "APE naive", "Skill"],
                           [[t["base_ay"], t["target_ay"], _f(t["ape_model"]), _f(t["ape_naive"]), _f(t["skill"])]
                            for t in f["test"]],
                           f"Held-out forecasts; ageing method chosen on the selection pairs: {f['chosen_method']}."))
    out.append(write_table("backtest_reform_cost", ["Reform", "Simulated cost (cr)", "Announced (cr)", "Ratio"],
                           [[r["reform"], _cr(r["simulated_cost_crore"]), _cr(r["announced_cost_crore"]),
                             _f(r["ratio_to_announced"], 2)] for r in b["reform_cost"]],
                           "Revenue cost of reforms against Budget-speech figures."))
    return out


def sensitivity_table(res_dir: Path) -> Path:
    s = json.loads((res_dir / "sensitivity.json").read_text(encoding="utf-8"))
    names = s["problem"]["names"]
    rows = [[out] + [_f(s["sobol"][out][n]["ST"], 2) for n in names] for out in s["sobol"]]
    return write_table("sensitivity", ["Output"] + names, rows,
                       f"Sobol total-order indices ({s['evaluations']} model evaluations).")


def headline_tables(res_dir: Path, runs: list[dict]) -> list[Path]:
    rows = []
    for r in runs:
        p = r["population"]
        rows.append([r["set"], r["system"], "yes" if r["complete"] else "no", _f(p["flip_rate"], 2),
                     _f(p.get("flip_rate_original"), 2),
                     _cr(p["revenue_change_expert_crore"]), _cr(p.get("revenue_change_system_crore")),
                     _f(p.get("decile_rate_l1"), 4),
                     ", ".join(f"{x['target']}: {x['reason']}" for x in r.get("review", [])) or ""])
    out = [write_table("headline", ["Reform", "System", "Assembled", "Flip rate", "Flip rate (original tests)",
                                    "dRev expert (cr)", "dRev system (cr)", "Decile L1", "Review"], rows,
                       "Expert-coded vs extracted rules: assembly, pre-registered conclusion flips and outcome divergence.",
                       "llcrrrrrl")]
    arows = []
    for r in runs:
        a = r.get("attribution") or {}
        for pl in a.get("players", []):
            arows.append([r["set"], r["system"], "yes" if r["complete"] else "partly", pl["target"],
                          _cr(pl["revenue_error_crore"]), _f(pl["flips"], 2),
                          ", ".join(a.get("minimal_restoring_set") or []) or ""])
    out.append(write_table("attribution", ["Reform", "System", "Assembled", "Provision target", "Shapley revenue error (cr)",
                                           "Shapley flips", "Minimal restoring set"], arows,
                           "Attribution of divergence to extracted provisions (exact Shapley values)."))
    return out


def stats_tables(res_dir: Path) -> list[Path]:
    s = json.loads((res_dir / "stats.json").read_text(encoding="utf-8"))
    rows = [[r["set"], r["system"], _f(r["flip_rate_calibrated"], 2), _f(r["flip_rate_mean"], 2),
             _f(min(r["persistence"].values()) if r["persistence"] else None, 2), _f(r["noise_floor_mean"], 3)]
            for r in s["robustness"]]
    out = [write_table("robustness", ["Reform", "System", "Flip rate", "Mean over draws", "Min persistence",
                                      "Expert noise floor"], rows,
                       f"Conclusion flips under {s['draws']} population draws.")]
    t = s["systems"]["tests"]
    out.append(write_table("mcnemar", ["Comparison", "Conclusions", "McNemar p (Holm)", "Reforms",
                                       "Better / worse", "Sign test p (Holm)"],
                           [[k, v.get("pairs"), _f(v.get("p_holm"), 4), v.get("reforms"),
                             "{} / {}".format(*[v.get(x) for x in v if x.endswith("_better_reforms")][:2]),
                             _f(v.get("p_sign_reforms_holm"), 3)] for k, v in sorted(t.items())],
                           "Paired comparison of systems: exact McNemar over conclusions (ignores their "
                           "correlation within a reform) and an exact sign test over reforms; both Holm-corrected."))
    return out


def error_injection_table(res_dir: Path) -> Optional[Path]:
    path = res_dir / "error_injection.json"
    if not path.exists():
        return None
    rows = [[r["set"], r["target"], r["error"], _f(r["flip_rate"], 2), _cr(r["revenue_error_crore"]),
             _f(r["decile_rate_l1"], 4), _f(r["min_persistence"], 2)]
            for r in json.loads(path.read_text(encoding="utf-8"))]
    return write_table("error_injection", ["Reform", "Target", "Injected error", "Flip rate", "Revenue error (cr)",
                                           "Decile L1", "Min persistence"], rows,
                       "Typed extraction errors injected into the expert law: which change a policy conclusion.",
                       "lllrrrr")


def numbers_file(res_dir: Path, runs: list[dict]) -> Path:
    """paper/tables/numbers.tex: every number the prose cites, as \\res{name}."""
    from collections import Counter, defaultdict
    vals: dict[str, str] = {}
    by = defaultdict(list)
    for r in runs:
        by[r["system"]].append(r)
    for system, rs in by.items():
        comp = [r for r in rs if r["complete"]]
        vals[f"reforms@{system}"] = str(len(rs))
        vals[f"assembled@{system}"] = str(len(comp))
        vals[f"flips@{system}"] = str(sum(round(r["population"]["flip_rate"] * len(r["population"]["conclusions_expert"]))
                                          for r in comp))
        errs = [abs(r["population"]["revenue_change_system_crore"] - r["population"]["revenue_change_expert_crore"])
                for r in comp]
        vals[f"maxreverr@{system}"] = f"{max(errs, default=0):,.0f}"
        kinds = Counter(x["reason"].split(":")[0].split(" between")[0] for r in rs for x in r["review"])
        for k, n in kinds.items():
            vals[f"review@{system}@{k}"] = str(n)
    vals["reforms"] = str(len({r["set"] for r in runs}))
    vals["systems"] = str(len(by))
    vals["conclusions"] = str(len(next(iter(runs))["population"]["conclusions_expert"])) if runs else "0"
    b = json.loads((res_dir / "backtest.json").read_text(encoding="utf-8"))
    for r in b["in_sample"]:
        vals[f"insample@{r['ay']}"] = f"{r['ratio']:.3f}"
        vals[f"bandlone@{r['ay']}"] = f"{r['tax_band_share_l1']:.3f}"
    vals["forecastmethod"] = b["forecast"]["chosen_method"].replace("_", "-")
    for t in b["forecast"]["test"]:
        k = f"{t['base_ay']}to{t['target_ay']}"
        vals[f"apemodel@{k}"] = f"{100 * t['ape_model']:.1f}"
        vals[f"apenaive@{k}"] = f"{100 * t['ape_naive']:.1f}"
        vals[f"skill@{k}"] = f"{t['skill']:.2f}"
    for r in b["reform_cost"]:
        vals[f"cost@{r['reform']}"] = f"{r['simulated_cost_crore']:,.0f}"
        vals[f"announced@{r['reform']}"] = f"{r['announced_cost_crore']:,.0f}"
        vals[f"costratio@{r['reform']}"] = f"{r['ratio_to_announced']:.1f}"
    s = json.loads((res_dir / "stats.json").read_text(encoding="utf-8"))
    nf = [r["noise_floor_mean"] for r in s["robustness"]]
    vals["noisefloormax"] = f"{max(nf, default=0):.3f}"
    vals["draws"] = str(s["draws"])
    inj_path = res_dir / "error_injection.json"
    if inj_path.exists():
        inj = json.loads(inj_path.read_text(encoding="utf-8"))
        vals["injections"] = str(len(inj))
        vals["injectionsflipping"] = str(sum(r["flip_rate"] > 0 for r in inj))
        for e in sorted({r["error"] for r in inj}):
            rows = [r for r in inj if r["error"] == e]
            vals[f"injflipmax@{e}"] = f"{100 * max(r['flip_rate'] for r in rows):.0f}"
            vals[f"injrevmax@{e}"] = f"{max(abs(r['revenue_error_crore']) for r in rows):,.0f}"
    from eval.v2.faithfulness import OUT_DIR as FAITH_DIR
    for p in sorted(FAITH_DIR.glob("*.json")) if FAITH_DIR.exists() else []:
        fs = json.loads(p.read_text(encoding="utf-8"))["summary"]
        tag = f"{fs['system']}@{fs['split']}"
        vals[f"faithitems@{tag}"] = str(fs["items"])
        for k in ("comprehensiveness", "random_comprehensiveness", "sufficiency", "rationale_share"):
            vals[f"faith{k.replace('_', '')}@{tag}"] = f"{fs[k]['mean']:.2f}"
    from eval.v2.rag_eval import OUT_DIR as RAG_DIR
    if (RAG_DIR / "retrieval.json").exists():
        rag = json.loads((RAG_DIR / "retrieval.json").read_text(encoding="utf-8"))
        vals["ragchunks"] = f"{rag['chunks']:,}"
        vals["ragqueries"] = str(rag["queries"]["answerable"])
        vals["ragunanswerable"] = str(rag["queries"]["unanswerable"])
        for k, v in rag["results"].items():
            vals[f"ragrfive@{k}"] = f"{v['r@5']['mean']:.2f}"
            vals[f"ragrone@{k}"] = f"{v['r@1']['mean']:.2f}"
            vals[f"ragauroc@{k}"] = f"{v['abstention_auroc']:.2f}"
    lines = ["% Generated by `python -m cli reproduce`; do not edit.",
             r"\providecommand{\res}[1]{\csname res@#1\endcsname}"]
    lines += [rf"\expandafter\def\csname res@{k}\endcsname{{{v}}}" for k, v in sorted(vals.items())]
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / "numbers.tex"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def rag_table() -> Optional[Path]:
    from eval.v2.rag_eval import OUT_DIR as RAG_DIR
    path = RAG_DIR / "retrieval.json"
    if not path.exists():
        return None
    r = json.loads(path.read_text(encoding="utf-8"))
    names = {"bm25": "BM25", "minilm": "MiniLM (dense)", "bge-small": "bge-small (dense)",
             "hybrid": "Hybrid BM25 + bge (RRF)", "hybrid+rerank": "Hybrid BM25 + bge, re-ranked",
             "hybrid-minilm": "Hybrid BM25 + MiniLM (RRF)",
             "hybrid-minilm+rerank": "Hybrid BM25 + MiniLM, re-ranked (application)"}

    def ci(m):
        return f"{m['mean']:.2f} ({m['ci95'][0]:.2f}-{m['ci95'][1]:.2f})"
    rows = [[names.get(k, k), f"{v['r@1']['mean']:.2f}", ci(v["r@5"]), f"{v['mrr@10']['mean']:.2f}",
             f"{v['ndcg@10']['mean']:.2f}", _f(v["abstention_auroc"], 2)] for k, v in r["results"].items()]
    return write_table("rag", ["Retriever", "R@1", "R@5 (95% CI)", "MRR@10", "nDCG@10", "Abstention AUROC"], rows,
                       f"Retrieval of the provision a section heading belongs to ({r['queries']['answerable']} "
                       f"queries over {r['chunks']} statute chunks); abstention AUROC separates them from "
                       f"{r['queries']['unanswerable']} headings of an Act that is not indexed.")


def faithfulness_table() -> Optional[Path]:
    from eval.v2.faithfulness import OUT_DIR
    rows = []
    for p in sorted(OUT_DIR.glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))["summary"]
        rows.append([s["system"], s["split"], s["items"], _f(s["comprehensiveness"]["mean"]),
                     _f(s["random_comprehensiveness"]["mean"]), _f(s["sufficiency"]["mean"]),
                     _f(s["rationale_share"]["mean"])])
    if not rows:
        return None
    return write_table("faithfulness", ["System", "Split", "Items", "Comprehensiveness", "Random deletion",
                                        "Sufficiency", "Rationale share"], rows,
                       "Faithfulness of grounded spans (ERASER).")


def extraction_table() -> Optional[Path]:
    from eval.v2 import runs
    gold_dir = runs.ANNOTATION_DIR / "adjudicated"
    if not gold_dir.exists() or not any(gold_dir.glob("*.json")):
        return None
    rows = []
    for sysdir in sorted(runs.RUNS_DIR.iterdir()):
        if not (sysdir / "test.jsonl").exists():
            continue
        r = runs.score(sysdir.name, "test")
        if not r["coverage"]["gold_items"]:
            continue
        rows.append([sysdir.name, r["coverage"]["gold_items"], _f(r["rules"]["f1"]), _f(r["modality"]["kappa"]),
                     _f(r["spans"]["action"]["relaxed"]["f1"]), _f(r["effects"]["kinds"]["f1"]),
                     _f(r["effects"]["numeric_exact"]), _f(r["hallucination_rate"])])
    return write_table("extraction", ["System", "Items", "Rule F1", "Modality kappa", "Action span F1",
                                      "Effect F1", "Numeric exact", "Hallucination"], rows,
                       "Extraction quality against adjudicated human annotation (test set).") if rows else None


# ── driver ───────────────────────────────────────────────────────────────────

def reproduce(sensitivity: bool = False, draws: int = 64, progress: Callable[[str], None] = print) -> list[Path]:
    os.environ["PRISM_OFFLINE"] = "1"
    from simulation.experiment.harness import RESULTS_DIR, run_set, save
    from simulation.experiment.stats import load_runs, report

    written = [corpus_table(), eval_sets_table()]

    import cli
    from simulation.backtest.run import Settings
    progress("back-test")
    cli.cmd_backtest(type("A", (), {"optimal_share": Settings.optimal_share, "via_scale": Settings.via_scale})())
    written += backtest_tables(RESULTS_DIR)
    if sensitivity:
        progress("sensitivity (slow)")
        cli.cmd_sensitivity(type("A", (), {"n": 1024, "morris": 40, "seed": 11})())  # the CLI defaults
    if (RESULTS_DIR / "sensitivity.json").exists():
        written.append(sensitivity_table(RESULTS_DIR))

    progress("headline experiment from cached extractions")
    for old in load_runs():
        r = run_set(old["set"], old["system"], use_cache=True, k=old.get("samples", 0))
        save(r)
    runs = load_runs()
    written += headline_tables(RESULTS_DIR, runs)
    progress("error injection")
    import cli as _cli
    _cli.cmd_error_injection(type("A", (), {"draws": draws // 2 or 1})())
    if (t := error_injection_table(RESULTS_DIR)) is not None:
        written.append(t)
    progress("population robustness and system comparison")
    report(draws, progress=lambda _m: None)
    written += stats_tables(RESULTS_DIR)
    from eval.v2 import faithfulness
    for prev in sorted(faithfulness.OUT_DIR.glob("*.json")) if faithfulness.OUT_DIR.exists() else []:
        system, split = prev.stem.rsplit("_", 1)
        progress(f"faithfulness {system} {split} from cached extractions")
        extract = None
        if system == "rules":
            from pipeline.extraction.rule_based import extract_unit as rb
            extract = lambda u: rb(u)[0]  # noqa: E731
        faithfulness.evaluate(system, split, extract=extract, progress=lambda _m: None)
    written.append(numbers_file(RESULTS_DIR, load_runs()))
    import paper_figures
    written += paper_figures.all_figures(RESULTS_DIR, load_runs())
    for extra in (faithfulness_table(), extraction_table(), rag_table()):
        if extra is not None:
            written.append(extra)
    return written
