"""
Run manifests: a JSON record of everything needed to reproduce a run.

Every evaluation, extraction batch and experiment writes one to
data/runs/{run_id}/manifest.json: the git commit, package versions, PRISM
format versions, the LLM model digests that were actually used, seeds and the
run's own configuration.
"""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from config import BASE_DIR, OLLAMA_URL
from prism_version import versions

RUNS_DIR = BASE_DIR / "data" / "runs"

_PACKAGES = [
    "fastapi", "pydantic", "numpy", "scipy", "pandas", "torch", "transformers",
    "sentence-transformers", "spacy", "mesa", "chromadb", "lime", "PyMuPDF",
    "scikit-learn", "httpx",
]


def git_info() -> dict:
    repo = BASE_DIR.parent

    def _git(*args: str) -> Optional[str]:
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


def package_versions() -> dict:
    found = {}
    for name in _PACKAGES:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return found


def ollama_digests(timeout: float = 3.0) -> dict:
    """{model_name: digest} for every locally installed Ollama model, or {}
    when Ollama is not reachable. Model tags can be re-pointed; digests can't."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError:
        return {}
    return {m.get("name"): m.get("digest") for m in r.json().get("models", [])}


def config_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def new_run_id(kind: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{kind}-{stamp}-{uuid.uuid4().hex[:6]}"


def build_manifest(kind: str, config: Optional[dict] = None, seeds: Optional[list[int]] = None,
                   run_id: Optional[str] = None, extra: Optional[dict[str, Any]] = None) -> dict:
    config = config or {}
    return {
        "run_id": run_id or new_run_id(kind),
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": git_info(),
        "formats": versions(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": package_versions(),
        "ollama_models": ollama_digests(),
        "seeds": seeds or [],
        "config": config,
        "config_sha256": config_hash(config),
        **(extra or {}),
    }


def write_manifest(manifest: dict) -> Path:
    run_dir = RUNS_DIR / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path
