"""
Personal income-tax calculator against hand-computed statutory examples,
property tests, and the gold tables checked row by row against the corpus.
"""
import json
import re
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from simulation.rac import gold
from simulation.rac.pit import liability, optimal_regime, round_to_10
from simulation.rac.types import PITParams

G = gold.build_gold()
L = 100_000


def tax(ay, regime, salary=0.0, other=0.0, deductions=0.0, age="below_60"):
    return float(liability(G[ay], regime, salary, other, deductions, age).total_tax[0])


# ── worked examples (computed by hand from the statute) ─────────────────────

@pytest.mark.parametrize("ay, regime, salary, other, ded, age, expected, why", [
    # FA 2025 new regime: ₹12 lakh after standard deduction is fully rebated.
    ("2026-27", "new", 12.75 * L, 0, 0, "below_60", 0,
     "TI 12,00,000 → slab tax 60,000 → rebate 60,000"),
    # Marginal relief above ₹12 lakh: tax limited to the income above it.
    ("2026-27", "new", 13 * L, 0, 0, "below_60", 26_000,
     "TI 12,25,000 → slab 63,750 → capped at 25,000 → +4% cess"),
    ("2026-27", "new", 16.75 * L, 0, 0, "below_60", 124_800,
     "TI 16,00,000 → 20,000 + 40,000 + 60,000 → +cess"),
    # FA 2023 new regime: ₹7 lakh rebate, marginal relief just above.
    ("2024-25", "new", 7.5 * L, 0, 0, "below_60", 0, "TI 7,00,000 → 25,000 rebated"),
    ("2024-25", "new", 7.6 * L, 0, 0, "below_60", 10_400, "TI 7,10,000 → 26,000 capped at 10,000 → +cess"),
    # Old regime with Chapter VI-A deductions.
    ("2023-24", "old", 10 * L, 0, 1.5 * L, "below_60", 75_400,
     "TI 8,00,000 → 12,500 + 60,000 → +cess"),
    # FA 2020 concessional regime: no standard deduction, no Chapter VI-A.
    ("2023-24", "new", 10 * L, 0, 1.5 * L, "below_60", 78_000,
     "TI 10,00,000 → 12,500 + 25,000 + 37,500 → +cess"),
    # Old regime rebate is a cliff (no marginal relief).
    ("2022-23", "old", 0, 5 * L, 0, "below_60", 0, "TI 5,00,000 → 12,500 rebated"),
    ("2022-23", "old", 0, 5.0001 * L, 0, "below_60", 13_000,
     "TI 5,00,010 → 12,500.5 tax, no rebate → +cess → rounded"),
    # Age bands.
    ("2022-23", "old", 0, 5 * L, 0, "80_plus", 0, "exempt up to 5 lakh for 80+"),
    ("2022-23", "old", 0, 5 * L, 0, "60_to_80", 0, "10,000 tax fully rebated"),
    ("2022-23", "old", 0, 12 * L, 0, "80_plus", 166_400,
     "0 + 1,00,000 + 60,000 = 1,60,000 → +cess"),
    # Surcharge marginal relief just above ₹50 lakh.
    ("2024-25", "old", 50.6 * L, 0, 0, "below_60", 1_375_400,
     "TI 50,10,000 → tax 13,15,500; surcharge capped at 7,000 → 13,22,500 + cess"),
])
def test_worked_examples(ay, regime, salary, other, ded, age, expected, why):
    assert tax(ay, regime, salary, other, ded, age) == pytest.approx(expected), why


def test_components_add_up():
    lia = liability(G["2026-27"], "new", np.array([13 * L, 30 * L, 80 * L]))
    pre_round = lia.tax_on_income - lia.rebate + lia.surcharge + lia.cess
    np.testing.assert_allclose(lia.total_tax, round_to_10(pre_round))
    assert np.all(lia.rebate <= lia.tax_on_income)


def test_new_regime_surcharge_never_exceeds_25_percent():
    for ay in ("2024-25", "2025-26", "2026-27", "2027-28"):
        lia = liability(G[ay], "new", np.array([6 * 10**8]))
        assert lia.surcharge[0] == pytest.approx(0.25 * lia.tax_on_income[0])
    old = liability(G["2026-27"], "old", np.array([6 * 10**8]))
    assert old.surcharge[0] == pytest.approx(0.37 * old.tax_on_income[0])


def test_optimal_regime_and_defaults():
    choice, best = optimal_regime(G["2026-27"], np.array([12.75 * L, 30 * L]), deductions=np.array([0, 5 * L]))
    assert choice[0] == "new" and best[0] == 0
    # AY 2020-21 offers only the old regime.
    choice, _ = optimal_regime(G["2020-21"], np.array([8 * L]))
    assert choice[0] == "old"


# ── properties ──────────────────────────────────────────────────────────────

incomes = st.floats(min_value=0, max_value=8 * 10**7, allow_nan=False, allow_infinity=False)


@settings(max_examples=300, deadline=None)
@given(a=incomes, b=incomes, ay=st.sampled_from(sorted(G)), regime=st.sampled_from(["old", "new"]),
       age=st.sampled_from(["below_60", "60_to_80", "80_plus"]))
def test_tax_is_monotone_in_income(a, b, ay, regime, age):
    if regime not in G[ay].regimes:
        return
    lo, hi = sorted((a, b))
    t_lo = liability(G[ay], regime, 0.0, lo, 0.0, age, round_tax=False).total_tax[0]
    t_hi = liability(G[ay], regime, 0.0, hi, 0.0, age, round_tax=False).total_tax[0]
    assert t_hi >= t_lo - 1e-6


@settings(max_examples=300, deadline=None)
@given(x=incomes, ay=st.sampled_from(sorted(G)), regime=st.sampled_from(["old", "new"]))
def test_marginal_rate_never_exceeds_100_percent(x, ay, regime):
    if regime not in G[ay].regimes:
        return
    rebate = G[ay].regimes[regime].rebate
    if rebate is not None and not rebate.marginal_relief and x <= rebate.max_income + 10 < x + 1000 + 10:
        # The old-regime s.87A rebate has no marginal relief: crossing its
        # income limit is a genuine statutory notch (tax jumps from nil).
        return
    t0 = liability(G[ay], regime, 0.0, x, round_tax=False).total_tax[0]
    t1 = liability(G[ay], regime, 0.0, x + 1000.0, round_tax=False).total_tax[0]
    # Marginal relief caps tax + surcharge at the threshold amount plus the
    # extra income, but cess is levied on top, so the statutory marginal rate
    # can reach 104% just above a surcharge threshold. Rounding total income
    # to ₹10 can move a ₹1,000 step by up to ₹10.
    assert t1 - t0 <= (1000.0 + 10.0) * (1 + G[ay].cess_rate) + 1e-6


# ── gold integrity ──────────────────────────────────────────────────────────

def test_gold_round_trips_through_json(tmp_path):
    for ay, params in G.items():
        again = PITParams.model_validate_json(params.model_dump_json())
        assert again.canonical_hash() == params.canonical_hash()
        assert again.diff(params) == []


def test_canonical_hash_ignores_citations_but_not_values():
    a = G["2026-27"]
    b = a.model_copy(deep=True)
    b.citations = {}
    assert a.canonical_hash() == b.canonical_hash()
    b.regimes["new"].rebate.max_rebate = 50_000
    assert a.canonical_hash() != b.canonical_hash()
    assert a.diff(b) == ["regimes.new.rebate.max_rebate"]


def test_every_ay_has_core_citations():
    for ay, params in G.items():
        for key in ("regimes.old.slabs", "cess_rate"):
            assert key in params.citations or params.law == "ITA2025", (ay, key)
        if "new" in params.regimes:
            assert "regimes.new.slabs" in params.citations, ay


CORPUS = Path(__file__).parent.parent / "data" / "corpus"
_ROW_RE = re.compile(r"(?:Upto|Up to|From)?\s*(?:Rs\.?\s*|₹)\s*([\d,]+)(?:\s*to\s*(?:Rs\.?\s*|₹)\s*([\d,]+))?.*?\|\s*(Nil|\d+(?:\.\d+)?)\s*(?:per cent|%)?")


def _corpus_table_after(statute: str, anchor: str, nth: int = 0):
    path = CORPUS / statute / "text.txt"
    if not path.exists():
        pytest.skip(f"{statute} not parsed")
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [i for i, ln in enumerate(lines) if anchor in ln]
    if len(starts) <= nth:
        pytest.skip(f"anchor {anchor!r} not found in {statute}")
    rows, i = [], starts[nth]
    while i < len(lines) and len(rows) < 12:
        ln = lines[i]
        if re.match(r"^\d+\.\s", ln) and ("Nil" in ln or "per cent" in ln or "%" in ln):
            above = re.search(r"Above\s*(?:Rs\.?\s*|₹)\s*([\d,]+)", ln)
            rate = 0.0 if "Nil" in ln else float(re.search(r"\|\s*(\d+(?:\.\d+)?)", ln).group(1)) / 100
            if above:
                rows.append((float(above.group(1).replace(",", "")), None, rate))
            else:
                nums = [float(n.replace(",", "")) for n in re.findall(r"(?:Rs\.?\s*|₹)\s*([\d,]+)", ln)]
                rows.append((nums[0], nums[1] if len(nums) > 1 else None, rate))
        elif rows:
            break
        i += 1
    return rows


def _gold_rows(slabs):
    out = []
    for s in slabs:
        if s.lower == 0:
            out.append((s.upper, None, s.rate))          # "Upto X | Nil"
        elif s.upper is None:
            out.append((s.lower, None, s.rate))          # "Above X"
        else:
            out.append((s.lower + 1, s.upper, s.rate))   # "From X+1 to Y"
    return out


@pytest.mark.parametrize("ay, statute, anchor, nth", [
    ("2021-22", "FA2020/enacted", "‘115BAC. (1)", 0),
    ("2024-25", "FA2023/enacted", "(1A) Notwithstanding anything contained in this Act", 0),
    ("2025-26", "FA2024N2/enacted", "(ii) for any previous year relevant to the assessment year beginning on or after the 1st day of April, 2025", 0),
    ("2026-27", "FA2025/enacted", "(iii) for any previous year relevant to the assessment year beginning on or after the 1st April, 2026", 0),
    ("2027-28", "ITA2025/amended_fa2026", "1. Upto ₹400000 | Nil", 0),
])
def test_gold_new_regime_table_matches_statute(ay, statute, anchor, nth):
    corpus_rows = _corpus_table_after(statute, anchor, nth)
    gold_rows = _gold_rows(G[ay].regimes["new"].slabs_for("below_60"))
    assert corpus_rows == gold_rows, f"{ay}: statute {corpus_rows} vs gold {gold_rows}"
