"""Simulation rule translation — threshold parsing and actor mapping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.rules import (
    ALL_AGENT_TYPES,
    BUSINESS_TYPES,
    HOUSEHOLD_TYPES,
    map_actors_to_agent_types,
    parse_threshold_string,
)


def test_rupee_amounts():
    assert parse_threshold_string("Rs. 5,00,000") == {"kind": "amount", "value": 500000.0}
    assert parse_threshold_string("₹ 1,000") == {"kind": "amount", "value": 1000.0}
    assert parse_threshold_string("INR 2500.50") == {"kind": "amount", "value": 2500.5}


def test_lakh_crore_units():
    assert parse_threshold_string("5 lakh") == {"kind": "amount", "value": 500000.0}
    assert parse_threshold_string("Rs. 2 crore") == {"kind": "amount", "value": 20000000.0}
    assert parse_threshold_string("1.5 crores") == {"kind": "amount", "value": 15000000.0}


def test_percentages():
    assert parse_threshold_string("20%") == {"kind": "percent", "value": 20.0}
    assert parse_threshold_string("12.5 per cent") == {"kind": "percent", "value": 12.5}


def test_durations_normalized_to_days():
    assert parse_threshold_string("30 days") == {"kind": "duration", "value": 30.0}
    assert parse_threshold_string("6 months") == {"kind": "duration", "value": 180.0}
    assert parse_threshold_string("2 years") == {"kind": "duration", "value": 730.0}


def test_unparseable_returns_none():
    assert parse_threshold_string("a reasonable period") is None
    assert parse_threshold_string("") is None
    # A bare "rupees," without digits must not crash (regression: empty match group)
    assert parse_threshold_string("rupees, as notified") is None


def test_actor_mapping():
    assert map_actors_to_agent_types(["every company"]) == sorted(BUSINESS_TYPES)
    assert map_actors_to_agent_types(["the assessee"]) == sorted(HOUSEHOLD_TYPES)
    assert set(map_actors_to_agent_types(["employer", "employee"])) == set(
        BUSINESS_TYPES + HOUSEHOLD_TYPES
    )
    assert map_actors_to_agent_types(["unknown party"]) == ALL_AGENT_TYPES
    assert map_actors_to_agent_types([]) == ALL_AGENT_TYPES


# ─── Module-C template translator ──────────────────────────────────────────────

def test_template_extractors_parse_params():
    """The extractors are pure (no embeddings) — verify they pull sane params."""
    from simulation.templates import TEMPLATES

    by_key = {t.key: t for t in TEMPLATES}
    # percentage tax above a threshold (numeric parser handles digit forms)
    p = by_key["percentage_tax_above_threshold"].extract(
        "tax at 30% on income exceeding Rs. 10,00,000", {}
    )
    assert p["rate_percent"] == 30.0
    assert p["threshold_value"] == 1_000_000.0
    # per-day penalty annualizes
    d = by_key["per_day_penalty"].extract("penalty of Rs. 200 for every day of default", {})
    assert d["base_penalty_amount"] == 200.0 * 90.0
    # filing deadline → duration in days
    f = by_key["filing_deadline"].extract("shall furnish the return within 30 days", {})
    assert f["threshold_kind"] == "duration" and f["threshold_value"] == 30.0


def test_template_semantic_match_optional():
    """Semantic matching needs the MiniLM embedder; skip if the model can't load
    (offline CI without the cached model)."""
    import pytest
    try:
        from simulation.templates import match_template
        m = match_template("tax shall be charged at 30% on income exceeding 10 lakh rupees")
    except Exception as e:
        pytest.skip(f"embedder unavailable: {e}")
    assert m is not None
    assert m.key == "percentage_tax_above_threshold"
    assert 0.0 <= m.score <= 1.0
