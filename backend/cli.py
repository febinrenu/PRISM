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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
