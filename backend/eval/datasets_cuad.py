"""
Public legal-clause dataset loader for the eval harness.

Intended dataset was CUAD, but its QA-formatted release is now a HuggingFace
*script* dataset, which `datasets` 5.x no longer supports, and the maintained
`theatticusproject/cuad` repo ships raw contract PDFs (no clause labels). So we
use **LEDGAR** (via the `lex_glue` benchmark) instead — a large, expert-labeled
corpus of ~80k contract-provision clauses across 100 categories, hosted as clean
parquet that loads reliably. Same spirit as the CUAD plan (real, public,
human-labeled legal clauses, out-of-domain from Indian statute), and it maps
naturally onto PRISM's tasks:

  1. is_causal (binary): positive when the clause's LEDGAR category imposes a
     duty / penalty / restriction (see _OBLIGATION_CATEGORIES); negative for
     boilerplate/definitional provisions (_BOILERPLATE_CATEGORIES). This drives
     the causal/obligation-detection benchmark.
  2. entity_label: a coarse category → PRISM-entity mapping for a light NER check.

Cached to backend/data/eval/ledgar_eval.json (one network hit). On any failure
the caller falls back to a tiny built-in synthetic set so the harness still runs.
"""
import json
from typing import Optional

from config import BASE_DIR

_CACHE = BASE_DIR / "data" / "eval" / "ledgar_eval.json"

# LEDGAR provision categories that carry a duty/penalty/restriction (positives).
_OBLIGATION_CATEGORIES = {
    "Compliance With Laws", "Indemnifications", "Indemnity", "Terminations",
    "Confidentiality", "Insurances", "Payments", "Tax Withholdings", "Withholdings",
    "Forfeitures", "Remedies", "Non-Disparagement", "Duties", "Anti-Corruption Laws",
    "Liens", "Specific Performance", "Taxes", "Fees", "Enforcements", "Sanctions",
}
# Boilerplate / definitional provisions (negatives).
_BOILERPLATE_CATEGORIES = {
    "Definitions", "Defined Terms", "Headings", "Counterparts", "Severability",
    "Entire Agreements", "Governing Laws", "Notices", "Interpretations",
    "Construction", "Titles", "Miscellaneous", "Integration", "Venues",
    "Consent To Jurisdiction", "Submission To Jurisdiction", "Waiver Of Jury Trials",
}
_CATEGORY_TO_ENTITY = {
    "Indemnifications": "PENALTY", "Indemnity": "PENALTY", "Remedies": "PENALTY",
    "Forfeitures": "PENALTY", "Sanctions": "PENALTY",
    "Compliance With Laws": "OBLIGATION", "Duties": "OBLIGATION",
    "Confidentiality": "OBLIGATION", "Insurances": "OBLIGATION",
    "Payments": "THRESHOLD", "Fees": "THRESHOLD", "Taxes": "THRESHOLD",
    "Tax Withholdings": "THRESHOLD",
}


class CUADUnavailable(RuntimeError):
    """Kept name for backward-compat; raised when no public dataset loads."""


def build_cuad_eval(limit: int = 200, force: bool = False) -> list[dict]:
    """Load LEDGAR, derive a balanced obligation-vs-boilerplate eval set, cache,
    and return it. Each item: {text, is_causal, category, entity_label|None}.
    Raises CUADUnavailable on any load failure."""
    if _CACHE.exists() and not force:
        return json.loads(_CACHE.read_text(encoding="utf-8"))

    try:
        from datasets import load_dataset
    except ImportError as e:
        raise CUADUnavailable("`datasets` not installed") from e

    try:
        ds = load_dataset("lex_glue", "ledgar", split="train")
        names = ds.features["label"].names
    except Exception as e:
        raise CUADUnavailable(f"could not load LEDGAR: {e}") from e

    half = max(1, limit // 2)
    pos: list[dict] = []
    neg: list[dict] = []
    for row in ds:
        if len(pos) >= half and len(neg) >= half:
            break
        category = names[row["label"]]
        text = (row.get("text") or "").strip()
        if len(text) < 40:
            continue
        if category in _OBLIGATION_CATEGORIES and len(pos) < half:
            pos.append({"text": text[:1000], "is_causal": True, "category": category,
                        "entity_label": _CATEGORY_TO_ENTITY.get(category)})
        elif category in _BOILERPLATE_CATEGORIES and len(neg) < half:
            neg.append({"text": text[:1000], "is_causal": False, "category": category,
                        "entity_label": None})

    items = pos + neg
    if not items:
        raise CUADUnavailable("LEDGAR produced no usable clauses")

    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


# A tiny built-in fallback so the harness (and its charts) still runs offline.
_SYNTHETIC = [
    {"text": "If the assessee fails to furnish the return within the prescribed time, "
             "interest shall be payable at one per cent per month.",
     "is_causal": True, "category": "penalty", "entity_label": "PENALTY"},
    {"text": "Every company shall maintain proper books of account at its registered office.",
     "is_causal": True, "category": "obligation", "entity_label": "OBLIGATION"},
    {"text": "The Board may make rules for the purposes of this Act.",
     "is_causal": False, "category": "definition", "entity_label": None},
    {"text": "This Act may be called the Income-tax Act.",
     "is_causal": False, "category": "title", "entity_label": None},
    {"text": "Where the turnover exceeds five crore rupees, the person shall be liable "
             "to a penalty of ten thousand rupees.",
     "is_causal": True, "category": "penalty", "entity_label": "THRESHOLD"},
    {"text": "A senior citizen is entitled to a deduction under this section.",
     "is_causal": False, "category": "right", "entity_label": "RIGHT"},
]


def load_eval_set(limit: int = 200) -> tuple[list[dict], str]:
    """Return (items, source) — LEDGAR if available, else the synthetic fallback."""
    try:
        return build_cuad_eval(limit=limit), "ledgar"
    except CUADUnavailable:
        return list(_SYNTHETIC), "synthetic"
