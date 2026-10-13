"""
Batch extraction on a GPU host (Kaggle, Colab) for open-weight models.

Hosted free tiers limit how many requests a study can make; an open-weight
model run in batch has no such limit and its pinned weights make every output
reproducible. The study never calls a "batch" system live:

    python -m cli batch-export --system llama-3.1-8b --scope experiment,test,dev
        → data/batch/llama-3.1-8b.requests.jsonl
    (run training/kaggle_batch_extract.ipynb on the file)
    python -m cli batch-import data/batch/llama-3.1-8b.responses.jsonl
        → answers stored in the cache under the same keys the pipeline uses

after which `cli experiment`, `cli eval-run` and `cli reproduce` work for the
system exactly as for any other, reading only the cache.

Requests file: one header line {"system", "model", "max_tokens", "prompt_version"}
then one line per request {"key", "prompt", "temperature", "seed"}.
Responses file: one line per request {"key", "text", "model_version"}.
"""
import json
from pathlib import Path
from typing import Iterable

from config import BASE_DIR
from pipeline.extraction import cache, prompts
from pipeline.extraction.backends import SYSTEMS

BATCH_DIR = BASE_DIR / "data" / "batch"


def _key(system, prompt: str, temperature: float, seed: int) -> str:
    return cache.key(provider=system.provider, model=system.model, prompt=prompt, temperature=temperature,
                     seed=seed, prompt_version=prompts.EXTRACTION_PROMPT_VERSION,
                     options=dict(system.options) or None)


def _experiment_units() -> Iterable:
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import PROVISION_SETS, units_for
    seen = set()
    for spec in PROVISION_SETS.values():
        units = build_units(*spec["statute"])
        for path in spec["targets"].values():
            for u in units_for(path, units):
                if (u.statute, u.unit_id) not in seen:
                    seen.add((u.statute, u.unit_id))
                    yield u


def _split_units(split: str) -> Iterable:
    from eval.v2 import runs
    for it in runs.split_items(split):
        yield runs.item_unit(it)


def requests(system_name: str, scopes: list[str], k: int = 4) -> list[dict]:
    """Every request the pipeline would make for `system_name`: greedy plus
    k self-consistency samples for the experiment's provisions, greedy only
    for evaluation splits. Requests already answered in the cache are left
    out."""
    from pipeline.extraction.consistency import SAMPLE_TEMPERATURE
    system = SYSTEMS[system_name]
    out, seen = [], set()

    def add(unit, temperature: float, seed: int):
        prompt = prompts.render(unit.text, unit.context)
        key = _key(system, prompt, temperature, seed)
        if key in seen or cache.get(key) is not None:
            return
        seen.add(key)
        out.append({"key": key, "prompt": prompt, "temperature": temperature, "seed": seed})

    for scope in scopes:
        if scope == "experiment":
            for u in _experiment_units():
                add(u, 0.0, 0)
                for s in range(1, k + 1):
                    add(u, SAMPLE_TEMPERATURE, s)
        else:
            for u in _split_units(scope):
                add(u, 0.0, 0)
    return out


def export(system_name: str, scopes: list[str], k: int = 4, path: Path | None = None) -> tuple[Path, int]:
    system = SYSTEMS[system_name]
    reqs = requests(system_name, scopes, k)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = path or BATCH_DIR / f"{system_name}.requests.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"system": system.name, "model": system.model, "max_tokens": system.max_tokens,
                             "prompt_version": prompts.EXTRACTION_PROMPT_VERSION,
                             "options": dict(system.options)}) + "\n")
        for r in reqs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path, len(reqs)


def import_responses(path: Path, requests_path: Path | None = None) -> dict:
    """Store answers in the cache. Every key must belong to the requests file
    of the same system, so answers cannot be filed under another system or
    prompt."""
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    header, rows = (lines[0], lines[1:]) if lines and "system" in lines[0] else ({}, lines)
    system_name = header.get("system")
    if system_name is None:
        raise ValueError("responses file has no header line naming the system")
    system = SYSTEMS[system_name]
    req_path = requests_path or BATCH_DIR / f"{system_name}.requests.jsonl"
    req = {json.loads(l)["key"]: json.loads(l) for l in
           req_path.read_text(encoding="utf-8").splitlines()[1:] if l.strip()}
    stored = skipped = unknown = 0
    for row in rows:
        r = req.get(row["key"])
        if r is None:
            unknown += 1
            continue
        if cache.get(row["key"]) is not None:
            skipped += 1
            continue
        cache.put(row["key"], {"text": row["text"], "system": system.name, "model": system.model,
                               "options": dict(system.options), "model_version": row.get("model_version"),
                               "elapsed_ms": row.get("elapsed_ms", 0), "temperature": r["temperature"],
                               "seed": r["seed"], "prompt_version": prompts.EXTRACTION_PROMPT_VERSION,
                               "batch": True})
        stored += 1
    return {"system": system_name, "stored": stored, "already_cached": skipped, "unknown_keys": unknown,
            "requests": len(req)}
