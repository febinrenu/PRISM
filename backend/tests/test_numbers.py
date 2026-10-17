"""Every number a reading states, checked against the law it cites
(pipeline/extraction/numbers.py), and every rate schedule of a document
read and checked (pipeline/schedules.py)."""
from pathlib import Path

import pytest

from pipeline.extraction.numbers import check_effect, unsupported_numbers
from pipeline.statute.corpus import CORPUS_DIR

PROV = ("1. Upto Rs. 4,00,000 | Nil\n2. From Rs. 4,00,001 to Rs. 8,00,000 | 5 per cent.\n"
        "3. Above Rs. 8,00,000 | 10 per cent.")
FA2025 = CORPUS_DIR / "FA2025" / "enacted" / "source.pdf"
DEMO = Path(__file__).resolve().parents[1] / "data" / "demo" / "income_tax_2025.pdf"


# ── effects ──────────────────────────────────────────────────────────────────

def test_numbers_in_the_quote_are_verified():
    c = check_effect({"kind": "slab_row", "lower": 400000, "upper": 800000, "rate": 0.05},
                     "2. From Rs. 4,00,001 to Rs. 8,00,000 | 5 per cent.", PROV)
    assert c.status == "verified" and [f.found for f in c.fields] == ["quote", "quote", "quote"]


def test_first_and_last_bands_and_nil():
    assert check_effect({"kind": "slab_row", "lower": 0, "upper": 400000, "rate": 0.0},
                        "1. Upto Rs. 4,00,000 | Nil", PROV).status == "verified"
    # no upper bound: nothing printed to check for it
    c = check_effect({"kind": "slab_row", "lower": 800000, "rate": 0.10}, "3. Above Rs. 8,00,000 | 10 per cent.", PROV)
    assert c.status == "verified" and {f.field for f in c.fields} == {"lower", "rate"}


def test_one_rupee_conventions_for_a_lower_bound():
    q = "2. From Rs. 4,00,001 to Rs. 8,00,000 | 5 per cent."
    assert check_effect({"kind": "slab_row", "lower": 400001, "upper": 800000, "rate": 0.05}, q, PROV).status == "verified"
    q2 = "where the total income exceeds Rs. 2,50,000 but does not exceed Rs. 5,00,000 | 5 per cent."
    assert check_effect({"kind": "slab_row", "lower": 250001, "upper": 500000, "rate": 0.05}, q2, q2).status == "verified"


def test_a_number_elsewhere_or_nowhere_is_flagged():
    q = "2. From Rs. 4,00,001 to Rs. 8,00,000 | 5 per cent."
    elsewhere = check_effect({"kind": "slab_row", "lower": 400000, "upper": 800000, "rate": 0.10}, q, PROV)
    assert elsewhere.status == "provision"
    nowhere = check_effect({"kind": "slab_row", "lower": 800000, "upper": 999999999, "rate": 0.10},
                           "3. Above Rs. 8,00,000 | 10 per cent.", PROV)
    assert nowhere.status == "unsupported" and [(f.field, f.value) for f in nowhere.missing] == [("upper", 999999999.0)]


def test_amounts_in_words_and_effects_without_numbers():
    q = 'for the words "seven hundred thousand rupees", the words "twelve hundred thousand rupees" shall be substituted'
    c = check_effect({"kind": "rebate", "max_income": 1200000, "max_rebate": 60000}, q, q + " sixty thousand rupees")
    assert [(f.field, f.found) for f in c.fields] == [("max_income", "quote"), ("max_rebate", "provision")]
    assert check_effect({"kind": "due_date", "description": "x"}, "x", "x").status == "unchecked"


def test_free_text_numbers():
    assert unsupported_numbers(["income exceeds ₹7,50,000", "tax at 5 per cent", None], PROV) == ["₹7,50,000"]
    assert unsupported_numbers(["income up to four lakh rupees"], PROV) == []


# ── model readings in the app ────────────────────────────────────────────────

def test_model_reading_flags_numbers_the_clause_lacks():
    from models.schemas import LLMCausalRule
    from pipeline.llm_extractor import check_numbers
    rule = LLMCausalRule(is_causal=True, condition="total income exceeds ₹12 lakh", thresholds=["₹60,000", "5%"])
    clause = "where the total income does not exceed twelve hundred thousand rupees, a rebate of sixty thousand rupees"
    assert check_numbers(rule, clause) == ["5%"]


@pytest.mark.skipif(not DEMO.exists(), reason="demo document not present")
def test_stored_readings_are_checked_when_loaded_not_rewritten():
    from storage import store
    path = store._doc_dir("demo_income_tax_2025") / "result.json"
    before = path.read_bytes()
    store._result_store.pop("demo_income_tax_2025", None)
    res = store.get_result("demo_income_tax_2025")
    flagged = {c.clause_id: c.llm_extraction.unsupported_numbers for c in res.clauses
               if c.llm_extraction and c.llm_extraction.unsupported_numbers}
    assert flagged.get("demo_income_tax_2025_c1800") == ["fifty crore rupees"]
    assert path.read_bytes() == before


# ── rate schedules ───────────────────────────────────────────────────────────

def test_schedule_checks():
    from pipeline.schedules import _check
    rows = [{"label": "1.", "text": "", "lower": 0.0, "upper": 300000.0, "rate": 0.0},
            {"label": "2.", "text": "", "lower": 400000.0, "upper": None, "rate": 0.05}]
    assert _check(rows) == {"ok": False, "reason": "gap or overlap between bands at 400,000"}
    rows[1]["lower"] = 300000.0
    assert _check(rows) == {"ok": True, "reason": None}
    rows[1]["rate"] = None
    assert _check(rows)["reason"].startswith("rows that could not be read")


@pytest.mark.skipif(not FA2025.exists(), reason="FA 2025 PDF not downloaded")
def test_finance_act_schedules_are_found_and_complete():
    from pipeline.schedules import find_schedules
    sch = find_schedules(str(FA2025))
    assert len(sch) == 9 and all(s["check"]["ok"] for s in sch)
    new = sch[0]
    assert new["assessment_year"] == "2026-27" and [r["rate"] for r in new["rows"]] == [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
    # the interleaved First Schedule, read from the page as printed
    old = next(s for s in sch if s["kind"] == "two_column")
    assert old["heading"].startswith("(I) In the case of every individual")
    assert [(r["lower"], r["upper"], r["rate"]) for r in old["rows"]] == \
        [(0.0, 250000.0, 0.0), (250000.0, 500000.0, 0.05), (500000.0, 1000000.0, 0.2), (1000000.0, None, 0.3)]


@pytest.mark.skipif(not DEMO.exists(), reason="demo document not present")
def test_schedules_route(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from main import app
    from routers import data
    monkeypatch.setattr(data, "_schedules_cache", lambda doc_id: tmp_path / "schedules.json")  # not in the repo
    c = TestClient(app)
    d = c.get("/api/schedules/demo_income_tax_2025").json()
    assert d["review"] == 0 and len(d["schedules"]) >= 1
    assert d["schedules"][0]["rows"][-1]["upper"] is None
    assert (tmp_path / "schedules.json").exists()
    assert c.get("/api/schedules/demo_income_tax_2025").json()["stamp"] == d["stamp"]
    assert c.get("/api/schedules/not_a_document").status_code == 404


# ── research views ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not (CORPUS_DIR / "FA2025" / "enacted" / "text.txt").exists(), reason="corpus not parsed")
def test_rules_numbers_are_grounded_by_construction():
    from simulation.experiment.structured_run import number_grounding
    rows = {r["condition"]: r for r in number_grounding(["rules"])}
    for r in rows.values():
        assert r["fields"] > 100 and r["in_quote"] == r["fields"] and r["missing"] == 0
