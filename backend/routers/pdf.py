"""
PDF serving endpoint — serves the raw PDF file for react-pdf in the browser.
GET /api/pdf/{doc_id} → returns the PDF file
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from storage.store import get_path, get_meta

router = APIRouter()


@router.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str):
    pdf_path = get_path(doc_id)
    meta = get_meta(doc_id)

    if not pdf_path or not meta:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{meta.filename}"',
        },
    )
