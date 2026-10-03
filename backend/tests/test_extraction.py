"""Extraction building blocks: quantities, grounding, the rule-based slab
reader, schedule assembly and the expert-vs-extracted harness."""
import pytest

from models.rules import LegalRule, Provenance, Rebate as RebateEffect, SlabRow
from pipeline.extraction.grounding import ground
from pipeline.extraction.rule_based import _slab_from_line
from pipeline.quantities import extract_quantities, words_to_number
from simulation.rac import gold
from simulation.translate.assemble import assemble, build_schedule

L = 100_000


@pytest.mark.parametrize("phrase, value", [
    ("twelve hundred thousand", 1_200_000), ("seven hundred thousand", 700_000),
    ("two lakh fifty thousand", 250_000), ("one crore twenty lakh", 12_000_000),
    ("twenty-five thousand", 25_000), ("one-half", 0.5), ("one hundred", 100),
])
def test_number_words(phrase, value):
    assert words_to_number(phrase) == value


@pytest.mark.parametrize("text, kind, value, comparator, upper, per", [
    ("a fee of ₹5,00,000 shall", "amount_inr", 500_000, None, None, None),
    ("Rs. 50 crores", "amount_inr", 5e8, None, None, None),
    ("fifty thousand rupees", "amount_inr", 50_000, None, None, None),
    ("exceeds Rs. 3,00,000 but does not exceed Rs. 7,00,000", "amount_inr", 300_000, "range", 700_000, None),
    ("one hundred rupees for every day", "amount_inr", 100, None, None, "day"),
    ("subject to a maximum amount of five thousand rupees", "amount_inr", 5_000, "le", None, None),
    ("at the rate of ten per cent. of", "rate_pct", 10, None, None, None),
    ("within thirty days", "duration_days", 30, None, None, None),
])
def test_quantities(text, kind, value, comparator, upper, per):
    q = extract_quantities(text)[0]
    assert (q.kind, q.value, q.comparator, q.upper, q.per) == (kind, value, comparator, upper, per)
    assert text[q.start:q.end] == q.text


def test_grounding_accepts_real_quotes_and_rejects_invented_ones():
    src = "(2) Where any person fails to furnish the return under sub-section (1), he shall pay a penalty of Rs. 5,000."
    assert ground("he shall pay a penalty of Rs. 5,000", src).method == "exact"
    assert ground("Where any  person FAILS to furnish the return", src).method == "normalised"
    fuzzy = ground("where a person fails to furnish the return under sub section (1)", src)
    assert fuzzy.method == "fuzzy" and src[fuzzy.start:fuzzy.end] == fuzzy.text
    assert ground("the assessee shall be imprisoned for life", src) is None


@pytest.mark.parametrize("line, expected", [
    ("1. | Upto Rs. 4,00,000 | Nil", {"lower": 0.0, "upper": 400_000, "rate": 0.0}),
    ("2. From Rs. 4,00,001 to Rs. 8,00,000 | 5 per cent.", {"lower": 400_000, "upper": 800_000, "rate": 0.05}),
    ("7. Above Rs. 24,00,000 | 30 per cent.", {"lower": 2_400_000, "upper": None, "rate": 0.30}),
    ("(2) where the total income exceeds Rs. 2,50,000 but does not exceed Rs. 5,00,000 | 5 per cent. of the amount",
     {"lower": 250_000, "upper": 500_000, "rate": 0.05}),
    ("Sl. No. | Total income | Rate of tax", None),
])
def test_rule_based_slab_lines(line, expected):
    assert _slab_from_line(line) == expected


def _rows(*bands):
    return [SlabRow(lower=lo, upper=hi, rate=r) for lo, hi, r in bands]


def test_schedule_validation():
    ok, why = build_schedule(_rows((0, 3 * L, 0), (3 * L, 7 * L, .05), (7 * L, None, .1)))
    assert why is None and len(ok) == 3
    assert build_schedule(_rows((1 * L, 3 * L, 0), (3 * L, None, .1)))[1].startswith("schedule does not start")
    assert "gap or overlap" in build_schedule(_rows((0, 3 * L, 0), (4 * L, None, .1)))[1]
    assert build_schedule(_rows((0, 3 * L, 0), (3 * L, 7 * L, .1)))[1] == "no open top band"
    assert build_schedule(_rows((0, 3 * L, .2), (3 * L, None, .1)))[1] == "rates decrease with income"


def _rule(*effects):
    return LegalRule(rule_id="r", statute="T", provision="p", modality="obligation",
                     effects=list(effects), provenance=Provenance(extractor="test"))


def test_assembler_scopes_rows_by_assessment_year_and_flags_missing_targets():
    G = gold.build_gold()
    both_years = _rule(
        *[SlabRow(lower=lo, upper=hi, rate=r, applies_to_ay="2024-25") for lo, hi, r in
          ((0, 3 * L, 0), (3 * L, 6 * L, .05), (6 * L, None, .1))],
        *[SlabRow(lower=lo, upper=hi, rate=r, applies_to_ay="2025-2026") for lo, hi, r in
          ((0, 3 * L, 0), (3 * L, 7 * L, .05), (7 * L, None, .1))],
    )
    res = assemble({"p": [both_years]}, {"new.slabs": "p", "new.rebate": "p"}, G["2025-26"], "2025-26")
    assert [s.upper for s in res.params.regimes["new"].slabs["below_60"]] == [3 * L, 7 * L, None]
    assert not res.complete and [r.target for r in res.review] == ["new.rebate"]


def test_assembler_rebate_and_expert_identity():
    G = gold.build_gold()
    reb = _rule(RebateEffect(max_income=12 * L, max_rebate=60_000, marginal_relief=True))
    res = assemble({"p": [reb]}, {"new.rebate": "p"}, G["2026-27"], "2026-27")
    assert res.complete and res.params.diff(G["2026-27"]) == []


def test_harness_rule_baseline_on_fa2020_new_regime():
    from pathlib import Path
    if not (Path(__file__).parent.parent / "data" / "corpus" / "FA2020" / "enacted" / "ast.json").exists():
        pytest.skip("FA2020 not parsed")
    from simulation.experiment.harness import run_set
    r = run_set("FA2020_new_regime", "rules")
    assert r["complete"] and r["comparisons"]["new:below_60"]["exact_match_rate"] == 1.0
