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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
