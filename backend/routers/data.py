"""
Data endpoints for retrieving analysis results.
"""
import os
from auth.deps import can_list, optional_user
from fastapi import Depends, APIRouter, HTTPException
from config import DEMO_DIR, DEMO_PDF_NAME
from storage.store import get_result, get_meta, lime_explained_ids, list_documents, save_meta, save_path

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
    explained = lime_explained_ids(doc_id)
    return {"doc_id": doc_id, "clauses": [_with_lime(c, explained) for c in result.clauses]}


def _with_lime(clause, explained: set[str]) -> dict:
    d = clause.model_dump()
    d["lime_available"] = bool(d.get("lime_available")) or clause.clause_id in explained
    return d


@router.get("/clause/{doc_id}/{clause_id}")
async def get_clause(doc_id: str, clause_id: str):
    """One clause, without sending the whole document."""
    result = _require_result(doc_id)
    for c in result.clauses:
        if c.clause_id == clause_id:
            return {"doc_id": doc_id, "clause": _with_lime(c, lime_explained_ids(doc_id))}
    raise HTTPException(status_code=404, detail=f"Clause {clause_id} not found in {doc_id}.")


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
async def list_docs(user: dict | None = Depends(optional_user)):
    """Shared documents, plus the signed-in user's own (admins see all)."""
    docs = [d for d in list_documents() if can_list(d, user)]
    return {"documents": [d.model_dump() for d in docs]}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: dict | None = Depends(optional_user)):
    """One document's metadata (name, pages, status) for page titles."""
    meta = get_meta(doc_id)
    if meta is None or not can_list(meta, user):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return meta.model_dump(exclude={"pdf_path", "owner_id"})


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict | None = Depends(optional_user)):
    """Delete a document and everything derived from it: stored analysis and
    caches, the uploaded PDF (and its object-storage copy), its rows in the
    database and its passages in the Ask index. The owner or an admin may
    delete it (anyone, for an anonymous upload, as for re-analysis); the
    demo cannot be deleted, nor a document while it is being analysed."""
    from auth import users
    from auth.deps import can_manage
    from services import job_manager
    from storage import r2
    from storage.store import delete_document as remove_files

    meta = get_meta(doc_id)
    if meta is None or not can_list(meta, user):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    if doc_id.startswith("demo_"):
        raise HTTPException(status_code=403, detail="The demo document is a fixed reference and cannot be deleted.")
    if not can_manage(meta, user):
        raise HTTPException(status_code=403, detail="Only the document's owner can delete it.")
    running = [k for k in (f"analyze:{doc_id}", f"llm:{doc_id}")
               if (j := job_manager.get_job(k)) is not None and j.status == "running"]
    if meta.status == "processing" or running:
        raise HTTPException(status_code=409, detail="The document is being analysed; delete it when that finishes.")
    removed = remove_files(doc_id)
    keys = users.forget_document(doc_id)
    removed["object_storage"] = sum(r2.delete_object(k) for k in keys)
    try:
        from rag import corpus_builder
        corpus_builder.remove_document(doc_id)
        removed["ask_index"] = True
    except Exception:  # noqa: BLE001 - the index may not be built on this install
        removed["ask_index"] = False
    return {"deleted": doc_id, "removed": removed}


SCHEDULES_VERSION = 2      # bump when pipeline.schedules reads tables differently


def _schedules_cache(doc_id: str):
    from storage.store import _doc_dir
    return _doc_dir(doc_id) / "schedules.json"


@router.get("/schedules/{doc_id}")
async def get_schedules(doc_id: str):
    """The document's rate schedules, each read row by row into bands and
    checked: starts at zero, no gaps or overlaps, an open top band, rates
    that do not fall (pipeline.schedules). Cached per PDF."""
    import asyncio
    import json

    from storage.store import get_path, load_ocr_lines

    pdf = get_path(doc_id)
    if pdf is None or not os.path.exists(pdf):
        raise HTTPException(status_code=404, detail=f"No PDF stored for {doc_id}.")
    cache = _schedules_cache(doc_id)
    stamp = f"{os.path.getsize(pdf)}:{int(os.path.getmtime(pdf))}:{SCHEDULES_VERSION}"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("stamp") == stamp:
            return data
    from pipeline.schedules import find_schedules
    ocr_pages = load_ocr_lines(doc_id)          # the scanned pages' recognised lines, if any
    schedules = await asyncio.get_running_loop().run_in_executor(None, find_schedules, str(pdf), ocr_pages)
    data = {"doc_id": doc_id, "stamp": stamp, "schedules": schedules,
            "review": sum(1 for s in schedules if not s["check"]["ok"])}
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data

