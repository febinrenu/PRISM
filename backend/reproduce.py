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


def structured_tables(headline: list[dict], runs: list[dict]) -> list[Path]:
    """The structured condition against the headline (see
    simulation.experiment.structured_run.summary)."""
    from simulation.experiment.structured_run import summary

    rows, detail = [], []
    for e in summary(headline, runs):
        frac = lambda c, k: f"{c[k]}/{c['reforms']}"  # noqa: E731
        if e["headline"]:
            h = e["headline"]
            rows.append([e["system"], "headline (text only, JSON mode)", frac(h, "assembled"), frac(h, "no_flip"), "", "", ""])
        for v in e["variants"]:
            f = v["first_pass"]
            rows.append([e["system"], f"{v['variant']}, first pass", frac(f, "assembled"), frac(f, "no_flip"), "", "", ""])
            if v["repaired"]:
                r = v["repaired"]
                rows.append([e["system"], f"{v['variant']}, after one repair", frac(r, "assembled"), frac(r, "no_flip"),
                             v["repairs_asked"], v["assembled_by_repair"], v["repaired_but_flipped"]])
            for x in v["reforms"]:
                detail.append([x["set"], e["system"], v["variant"], "yes" if x["first_complete"] else "no",
                               _f(x["first_flip_rate"], 2), "yes" if x["complete"] else "no", _f(x["flip_rate"], 2),
                               x["repairs"], ", ".join(f"{i['target']}: {i['reason']}" for i in x["review"]) or ""])
    out = [write_table("structured", ["System", "Condition", "Assembled", "No conclusion flipped", "Repairs asked",
                                      "Assembled by repair", "Repaired but flipped"], rows,
                       "Rebuilt rate tables, schema-constrained decoding and one repair round, against the headline "
                       "(same reforms, scoring and expert law). The condition was designed after the headline's "
                       "failures were inspected on these reforms.", "llrrrrr")]
    out.append(write_table("structured_detail", ["Reform", "System", "Condition", "Assembled (first)", "Flip rate (first)",
                                                 "Assembled (final)", "Flip rate (final)", "Repairs", "Review (final)"],
                           detail, "Structured condition per reform.", "lllcrcrrl"))
    return out


def number_grounding_table(rows: list[dict]) -> Path:
    def pct(k, r):
        return f"{100 * r[k] / r['fields']:.1f}" if r["fields"] else ""
    out = [[r["system"], r["condition"], r["fields"], pct("in_quote", r), pct("in_provision", r), pct("missing", r),
            f"{r['effects_unsupported']}/{r['effects']}"] for r in rows]
    return write_table("number_grounding", ["System", "Condition", "Numbers", "In its quote (%)",
                                            "Elsewhere in the provision (%)", "Nowhere (%)", "Unsupported effects"],
                       out, "Is each number a reading states in the law it cites? Numeric fields of the extracted "
                            "effects, looked up among the quantities of the effect's quote and of its provision.",
                       "llrrrrr")


def heldout_table(rows: list[dict]) -> Path:
    out = []
    for r in rows:
        g = r["numbers"]
        n = r["reforms"]
        out.append([r["system"], r["condition"], f"{r['first_pass']['no_flip']}/{n}", f"{r['final']['no_flip']}/{n}",
                    r["repairs"], f"{100 * g['in_quote'] / g['fields']:.1f}" if g else "",
                    f"{100 * g['missing'] / g['fields']:.1f}" if g else ""])
    return write_table("heldout", ["System", "Condition", "No flip (first pass)", "No flip (after repair)", "Repairs",
                                   "Numbers in their quote (%)", "Numbers nowhere (%)"], out,
                       "Held-out check, pre-registered before any run: five reforms whose provisions were not opened "
                       "while the structured condition was built.", "llrrrrr")


def rules_v2_table(summary: dict) -> Path:
    label = {"headline": "the ten headline reforms", "heldout": "the five held-out reforms"}
    rows = [[label[r["scope"]], "rebuilt tables" if r["condition"] == "tables" else "canonical text",
             f"{r['v1_no_flip']}/{r['reforms']}", f"{r['v2_no_flip']}/{r['reforms']}"] for r in summary["rows"]]
    return write_table("rules_v2", ["Reforms", "Condition", "Rule baseline (reported)", "Version 2 (post-hoc)"], rows,
                       "Post-hoc: the rule baseline with the two defects the held-out check exposed fixed. "
                       "Reforms on which every conclusion is kept. Version 2 was written after the held-out "
                       "results were seen, so its held-out row is not a held-out test.", "llrr")


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
    if (res_dir / "behaviour.json").exists():
        bh = json.loads((res_dir / "behaviour.json").read_text(encoding="utf-8"))
        pr = bh["paired"]
        vals["bhgapmedian"] = f"{pr['expert_gap_across_draws']['median']:.2f}"
        vals["bhgapfive"] = f"{pr['expert_gap_across_draws']['p5']:.2f}"
        vals["bhgapninetyfive"] = f"{pr['expert_gap_across_draws']['p95']:.2f}"
        vals["bhdiffmean"] = f"{pr['difference']['mean']:.3f}"
        vals["bhdifffive"] = f"{pr['difference']['p5']:.3f}"
        vals["bhdiffninetyfive"] = f"{pr['difference']['p95']:.3f}"
        vals["bhdraws"] = str(pr["draws"])
        vals["bhruns"] = str(bh["sobol"]["runs"])
        for n, v in bh["sobol"]["indices"]["tax_gap"].items():
            if n != "range":
                vals[f"bhst@{n}"] = f"{v['ST']:.2f}"
        vals["bhothermedian"] = f"{bh['sobol']['indices']['gap_other']['range']['median']:.2f}"
        conv = bh["convergence"]
        vals["bhsdsmall"] = f"{conv[min(conv, key=int)]['sd']:.3f}"
        vals["bhsdlarge"] = f"{conv[max(conv, key=int)]['sd']:.3f}"
        vals["bhcorrect"] = str(sum(1 for v in bh["systems"].values() if v.get("matches_expert")))
    from simulation.experiment import structured_run
    srun = structured_run.load_runs()
    if srun:
        inter = structured_run.interleaved_sets()
        vals["interleavedreforms"] = str(len(inter))
        for e in structured_run.summary(runs, srun):
            for v in e["variants"]:
                tag = f"st@{e['system']}@{v['variant']}"
                vals[f"{tag}@first@assembled"] = str(v["first_pass"]["assembled"])
                vals[f"{tag}@first@noflip"] = str(v["first_pass"]["no_flip"])
                vals[f"{tag}@targets"] = str(v["targets"])
                vals[f"{tag}@emptytargets"] = str(v["empty_targets"])
                if v["repaired"]:
                    vals[f"{tag}@final@assembled"] = str(v["repaired"]["assembled"])
                    vals[f"{tag}@final@noflip"] = str(v["repaired"]["no_flip"])
                    vals[f"{tag}@repairs"] = str(v["repairs_asked"])
                    vals[f"{tag}@repairfixed"] = str(v["assembled_by_repair"])
                    vals[f"{tag}@repairwrong"] = str(v["repaired_but_flipped"])
                # the reforms with interleaved tables, under this variant
                vals[f"{tag}@interleavedok"] = str(sum(1 for x in v["reforms"] if x["set"] in inter
                                                      and x["first_complete"] and x["first_flip_rate"] == 0))
            if e["headline"]:
                vals[f"st@{e['system']}@headline@noflip"] = str(e["headline"]["no_flip"])
        from simulation.experiment import heldout
        from simulation.experiment.provision_sets import HELD_OUT_SETS
        ho = heldout.load()
        if ho:
            vals["horeforms"] = str(len(HELD_OUT_SETS))
            for r in heldout.summary(ho):
                tag = f"ho@{r['system']}@{r['condition']}"
                vals[f"{tag}@first"] = str(r["first_pass"]["no_flip"])
                vals[f"{tag}@final"] = str(r["final"]["no_flip"])
                vals[f"{tag}@repairs"] = str(r["repairs"])
                if r["numbers"]:
                    vals[f"{tag}@quote"] = f"{100 * r['numbers']['in_quote'] / r['numbers']['fields']:.1f}"
        from simulation.experiment import rules_v2
        if rules_v2.load():
            for r in rules_v2.summary()["rows"]:
                tag = f"rv2@{r['scope']}@{r['condition']}"
                vals[f"{tag}@v1"] = str(r["v1_no_flip"])
                vals[f"{tag}@v2"] = str(r["v2_no_flip"])
        for g in structured_run.number_grounding():
            if g["fields"]:
                tag = f"num@{g['system']}@{g['condition']}"
                vals[f"{tag}@quote"] = f"{100 * g['in_quote'] / g['fields']:.1f}"
                vals[f"{tag}@provision"] = f"{100 * g['in_provision'] / g['fields']:.1f}"
                vals[f"{tag}@missing"] = f"{100 * g['missing'] / g['fields']:.1f}"
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


def behaviour_tables(res_dir: Path) -> list[Path]:
    path = res_dir / "behaviour.json"
    if not path.exists():
        return []
    b = json.loads(path.read_text(encoding="utf-8"))
    idx = b["sobol"]["indices"]
    names = [n for n in b["problem"]["names"]]
    rows = [[n.replace("_", " "), _f(idx["tax_gap"][n]["ST"], 2), _f(idx["gap_other"][n]["ST"], 2)]
            for n in sorted(names, key=lambda n: -idx["tax_gap"][n]["ST"])]
    out = [write_table("behaviour_sobol", ["Input", "ST (tax gap)", "ST (gap, non-salaried)"], rows,
                       f"Compliance model: Sobol total-order indices over {b['sobol']['runs']} runs.")]
    srows = [[s, v["status"], _f(v["penalty_rate"], 2) if v["penalty_rate"] is not None else "none",
              "yes" if v.get("matches_expert") else "no"] for s, v in b["systems"].items()]
    out.append(write_table("behaviour_systems", ["System", "Status", "Penalty rate read from s.439(10)",
                                                 "Same as expert (2.00)"], srows,
                           "The penalty parameter of the compliance model as read by each system."))
    return out


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
    from pipeline.extraction.backends import OfflineCacheMiss
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
    progress("structured condition from cached extractions")
    from simulation.experiment import structured_run
    for old in structured_run.load_runs():
        r = structured_run.run_set(old["set"], old["system"], use_schema=old.get("use_schema", True),
                                   repair=old.get("repair", True))
        structured_run.save(r)
    srun = structured_run.load_runs()
    if srun:
        written += structured_tables(runs, srun)
    progress("number grounding of every cached extraction")
    written.append(number_grounding_table(structured_run.number_grounding()))
    progress("held-out check from cached extractions")
    from simulation.experiment import heldout
    for old in heldout.load():
        heldout.save(heldout.run(old["set"], old["system"], old["condition"]))
    if heldout.load():
        written.append(heldout_table(heldout.summary(heldout.load())))
    progress("post-hoc rule baseline (rules-v2)")
    from simulation.experiment import rules_v2
    rules_v2.run_all(progress=lambda _m: None)
    written.append(rules_v2_table(rules_v2.summary()))
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
        try:
            faithfulness.evaluate(system, split, extract=extract, progress=lambda _m: None)
        except OfflineCacheMiss as e:
            # Some items' unit context changed in a later parser fix (the
            # context is taken from the current parse; runs written before
            # contexts were recorded cannot restore it), so their perturbed
            # prompts are not in the cache. The stored result is kept and
            # still produces the table; it is not re-derived here.
            progress(f"faithfulness {system} {split}: stored result kept, not re-derivable offline ({str(e)[:80]})")
    written.append(numbers_file(RESULTS_DIR, load_runs()))
    import paper_figures
    written += paper_figures.all_figures(RESULTS_DIR, load_runs())
    written += behaviour_tables(RESULTS_DIR)
    for extra in (faithfulness_table(), extraction_table(), rag_table()):
        if extra is not None:
            written.append(extra)
    return written
