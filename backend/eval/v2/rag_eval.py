"""
Retrieval over the statute corpus: which retriever finds the right provision?

Index: every extraction unit (statute AST node) of the corpus statutes, the
unit's own text only. A section's heading is removed from the indexed text,
so a heading never matches itself.

Queries (structure-derived; no human-written questions yet):
    answerable   the official headings of sections of the Income-tax Act 2025,
                 the CGST Act and the Code on Wages, e.g. "Rebate of income-tax
                 in case of certain individuals". Relevant = every unit of the
                 section the heading belongs to. Generic headings that recur
                 ("Definitions", "Power to make rules") are left out.
    unanswerable the headings of the DPDP Act, which is not indexed. A
                 retriever's top score should separate these from answerable
                 queries (AUROC), the basis for abstaining.
Human-written questions (docs/rag_questions.jsonl, when the annotators have
written them) are evaluated the same way.

Retrievers: BM25; dense all-MiniLM-L6-v2 (the web app's encoder) and
bge-small-en-v1.5; hybrid reciprocal-rank fusion of BM25 and bge; and the
hybrid's top 30 re-ranked by a cross-encoder (ms-marco-MiniLM-L-6-v2).

Metrics: Recall@1/5/10, MRR@10 and nDCG@10 with bootstrap 95% intervals.
"""
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from eval.v2 import sampling
from rag.hybrid import BM25, rrf as _rrf   # shared with the application

OUT_DIR = sampling.EVAL_DIR / "rag"
SEED = 20261003
INDEXED = ["ITA2025/amended_fa2026", "CGST2017/consolidated", "COW2019/enacted", "FA2019N2/enacted",
           "FA2020/enacted", "FA2023/enacted", "FA2024N2/enacted", "FA2025/enacted", "FA2026/enacted"]
QUERY_STATUTES = ["ITA2025/amended_fa2026", "CGST2017/consolidated", "COW2019/enacted"]
HELD_OUT = "DPDP2023/enacted"
DENSE = {"minilm": ("sentence-transformers/all-MiniLM-L6-v2", ""),
         "bge-small": ("BAAI/bge-small-en-v1.5", "Represent this sentence for searching relevant passages: ")}
RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# ── corpus and queries ──────────────────────────────────────────────────────

def _sections(statute_key: str) -> dict[str, dict]:
    from pipeline.extraction.units import load_statute
    ast, _ = load_statute(*statute_key.split("/"))
    return {n["path"]: n for n in ast["nodes"] if n["kind"] == "section" and not n["quoted"]}


def _section_of(path: str, sections: dict) -> Optional[str]:
    parts = path.split("/")
    for i in range(len(parts), 1, -1):
        cand = "/".join(parts[:i])
        if cand in sections:
            return cand
    return None


def build_corpus() -> list[dict]:
    from pipeline.extraction.units import build_units
    chunks = []
    for key in INDEXED:
        secs = _sections(key)
        for u in build_units(*key.split("/")):
            sec = _section_of(u.path, secs)
            text = u.text
            heading = (secs[sec].get("heading") or "").strip() if sec else ""
            if heading and len(heading) > 3:
                text = re.sub(re.escape(heading) + r"\s*[.—–-]*", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) >= 20:
                chunks.append({"id": f"{key}#{u.unit_id}", "statute": key, "section": sec, "text": text})
    return chunks


def _headings(statute_key: str) -> list[tuple[str, str]]:
    return [(p, n["heading"].strip().rstrip(".")) for p, n in _sections(statute_key).items()
            if n.get("heading") and len(n["heading"].split()) >= 3]


def build_queries(per_statute: int = 150, seed: int = SEED) -> list[dict]:
    # A heading that occurs more than once anywhere (indexed or held out) is
    # generic, and an unanswerable query must not occur in any indexed statute.
    generic = Counter(h.lower() for key in INDEXED + [HELD_OUT] for _, h in _headings(key))
    rng = random.Random(seed)
    queries = []
    for key in QUERY_STATUTES:
        cands = sorted((p, h) for p, h in _headings(key) if generic[h.lower()] == 1)
        rng.shuffle(cands)
        for p, h in cands[:per_statute]:
            queries.append({"qid": f"h:{p}", "query": h, "statute": key, "section": p, "answerable": True})
    for p, h in sorted(_headings(HELD_OUT)):
        if generic[h.lower()] == 1:
            queries.append({"qid": f"u:{p}", "query": h, "statute": HELD_OUT, "section": None, "answerable": False})
    human = sampling.EVAL_DIR.parent.parent.parent / "docs" / "rag_questions.jsonl"
    if human.exists():
        for line in human.read_text(encoding="utf-8").splitlines():
            if line.strip():
                q = json.loads(line)
                queries.append({"qid": f"q:{q['id']}", "query": q["question"], "statute": q.get("statute"),
                                "section": q.get("section"), "answerable": q.get("section") is not None,
                                "human": True})
    return queries


# ── retrievers ──────────────────────────────────────────────────────────────

def _corpus_hash(chunks: list[dict]) -> str:
    return hashlib.sha256("\n".join(c["id"] + c["text"] for c in chunks).encode()).hexdigest()[:12]


def dense_embeddings(name: str, chunks: list[dict], progress=print) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model_id, _ = DENSE[name]
    path = OUT_DIR / f"emb_{name}_{_corpus_hash(chunks)}.npy"
    if path.exists():
        return np.load(path)
    progress(f"encoding {len(chunks)} chunks with {model_id}")
    model = SentenceTransformer(model_id, device="cpu")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Resumable: blocks of 1,000 chunks are saved as they finish, so a long
    # encoding can be completed over several runs.
    block, parts = 1000, []
    for start in range(0, len(chunks), block):
        part_path = path.with_name(f"{path.stem}.part{start // block:03d}.npy")
        if part_path.exists():
            parts.append(np.load(part_path))
            continue
        part = model.encode([c["text"] for c in chunks[start:start + block]], batch_size=32,
                            normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
        np.save(part_path, part)
        parts.append(part)
        progress(f"  {min(start + block, len(chunks))}/{len(chunks)}")
    emb = np.concatenate(parts)
    np.save(path, emb)
    for p in path.parent.glob(f"{path.stem}.part*.npy"):
        p.unlink()
    return emb


# ── metrics ─────────────────────────────────────────────────────────────────

def _metrics(ranked: list[int], relevant: set[int]) -> dict:
    hits = [i in relevant for i in ranked[:10]]
    first = next((r for r, h in enumerate(hits) if h), None)
    dcg = sum(1 / math.log2(r + 2) for r, h in enumerate(hits) if h)
    idcg = sum(1 / math.log2(r + 2) for r in range(min(len(relevant), 10)))
    return {"r@1": float(any(hits[:1])), "r@5": float(any(hits[:5])), "r@10": float(any(hits[:10])),
            "mrr@10": 0.0 if first is None else 1.0 / (first + 1), "ndcg@10": dcg / idcg if idcg else 0.0}


def _ci(values: list[float]) -> dict:
    v = np.array(values, dtype=float)
    if not len(v):
        return {"mean": None}
    boots = np.random.default_rng(SEED).choice(v, size=(2000, len(v))).mean(axis=1)
    return {"mean": round(float(v.mean()), 4),
            "ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]}


def _auroc(pos: list[float], neg: list[float]) -> Optional[float]:
    if not pos or not neg:
        return None
    s = np.array(pos + neg)
    ranks = s.argsort().argsort() + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


# ── driver ──────────────────────────────────────────────────────────────────

def evaluate(per_statute: int = 150, rerank_depth: int = 30, progress: Callable[[str], None] = print) -> dict:
    chunks = build_corpus()
    queries = build_queries(per_statute)
    progress(f"{len(chunks)} chunks, {sum(q['answerable'] for q in queries)} answerable and "
             f"{sum(not q['answerable'] for q in queries)} unanswerable queries")
    by_section = defaultdict(set)
    for i, c in enumerate(chunks):
        if c["section"]:
            by_section[c["section"]].add(i)
    bm25 = BM25([c["text"] for c in chunks])
    emb = {name: dense_embeddings(name, chunks, progress) for name in DENSE}
    from sentence_transformers import CrossEncoder, SentenceTransformer
    encoders = {name: SentenceTransformer(mid, device="cpu") for name, (mid, _) in DENSE.items()}
    reranker = CrossEncoder(RERANKER, device="cpu")

    systems = ["bm25", "minilm", "bge-small", "hybrid", "hybrid+rerank", "hybrid-minilm", "hybrid-minilm+rerank"]
    per = {s: [] for s in systems}
    top_scores = {s: {"answerable": [], "unanswerable": []} for s in systems}
    by_statute = {s: defaultdict(list) for s in systems}
    # Per-query results are appended as they are computed, so an interrupted
    # evaluation resumes where it stopped (the file is tied to the corpus).
    done_path = OUT_DIR / f"per_query_{_corpus_hash(chunks)}_d{rerank_depth}_v2.jsonl"
    done = {}
    if done_path.exists():
        for line in done_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["qid"]] = row
    fh = open(done_path, "a", encoding="utf-8")
    for qi, q in enumerate(queries):
        if q["qid"] in done:
            ranked, top = done[q["qid"]]["ranked"], done[q["qid"]]["top"]
        else:
            bm = bm25.scores(q["query"])
            dense = {}
            for name, (_, instr) in DENSE.items():
                qv = encoders[name].encode([instr + q["query"]], normalize_embeddings=True)[0]
                dense[name] = emb[name] @ qv
            rankings = {"bm25": np.argsort(-bm), "minilm": np.argsort(-dense["minilm"]),
                        "bge-small": np.argsort(-dense["bge-small"])}
            fused = _rrf(rankings["bm25"], rankings["bge-small"])
            hybrid = sorted(fused, key=fused.get, reverse=True)
            cand = hybrid[:rerank_depth]
            rr = reranker.predict([(q["query"], chunks[i]["text"][:1500]) for i in cand])
            reranked = [cand[i] for i in np.argsort(-rr)]
            # The web application's configuration: BM25 fused with its own
            # MiniLM embeddings, then the same cross-encoder.
            fused_m = _rrf(rankings["bm25"], rankings["minilm"])
            hybrid_m = sorted(fused_m, key=fused_m.get, reverse=True)
            cand_m = hybrid_m[:rerank_depth]
            rr_m = reranker.predict([(q["query"], chunks[i]["text"][:1500]) for i in cand_m])
            reranked_m = [cand_m[i] for i in np.argsort(-rr_m)]
            ranked = {"hybrid-minilm": [int(i) for i in hybrid_m[:10]],
                      "hybrid-minilm+rerank": [int(i) for i in reranked_m[:10]],"bm25": [int(i) for i in rankings["bm25"][:10]],
                      "minilm": [int(i) for i in rankings["minilm"][:10]],
                      "bge-small": [int(i) for i in rankings["bge-small"][:10]],
                      "hybrid": [int(i) for i in hybrid[:10]], "hybrid+rerank": [int(i) for i in reranked[:10]]}
            top = {"bm25": float(bm.max()), "minilm": float(dense["minilm"].max()),
                   "bge-small": float(dense["bge-small"].max()), "hybrid": float(fused[hybrid[0]]),
                   "hybrid+rerank": float(rr.max()), "hybrid-minilm": float(fused_m[hybrid_m[0]]),
                   "hybrid-minilm+rerank": float(rr_m.max())}
            fh.write(json.dumps({"qid": q["qid"], "ranked": ranked, "top": top}) + "\n")
            fh.flush()
        for s in systems:
            top_scores[s]["answerable" if q["answerable"] else "unanswerable"].append(top[s])
            if q["answerable"]:
                m = _metrics([int(i) for i in ranked[s]], by_section.get(q["section"], set()))
                per[s].append(m)
                by_statute[s][q["statute"]].append(m["r@5"])
        if (qi + 1) % 50 == 0:
            progress(f"{qi + 1}/{len(queries)} queries")
    fh.close()

    results = {}
    for s in systems:
        results[s] = {k: _ci([m[k] for m in per[s]]) for k in ("r@1", "r@5", "r@10", "mrr@10", "ndcg@10")}
        results[s]["r@5_by_statute"] = {k: round(float(np.mean(v)), 4) for k, v in by_statute[s].items()}
        results[s]["abstention_auroc"] = _auroc(top_scores[s]["answerable"], top_scores[s]["unanswerable"])
    out = {"chunks": len(chunks), "queries": {"answerable": sum(q["answerable"] for q in queries),
                                              "unanswerable": sum(not q["answerable"] for q in queries)},
           "indexed": INDEXED, "held_out": HELD_OUT, "models": {**{k: v[0] for k, v in DENSE.items()},
                                                                 "reranker": RERANKER},
           "results": results}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "retrieval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
