"""
Phase 3, Module D — persistent multi-document RAG corpus (ChromaDB).

Reuses the Phase 1 artifacts already on disk: `result.json` (clauses) and
`embeddings.npy` (the 384-d MiniLM vectors, row i ↔ clauses[i]). Ingestion is
therefore a pure re-index — no re-embedding — so adding an analysed document to
the corpus is fast and never recomputes anything.

Every clause is stored with metadata that powers filtered retrieval and the
citation cards: doc_id, doc_name, section path, page, entity types, has_causal.
"""
import threading
from typing import Optional

import numpy as np

from config import CHROMA_DIR, CORPUS_COLLECTION
from storage import store

_client = None
_collection = None
_lock = threading.Lock()


def _get_collection():
    """Lazily open the persistent Chroma collection (cosine space)."""
    global _client, _collection
    if _collection is None:
        with _lock:
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


def ingest_document(doc_id: str) -> dict:
    """(Re)index all clauses of an analysed document into the corpus.

    Idempotent: existing rows for this doc are deleted first so re-ingest after
    a re-analyse never leaves stale clauses behind.
    """
    result = store.get_result(doc_id)
    if result is None:
        raise ValueError(f"No analysis results for {doc_id}")
    embeddings = store.load_embeddings(doc_id)
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

    ids, embs, docs, metas = [], [], [], []
    for i, clause in enumerate(clauses):
        if clause.clause_type == "table" or not clause.text.strip():
            continue  # tables aren't prose — excluded from semantic QA
        entity_labels = sorted({e.label for e in clause.entities})
        has_causal = bool(clause.llm_extraction and clause.llm_extraction.is_causal) or bool(
            clause.causal_patterns
        )
        ids.append(f"{doc_id}::{clause.clause_id}")
        embs.append(embeddings[i].astype(float).tolist())
        docs.append(clause.text)
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


_lexical = {"count": -1, "index": None, "ids": [], "texts": {}, "metas": {}}


def _lexical_index():
    """BM25 over every clause in the corpus, rebuilt when the corpus changes."""
    from rag.hybrid import BM25
    collection = _get_collection()
    n = collection.count()
    with _lock:
        if _lexical["count"] != n:
            got = collection.get(include=["documents", "metadatas"]) if n else {"ids": [], "documents": [], "metadatas": []}
            ids, docs, metas = got.get("ids", []), got.get("documents", []), got.get("metadatas", [])
            _lexical.update(count=n, ids=list(ids), texts=dict(zip(ids, docs)), metas=dict(zip(ids, metas)),
                            index=BM25(list(docs)) if docs else None)
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
    texts = {**lex["texts"], **{h["id"]: h["text"] for h in dense}}
    by_id = {h["id"]: h for h in dense}
    out = []
    for cid, score in fuse_and_rerank(query, [h["id"] for h in dense], lexical, texts, n_results, depth):
        hit = dict(by_id.get(cid) or {"id": cid, "text": texts[cid], "similarity": None, **lex["metas"].get(cid, {})})
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
