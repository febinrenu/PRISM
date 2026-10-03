"""
Annotation API for the human evaluation sets.

    GET  /api/annotate/sets                     pilot / dev / test with my progress
    GET  /api/annotate/sets/{split}             items in a set with my status
    GET  /api/annotate/items/{item_id}          text, context, my annotation
    PUT  /api/annotate/items/{item_id}          save my annotation (draft or done)
    GET  /api/annotate/effect-kinds             effect kinds and their fields

Blind by design: an annotator only ever sees the provision and their own
work — never a model's output or another annotator's labels.
"""
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter, ValidationError

from auth.deps import current_user
from config import BASE_DIR
from models.annotation import GUIDELINE_VERSION, Annotation
from models.rules import Effect

router = APIRouter()
ANNOTATION_DIR = BASE_DIR / "data" / "annotations"
_EFFECT = TypeAdapter(Effect)

EFFECT_FIELDS = {
    "slab_row": ["lower", "upper", "rate", "regime", "age_band", "applies_to_ay"],
    "rebate": ["max_income", "max_rebate", "marginal_relief", "regime", "applies_to_ay"],
    "standard_deduction": ["amount", "regime", "applies_to_ay"],
    "surcharge_band": ["threshold", "rate", "regime", "applies_to_ay"],
    "surcharge_cap": ["max_rate", "regime", "applies_to_ay"],
    "cess": ["rate", "applies_to_ay"],
    "penalty": ["amount", "per_day", "rate", "rate_per_month", "max_amount", "trigger"],
    "fee": ["amount", "per_day", "rate", "max_amount", "trigger"],
    "interest": ["rate", "rate_per_month", "trigger"],
    "tds": ["rate", "description"],
    "advance_tax": ["rate", "description"],
    "due_date": ["days", "description"],
}


@lru_cache(maxsize=1)
def _manifest() -> dict:
    from eval.v2.sampling import load
    return load()


@lru_cache(maxsize=16)
def _statute(key: str) -> tuple[str, dict]:
    from pipeline.extraction.units import build_units, load_statute
    statute, version = key.split("/")
    ast, text = load_statute(statute, version)
    contexts = {u.unit_id: (u.context, u.heading, u.section) for u in build_units(statute, version, ast=ast, text=text)}
    return text, contexts


def _items(split: str) -> list[dict]:
    m = _manifest()
    if split == "pilot":
        dev = {it["item_id"]: it for it in m["dev"]}
        return [dev[i] for i in m["pilot"]]
    if split not in ("dev", "test"):
        raise HTTPException(status_code=404, detail=f"Unknown set {split}")
    return m[split]


def _find(item_id: str) -> dict:
    for split in ("test", "dev"):
        for it in _manifest()[split]:
            if it["item_id"] == item_id:
                return it
    raise HTTPException(status_code=404, detail="Item not found")


def _path(user: dict, item_id: str) -> Path:
    safe_user = "".join(ch for ch in user["id"] if ch.isalnum() or ch in "-_")
    return ANNOTATION_DIR / safe_user / f"{item_id}.json"


def _load(user: dict, item_id: str):
    p = _path(user, item_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _status(user: dict, item_id: str) -> str:
    a = _load(user, item_id)
    return a["status"] if a else "todo"


@router.get("/annotate/sets")
def sets(user: dict = Depends(current_user)):
    out = []
    for split in ("pilot", "dev", "test"):
        items = _items(split)
        statuses = [_status(user, it["item_id"]) for it in items]
        out.append({"set": split, "items": len(items), "done": statuses.count("done"),
                    "draft": statuses.count("draft")})
    return {"sets": out, "guideline_version": GUIDELINE_VERSION}


@router.get("/annotate/sets/{split}")
def set_items(split: str, user: dict = Depends(current_user)):
    return {"set": split, "items": [
        {"item_id": it["item_id"], "statute": it["statute"], "path": it["path"], "kind": it["kind"],
         "chars": it["chars"], "status": _status(user, it["item_id"])}
        for it in _items(split)]}


@router.get("/annotate/items/{item_id}")
def item(item_id: str, user: dict = Depends(current_user)):
    it = _find(item_id)
    text, contexts = _statute(it["statute"])
    body = text[it["start"]:it["end"]]
    context, heading, section = contexts.get(it["unit_id"], ("", "", ""))
    return {"item": it, "text": body, "context": context, "heading": heading, "section": section,
            "annotation": _load(user, item_id), "effect_fields": EFFECT_FIELDS}


@router.put("/annotate/items/{item_id}")
def save(item_id: str, ann: Annotation, user: dict = Depends(current_user)):
    it = _find(item_id)
    n = it["end"] - it["start"]
    for s in ann.spans():
        if s.end > n:
            raise HTTPException(status_code=422, detail=f"Span {s.start}-{s.end} is outside the text (length {n}).")
    errors = []
    for i, r in enumerate(ann.rules):
        for j, e in enumerate(r.effects):
            payload = {"kind": e.kind, **{k: v for k, v in e.fields.items() if v not in (None, "")}}
            try:
                _EFFECT.validate_python(payload)
            except ValidationError as ex:
                errors.append(f"rule {i + 1}, effect {j + 1} ({e.kind}): {ex.errors()[0]['msg']}")
    if errors and ann.status == "done":
        raise HTTPException(status_code=422, detail="; ".join(errors))
    if ann.status == "done" and not ann.no_rule and not ann.rules:
        raise HTTPException(status_code=422, detail="Add at least one rule, or mark the provision as stating no rule.")
    ann.item_id = item_id
    ann.annotator_id = user["id"]
    ann.annotator_name = user.get("name") or user.get("email", "")
    ann.updated_at = datetime.now(timezone.utc).isoformat()
    p = _path(user, item_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(ann.model_dump_json(indent=1), encoding="utf-8")
    tmp.replace(p)
    return {"saved": True, "status": ann.status, "warnings": errors}


@router.get("/annotate/effect-kinds")
def effect_kinds():
    return EFFECT_FIELDS
