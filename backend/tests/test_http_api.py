"""
HTTP-level tests through FastAPI's TestClient, against a temporary document
store and upload directory (never the real data/ folder).

Covers upload validation, the full analyze SSE pipeline on a small generated
statute, cached replay when the PDF is gone, the PDF route with a non-ASCII
filename, doc_id validation, and the committed demo metadata being portable.
"""
import asyncio
import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest

BACKEND = Path(__file__).parent.parent

_STATUTE_TEXT = [
    "THE SAMPLE TAX ACT, 2026",
    "1. Short title.— This Act may be called the Sample Tax Act, 2026.",
    "2. Return of income.— (1) Every person whose total income exceeds "
    "Rs. 5,00,000 shall furnish a return of income on or before the due date.",
    "(2) Where any person fails to furnish the return under sub-section (1), "
    # Base-14 Helvetica has no rupee glyph, so the PDF uses "Rs."; the ₹ form
    # is covered directly in test_threshold_patterns.py.
    "he shall pay a penalty of Rs. 5,000.",
    "3. Rate of tax.— Income-tax shall be charged at the rate of 20% of the "
    "total income exceeding the threshold.",
]


def _make_pdf(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in _STATUTE_TEXT:
        rect = fitz.Rect(72, y, 540, y + 60)
        page.insert_textbox(rect, line, fontsize=10, fontname="helv")
        y += 64
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("api")
    store_dir, upload_dir = root / "store", root / "uploads"
    store_dir.mkdir()
    upload_dir.mkdir()

    import config
    from routers import upload as upload_router
    from storage import store

    mp.setattr(config, "STORE_DIR", store_dir)
    mp.setattr(store, "STORE_DIR", store_dir)
    mp.setattr(upload_router, "UPLOAD_DIR", upload_dir)
    store._meta_store.clear()
    store._result_store.clear()
    store._embeddings_cache.clear()

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        client.sample_pdf = _make_pdf(root / "sample.pdf")
        client.root = root
        yield client

    store._meta_store.clear()
    store._result_store.clear()
    store._embeddings_cache.clear()
    mp.undo()


def _sse_events(response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


def _upload(api, path: Path, name: str = "sample.pdf"):
    with open(path, "rb") as fh:
        return api.post("/api/upload", files={"file": (name, fh, "application/pdf")})


def test_health(api):
    assert api.get("/health").status_code == 200


def test_upload_rejects_wrong_extension(api, tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    with open(f, "rb") as fh:
        r = api.post("/api/upload", files={"file": ("notes.txt", fh, "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_file_that_is_not_a_pdf(api, tmp_path):
    f = tmp_path / "fake.pdf"
    f.write_bytes(b"this is not a pdf at all")
    r = _upload(api, f, "fake.pdf")
    assert r.status_code == 400
    assert "not a valid PDF" in r.json()["detail"]


def test_upload_rejects_oversize(api, monkeypatch):
    from routers import upload as upload_router

    monkeypatch.setattr(upload_router, "_MAX_BYTES", 100)
    r = _upload(api, api.sample_pdf)
    assert r.status_code == 413


def test_upload_analyze_and_replay(api):
    r = _upload(api, api.sample_pdf)
    assert r.status_code == 200, r.text
    doc_id = r.json()["doc_id"]
    assert r.json()["pages"] == 1

    with api.stream("GET", f"/api/analyze/{doc_id}") as resp:
        assert resp.status_code == 200
        events = _sse_events(resp)
    stages = [e.get("stage") for e in events]
    assert stages[-1] == "complete", stages[-5:]

    clauses = api.get(f"/api/clauses/{doc_id}").json()
    clause_list = clauses["clauses"] if isinstance(clauses, dict) else clauses
    assert len(clause_list) >= 2
    thresholds = {
        e["text"] for c in clause_list for e in c["entities"] if e["label"] == "THRESHOLD"
    }
    assert "Rs. 5,000" in thresholds
    assert any("20%" in t for t in thresholds)

    # A completed analysis replays from the store even after the PDF is gone.
    from storage import store

    Path(store.get_path(doc_id)).unlink()
    with api.stream("GET", f"/api/analyze/{doc_id}") as resp:
        assert resp.status_code == 200
        replay = _sse_events(resp)
    assert replay[-1]["stage"] == "complete"
    assert all(e.get("replay") for e in replay if e.get("stage") in ("parsing", "segmentation"))


def test_pdf_route_serves_non_ascii_filename(api):
    from models.schemas import DocumentMeta
    from storage import store

    meta = DocumentMeta(doc_id="hindi_name", filename="आयकर अधिनियम.pdf", pages=1,
                        file_size_kb=1.0, status="complete")
    store.save_meta(meta)
    store.save_path("hindi_name", str(api.sample_pdf))

    r = api.get("/api/pdf/hindi_name")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "filename*=utf-8''" in r.headers["content-disposition"]


@pytest.mark.parametrize("bad", ["a.b", "..%5C..%5Cconfig", "x%2Fy"])
def test_invalid_doc_ids_return_404(api, bad):
    for url in (f"/api/pdf/{bad}", f"/api/clauses/{bad}", f"/api/analyze/{bad}"):
        assert api.get(url).status_code == 404, url


def test_committed_demo_meta_is_portable():
    meta_path = BACKEND / "data" / "store" / "demo_income_tax_2025" / "meta.json"
    if not meta_path.exists():
        pytest.skip("demo store not present")
    stored = json.loads(meta_path.read_text(encoding="utf-8"))["pdf_path"]
    assert not Path(stored).is_absolute() and ":" not in stored, stored


# ── job manager ──────────────────────────────────────────────────────────────

def test_job_manager_dedupes_and_handles_cancellation():
    from services import job_manager

    async def scenario():
        started = {"n": 0}
        gate = asyncio.Event()

        async def work():
            started["n"] += 1
            await gate.wait()
            return "done"

        a = job_manager.start("t:dedupe", work)
        b = job_manager.start("t:dedupe", work)
        assert a is b
        await asyncio.sleep(0)
        gate.set()
        await a.task
        assert started["n"] == 1 and a.status == "complete"

        async def forever():
            await asyncio.sleep(3600)

        c = job_manager.start("t:cancel", forever)
        await asyncio.sleep(0)
        c.task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await c.task
        assert c.status == "error" and c.error == "cancelled"
        # A cancelled key can be started again.
        d = job_manager.start("t:cancel", work)
        assert d is not c
        await d.task

    asyncio.run(scenario())


def test_job_manager_evicts_old_finished_jobs():
    from services import job_manager

    async def scenario():
        async def work():
            return 1

        job = job_manager.start("t:evict", work)
        await job.task
        job.finished_at -= job_manager.FINISHED_JOB_TTL_S + 1
        job_manager.start("t:other", work)
        assert job_manager.get_job("t:evict") is None

    asyncio.run(scenario())
