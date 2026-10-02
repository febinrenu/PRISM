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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
