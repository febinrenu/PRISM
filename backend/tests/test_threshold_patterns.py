"""Threshold and money/rate detection: the "₹" and "%" edge cases that a
plain \b word boundary misses, plus WHERE-rules keeping their consequence."""
import pytest

from pipeline.causal_detector import detect_causal_patterns
from pipeline.legal_ner import extract_entities


def _thresholds(text):
    return [e.text for e in extract_entities(text) if e.label == "THRESHOLD"]


@pytest.mark.parametrize("text, expected", [
    ("A fee of ₹50,000 shall be paid.", "₹50,000"),
    ("a fee of ₹ 5,00,000 is payable", "₹ 5,00,000"),
    ("tax at 20% of the income", "20%"),
    ("interest at 1.5 per cent for every month", "1.5 per cent"),
    ("a sum of Rs. 5,00,000 shall be deposited", "Rs. 5,00,000"),
    ("a sum of Rs 2,50,000 is exempt", "Rs 2,50,000"),
    ("income of 2.5 lakh rupees", "2.5 lakh"),
    ("INR 10 crore or more", "INR 10 crore"),
])
def test_money_and_rates_are_detected(text, expected):
    assert expected in _thresholds(text)


def test_threshold_offsets_are_exact():
    text = "Where the turnover exceeds ₹ 2 crore, a penalty of 20% applies."
    for e in extract_entities(text):
        assert text[e.start:e.end] == e.text


def test_where_rule_keeps_modal_negation_and_consequence():
    text = ("Where the assessee incurs any expenditure by way of such payments, "
            "then the expenditure shall not be allowed as deduction.")
    [p] = detect_causal_patterns(text, "c1")
    assert "shall not be allowed as deduction" in p.action_span
    assert text[p.action_start:p.action_end] == p.action_span
    assert text[p.condition_start:p.condition_end] == p.condition_span


def test_money_rate_signal_raises_risk_tier():
    text = "If the turnover exceeds 10% of the limit, the dealer shall register."
    [p] = detect_causal_patterns(text, "c2")
    assert p.risk_tier == "HIGH"
