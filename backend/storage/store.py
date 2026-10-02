"""
Disk-backed document store with an in-memory write-through cache.

Layout on disk (all writes atomic: tmp file + os.replace):
    data/store/{doc_id}/meta.json                  DocumentMeta (incl. pdf_path)
    data/store/{doc_id}/result.json                AnalysisResult
    data/store/{doc_id}/embeddings.npy             (N, 384) float32, row i = clauses[i]
    data/store/{doc_id}/llm/extractions.json       LLM extraction cache
    data/store/{doc_id}/lime/{clause_id}.{mode}.json
    data/store/{doc_id}/simulations/{sim_id}.json  SimulationResult
"""
import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from config import BASE_DIR, STORE_DIR
from models.schemas import AnalysisResult, DocumentMeta, SimulationResult

_meta_store: dict[str, DocumentMeta] = {}
_result_store: dict[str, AnalysisResult] = {}
_embeddings_cache: dict[str, np.ndarray] = {}

# result.json has two writers (analyze pipeline, LLM merge) — serialize per process.
_write_lock = threading.Lock()


# doc_ids are UUIDs or slugs like "demo_income_tax_2025". Anything else
# (dots, slashes, backslashes, "..") could escape STORE_DIR.
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InvalidDocId(ValueError):
    """Raised for a doc_id that could not have been issued by this store.
    main.py maps it to a 404."""


def is_valid_doc_id(doc_id: str) -> bool:
    return bool(doc_id) and bool(_DOC_ID_RE.match(doc_id))


def _doc_dir(doc_id: str) -> Path:
    if not is_valid_doc_id(doc_id):
        raise InvalidDocId(f"Invalid doc_id: {doc_id!r}")
    return STORE_DIR / doc_id


def to_stored_path(path: str) -> str:
    """Paths under the backend directory are stored relative to it (POSIX
    separators), so a store copied to another machine or a fresh clone
    still resolves its PDFs."""
    p = Path(path)
    try:
        return p.resolve().relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return str(p)


def resolve_stored_path(stored: Optional[str]) -> Optional[str]:
    """Inverse of to_stored_path. Also repairs absolute paths recorded on a
    different machine: if the path doesn't exist but contains a `data/`
    segment, it is re-rooted under this checkout's backend directory."""
    if not stored:
        return None
    p = Path(stored)
    if not p.is_absolute() and not re.match(r"^[A-Za-z]:[\\/]", stored):
        return str(BASE_DIR / p)
    if p.exists():
        return str(p)
    parts = re.split(r"[\\/]+", stored)
    if "data" in parts:
        idx = len(parts) - 1 - parts[::-1].index("data")
        candidate = BASE_DIR.joinpath(*parts[idx:])
        if candidate.exists():
            return str(candidate)
    return str(p)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_npy(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, arr)
    os.replace(tmp, path)


def load_index() -> int:
    """Rebuild the in-memory index from disk. Called once at startup."""
    count = 0
    if not STORE_DIR.exists():
        return count
    for meta_path in STORE_DIR.glob("*/meta.json"):
        try:
            meta = DocumentMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
            _meta_store[meta.doc_id] = meta
            count += 1
        except Exception:
            continue  # skip corrupt entries rather than failing startup
    return count


# --- meta / path ---

def save_meta(meta: DocumentMeta) -> None:
    _meta_store[meta.doc_id] = meta
    _atomic_write_text(_doc_dir(meta.doc_id) / "meta.json", meta.model_dump_json())


def get_meta(doc_id: str) -> Optional[DocumentMeta]:
    if not is_valid_doc_id(doc_id):
        return None
    if doc_id in _meta_store:
        return _meta_store[doc_id]
    path = _doc_dir(doc_id) / "meta.json"
    if path.exists():
        meta = DocumentMeta.model_validate_json(path.read_text(encoding="utf-8"))
        _meta_store[doc_id] = meta
        return meta
    return None


def save_path(doc_id: str, path: str) -> None:
    meta = get_meta(doc_id)
    if meta is not None:
        meta.pdf_path = to_stored_path(path)
        save_meta(meta)


def get_path(doc_id: str) -> Optional[str]:
    """Absolute, existing-on-this-machine path of the document's PDF."""
    meta = get_meta(doc_id)
    return resolve_stored_path(meta.pdf_path) if meta else None


def set_status(doc_id: str, status: str) -> None:
    meta = get_meta(doc_id)
    if meta is not None:
        meta.status = status  # type: ignore[assignment]
        save_meta(meta)


def list_documents() -> list[DocumentMeta]:
    # get_meta lazily fills the cache; ensure disk-only docs are visible too.
    if STORE_DIR.exists():
        for meta_path in STORE_DIR.glob("*/meta.json"):
            doc_id = meta_path.parent.name
            if doc_id not in _meta_store:
                get_meta(doc_id)
    return list(_meta_store.values())


# --- analysis result ---

def save_result(result: AnalysisResult) -> None:
    with _write_lock:
        _result_store[result.doc_id] = result
        _atomic_write_text(_doc_dir(result.doc_id) / "result.json", result.model_dump_json())
    set_status(result.doc_id, "complete")


def get_result(doc_id: str) -> Optional[AnalysisResult]:
    if not is_valid_doc_id(doc_id):
        return None
    if doc_id in _result_store:
        return _result_store[doc_id]
    path = _doc_dir(doc_id) / "result.json"
    if path.exists():
        result = AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
        _result_store[doc_id] = result
        return result
    return None


def update_result(doc_id: str, mutate) -> Optional[AnalysisResult]:
    """Atomically read-modify-write the stored result. `mutate(result)` edits in place."""
    with _write_lock:
        result = get_result(doc_id)
        if result is None:
            return None
        mutate(result)
        _result_store[doc_id] = result
        _atomic_write_text(_doc_dir(doc_id) / "result.json", result.model_dump_json())
        return result


# --- full embeddings (Phase 1 fix: persist 384-d vectors) ---

def save_embeddings(doc_id: str, arr: np.ndarray) -> None:
    arr = np.asarray(arr, dtype=np.float32)
    _embeddings_cache[doc_id] = arr
    _atomic_write_npy(_doc_dir(doc_id) / "embeddings.npy", arr)


def load_embeddings(doc_id: str) -> Optional[np.ndarray]:
    if doc_id in _embeddings_cache:
        return _embeddings_cache[doc_id]
    path = _doc_dir(doc_id) / "embeddings.npy"
    if path.exists():
        arr = np.load(path)
        _embeddings_cache[doc_id] = arr
        return arr
    return None


# --- Phase 2: LLM extraction cache ---

def save_llm_extractions(doc_id: str, payload: dict) -> None:
    _atomic_write_text(
        _doc_dir(doc_id) / "llm" / "extractions.json",
        json.dumps(payload, ensure_ascii=False),
    )


def load_llm_extractions(doc_id: str) -> Optional[dict]:
    path = _doc_dir(doc_id) / "llm" / "extractions.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


# --- Phase 2: LIME cache ---

def save_lime(doc_id: str, clause_id: str, mode: str, payload: dict) -> None:
    _atomic_write_text(
        _doc_dir(doc_id) / "lime" / f"{clause_id}.{mode}.json",
        json.dumps(payload, ensure_ascii=False),
    )


def load_lime(doc_id: str, clause_id: str, mode: str) -> Optional[dict]:
    path = _doc_dir(doc_id) / "lime" / f"{clause_id}.{mode}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_lime_clause_ids(doc_id: str) -> list[str]:
    """Clause IDs that have a cached LIME explanation on disk (any mode).
    Used by the eval harness, which can't rely on the in-result lime_available
    flag (that flag isn't persisted back when an explanation is generated)."""
    lime_dir = _doc_dir(doc_id) / "lime"
    if not lime_dir.exists():
        return []
    ids = set()
    for p in lime_dir.glob("*.json"):
        # filename is "{clause_id}.{mode}.json" — strip the trailing ".{mode}".
        stem = p.name.rsplit(".", 2)[0]
        ids.add(stem)
    return sorted(ids)


# --- Phase 3: deep (on-demand) clause reasoning ---

def save_deep_reasoning(doc_id: str, clause_id: str, payload: dict) -> None:
    _atomic_write_text(
        _doc_dir(doc_id) / "deep_reasoning" / f"{clause_id}.json",
        json.dumps(payload, ensure_ascii=False),
    )


def load_deep_reasoning(doc_id: str, clause_id: str) -> Optional[dict]:
    path = _doc_dir(doc_id) / "deep_reasoning" / f"{clause_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


# --- Phase 2: simulations ---

def save_simulation(result: SimulationResult) -> None:
    _atomic_write_text(
        _doc_dir(result.doc_id) / "simulations" / f"{result.simulation_id}.json",
        result.model_dump_json(),
    )


def load_simulation(doc_id: str, simulation_id: str) -> Optional[SimulationResult]:
    path = _doc_dir(doc_id) / "simulations" / f"{simulation_id}.json"
    if path.exists():
        return SimulationResult.model_validate_json(path.read_text(encoding="utf-8"))
    return None


def list_simulations(doc_id: str) -> list[str]:
    sim_dir = _doc_dir(doc_id) / "simulations"
    if not sim_dir.exists():
        return []
    files = sorted(sim_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return [p.stem for p in files]
