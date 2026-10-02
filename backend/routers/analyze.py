"""
Analysis router: SSE streaming analysis pipeline.
GET /api/analyze/{doc_id} → Server-Sent Events stream

The full 5-stage pipeline (parse → segment → NER/causal → embed/UMAP → graph)
is CPU-bound, so it runs synchronously on a worker thread and emits events
into an asyncio.Queue via loop.call_soon_threadsafe. The async generator
drains the queue and yields a heartbeat comment whenever no event arrives
within 2 seconds — the event loop stays free during every stage.
"""
import asyncio
import json
import logging
import os
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services import job_manager
from storage import store
from models.schemas import Clause, AnalysisResult
from pipeline.pdf_parser import extract_pages
from pipeline.clause_segmenter import segment_clauses
from pipeline.legal_ner import extract_entities_batch
from pipeline.causal_detector import detect_causal_patterns
from pipeline.embedder import embed_texts, project_umap
from pipeline.graph_builder import build_provenance_graph

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL_S = 2.0


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _heartbeat() -> str:
    """SSE comment line — keeps connection alive without frontend parsing."""
    return ": heartbeat\n\n"


def _pipeline_worker(
    doc_id: str,
    pdf_path: str,
    filename: str,
    emit: Callable[[dict], None],
) -> None:
    """Synchronous 5-stage pipeline. Runs on a worker thread; every event is
    delivered through `emit`. Always ends with a `complete` or `error` event."""
    store.set_status(doc_id, "processing")

    try:
        # ── Stage 1: PDF Parsing ──────────────────────────────────────────────
        emit({"stage": "parsing", "message": "Opening PDF…", "progress": 0})
        try:
            pages = extract_pages(pdf_path)
        except Exception as e:
            store.set_status(doc_id, "error")
            emit({"stage": "error", "message": f"PDF parsing failed: {e}"})
            return

        total_pages = len(pages)
        emit({
            "stage": "parsing",
            "message": f"Extracted {total_pages} pages",
            "pages": total_pages,
            "progress": 100,
        })

        # ── Stage 2: Clause Segmentation ─────────────────────────────────────
        emit({"stage": "segmentation", "message": "Segmenting clauses…", "progress": 0})
        try:
            raw_clauses = segment_clauses(pages)
        except Exception as e:
            store.set_status(doc_id, "error")
            emit({"stage": "error", "message": f"Segmentation failed: {e}"})
            return

        total_clauses = len(raw_clauses)
        emit({
            "stage": "segmentation",
            "message": f"Identified {total_clauses} clauses",
            "total": total_clauses,
            "progress": 100,
        })

        if total_clauses == 0:
            store.set_status(doc_id, "error")
            emit({"stage": "error", "message": "No clauses found in document. Try a different PDF."})
            return

        # ── Stage 3: NER + Causal Detection (streamed per clause) ────────────
        processed_clauses: list[Clause] = []
        warnings = 0

        # NER runs once, batched via nlp.pipe(), instead of once per clause —
        # spaCy amortizes tokenizer overhead across the whole batch. The SSE
        # loop below is unchanged: it still emits one `ner` event per clause,
        # in order, and just looks up the precomputed entities for it. Falls
        # back to the old per-clause path (same try/except as before) if the
        # batch call itself fails, so a pipeline-level error can't silently
        # blank out every clause's entities.
        prose_indices = [i for i, raw in enumerate(raw_clauses) if not raw.is_table]
        try:
            batch_entities = extract_entities_batch([raw_clauses[i].text for i in prose_indices])
            entities_by_index = dict(zip(prose_indices, batch_entities))
        except Exception as e:
            logger.warning("Batch NER failed for %s, falling back to per-clause: %s", doc_id, e)
            entities_by_index = {}
            for i in prose_indices:
                try:
                    entities_by_index[i] = extract_entities_batch([raw_clauses[i].text])[0]
                except Exception as ce:
                    logger.warning("NER failed for clause %d: %s", i, ce)
                    warnings += 1
                    entities_by_index[i] = []

        for i, raw in enumerate(raw_clauses):
            clause_id = f"{doc_id}_c{i:04d}"

            # Tables are tagged and rendered as-is; running prose NER/causal
            # regexes over tabular fragments only produces noise, so skip them.
            if raw.is_table:
                clause = Clause(
                    clause_id=clause_id,
                    doc_id=doc_id,
                    page=raw.page,
                    section_hierarchy=raw.section_hierarchy,
                    text=raw.text,
                    char_start=raw.char_start,
                    char_end=raw.char_end,
                    bbox=raw.bbox,
                    entities=[],
                    causal_patterns=[],
                    complexity_score=0.0,
                    clause_type="table",
                )
                processed_clauses.append(clause)
                emit({
                    "stage": "ner",
                    "message": f"Processing clause {i + 1} of {total_clauses}…",
                    "current": i + 1,
                    "total": total_clauses,
                    "progress": round((i + 1) / total_clauses * 100),
                    "warnings": warnings,
                    "clause": clause.model_dump(),
                })
                continue

            entities = entities_by_index.get(i, [])

            try:
                causal = detect_causal_patterns(raw.text, clause_id)
            except Exception as e:
                logger.warning("Causal detection failed for %s: %s", clause_id, e)
                warnings += 1
                causal = []

            complexity = len(entities) / max(len(raw.text.split()), 1)

            clause = Clause(
                clause_id=clause_id,
                doc_id=doc_id,
                page=raw.page,
                section_hierarchy=raw.section_hierarchy,
                text=raw.text,
                char_start=raw.char_start,
                char_end=raw.char_end,
                bbox=raw.bbox,
                entities=entities,
                causal_patterns=causal,
                complexity_score=round(complexity, 4),
                clause_type="prose",
            )
            processed_clauses.append(clause)

            emit({
                "stage": "ner",
                "message": f"Processing clause {i + 1} of {total_clauses}…",
                "current": i + 1,
                "total": total_clauses,
                "progress": round((i + 1) / total_clauses * 100),
                "warnings": warnings,
                "clause": clause.model_dump(),
            })

        # ── Stage 4: Embeddings + UMAP ────────────────────────────────────────
        emit({"stage": "embedding", "message": "Generating semantic embeddings…", "progress": 0})
        try:
            embeddings = embed_texts([c.text for c in processed_clauses])
        except Exception as e:
            store.set_status(doc_id, "error")
            emit({"stage": "error", "message": f"Embedding failed: {e}"})
            return

        # Persist full 384-d vectors — semantic search and clause-level
        # document diff read these instead of re-encoding the document.
        store.save_embeddings(doc_id, embeddings)

        emit({"stage": "embedding", "message": "Projecting to 2D with UMAP…", "progress": 50})
        try:
            coords_2d = project_umap(embeddings)
            for i, clause in enumerate(processed_clauses):
                clause.embedding_2d = [
                    round(float(coords_2d[i][0]), 4),
                    round(float(coords_2d[i][1]), 4),
                ]
            emit({
                "stage": "embeddings_update",
                "updates": [
                    {"clause_id": c.clause_id, "embedding_2d": c.embedding_2d}
                    for c in processed_clauses
                    if c.embedding_2d is not None
                ],
            })
        except Exception as e:
            # Not fatal — the scatter plot just won't render.
            logger.warning("UMAP projection failed for %s: %s", doc_id, e)
            warnings += 1

        emit({"stage": "embedding", "message": "Embeddings complete", "progress": 100})

        # ── Stage 5: Knowledge Graph ──────────────────────────────────────────
        emit({"stage": "graph", "message": "Building provenance graph…", "progress": 0})
        try:
            graph = build_provenance_graph(processed_clauses, doc_id, filename)
        except Exception as e:
            store.set_status(doc_id, "error")
            emit({"stage": "error", "message": f"Graph building failed: {e}"})
            return

        # ── Stats + Save ──────────────────────────────────────────────────────
        entity_type_counts: dict[str, int] = {}
        causal_count = 0
        risk_counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        confidence_counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

        for clause in processed_clauses:
            for e in clause.entities:
                entity_type_counts[e.label] = entity_type_counts.get(e.label, 0) + 1
                confidence_counts[e.confidence] = confidence_counts.get(e.confidence, 0) + 1
            for p in clause.causal_patterns:
                causal_count += 1
                risk_counts[p.risk_tier] = risk_counts.get(p.risk_tier, 0) + 1

        most_complex = max(processed_clauses, key=lambda c: c.complexity_score)

        try:
            from routers.intelligence import _detect_domain
            domain = _detect_domain(processed_clauses)
        except Exception:
            domain = "General Legislation"

        stats = {
            "total_clauses": total_clauses,
            "total_entities": sum(entity_type_counts.values()),
            "entity_type_counts": entity_type_counts,
            "entity_confidence_counts": confidence_counts,
            "causal_patterns_found": causal_count,
            "causal_risk_counts": risk_counts,
            "total_pages": total_pages,
            "graph_nodes": len(graph.nodes),
            "graph_edges": len(graph.edges),
            "most_complex_clause_id": most_complex.clause_id,
            "domain": domain,
            "warnings": warnings,
        }

        store.save_result(AnalysisResult(
            doc_id=doc_id,
            clauses=processed_clauses,
            graph=graph,
            stats=stats,
        ))

        emit({
            "stage": "complete",
            "message": "Analysis complete",
            "doc_id": doc_id,
            "stats": stats,
        })

    except Exception as e:
        logger.exception("Analysis failed for %s", doc_id)
        store.set_status(doc_id, "error")
        emit({"stage": "error", "message": f"Analysis failed: {e}"})


def _start_analysis_job(doc_id: str, pdf_path: str, filename: str) -> str:
    """Run the pipeline as a background job keyed by doc_id. A reconnecting
    client or a second tab attaches to the running job instead of starting a
    second pipeline that would race the first on result.json."""
    key = f"analyze:{doc_id}"

    async def _run():
        loop = asyncio.get_running_loop()

        def emit(ev: dict) -> None:
            loop.call_soon_threadsafe(job_manager.publish, key, ev)

        await loop.run_in_executor(None, _pipeline_worker, doc_id, pdf_path, filename, emit)

    job_manager.start(key, _run)
    return key


async def _analysis_generator(job_key: str):
    """Stream the job's events (history replay first, then live); heartbeat
    while idle. Disconnecting does not stop the job."""
    async for ev in job_manager.subscribe(job_key):
        if ev is None:
            yield _heartbeat()
            continue
        yield _sse(ev)
        if ev.get("stage") in ("complete", "error"):
            break


async def _replay_generator(result: AnalysisResult):
    """Fast replay of a stored analysis — same event shapes as a live run,
    so the frontend needs no special casing. No CPU work, near-instant."""
    stats = result.stats
    total = len(result.clauses)

    yield _sse({
        "stage": "parsing",
        "message": f"Loaded {stats.get('total_pages', '?')} pages (cached)",
        "pages": stats.get("total_pages", 0),
        "progress": 100,
        "replay": True,
    })
    yield _sse({
        "stage": "segmentation",
        "message": f"Identified {total} clauses (cached)",
        "total": total,
        "progress": 100,
        "replay": True,
    })

    for i, clause in enumerate(result.clauses):
        yield _sse({
            "stage": "ner",
            "message": f"Clause {i + 1} of {total} (cached)",
            "current": i + 1,
            "total": total,
            "progress": round((i + 1) / total * 100),
            "clause": clause.model_dump(),
            "replay": True,
        })
        if i % 25 == 24:
            await asyncio.sleep(0)  # yield the loop on large documents

    yield _sse({"stage": "embedding", "message": "Embeddings loaded (cached)", "progress": 100, "replay": True})
    yield _sse({"stage": "graph", "message": "Graph loaded (cached)", "progress": 100, "replay": True})
    yield _sse({
        "stage": "complete",
        "message": "Analysis complete (cached)",
        "doc_id": result.doc_id,
        "stats": stats,
        "replay": True,
    })


@router.get("/analyze/{doc_id}")
async def stream_analysis(doc_id: str, force: bool = False):
    pdf_path = store.get_path(doc_id)
    meta = store.get_meta(doc_id)

    if not pdf_path or not meta:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }

    # A completed analysis is replayed from disk instead of silently
    # re-running the whole pipeline; pass ?force=true to re-analyze.
    if not force:
        existing = store.get_result(doc_id)
        if existing is not None:
            return StreamingResponse(
                _replay_generator(existing),
                media_type="text/event-stream",
                headers=headers,
            )

    # Only a fresh run needs the PDF itself; a cached result replays without it.
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    running = job_manager.get_job(f"analyze:{doc_id}")
    if running is not None and running.status == "running":
        job_key = running.key
    else:
        job_key = _start_analysis_job(doc_id, pdf_path, meta.filename)

    return StreamingResponse(
        _analysis_generator(job_key),
        media_type="text/event-stream",
        headers=headers,
    )
