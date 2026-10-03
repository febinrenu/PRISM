"""
PRISM command-line entry point. Run from backend/:

    python -m cli runinfo                  print the manifest a run would record
    python -m cli migrate-paths            store PDF paths relative to backend/
    python -m cli clean-extractions        drop LLM extractions whose clause text changed

Later phases add ingest / parse / extract / annotate / reproduce commands here,
so every number in the paper is produced by one documented command.
"""
import argparse
import json
import sys


def cmd_runinfo(args) -> int:
    from services.run_manifest import build_manifest

    print(json.dumps(build_manifest("runinfo"), indent=2, default=str))
    return 0


def cmd_migrate_paths(args) -> int:
    from storage import store

    changed = 0
    for meta in store.list_documents():
        if not meta.pdf_path:
            continue
        resolved = store.resolve_stored_path(meta.pdf_path)
        stored = store.to_stored_path(resolved)
        if stored != meta.pdf_path:
            print(f"{meta.doc_id}: {meta.pdf_path} -> {stored}")
            if not args.dry_run:
                meta.pdf_path = stored
                store.save_meta(meta)
            changed += 1
    print(f"{changed} document path(s) {'would change' if args.dry_run else 'migrated'}.")
    return 0


def cmd_clean_extractions(args) -> int:
    from pipeline.llm_extractor import merge_extractions
    from storage import store

    total = {"attached": 0, "cleared": 0}
    for meta in store.list_documents():
        if store.get_result(meta.doc_id) is None:
            continue
        entries = (store.load_llm_extractions(meta.doc_id) or {}).get("entries", {})
        counts: dict = {}

        def _mutate(analysis, entries=entries, counts=counts):
            counts.update(merge_extractions(analysis, entries))

        if args.dry_run:
            _mutate(store.get_result(meta.doc_id).model_copy(deep=True))
        else:
            store.update_result(meta.doc_id, _mutate)
        print(f"{meta.doc_id}: {counts['attached']} kept, {counts['cleared']} stale extraction(s) removed")
        for k in total:
            total[k] += counts.get(k, 0)
    print(f"Total: {total['attached']} kept, {total['cleared']} removed"
          f"{' (dry run)' if args.dry_run else ''}.")
    return 0


def cmd_ingest(args) -> int:
    from pipeline.statute import corpus

    sources = corpus.load_sources()
    if args.statute != "all":
        sources = [s for s in sources if s.id == args.statute
                   and (args.version is None or s.version == args.version)]
        if not sources:
            print(f"Unknown statute {args.statute}", file=sys.stderr)
            return 2
    failed = 0
    for src in sources:
        try:
            rec = corpus.fetch(src, force=args.force)
        except RuntimeError as e:
            print(f"FAIL {src.key}: {e}", file=sys.stderr)
            failed += 1
            continue
        state = "downloaded" if rec["downloaded"] else "verified"
        print(f"{state:10s} {src.key:28s} {rec['bytes'] / 1e6:6.1f} MB  {rec['sha256'][:12]}  {rec['url']}")
    return 1 if failed else 0


def cmd_parse(args) -> int:
    from pipeline.statute import corpus
    from pipeline.statute.parser import parse_statute
    from prism_version import PARSER_VERSION

    sources = [s for s in corpus.load_sources()
               if args.statute in ("all", s.id) and (args.version is None or s.version == args.version)]
    for src in sources:
        if not src.usable:
            print(f"skip {src.key}: marked unusable in sources.json")
            continue
        if not corpus.verify(src):
            print(f"skip {src.key}: PDF missing or hash mismatch (run `python -m cli ingest`)")
            continue
        ast = parse_statute(str(src.pdf_path), src.id, src.version, src.kind, src.title)
        out = ast.to_dict()
        out["parser_version"] = PARSER_VERSION
        out["source_sha256"] = corpus.sha256_file(src.pdf_path)
        (src.dir / "text.txt").write_text(ast.text, encoding="utf-8")
        (src.dir / "ast.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        st = ast.stats
        print(f"{src.key:28s} sections={st['sections']:4d} chapters={st['chapters']:3d} "
              f"nodes={len(ast.nodes):6d} chars={st['chars']:8d}")
    return 0


def cmd_gold_export(args) -> int:
    from simulation.rac import gold

    for p in gold.export_json():
        print(f"wrote {p}")
    return 0


def cmd_calc_vectors(args) -> int:
    """Write the CSV of taxpayer cases to check against the official
    Income Tax Department calculator, with PRISM's answer filled in."""
    import csv

    from simulation.rac import gold
    from simulation.rac.pit import liability

    G = gold.build_gold()
    L = 100_000
    # Salaried individuals below 60: points either side of every rebate limit
    # and surcharge threshold, plus ordinary mid-range incomes.
    salaries = {
        "new": [5 * L, 7.75 * L, 7.85 * L, 10 * L, 12.75 * L, 12.85 * L, 13.5 * L, 18 * L, 25 * L, 50.75 * L, 51 * L, 101 * L],
        "old": [5.5 * L, 5.6 * L, 8 * L, 10 * L, 15 * L, 50.5 * L, 51 * L, 101 * L],
    }
    rows = []
    for ay in ("2024-25", "2025-26", "2026-27"):
        for regime, sal_list in salaries.items():
            for sal in sal_list:
                ded = 150_000 if regime == "old" else 0
                lia = liability(G[ay], regime, sal, 0.0, ded, "below_60")
                rows.append({
                    "case": len(rows) + 1, "assessment_year": ay, "regime": regime, "age": "below 60",
                    "residential_status": "resident", "gross_salary": int(sal), "other_income": 0,
                    "deduction_80C": ded, "prism_total_income": int(lia.total_income[0]),
                    "prism_tax_payable": int(lia.total_tax[0]), "official_tax_payable": "", "notes": "",
                })
    out = args.out
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} cases to {out}")
    return 0


def _strip_notes(obj):
    if isinstance(obj, dict):
        return {k: _strip_notes(v) for k, v in obj.items() if k not in ("source", "note")}
    if isinstance(obj, list):
        return [_strip_notes(v) for v in obj]
    return obj


def cmd_gold_agree(args) -> int:
    """Compare a second coder's PIT parameters with the gold coding:
    parameter-level agreement and execution agreement (same tax on a grid of
    synthetic taxpayers)."""
    import numpy as np

    from simulation.rac import gold
    from simulation.rac.pit import liability
    from simulation.rac.types import PITParams, _flatten

    G = gold.build_gold()
    coder2 = json.loads(open(args.coder2, encoding="utf-8").read())
    rng = np.random.default_rng(0)
    incomes = np.concatenate([rng.uniform(0, 30e5, 1500), rng.uniform(30e5, 6e7, 500)])
    total_params = total_diff = 0
    exec_total = exec_same = 0
    report = {}
    for ay, gp in G.items():
        if ay not in coder2:
            print(f"{ay}: missing from coder 2")
            continue
        try:
            cp = PITParams.model_validate(_strip_notes(coder2[ay]))
        except Exception as e:  # noqa: BLE001 - report any malformed entry
            print(f"{ay}: coder 2 entry is incomplete or malformed: {str(e)[:200]}")
            continue
        n_params = len(_flatten(gp.model_dump(exclude={"citations", "scope"})))
        diffs = gp.diff(cp)
        total_params += n_params
        total_diff += len(diffs)
        same_exec = 0
        for regime in gp.regimes:
            if regime not in cp.regimes:
                continue
            a = liability(gp, regime, incomes).total_tax
            b = liability(cp, regime, incomes).total_tax
            same_exec += int(np.sum(np.abs(a - b) <= 10))
            exec_total += len(incomes)
        exec_same += same_exec
        report[ay] = diffs
        print(f"{ay}: {n_params - len(diffs)}/{n_params} parameters agree"
              + (f"; differ: {', '.join(diffs[:8])}{' …' if len(diffs) > 8 else ''}" if diffs else ""))
    if total_params:
        print(f"\nParameter agreement: {1 - total_diff / total_params:.4f} "
              f"({total_params - total_diff}/{total_params})")
    if exec_total:
        print(f"Execution agreement (tax within ₹10 on {exec_total} taxpayer-regime cases): "
              f"{exec_same / exec_total:.4f}")
    return 0


def cmd_gold_blind(args) -> int:
    """Blind second coding by a language model from statute excerpts only."""
    import time

    from services.run_manifest import build_manifest, write_manifest
    from simulation.rac.gold.blind_coder import code_year

    template = json.loads(open(args.template, encoding="utf-8").read())
    codings, log = {}, {}
    for ay, tpl in template.items():
        for attempt in range(4):
            try:
                res = code_year(ay, tpl, model=args.model)
                break
            except Exception as e:  # noqa: BLE001 - retry transient API errors
                print(f"{ay}: attempt {attempt + 1} failed: {str(e)[:160]}")
                time.sleep(20 * (attempt + 1))
        else:
            continue
        codings[ay] = res["coding"]
        log[ay] = {k: v for k, v in res.items() if k != "coding"}
        print(f"{ay}: coded by {res['model_version']} from {len(res['sources'])} excerpt(s)")
        time.sleep(args.pause)
    open(args.out, "w", encoding="utf-8").write(json.dumps(codings, indent=2, ensure_ascii=False))
    manifest = build_manifest("gold-blind", config={"model": args.model, "template": args.template},
                              extra={"per_year": log})
    print(f"wrote {args.out}; manifest {write_manifest(manifest)}")
    return 0


def cmd_eval_sample(args) -> int:
    from eval.v2 import sampling

    manifest = sampling.draw(args.seed)
    path = sampling.write(manifest, overwrite=args.overwrite)
    print(f"wrote {path}: {manifest['sizes']}")
    return 0


def cmd_eval_verify(args) -> int:
    from eval.v2 import sampling

    problems = sampling.verify_manifest(sampling.load())
    for p in problems[:50]:
        print(p)
    print("manifest OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_eval_run(args) -> int:
    from eval.v2 import runs

    path = runs.run(args.system, args.split, args.limit)
    print(f"records in {path}")
    return 0


def cmd_eval_agree(args) -> int:
    from eval.v2 import runs

    res = runs.agreement(args.split)
    if not res:
        print("No item has been finished by two annotators yet.")
        return 0
    print(json.dumps(res, indent=1))
    return 0


def cmd_eval_score(args) -> int:
    from eval.v2 import runs

    print(json.dumps(runs.score(args.system, args.split, args.gold), indent=1))
    return 0


def cmd_eval_faithfulness(args) -> int:
    from eval.v2 import faithfulness

    extract = None
    if args.system == "rules":
        from pipeline.extraction.rule_based import extract_unit as rb
        extract = lambda u: rb(u)[0]  # noqa: E731
    print(json.dumps(faithfulness.evaluate(args.system, args.split, args.limit, extract), indent=1))
    return 0


def cmd_cbdt_targets(args) -> int:
    from simulation.population.cbdt import parse_all, write_targets

    rows = parse_all()
    for p in write_targets(rows):
        print(f"wrote {p}")
    return 0


def cmd_backtest(args) -> int:
    """In-sample reproduction, held-out forecast and reform costing."""
    from services.run_manifest import build_manifest, write_manifest
    from simulation.backtest.run import Settings, forecast_protocol, in_sample, reform_cost
    from simulation.experiment.harness import RESULTS_DIR

    s = Settings(optimal_share=args.optimal_share, via_scale=args.via_scale)
    out = {
        "settings": s.__dict__,
        "in_sample": [in_sample(ay, s) for ay in ("2020-21", "2022-23", "2023-24")],
        "forecast": forecast_protocol(s),
        "reform_cost": [reform_cost(r, s) for r in ("FA2023", "FA2025")],
    }
    for r in out["in_sample"]:
        r["summary"].pop("deciles", None)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "backtest.json"
    path.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    write_manifest(build_manifest("backtest", config=s.__dict__))
    for r in out["in_sample"]:
        print(f"in-sample {r['ay']}: simulated/reported tax = {r['ratio']:.3f}; tax-band L1 = {r['tax_band_share_l1']:.3f}")
    f = out["forecast"]
    print(f"forecast: method chosen on selection pairs = {f['chosen_method']}")
    for t in f["test"]:
        print(f"  {t['base_ay']} -> {t['target_ay']}: APE model {t['ape_model']:.3f}, naive {t['ape_naive']:.3f}, skill {t['skill']:.3f}")
    for r in out["reform_cost"]:
        print(f"{r['reform']}: simulated cost Rs {r['simulated_cost_crore']:,.0f} cr vs announced Rs {r['announced_cost_crore']:,} cr")
    print(f"wrote {path}")
    return 0


def cmd_sensitivity(args) -> int:
    from services.run_manifest import build_manifest, write_manifest
    from simulation.engine.sensitivity import OUTPUTS, run
    from simulation.experiment.harness import RESULTS_DIR

    res = run(n_sobol=args.n, n_morris=args.morris, seed=args.seed)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "sensitivity.json"
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_manifest(build_manifest("sensitivity", config={"n_sobol": args.n, "n_morris": args.morris}, seeds=[args.seed]))
    for out in OUTPUTS:
        rng = res["output_ranges"][out]
        st = sorted(res["sobol"][out].items(), key=lambda kv: -kv[1]["ST"])
        print(f"{out}: median {rng['median']:.4g} (5-95%: {rng['p5']:.4g} - {rng['p95']:.4g})")
        for name, v in st:
            print(f"    {name:14s} S1={v['S1']:+.3f}±{v['S1_conf']:.3f}  ST={v['ST']:.3f}±{v['ST_conf']:.3f}")
    print(f"wrote {path}")
    return 0


def cmd_experiment(args) -> int:
    """Expert-vs-extracted across provision sets and systems."""
    from services.run_manifest import build_manifest, write_manifest
    from simulation.experiment.harness import RESULTS_DIR, run_set, save
    from simulation.experiment.provision_sets import PROVISION_SETS

    systems = args.systems.split(",")
    sets = args.sets.split(",") if args.sets else list(PROVISION_SETS)
    rows = []
    for system in systems:
        for set_name in sets:
            try:
                r = run_set(set_name, system, k=0 if system == "rules" else args.k)
            except Exception as e:  # noqa: BLE001 - keep going across systems
                print(f"{set_name} / {system}: FAILED {str(e)[:200]}", flush=True)
                continue
            save(r)
            p = r["population"]
            rows.append((set_name, system, r["complete"], p["flip_rate"], p.get("revenue_change_system_crore"),
                         p["revenue_change_expert_crore"], p.get("decile_rate_l1")))
            print(f"{set_name:20s} {system:16s} complete={r['complete']!s:5s} flip={p['flip_rate']:.2f} "
                  f"dRev sys={p.get('revenue_change_system_crore')} expert={p['revenue_change_expert_crore']:.0f}", flush=True)
    # The summary covers every saved run, not only this invocation's.
    summary = RESULTS_DIR / "headline_summary.json"
    allrows = []
    for path in sorted(RESULTS_DIR.glob("*__*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        p = r["population"]
        allrows.append({"set": r["set"], "system": r["system"], "complete": r["complete"], "flip_rate": p["flip_rate"],
                        "d_rev_system_crore": p.get("revenue_change_system_crore"),
                        "d_rev_expert_crore": p["revenue_change_expert_crore"], "decile_rate_l1": p.get("decile_rate_l1")})
    summary.write_text(json.dumps(allrows, indent=1), encoding="utf-8")
    write_manifest(build_manifest("experiment", config={"systems": systems, "sets": sets, "k": args.k}))
    print(f"wrote {summary}")
    return 0


def cmd_experiment_stats(args) -> int:
    from simulation.experiment.stats import report

    out = report(args.draws)
    print(json.dumps(out["systems"], indent=1))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli", description="PRISM command line")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("runinfo", help="print the run manifest for this environment").set_defaults(func=cmd_runinfo)

    p = sub.add_parser("migrate-paths", help="store PDF paths relative to backend/")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_migrate_paths)

    p = sub.add_parser("clean-extractions",
                       help="remove LLM extractions that no longer match their clause text")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_clean_extractions)

    p = sub.add_parser("ingest", help="download statute PDFs listed in data/corpus/sources.json")
    p.add_argument("--statute", default="all", help="statute id, or 'all'")
    p.add_argument("--version", default=None)
    p.add_argument("--force", action="store_true", help="re-download even if the hash matches")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("parse", help="parse downloaded statutes into ast.json + text.txt")
    p.add_argument("--statute", default="all")
    p.add_argument("--version", default=None)
    p.set_defaults(func=cmd_parse)

    sub.add_parser("gold-export", help="write expert PIT parameters to simulation/rac/gold/*.json") \
        .set_defaults(func=cmd_gold_export)

    p = sub.add_parser("calc-vectors", help="cases to check against the official tax calculator")
    p.add_argument("--out", default="../docs/official_calculator_check.csv")
    p.set_defaults(func=cmd_calc_vectors)

    p = sub.add_parser("gold-agree", help="agreement between gold and a second coder's PIT parameters")
    p.add_argument("--coder2", required=True)
    p.set_defaults(func=cmd_gold_agree)

    p = sub.add_parser("gold-blind", help="blind LLM second coding of PIT parameters from statute excerpts")
    p.add_argument("--model", default=None)
    p.add_argument("--template", default="../docs/expert_coding_template.json")
    p.add_argument("--out", default="../docs/coder2_blind_gemini.json")
    p.add_argument("--pause", type=float, default=8.0)
    p.set_defaults(func=cmd_gold_blind)

    p = sub.add_parser("eval-sample", help="draw and freeze the v2 evaluation sets")
    p.add_argument("--seed", type=int, default=20261003)
    p.add_argument("--overwrite", action="store_true", help="only before annotation has started")
    p.set_defaults(func=cmd_eval_sample)

    sub.add_parser("eval-verify", help="check the frozen evaluation sets against the corpus") \
        .set_defaults(func=cmd_eval_verify)

    p = sub.add_parser("eval-run", help="run an extraction system over an evaluation set")
    p.add_argument("--system", required=True, help="rules | phi3.5 | gemma2-2b | gpt-oss-120b | gpt-oss-20b | qwen3.8-27b | gemini-3.8-flash")
    p.add_argument("--split", default="dev", choices=["pilot", "dev", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_eval_run)

    p = sub.add_parser("eval-agree", help="agreement between annotators on finished items")
    p.add_argument("--split", default="pilot", choices=["pilot", "dev", "test"])
    p.set_defaults(func=cmd_eval_agree)

    p = sub.add_parser("eval-score", help="score a system run against human gold")
    p.add_argument("--system", required=True)
    p.add_argument("--split", default="dev", choices=["pilot", "dev", "test"])
    p.add_argument("--gold", default="adjudicated", help="'adjudicated' or an annotator id")
    p.set_defaults(func=cmd_eval_score)

    p = sub.add_parser("eval-faithfulness", help="ERASER comprehensiveness / sufficiency of grounded spans")
    p.add_argument("--system", required=True)
    p.add_argument("--split", default="dev", choices=["pilot", "dev", "test"])
    p.add_argument("--limit", type=int, default=None, help="stop after this many scored items")
    p.set_defaults(func=cmd_eval_faithfulness)

    sub.add_parser("cbdt-targets", help="parse Income Tax Return Statistics PDFs into target CSVs") \
        .set_defaults(func=cmd_cbdt_targets)

    p = sub.add_parser("backtest", help="validate the microsimulation against published outcomes")
    p.add_argument("--optimal-share", type=float, default=1.0)
    p.add_argument("--via-scale", type=float, default=1.0)
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("sensitivity", help="Morris + Sobol global sensitivity of simulated outcomes")
    p.add_argument("--n", type=int, default=1024, help="Saltelli base sample size")
    p.add_argument("--morris", type=int, default=40)
    p.add_argument("--seed", type=int, default=11)
    p.set_defaults(func=cmd_sensitivity)

    p = sub.add_parser("experiment", help="expert-vs-extracted policy experiment across systems")
    p.add_argument("--systems", default="rules,gpt-oss-120b,gpt-oss-20b,qwen3.8-27b,gemini-3.8-flash")
    p.add_argument("--sets", default="", help="comma-separated provision sets (default: all)")
    p.add_argument("--k", type=int, default=4, help="self-consistency samples per provision")
    p.set_defaults(func=cmd_experiment)

    p = sub.add_parser("experiment-stats", help="population robustness of flips and McNemar tests between systems")
    p.add_argument("--draws", type=int, default=64)
    p.set_defaults(func=cmd_experiment_stats)

    args = parser.parse_args(argv)
    if getattr(args, "model", "unset") is None:
        from config import GEMINI_MODEL
        args.model = GEMINI_MODEL
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
