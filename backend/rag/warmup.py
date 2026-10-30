"""
What the server does in the background after it starts, so the first question is fast.

  seed      a fresh install (a new Docker volume) has an empty corpus: the bundled demo
            document is indexed so Ask works at once
  statutes  the parsed statutes are indexed for exact section lookup and Act
            comparison (only those that are missing or changed)
  warm      the re-ranker, the BM25 index over every passage and the local language
            model are loaded now rather than on the first question

None of it may take the server down: each runs on its own thread and reports a failure
as a warning.
"""
import asyncio
import threading
from typing import Callable

from storage import store

DEMO = "demo_income_tax_2025"


def _run(name: str, fn: Callable[[], None], log) -> threading.Thread:
    def target():
        try:
            fn()
        except Exception as e:      # never take the server down for this
            log(f"[warn] {name} failed: {e}")

    t = threading.Thread(target=target, daemon=True, name=name)
    t.start()
    return t


def start(log=print) -> list[threading.Thread]:
    from rag import corpus_builder, statute_index

    n = corpus_builder.corpus_stats()["total_clauses"]
    log(f"[ok] RAG corpus ready ({n} passages indexed)")
    threads: list[threading.Thread] = []

    if n == 0 and store.get_result(DEMO) is not None:
        def seed():
            r = corpus_builder.ingest_document(DEMO)
            log(f"[ok] RAG corpus seeded with the demo ({r.get('indexed', '?')} clauses)")

        threads.append(_run("rag-seed", seed, log))

    threads.append(_run("statute-index", lambda: statute_index.ensure_indexed(log=log), log))

    def warm():
        from pipeline import llm_backend
        from rag import hybrid

        from simulation import templates

        hybrid.rerank("warm", ["up"])
        corpus_builder._lexical_index()
        templates._ensure_exemplars()        # the sandbox's template matcher: its first use embeds every exemplar
        if asyncio.run(llm_backend.warm()):
            log("[ok] language model loaded")

    threads.append(_run("rag-warm", warm, log))
    return threads
