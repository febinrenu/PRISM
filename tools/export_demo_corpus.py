#!/usr/bin/env python
"""
Writes backend/data/demo/passages.jsonl.gz: the passages the hosted demo searches.

    cd backend && python ../tools/export_demo_corpus.py        # needs the local Chroma index

The full deployment searches a ChromaDB index of every statute passage and every analysed document.
The hosted demo has no vector database, so it searches this file instead: the same passages and
metadata (text and where it came from, no embeddings), for the statutes and the documents that ship
with the demo. Run it again after the index changes.
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from rag import corpus_builder  # noqa: E402
from config import BASE_DIR  # noqa: E402

SHIPPED_DOCS = {"demo_income_tax_2025", "41f81963-1809-467d-aeb4-885564035ff7", "a6f7cc86-f612-4c3f-bdfc-4c20c92c503c"}
OUT = BASE_DIR / "data" / "demo" / "passages.jsonl.gz"


def main() -> None:
    col = corpus_builder._get_collection()
    got = col.get(include=["documents", "metadatas"])
    rows = []
    for cid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"]):
        did = str((meta or {}).get("doc_id", ""))
        if did.startswith("statute:") or did in SHIPPED_DOCS:
            rows.append({"id": cid, "text": doc, "meta": meta})
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(BASE_DIR.parent)}: {len(rows)} passages, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
