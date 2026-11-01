"""Statute comparison: matching by meaning, figure changes, noise-proof highlighting, and the endpoints."""
import pytest
from fastapi.testclient import TestClient

from pipeline.statute.compare import (clean, compact, compare_sections, diff_ranges, figure_changes, figures,
                                      strip_heading_bleed)
from tests.corpus_marks import needs_parsed_corpus


def _sec(n, heading, text):
    return {"path": f"X/s{n}", "number": str(n), "heading": heading, "text": text}


def test_figures_are_found_as_printed_and_compared_without_spacing_or_commas():
    assert set(figures("a rebate of ₹ 12,500 and tax at 5 per cent and 7.5%").values()) == {"₹ 12,500", "5 per cent", "7.5%"}
    ch = figure_changes("rebate of ₹12,500 at 5%", "rebate of ₹ 60,000 at 5 per cent")
    assert ch == {"removed": ["₹12,500"], "added": ["₹ 60,000"]}
    assert figure_changes("₹12,500 and 5%", "₹ 12500 and 5 per cent") is None


def test_printing_differences_are_not_changes():
    assert compact("income-tax -- (a) proceed ing") == compact("Income–tax - (a) proceeding")
    assert compact("liable (43 of 1961) to pay") == compact("liable to pay")
    assert clean("`[twelve]`") == "twelve"
    assert compact("rate 5%") != compact("rate 10%")


def test_diff_ranges_mark_only_the_words_that_changed():
    a = "The tax is 5% of total income, payable within 30 days."
    b = "The tax is 10% of total  income, pay able within 30 days (43 of 1961)."
    dels, ins = diff_ranges(a, b)
    assert [a[s:e] for s, e in dels] == ["5%"]
    assert [b[s:e] for s, e in ins] == ["10%"]
    assert diff_ranges("same words here", "same  words   here") == ([], [])


def test_the_next_sections_heading_is_cut_from_the_end():
    rows = [("s1", "1", "Short title", "1. (1) This Act may be called X. Charge of tax."),
            ("s2", "2", "Charge of tax", "2. Tax is charged.")]
    out = strip_heading_bleed(rows)
    assert out[0][3] == "1. (1) This Act may be called X."
    assert out[1][3] == "2. Tax is charged."


def test_sections_are_matched_by_what_they_say_not_by_number():
    base = "The tax payable by an assessee on total income shall be computed at the rates below for the year. "
    a = [_sec(1, "Charge", base + "Rate is 5% on income up to the limit."),
         _sec(2, "Rebate", "A resident individual is entitled to a deduction from tax as rebate under this section."),
         _sec(3, "Penalty", "Whoever fails to furnish the return shall pay a penalty of ₹5,000 for each default made."),
         _sec(4, "Old only", "This provision about the sale of toll bridges applies only in the first Act and nowhere else.")]
    b = [_sec(10, "Charge", base + "Rate is 10% on income up to the limit."),     # same section, rate changed
         _sec(11, "Rebate", "A resident individual is entitled to a deduction from tax as rebate under this section."),
         _sec(30, "Penalty", "Whoever fails to furnish the return shall pay a penalty of ₹5,000 for each default made."),
         _sec(40, "New only", "Digital platforms shall report every transaction above the threshold to the authority monthly.")]
    out = compare_sections(a, b)
    by = {(r["a"] or {}).get("number") or "+" + r["b"]["number"]: r for r in out["rows"]}
    assert by["1"]["status"] == "modified" and by["1"]["b"]["number"] == "10"
    assert by["1"]["figures"] == {"removed": ["5%"], "added": ["10%"]}
    assert by["2"]["status"] == "renumbered" and by["2"]["b"]["number"] == "11"
    assert by["3"]["status"] == "renumbered"
    assert by["4"]["status"] == "removed" and by["+40"]["status"] == "added"
    assert out["summary"]["matched"] == 3 and out["summary"]["removed"] == 1 and out["summary"]["added"] == 1


@pytest.fixture(scope="module")
def client():
    import main
    return TestClient(main.app)


@needs_parsed_corpus
def test_two_versions_of_the_income_tax_act_compare(client):
    r = client.get("/api/corpus/compare", params={"a": "ITA2025/enacted", "b": "ITA2025/amended_fa2026"})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["matched"] > 500 and s["modified"] > 0 and s["unchanged"] + s["formatting"] > s["modified"]
    row = next(x for x in r.json()["rows"] if x["status"] == "modified")
    pair = client.get("/api/corpus/compare/pair", params={
        "a": "ITA2025/enacted", "pa": row["a"]["path"], "b": "ITA2025/amended_fa2026", "pb": row["b"]["path"]}).json()
    assert pair["a"]["marked"] or pair["b"]["marked"]
    assert all(0 <= s < e <= len(pair["a"]["text"]) for s, e in pair["a"]["marked"])
    assert all(0 <= s < e <= len(pair["b"]["text"]) for s, e in pair["b"]["marked"])


@needs_parsed_corpus
def test_compare_refuses_unknown_and_identical_statutes(client):
    assert client.get("/api/corpus/compare", params={"a": "nope/x", "b": "ITA2025/enacted"}).status_code == 404
    assert client.get("/api/corpus/compare", params={"a": "ITA2025/enacted", "b": "ITA2025/enacted"}).status_code == 422
    assert client.get("/api/corpus/compare/pair", params={
        "a": "ITA2025/enacted", "pa": "nope", "b": "ITA2025/enacted", "pb": "ITA2025/s156"}).status_code == 404
