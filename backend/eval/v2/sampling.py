"""
Frozen evaluation sets, drawn at random from every provision of the corpus.

Unlike the v1 gold sets (seeded from the system's own output), items are
sampled from all extraction units, stratified by statute × provision kind ×
length, with a fixed seed. No system output is consulted. The manifest
records each item's offsets and text hash plus the hash of every source PDF,
so a set can never silently change; `verify_manifest` checks it.

Sets:
    test    300 provisions, 50 per statute — scored once, at the end
    dev     100 provisions — prompt and threshold development
    pilot    30 provisions drawn from dev — annotation-guideline pilot
"""
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from config import BASE_DIR
from pipeline.extraction.units import build_units
from pipeline.statute.corpus import get_source, sha256_file
from prism_version import EVAL_SET_VERSION

EVAL_DIR = BASE_DIR / "data" / "eval" / "v2"
MANIFEST = EVAL_DIR / "manifest.json"

# One version per statute; the enacted Income-tax Act 2025 is left out
# because it duplicates the amended text almost verbatim.
STATUTES = [
    ("ITA2025", "amended_fa2026"),
    ("CGST2017", "consolidated"),
    ("COW2019", "enacted"),
    ("DPDP2023", "enacted"),
    ("FA2023", "enacted"),
    ("FA2025", "enacted"),
]
PER_STATUTE_TEST = 50
PER_STATUTE_DEV = 17
PILOT = 30
MIN_CHARS = 60
SEED = 20261003


def _kind_group(u) -> str:
    if u.section.startswith("Schedule"):
        return "schedule"
    return {"section": "section", "subsection": "subsection", "clause": "clause", "subclause": "clause",
            "item": "clause", "subitem": "clause", "proviso": "proviso", "explanation": "explanation",
            "table_row": "table", "text": "other", "quoted": "other"}.get(u.kind, "other")


def _length_band(n: int) -> str:
    return "short" if n < 300 else "medium" if n < 1200 else "long"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def draw(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    items = {"test": [], "dev": []}
    sources = {}
    for statute, version in STATUTES:
        src = get_source(statute, version)
        sources[f"{statute}/{version}"] = sha256_file(src.pdf_path)
        units = [u for u in build_units(statute, version) if len(u.text.strip()) >= MIN_CHARS]
        strata = defaultdict(list)
        for u in units:
            strata[(_kind_group(u), _length_band(len(u.text)))].append(u)
        # Proportional allocation with at least one item per non-empty stratum.
        need = PER_STATUTE_TEST + PER_STATUTE_DEV
        total = sum(len(v) for v in strata.values())
        alloc = {k: max(1, round(need * len(v) / total)) for k, v in strata.items()}
        while sum(alloc.values()) > need:
            k = max(alloc, key=lambda k: alloc[k])
            alloc[k] -= 1
        while sum(alloc.values()) < need:
            k = max(strata, key=lambda k: len(strata[k]) - alloc[k])
            alloc[k] += 1
        chosen = []
        for k in sorted(strata):
            pool = sorted(strata[k], key=lambda u: u.unit_id)
            chosen.extend((k, u) for u in rng.sample(pool, min(alloc[k], len(pool))))
        rng.shuffle(chosen)
        for i, (k, u) in enumerate(chosen):
            split = "test" if i < PER_STATUTE_TEST else "dev"
            items[split].append({
                "item_id": f"{split}-{statute}-{i:03d}", "statute": f"{statute}/{version}",
                "unit_id": u.unit_id, "path": u.path, "kind": u.kind, "stratum": "/".join(k),
                "start": u.start, "end": u.end, "chars": len(u.text), "text_sha256": _sha(u.text),
            })
    pilot = rng.sample(sorted(items["dev"], key=lambda it: it["item_id"]), PILOT)
    return {
        "eval_set_version": EVAL_SET_VERSION, "seed": seed, "statutes": [f"{s}/{v}" for s, v in STATUTES],
        "source_sha256": sources, "min_chars": MIN_CHARS,
        "sizes": {"test": len(items["test"]), "dev": len(items["dev"]), "pilot": len(pilot)},
        "test": items["test"], "dev": items["dev"], "pilot": [it["item_id"] for it in pilot],
    }


def write(manifest: dict, path: Path = MANIFEST, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; evaluation sets are frozen (pass overwrite only before annotation starts)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return path


def load(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def item_text(item: dict) -> str:
    from pipeline.extraction.units import load_statute
    statute, version = item["statute"].split("/")
    _, text = load_statute(statute, version)
    return text[item["start"]:item["end"]]


def verify_manifest(manifest: dict) -> list[str]:
    """Problems found (empty = every item's text matches its recorded hash)."""
    problems = []
    for key, sha in manifest["source_sha256"].items():
        statute, version = key.split("/")
        if sha256_file(get_source(statute, version).pdf_path) != sha:
            problems.append(f"source PDF changed: {key}")
    for split in ("test", "dev"):
        for it in manifest[split]:
            if _sha(item_text(it)) != it["text_sha256"]:
                problems.append(f"text changed: {it['item_id']}")
    return problems
