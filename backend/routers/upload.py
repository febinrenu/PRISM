"""
Upload router: handles PDF file uploads.
POST /api/upload → returns doc_id + metadata
"""
import asyncio
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

from config import UPLOAD_DIR, MAX_FILE_SIZE_MB, MAX_PDF_PAGES
from models.schemas import DocumentMeta
from storage.store import save_meta, save_path
from pipeline.pdf_parser import get_page_count

router = APIRouter()

_MAX_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_CHUNK = 1024 * 1024


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.",
    )


async def read_capped(file: UploadFile) -> bytes:
    """Read an upload in chunks, refusing as soon as it passes the size cap,
    so an oversized body is never held in memory whole."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_BYTES:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


async def ingest_pdf(filename: str, content: bytes) -> tuple[str, DocumentMeta]:
    """Persist an uploaded PDF and its metadata. Shared by the web upload route
    and the public /v1 API so both take exactly the same ingest path."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    if len(content) > _MAX_BYTES:
        raise _too_large()
    # The PDF header may be preceded by a little junk (allowed by the spec).
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=400, detail="The file is not a valid PDF.")

    doc_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, file_path.write_bytes, content)

    try:
        page_count = await loop.run_in_executor(None, get_page_count, str(file_path))
    except Exception:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The PDF could not be opened. It may be corrupt or encrypted.")
    if page_count == 0:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The PDF has no pages.")
    if page_count > MAX_PDF_PAGES:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"The PDF has {page_count} pages. The maximum is {MAX_PDF_PAGES}.",
        )

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
    content = await read_capped(file)
    doc_id, meta = await ingest_pdf(file.filename or "", content)
    return {
        "doc_id": doc_id,
        "filename": meta.filename,
        "pages": meta.pages,
        "file_size_kb": meta.file_size_kb,
    }
