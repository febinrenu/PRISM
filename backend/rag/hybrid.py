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


def stem(w: str) -> str:
    """A light suffix-stripper (assessees, reporting, reported all meet): used only where there is no
    dense retrieval to bridge the wording, i.e. the hosted demo."""
    if len(w) > 5 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("sses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    for suf in ("ing", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)]
    return w


def stem_tokens(s: str) -> list[str]:
    return [stem(w) for w in tokens(s)]


class BM25:
    """Okapi BM25 over a fixed list of texts (k1 = 1.5, b = 0.75)."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75, tokenizer=None):
        from scipy.sparse import csr_matrix
        self.tok = tokenizer or tokens
        docs = [self.tok(t) for t in texts]
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

    def document_frequency(self, term: str) -> Optional[int]:
        """How many texts contain `term`; None when it is not in the vocabulary."""
        t = self.tok(term)
        i = self.vocab.get(t[0] if len(t) == 1 else term.lower())
        if i is None:
            return None
        return int(self.w.indptr[i + 1] - self.w.indptr[i])       # self.w is column-compressed

    def scores(self, query: str) -> np.ndarray:
        ids = [self.vocab[w] for w in set(self.tok(query)) if w in self.vocab]
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


_lexical_index = None       # the BM25 index of the corpus, set where there is no cross-encoder (idf for weighting)


def use_lexical_index(index) -> None:
    global _lexical_index
    _lexical_index = index


def lexical_scores(query: str, texts: list[str]) -> np.ndarray:
    """A stand-in for the cross-encoder where it cannot run (the hosted demo): how much of the query
    a text covers, counting each query word by how rare it is in the corpus (a word the corpus
    never uses weighs most, so a question about something else scores low everywhere), plus the
    share of its adjacent word pairs. Mapped onto the cross-encoder's logit scale so that
    `confidence` and the abstention gate keep their meaning."""
    q = stem_tokens(query)
    if not q or not texts:
        return np.full(len(texts), -4.5)
    qset = list(dict.fromkeys(q))
    idx = _lexical_index
    if idx is not None and len(idx.idf):
        top = float(idx.idf.max())
        weight = {w: (float(idx.idf[idx.vocab[w]]) if w in idx.vocab else top) for w in qset}
    else:
        weight = {w: 1.0 for w in qset}
    total = sum(weight.values()) or 1.0
    bigrams = {f"{a} {b}" for a, b in zip(q, q[1:])}
    out = []
    for t in texts:
        words = stem_tokens(t)
        have = set(words)
        joined = " ".join(words)
        cover = sum(weight[w] for w in qset if w in have) / total
        pairs = (sum(1 for g in bigrams if g in joined) / len(bigrams)) if bigrams else cover
        out.append(9.0 * (0.75 * cover + 0.25 * pairs) - 4.5)
    return np.asarray(out, dtype=float)


def rerank(query: str, texts: list[str]) -> np.ndarray:
    global _reranker
    from config import DEMO_MODE
    if not texts:
        return np.zeros(0)
    if DEMO_MODE or _reranker is False:
        return lexical_scores(query, texts)
    if _reranker is None:
        with _lock:
            if _reranker is None:
                try:
                    from sentence_transformers import CrossEncoder
                    _reranker = CrossEncoder(RERANKER, device="cpu")
                except ImportError:         # no ML stack installed: rank by word overlap instead
                    _reranker = False
        if _reranker is False:
            return lexical_scores(query, texts)
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
