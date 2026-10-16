"""
The JSON schema of an extraction answer, for constrained decoding.

The prompt describes the answer; JSON mode only guarantees *some* JSON. With
a schema the decoder can only produce answers of the right shape, which
matters most for small models (a 2B model asked for JSON copies the prompt's
template literally). Two variants:

    strict   every field present, nullable where optional, no other fields
             (OpenAI-style strict structured outputs: Groq's GPT-OSS models)
    lenient  only the fields a rule or effect cannot do without are required
             (grammar-constrained decoding in Ollama; best-effort providers)

An effect is one flat object rather than a union per kind: the extractor
drops null fields and validates the rest against the typed effect of its
kind (models.rules), so both shapes reach the same validation.
"""
import hashlib
import json

MODALITIES = ["obligation", "prohibition", "permission", "power", "deeming", "definition"]
EFFECT_KINDS = ["slab_row", "rebate", "standard_deduction", "surcharge_band", "surcharge_cap", "cess",
                "penalty", "fee", "interest", "tds", "advance_tax", "due_date"]

_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}

_EFFECT_FIELDS = {
    "kind": {"type": "string", "enum": EFFECT_KINDS},
    "lower": _NUM, "upper": _NUM, "rate": _NUM,
    "max_income": _NUM, "max_rebate": _NUM, "marginal_relief": {"type": ["boolean", "null"]},
    "amount": _NUM, "threshold": _NUM, "max_rate": _NUM,
    "per_day": _NUM, "rate_per_month": _NUM, "max_amount": _NUM, "days": {"type": ["integer", "null"]},
    "regime": {"type": ["string", "null"], "enum": ["old", "new", "both", None]},
    "age_band": {"type": ["string", "null"], "enum": ["below_60", "60_to_80", "80_plus", "all", None]},
    "applies_to_ay": _STR, "trigger": _STR, "description": _STR,
    "quote": {"type": "string"},
}

_RULE_FIELDS = {
    "modality": {"type": "string", "enum": MODALITIES},
    "subject": _STR,
    "agent_class": _STR,
    "conditions": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"quote": {"type": "string"}, "negated": {"type": "boolean"}},
        "required": ["quote", "negated"]}},
    "action": _STR,
    "consequence": _STR,
    "exceptions": {"type": "array", "items": {"type": "string"}},
    "cross_refs": {"type": "array", "items": {"type": "string"}},
}


def answer_schema(strict: bool) -> dict:
    effect = {"type": "object", "additionalProperties": False, "properties": dict(_EFFECT_FIELDS),
              "required": list(_EFFECT_FIELDS) if strict else ["kind", "quote"]}
    rule_props = {**_RULE_FIELDS, "effects": {"type": "array", "items": effect}}
    rule = {"type": "object", "additionalProperties": False, "properties": rule_props,
            "required": list(rule_props) if strict else ["modality", "effects"]}
    return {"type": "object", "additionalProperties": False,
            "properties": {"rules": {"type": "array", "items": rule}}, "required": ["rules"]}


def fingerprint(schema: dict) -> str:
    """Short stable id of a schema (enters the cache key)."""
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:12]
