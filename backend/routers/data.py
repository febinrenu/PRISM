"""
Data endpoints for retrieving analysis results.
"""
import os
from fastapi import APIRouter, HTTPException
from config import DEMO_DIR, DEMO_PDF_NAME
from storage.store import get_result, get_meta, list_documents, save_meta, save_path

router = APIRouter()


def _require_result(doc_id: str):
    result = get_result(doc_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results found for {doc_id}. Run /api/analyze/{doc_id} first.",
        )
    return result


@router.get("/clauses/{doc_id}")
async def get_clauses(doc_id: str):
    result = _require_result(doc_id)
    return {"doc_id": doc_id, "clauses": [c.model_dump() for c in result.clauses]}


@router.get("/entities/{doc_id}")
async def get_entities(doc_id: str):
    result = _require_result(doc_id)

    # Build entity list with co-occurrence matrix info
    all_entities = []
    entity_cooccurrence: dict[str, dict[str, int]] = {}

    for clause in result.clauses:
        clause_entity_keys = [f"{e.label}:{e.text[:30]}" for e in clause.entities]
        for entity in clause.entities:
            key = f"{entity.label}:{entity.text[:30]}"
            entry = {
                "label": entity.label,
                "text": entity.text,
                "clause_id": clause.clause_id,
                "page": clause.page,
            }
            all_entities.append(entry)

            # Build co-occurrence
            if key not in entity_cooccurrence:
                entity_cooccurrence[key] = {}
            for other_key in clause_entity_keys:
                if other_key != key:
                    entity_cooccurrence[key][other_key] = (
                        entity_cooccurrence[key].get(other_key, 0) + 1
                    )

    return {
        "doc_id": doc_id,
        "entities": all_entities,
        "cooccurrence": entity_cooccurrence,
    }


@router.get("/causal/{doc_id}")
async def get_causal_patterns(doc_id: str):
    result = _require_result(doc_id)
    patterns = []
    for clause in result.clauses:
        for cp in clause.causal_patterns:
            patterns.append({
                **cp.model_dump(),
                "clause_page": clause.page,
                "clause_preview": clause.text[:100],
                "section": " > ".join(clause.section_hierarchy) if clause.section_hierarchy else "—",
            })
    return {"doc_id": doc_id, "patterns": patterns, "total": len(patterns)}


@router.get("/embeddings/{doc_id}")
async def get_embeddings(doc_id: str):
    result = _require_result(doc_id)
    points = []
    for clause in result.clauses:
        if clause.embedding_2d:
            dominant_entity = (
                clause.entities[0].label if clause.entities else "NONE"
            )
            points.append({
                "clause_id": clause.clause_id,
                "x": clause.embedding_2d[0],
                "y": clause.embedding_2d[1],
                "dominant_entity": dominant_entity,
                "entity_count": len(clause.entities),
                "text_preview": clause.text[:120],
                "page": clause.page,
            })
    return {"doc_id": doc_id, "points": points}


@router.get("/graph/{doc_id}")
async def get_graph(doc_id: str):
    result = _require_result(doc_id)
    return {
        "doc_id": doc_id,
        "nodes": [n.model_dump() for n in result.graph.nodes],
        "edges": [e.model_dump() for e in result.graph.edges],
    }


@router.get("/stats/{doc_id}")
async def get_stats(doc_id: str):
    result = _require_result(doc_id)
    return {"doc_id": doc_id, **result.stats}


async def _register_demo():
    """
    Register the pre-loaded demo PDF for analysis.
    Returns a doc_id that can be used with /api/analyze/{doc_id}.

    The doc_id is stable so a previously completed demo analysis is served
    from the disk store (fast replay) instead of re-running the pipeline.
    """
    demo_path = DEMO_DIR / DEMO_PDF_NAME

    if not demo_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Demo PDF not found at {demo_path}. "
                "Please place 'income_tax_2025.pdf' in the backend/data/demo/ directory."
            ),
        )

    doc_id = "demo_" + DEMO_PDF_NAME.rsplit(".", 1)[0]

    existing = get_meta(doc_id)
    if existing is not None and existing.status == "complete":
        return {
            "doc_id": doc_id,
            "filename": DEMO_PDF_NAME,
            "pages": existing.pages,
            "message": "Demo document already analyzed. Results are cached.",
        }

    from models.schemas import DocumentMeta
    from pipeline.pdf_parser import get_page_count

    try:
        pages = get_page_count(str(demo_path))
    except Exception:
        pages = 0

    file_size_kb = round(os.path.getsize(str(demo_path)) / 1024, 1)

    meta = DocumentMeta(
        doc_id=doc_id,
        filename=DEMO_PDF_NAME,
        pages=pages,
        file_size_kb=file_size_kb,
        status="pending",
    )
    save_meta(meta)
    save_path(doc_id, str(demo_path))

    return {
        "doc_id": doc_id,
        "filename": DEMO_PDF_NAME,
        "pages": pages,
        "message": f"Demo document registered. Call GET /api/analyze/{doc_id} to start analysis.",
    }


@router.get("/demo")
async def trigger_demo_get():
    return await _register_demo()


@router.post("/demo")
async def trigger_demo_post():
    # Kept as an alias — the original frontend calls POST.
    return await _register_demo()


@router.get("/documents")
async def list_docs():
    docs = list_documents()
    return {"documents": [d.model_dump() for d in docs]}
