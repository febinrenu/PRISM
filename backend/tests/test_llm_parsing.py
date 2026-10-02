"""LLM output parsing — no network required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.llm_extractor import compute_extraction_method, parse_llm_json, _coerce_rule


def test_plain_json():
    parsed = parse_llm_json('{"is_causal": true, "confidence": 0.9}')
    assert parsed == {"is_causal": True, "confidence": 0.9}


def test_fenced_json():
    raw = '```json\n{"is_causal": false, "confidence": 0.4}\n```'
    parsed = parse_llm_json(raw)
    assert parsed is not None and parsed["is_causal"] is False


def test_json_with_prose_wrapper():
    raw = 'Here is the extraction:\n{"is_causal": true, "condition": "if x"} hope that helps!'
    parsed = parse_llm_json(raw)
    assert parsed is not None and parsed["condition"] == "if x"


def test_garbage_returns_none():
    assert parse_llm_json("I cannot extract anything from this.") is None
    assert parse_llm_json("") is None
    assert parse_llm_json("{broken json") is None


def test_coercion_of_sloppy_types():
    rule = _coerce_rule(
        {
            "is_causal": "true",
            "condition": None,
            "action": "null",
            "consequence": "pay fine",
            "actors": "the assessee",
            "thresholds": ["Rs. 5,00,000", ""],
            "confidence": "1.7",
            "reasoning": 42,
        },
        elapsed_ms=100,
    )
    assert rule.is_causal is True
    assert rule.condition is None
    assert rule.action is None  # "null" string → None
    assert rule.consequence == "pay fine"
    assert rule.actors == ["the assessee"]  # str → single-item list
    assert rule.thresholds == ["Rs. 5,00,000"]  # empties dropped
    assert rule.confidence == 1.0  # clamped
    assert rule.reasoning == "42"


def test_extraction_method_matrix():
    assert compute_extraction_method(True, True) == "both"
    assert compute_extraction_method(False, True) == "llm"
    assert compute_extraction_method(True, False) == "conflict"
    assert compute_extraction_method(False, False) == "rule_based"
    assert compute_extraction_method(True, None) == "failed"  # parse failure
