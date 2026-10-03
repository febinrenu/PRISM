"""
Content-addressed, append-only cache of raw model outputs.

The key covers everything that can change an output — provider, model,
prompt text, prompt version, temperature and seed — so a cache hit is
always the answer to exactly this request. Entries are never overwritten;
paper runs can be frozen by copying the referenced entries.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from config import BASE_DIR

CACHE_DIR = BASE_DIR / "data" / "cache" / "llm"


def key(*, provider: str, model: str, prompt: str, temperature: float, seed: int, prompt_version: int) -> str:
    blob = json.dumps({"provider": provider, "model": model, "prompt": prompt,
                       "temperature": round(float(temperature), 4), "seed": int(seed),
                       "prompt_version": int(prompt_version)}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _path(k: str) -> Path:
    return CACHE_DIR / k[:2] / f"{k}.json"


def get(k: str) -> Optional[dict]:
    p = _path(k)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def put(k: str, payload: dict) -> None:
    p = _path(k)
    if p.exists():
        return  # append-only
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
