"""
Hybrid retrieval: BM25 and dense similarity fused by reciprocal rank, then
re-ranked by a cross-encoder.

Chosen on the retrieval benchmark (eval/v2/rag_eval.py, paper Appendix A):
over statute chunks, BM25 + the corpus's MiniLM embeddings with cross-encoder
re-ranking retrieves the right section within five results for 0.72 of the
queries against 0.52 for MiniLM alone, and its top score is the better signal
for abstaining (AUROC 0.85 against 0.76).
"""
import math
import re
import threading
from collections import Counter, defaultdict
from typing import Optional

import numpy as np

RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("the of and to in a or for by any be is as on with under such shall which that this from at an "
            "it its other than not where".split())


def tokens(s: str) -> list[str]:
    return [w for w in _WORD.findall(s.lower()) if w not in _STOP]


class BM25:
    """Okapi BM25 over a fixed list of texts (k1 = 1.5, b = 0.75)."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        from scipy.sparse import csr_matrix
        docs = [tokens(t) for t in texts]
        self.vocab = {w: i for i, w in enumerate(sorted({w for d in docs for w in d}))}
        rows, cols, vals = [], [], []
        for i, d in enumerate(docs):
            for w, c in Counter(d).items():
                rows.append(i)
                cols.append(self.vocab[w])
                vals.append(c)
        n = max(len(docs), 1)
        shape = (len(docs), max(len(self.vocab), 1))
        tf = csr_matrix((vals, (rows, cols)), shape=shape, dtype=np.float32)
        lengths = np.array([len(d) for d in docs], dtype=np.float32)
        df = np.bincount(cols, minlength=shape[1])
        self.idf = np.log(1 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
        norm = k1 * (1 - b + b * lengths / max(float(lengths.mean()) if len(lengths) else 1.0, 1.0))
        tf = tf.tocoo()
        weights = tf.data * (k1 + 1) / (tf.data + norm[tf.row])
        self.w = csr_matrix((weights, (tf.row, tf.col)), shape=shape).tocsc()

    def scores(self, query: str) -> np.ndarray:
        ids = [self.vocab[w] for w in set(tokens(query)) if w in self.vocab]
        if not ids:
            return np.zeros(self.w.shape[0], dtype=np.float32)
        return np.asarray(self.w[:, ids] @ self.idf[ids]).ravel()


def rrf(*rankings, k: int = 60, depth: int = 200) -> dict:
    """Reciprocal-rank fusion of rankings (sequences of ids, best first)."""
    fused: dict = defaultdict(float)
    for r in rankings:
        for rank, i in enumerate(list(r)[:depth]):
            fused[i] += 1.0 / (k + rank + 1)
    return fused


_reranker = None
_lock = threading.Lock()


def rerank(query: str, texts: list[str]) -> np.ndarray:
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder
                _reranker = CrossEncoder(RERANKER, device="cpu")
    if not texts:
        return np.zeros(0)
    return np.asarray(_reranker.predict([(query, t[:1500]) for t in texts]), dtype=float)


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def fuse_and_rerank(query: str, dense: list[str], lexical: list[str], texts: dict[str, str],
                    top_k: int, depth: int = 30) -> list[tuple[str, float]]:
    """(id, re-ranker score) for the best `top_k` of the fused candidates."""
    fused = rrf(dense, lexical)
    cand = sorted(fused, key=fused.get, reverse=True)[:depth]
    if not cand:
        return []
    scores = rerank(query, [texts[i] for i in cand])
    order = np.argsort(-scores)[:top_k]
    return [(cand[i], float(scores[i])) for i in order]


def confidence(scores: list[float]) -> Optional[float]:
    """Retrieval confidence from the re-ranker's top score (logistic)."""
    return round(sigmoid(max(scores)), 3) if scores else None
