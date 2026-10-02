"""
Phase 3, Module D — RAG query engine.

retrieve (ChromaDB) → build grounded, source-numbered context → stream a cited
answer from the active LLM backend (Ollama local / Groq cloud). Every answer is
grounded in retrieved corpus clauses with [Source N] citations, so the chat is
the properly-cited successor to the Phase 1 stitched/extractive search.
"""
import re
from typing import AsyncIterator, Optional

from config import RAG_TOP_K
from pipeline import llm_backend
from rag import corpus_builder

_SYSTEM = (
    "You are PRISM Legal AI, an expert on Indian policy and statute. "
    "Answer using ONLY the provided legal clauses. Cite every claim with its "
    "source marker like [Source 2]. If the answer is not in the sources, say "
    '"Not found in the loaded corpus." Be precise and quote thresholds exactly.'
)

_SYSTEM_EXTENDED = (
    "You are PRISM Legal AI, an expert on Indian policy and statute. Prefer the "
    "provided legal clauses and cite them as [Source N]. You may add general "
    "legal knowledge, but clearly mark anything not grounded in the sources as "
    "'(general knowledge, not in corpus)'."
)


def build_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        loc = h.get("doc_name", "?")
        if h.get("section"):
            loc += f", {h['section']}"
        blocks.append(f"[Source {i}: {loc} (p.{h.get('page', '?')})]\n{h['text']}")
    return "\n\n".join(blocks)


def build_prompt(question: str, context: str) -> str:
    return (
        f"Legal Clauses:\n{context}\n\n"
        f"Question: {question}\n\nAnswer (cite sources as [Source N]):"
    )


_CITE_RE = re.compile(r"\[\s*Sources?\s+([\d,\s]+)\]", re.IGNORECASE)
_ABSTAIN_RE = re.compile(r"not\s+found\s+in\s+the\s+loaded\s+corpus", re.IGNORECASE)


def assess_grounding(answer: str, n_sources: int) -> dict:
    """Structural grounding check of a generated answer against the sources it
    was given. An answer counts as grounded only when it cites at least one
    real source and every [Source N] marker points at a source that exists.
    An explicit "Not found" is an abstention, not a grounded answer. This
    checks citation validity only; whether each cited source actually
    supports its claim needs a separate entailment check."""
    cited: set[int] = set()
    for group in _CITE_RE.findall(answer or ""):
        for part in re.split(r"[,\s]+", group.strip()):
            if part.isdigit():
                cited.add(int(part))
    valid = sorted(i for i in cited if 1 <= i <= n_sources)
    invalid = sorted(i for i in cited if not 1 <= i <= n_sources)
    abstained = bool(_ABSTAIN_RE.search(answer or ""))
    return {
        "grounded": bool(valid) and not invalid and not abstained,
        "abstained": abstained,
        "cited_sources": valid,
        "invalid_citations": invalid,
    }


def retrieve(question: str, doc_ids: Optional[list[str]] = None, top_k: int = RAG_TOP_K) -> list[dict]:
    return corpus_builder.semantic_search(question, n_results=top_k, doc_ids=doc_ids)


def retrieval_confidence(hits: list[dict]) -> float:
    if not hits:
        return 0.0
    top = [h["similarity"] for h in hits[: min(4, len(hits))]]
    return round(sum(top) / len(top), 3)


def citations(hits: list[dict]) -> list[dict]:
    """Source cards shown under a chat answer."""
    return [
        {
            "index": i,
            "doc_id": h.get("doc_id"),
            "doc_name": h.get("doc_name"),
            "clause_id": h.get("clause_id"),
            "section": h.get("section", ""),
            "page": h.get("page"),
            "similarity": h.get("similarity"),
            "text": h["text"],
            "text_preview": h["text"][:240] + ("…" if len(h["text"]) > 240 else ""),
            "entity_types": [t for t in h.get("entity_types", "").split(",") if t],
        }
        for i, h in enumerate(hits, 1)
    ]


async def answer_stream(
    question: str,
    doc_ids: Optional[list[str]] = None,
    strict: bool = True,
    top_k: int = RAG_TOP_K,
) -> AsyncIterator[dict]:
    """Yield SSE-shaped events: retrieval metadata first, then answer tokens,
    then a final done event. The router serialises these to `data:` frames."""
    hits = retrieve(question, doc_ids=doc_ids, top_k=top_k)
    cites = citations(hits)
    conf = retrieval_confidence(hits)

    yield {"stage": "retrieval", "citations": cites, "retrieval_confidence": conf,
           "n_sources": len(cites), "backend": llm_backend.active_backend()}

    if not hits:
        msg = "Not found in the loaded corpus. No documents matched your question — try ingesting a document first or rephrasing."
        yield {"stage": "token", "token": msg}
        yield {"stage": "done", "answer": msg, "grounded": False,
               "n_sources": 0, "retrieval_confidence": 0.0}
        return

    context = build_context(hits)
    prompt = build_prompt(question, context)
    system = _SYSTEM if strict else _SYSTEM_EXTENDED

    parts: list[str] = []
    try:
        async for tok in llm_backend.stream_generate(prompt, system=system, temperature=0.1, num_predict=1024):
            parts.append(tok)
            yield {"stage": "token", "token": tok}
    except Exception as e:  # backend down → honest surfaced error
        yield {"stage": "error", "message": f"LLM backend error: {e}"}
        return

    answer = "".join(parts).strip()
    yield {"stage": "done", "answer": answer, **assess_grounding(answer, len(cites)),
           "n_sources": len(cites), "retrieval_confidence": conf}


async def answer(question: str, doc_ids: Optional[list[str]] = None, strict: bool = True) -> dict:
    """Non-streaming convenience wrapper (used by the public /v1 API)."""
    hits = retrieve(question, doc_ids=doc_ids)
    if not hits:
        return {"answer": "Not found in the loaded corpus.", "grounded": False,
                "abstained": True, "cited_sources": [], "invalid_citations": [],
                "citations": [], "retrieval_confidence": 0.0}
    context = build_context(hits)
    system = _SYSTEM if strict else _SYSTEM_EXTENDED
    text = await llm_backend.generate(build_prompt(question, context), system=system,
                                      temperature=0.1, num_predict=1024)
    return {
        "answer": text.strip(),
        **assess_grounding(text, len(hits)),
        "citations": citations(hits),
        "retrieval_confidence": retrieval_confidence(hits),
    }
