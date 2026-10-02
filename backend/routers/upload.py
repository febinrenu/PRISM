"""
Upload router: handles PDF file uploads.
POST /api/upload → returns doc_id + metadata
"""
import asyncio
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

from config import UPLOAD_DIR, MAX_FILE_SIZE_MB
from models.schemas import DocumentMeta
from storage.store import save_meta, save_path
from pipeline.pdf_parser import get_page_count

router = APIRouter()


async def ingest_pdf(filename: str, content: bytes) -> tuple[str, DocumentMeta]:
    """Persist an uploaded PDF and its metadata. Shared by the web upload route
    and the public /v1 API so both take exactly the same ingest path."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.",
        )

    doc_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, file_path.write_bytes, content)

    try:
        page_count = await loop.run_in_executor(None, get_page_count, str(file_path))
    except Exception:
        page_count = 0

    meta = DocumentMeta(
        doc_id=doc_id,
        filename=filename,
        pages=page_count,
        file_size_kb=round(len(content) / 1024, 1),
        status="pending",
    )
    save_meta(meta)
    save_path(doc_id, str(file_path))
    return doc_id, meta


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    doc_id, meta = await ingest_pdf(file.filename or "", content)
    return {
        "doc_id": doc_id,
        "filename": meta.filename,
        "pages": meta.pages,
        "file_size_kb": meta.file_size_kb,
    }
