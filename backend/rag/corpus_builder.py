"""
Phase 3, Module D — persistent multi-document RAG corpus (ChromaDB).

Reuses the Phase 1 artifacts already on disk: `result.json` (clauses) and
`embeddings.npy` (the 384-d MiniLM vectors, row i ↔ clauses[i]). Ingestion is
therefore a pure re-index — no re-embedding — so adding an analysed document to
the corpus is fast and never recomputes anything.

Every clause is stored with metadata that powers filtered retrieval and the
citation cards: doc_id, doc_name, section path, page, entity types, has_causal.
"""
import gzip
import json
import threading
from typing import Optional

import numpy as np

from config import BASE_DIR, CHROMA_DIR, CORPUS_COLLECTION, DEMO_MODE
from storage import store

# A clause shorter than this that is followed by another on the same or next page is a
# heading ("156. Rebate of income-tax ..."); it is indexed with the clause it heads.
HEADING_ONLY_CHARS = 90

_client = None
_collection = None
_lock = threading.Lock()


class _LiteCollection:
    """The corpus without a vector database, for the hosted demo.

    It holds the same passages and metadata as the Chroma collection (loaded from
    data/demo/passages.jsonl.gz, written by tools/export_demo_corpus.py) in memory and answers the
    calls the app makes of a collection. There are no embeddings, so search is lexical (BM25)."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, dict]] = {}
        path = BASE_DIR / "data" / "demo" / "passages.jsonl.gz"
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    self.rows[r["id"]] = (r["text"], r["meta"])

    @staticmethod
    def _wanted(where: Optional[dict]) -> Optional[set]:
        if not where:
            return None
        cond = where.get("doc_id")
        if isinstance(cond, dict):
            return set(cond.get("$in", []))
        return {cond} if cond is not None else None

    def count(self) -> int:
        return len(self.rows)

    def get(self, include=None, where=None, ids=None) -> dict:
        wanted = self._wanted(where)
        picked = [(i, t, m) for i, (t, m) in self.rows.items()
                  if (wanted is None or m.get("doc_id") in wanted) and (ids is None or i in ids)]
        return {"ids": [p[0] for p in picked], "documents": [p[1] for p in picked], "metadatas": [p[2] for p in picked]}

    def delete(self, where=None, ids=None) -> None:
        wanted = self._wanted(where)
        for i in [i for i, (_, m) in self.rows.items()
                  if (wanted is not None and m.get("doc_id") in wanted) or (ids is not None and i in ids)]:
            del self.rows[i]

    def add(self, ids, embeddings=None, documents=None, metadatas=None) -> None:
        for i, d, m in zip(ids, documents or [], metadatas or []):
            self.rows[i] = (d, m)


def _get_collection():
    """Lazily open the persistent Chroma collection (cosine space); the hosted demo uses a
    lexical in-memory stand-in."""
    global _client, _collection
    if _collection is None:
        with _lock:
            if _collection is None and DEMO_MODE:
                _collection = _LiteCollection()
            if _collection is None:
                import chromadb

                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
                _collection = _client.get_or_create_collection(
                    name=CORPUS_COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
    return _collection


def doc_name_for(doc_id: str) -> str:
    meta = store.get_meta(doc_id)
    if meta and meta.filename:
        name = meta.filename
        return name[:-4] if name.lower().endswith(".pdf") else name
    return doc_id


def index_rows(clauses) -> list[tuple[int, str, bool]]:
    """What to index for a document's clauses: (clause index, text, whether it was merged).

    Tables and empty clauses are not prose and are left out. A heading-only clause
    ("156. Rebate of income-tax ...") matches a question by its title and says nothing, so it is
    joined to the clause that follows it (on the same or the next page); consecutive headings
    join together. A heading with no clause after it, or followed by a table, stays a passage of
    its own rather than vanishing or being glued onto unrelated text."""
    rows: list[tuple[int, str, bool]] = []
    pending: Optional[tuple[int, str]] = None
    n = len(clauses)
    for i, c in enumerate(clauses):
        text = c.text.strip()
        prose = c.clause_type != "table" and bool(text)
        if not prose:
            if pending is not None:
                rows.append((pending[0], pending[1], False))
                pending = None
            continue
        is_heading = len(text) < HEADING_ONLY_CHARS and i + 1 < n and clauses[i + 1].page - c.page <= 1
        if pending is not None:
            if is_heading:
                pending = (pending[0], pending[1] + "\n" + text)
                continue
            rows.append((i, pending[1] + "\n" + c.text, True))
            pending = None
            continue
        if is_heading:
            pending = (i, text)
            continue
        rows.append((i, c.text, False))
    if pending is not None:
        rows.append((pending[0], pending[1], False))
    return rows


def ingest_document(doc_id: str) -> dict:
    """(Re)index all clauses of an analysed document into the corpus.

    Idempotent: existing rows for this doc are deleted first so re-ingest after
    a re-analyse never leaves stale clauses behind.
    """
    result = store.get_result(doc_id)
    if result is None:
        raise ValueError(f"No analysis results for {doc_id}")
    embeddings = store.load_embeddings(doc_id)
    if DEMO_MODE and embeddings is None:
        embeddings = np.zeros((len(result.clauses), 1), dtype=np.float32)   # lexical index: vectors unused
    if embeddings is None or len(embeddings) == 0:
        raise ValueError(f"No embeddings stored for {doc_id}")

    clauses = result.clauses
    if len(embeddings) != len(clauses):
        # Row alignment is the store's invariant; refuse rather than mis-cite.
        raise ValueError(
            f"Embedding/clause mismatch for {doc_id}: "
            f"{len(embeddings)} vs {len(clauses)}"
        )

    name = doc_name_for(doc_id)
    collection = _get_collection()

    # Drop any prior rows for this doc (idempotent re-index).
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        pass

    rows = index_rows(clauses)
    # A clause merged with its heading has new text, so it gets a new embedding (the stored one
    # is of the body alone); the rest keep theirs.
    merged = [k for k, (_, _, m) in enumerate(rows) if m and not DEMO_MODE]
    fresh: dict[int, list[float]] = {}
    if merged:
        from pipeline.embedder import embed_texts

        vectors = embed_texts([rows[k][1] for k in merged])
        fresh = {k: v.astype(float).tolist() for k, v in zip(merged, vectors)}

    ids, embs, docs, metas = [], [], [], []
    for k, (i, text, _) in enumerate(rows):
        clause = clauses[i]
        entity_labels = sorted({e.label for e in clause.entities})
        has_causal = bool(clause.llm_extraction and clause.llm_extraction.is_causal) or bool(
            clause.causal_patterns
        )
        ids.append(f"{doc_id}::{clause.clause_id}")
        embs.append(fresh.get(k) or embeddings[i].astype(float).tolist())
        docs.append(text)
        metas.append({
            "doc_id": doc_id,
            "doc_name": name,
            "clause_id": clause.clause_id,
            "section": " > ".join(clause.section_hierarchy) if clause.section_hierarchy else "",
            "page": int(clause.page),
            "entity_types": ",".join(entity_labels),
            "has_causal": has_causal,
        })

    if ids:
        collection.add(ids=ids, embeddings=embs, documents=docs, metadatas=metas)

    return {"doc_id": doc_id, "doc_name": name, "indexed": len(ids)}


def semantic_search(query: str, n_results: int = 8, doc_ids: Optional[list[str]] = None) -> list[dict]:
    """Embed the query with the same MiniLM encoder and retrieve top-k clauses."""
    if DEMO_MODE:
        return []                       # no encoder in the hosted demo: hybrid_search falls back to BM25 alone
    from pipeline.embedder import embed_texts

    collection = _get_collection()
    if collection.count() == 0:
        return []

    q = embed_texts([query])[0].astype(float).tolist()
    where = None
    if doc_ids:
        where = {"doc_id": {"$in": list(doc_ids)}} if len(doc_ids) > 1 else {"doc_id": doc_ids[0]}

    n = min(n_results, collection.count())
    res = collection.query(
        query_embeddings=[q],
        n_results=n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    ids = res.get("ids", [[]])[0]
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        # cosine distance → similarity
        hits.append({
            "id": cid,
            "text": doc,
            "similarity": round(1.0 - float(dist), 4),
            **meta,
        })
    return hits


_lexical = {"count": -1, "index": None, "ids": [], "texts": {}, "metas": {}, "search": {}}


def _lexical_index():
    """BM25 over every clause in the corpus, rebuilt when the corpus changes."""
    from rag import hybrid
    from rag.hybrid import BM25
    collection = _get_collection()
    n = collection.count()
    with _lock:
        if _lexical["count"] != n:
            got = collection.get(include=["documents", "metadatas"]) if n else {"ids": [], "documents": [], "metadatas": []}
            ids, docs, metas = got.get("ids", []), got.get("documents", []), got.get("metadatas", [])
            if DEMO_MODE:
                # no dense retrieval to bridge the wording: index each passage with its heading and place,
                # and stem the words (what the embedding of the passage carries in the full system)
                search = [f"{(m or {}).get('heading', '')} {(m or {}).get('heading', '')} {(m or {}).get('doc_name', '')} "
                          f"section {(m or {}).get('section', '')} {d}" for d, m in zip(docs, metas)]
                index = BM25(search, tokenizer=hybrid.stem_tokens) if docs else None
                hybrid.use_lexical_index(index)
            else:
                search, index = list(docs), (BM25(list(docs)) if docs else None)
            _lexical.update(count=n, ids=list(ids), texts=dict(zip(ids, docs)), metas=dict(zip(ids, metas)),
                            index=index, search=dict(zip(ids, search)))
    return _lexical


def hybrid_search(query: str, n_results: int = 8, doc_ids: Optional[list[str]] = None,
                  depth: int = 30) -> list[dict]:
    """BM25 and MiniLM candidates fused by reciprocal rank and re-ranked by a
    cross-encoder (rag/hybrid.py; chosen on the retrieval benchmark)."""
    from rag.hybrid import fuse_and_rerank
    dense = semantic_search(query, n_results=50, doc_ids=doc_ids)
    lex = _lexical_index()
    lexical: list[str] = []
    if lex["index"] is not None:
        scores = lex["index"].scores(query)
        order = np.argsort(-scores)
        wanted = set(doc_ids) if doc_ids else None
        for i in order[:400]:
            if scores[i] <= 0:
                break
            cid = lex["ids"][i]
            if wanted is None or lex["metas"][cid].get("doc_id") in wanted:
                lexical.append(cid)
            if len(lexical) >= 50:
                break
    texts = {**(lex["search"] if DEMO_MODE else lex["texts"]), **{h["id"]: h["text"] for h in dense}}
    by_id = {h["id"]: h for h in dense}
    out = []
    for cid, score in fuse_and_rerank(query, [h["id"] for h in dense], lexical, texts, n_results, depth):
        hit = dict(by_id.get(cid) or {"id": cid, "text": lex["texts"].get(cid) or texts[cid], "similarity": None,
                                       **lex["metas"].get(cid, {})})
        hit["rerank_score"] = round(score, 4)
        out.append(hit)
    return out


def corpus_stats() -> dict:
    """Per-document + global counts for the corpus explorer / chat header."""
    collection = _get_collection()
    total = collection.count()
    docs: dict[str, dict] = {}
    if total:
        got = collection.get(include=["metadatas"])
        for meta in got.get("metadatas", []) or []:
            did = meta.get("doc_id", "?")
            entry = docs.setdefault(did, {
                "doc_id": did, "doc_name": meta.get("doc_name", did),
                "clauses": 0, "causal": 0,
            })
            entry["clauses"] += 1
            if meta.get("has_causal"):
                entry["causal"] += 1
    return {
        "total_clauses": total,
        "documents": sorted(docs.values(), key=lambda d: d["doc_name"]),
        "collection": CORPUS_COLLECTION,
    }


def remove_document(doc_id: str) -> None:
    collection = _get_collection()
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        pass
