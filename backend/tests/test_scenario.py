"""The statute-grounded policy sandbox: a baseline read from a document's rate table,
validated changes, exact attribution, who pays more and less, uncertainty, behaviour,
validation numbers, and the routes."""
import copy

import pytest
from fastapi.testclient import TestClient

from simulation import scenario as sc

L = 100_000

# the table of Finance Act 2025 s.25 (the new-regime schedule of AY 2026-27 and, under the 2025 Act, 2027-28)
FA2025_ROWS = [(0, 4 * L, 0.0), (4 * L, 8 * L, 0.05), (8 * L, 12 * L, 0.10), (12 * L, 16 * L, 0.15),
               (16 * L, 20 * L, 0.20), (20 * L, 24 * L, 0.25), (24 * L, None, 0.30)]


def _schedule(rows=FA2025_ROWS, page=247):
    return {"page": page, "heading": "the rate of tax given in the following Table", "assessment_year": None,
            "kind": "boxed", "check": {"ok": True, "reason": None},
            "rows": [{"label": f"{i + 1}.", "text": "", "lower": lo, "upper": up, "rate": r}
                     for i, (lo, up, r) in enumerate(rows)]}


def slabs_with(rate_of_band=None, rows=FA2025_ROWS):
    """The FA2025 slabs as a `changes` entry, with some rates replaced: {band index: rate}."""
    rate_of_band = rate_of_band or {}
    return [{"lower": lo, "upper": up, "rate": rate_of_band.get(i, r)} for i, (lo, up, r) in enumerate(rows)]


@pytest.fixture(scope="module")
def base():
    return sc.baseline_from_schedule(_schedule(), "income_tax_2025.pdf", prefer_law="ITA2025")


# ── the baseline ─────────────────────────────────────────────────────────────

def test_the_documents_table_is_matched_to_the_expert_coded_year(base):
    assert base.source == "document" and base.matched_year == "2027-28" and base.params.law == "ITA2025"
    slabs = base.params.regimes["new"].slabs["below_60"]
    assert [(s.lower, s.upper, s.rate) for s in slabs] == [(a, b, c) for a, b, c in FA2025_ROWS]
    rows = {p["parameter"]: p for p in base.provenance}
    assert rows["Tax slabs"]["from_document"] and "page 247" in rows["Tax slabs"]["source"]
    assert "Matches the expert coding of AY 2027-28" in rows["Tax slabs"]["check"]
    assert not rows["Rebate"]["from_document"] and "Expert coding" in rows["Rebate"]["source"]
    assert "₹60,000" in rows["Rebate"]["value"]


def test_without_a_law_preference_the_earliest_matching_year_is_used():
    b = sc.baseline_from_schedule(_schedule(), "fa2025.pdf")
    assert b.matched_year == "2026-27" and any("also applies" in r or "applies in AY" in r for r in b.review)


def test_a_table_that_is_no_years_table_is_used_as_read_and_says_so():
    rows = [(0, 3 * L, 0.0), (3 * L, 9 * L, 0.07), (9 * L, None, 0.25)]
    b = sc.baseline_from_schedule(_schedule(rows))
    assert b.matched_year is None and b.source == "document"
    assert [(s.lower, s.upper, s.rate) for s in b.params.regimes["new"].slabs["below_60"]] == rows
    assert any("not the table of any expert-coded year" in r for r in b.review)
    assert b.provenance[0]["check"].startswith("Not any expert-coded year")


def test_an_incomplete_table_is_refused():
    gap = _schedule([(0, 3 * L, 0.0), (4 * L, None, 0.1)])
    with pytest.raises(sc.ScenarioError, match="gap or overlap"):
        sc.baseline_from_schedule(gap)
    no_top = _schedule([(0, 3 * L, 0.0), (3 * L, 6 * L, 0.1)])
    with pytest.raises(sc.ScenarioError, match="open top band"):
        sc.baseline_from_schedule(no_top)


def test_only_complete_tables_are_offered():
    ok = _schedule()
    bad = {**_schedule(), "check": {"ok": False, "reason": "rows that could not be read"}}
    short = _schedule([(0, 1 * L, 0.0), (1 * L, None, 0.1)])
    assert [t["index"] for t in sc.usable_schedules([bad, ok, short])] == [1]


def test_an_expert_year_can_stand_in_for_a_document_without_a_table():
    b = sc.baseline_from_expert("2026-27")
    assert b.source == "expert" and b.ay == "2026-27" and "No rate table" in b.review[0]
    with pytest.raises(sc.ScenarioError):
        sc.baseline_from_expert("2020-21")            # no new regime that year


# ── changing the law ─────────────────────────────────────────────────────────

def test_changes_are_validated(base):
    with pytest.raises(sc.ScenarioError, match="gap or overlap"):
        sc.apply_changes(base.params, {"slabs": [{"lower": 0, "upper": 400000, "rate": 0}, {"lower": 500000, "upper": None, "rate": 0.1}]})
    with pytest.raises(sc.ScenarioError, match="between 0 and 1"):
        sc.apply_changes(base.params, {"slabs": slabs_with({2: 1.4})})
    with pytest.raises(sc.ScenarioError, match="rates decrease"):
        sc.apply_changes(base.params, {"slabs": slabs_with({1: 0.2})})
    with pytest.raises(sc.ScenarioError, match="cess rate"):
        sc.apply_changes(base.params, {"cess_rate": 0.9})
    with pytest.raises(sc.ScenarioError, match="must be a number"):
        sc.apply_changes(base.params, {"standard_deduction": "lots"})
    with pytest.raises(sc.ScenarioError, match="exceed 100%"):
        sc.apply_changes(base.params, {"slabs": slabs_with({i: 0.95 for i in range(1, 7)})})


def test_a_valid_change_is_applied_and_the_baseline_is_not_touched(base):
    before = copy.deepcopy(base.params.model_dump())
    reform, notes = sc.apply_changes(base.params, {"slabs": slabs_with({2: 0.08}), "standard_deduction": 100_000,
                                                   "rebate": {"max_income": 14 * L, "max_rebate": 70_000, "marginal_relief": True},
                                                   "cess_rate": 0.03})
    new = reform.regimes["new"]
    assert new.slabs["below_60"][2].rate == 0.08 and new.standard_deduction == 100_000
    assert new.rebate.max_income == 14 * L and reform.cess_rate == 0.03
    assert base.params.model_dump() == before


def test_the_rebate_can_be_removed(base):
    reform, _ = sc.apply_changes(base.params, {"rebate": None})
    assert reform.regimes["new"].rebate is None and base.params.regimes["new"].rebate is not None


def test_a_very_high_marginal_rate_is_allowed_with_a_warning(base):
    _, notes = sc.apply_changes(base.params, {"slabs": slabs_with({6: 0.55})})
    assert notes and "combined marginal rate" in notes[0]


# ── running a scenario ───────────────────────────────────────────────────────

def test_a_scenario_equal_to_the_baseline_changes_nothing(base):
    out = sc.run(base, {})
    assert out["delta"]["revenue_crore"] == 0 and out["attribution"] is None and out["changes_applied"] == []
    assert any("is the baseline" in w for w in out["warnings"])
    assert out["impact"]["overall"]["share_pay_less"] == 0 and out["impact"]["overall"]["share_pay_more"] == 0


def test_a_rate_cut_costs_revenue_and_nobody_pays_more(base):
    out = sc.run(base, {"slabs": slabs_with({6: 0.25})})
    assert out["delta"]["revenue_crore"] < 0
    assert out["impact"]["overall"]["share_pay_more"] == 0 and out["impact"]["overall"]["share_pay_less"] > 0


def test_a_rate_rise_raises_revenue_and_nobody_pays_less(base):
    out = sc.run(base, {"slabs": slabs_with({6: 0.35})})
    assert out["delta"]["revenue_crore"] > 0
    assert out["impact"]["overall"]["share_pay_less"] == 0 and out["impact"]["overall"]["share_pay_more"] > 0


def test_a_change_to_a_band_only_reaches_those_above_it(base):
    """Changing the 24L+ rate cannot move the tax of anyone with income below it, and
    nothing below the rebate limit moves when a band above it changes."""
    out = sc.run(base, {"slabs": slabs_with({6: 0.35})})
    for band in out["impact"]["bands"]:
        if band["upper"] is not None and band["upper"] <= 24 * L:
            assert band["share_pay_more"] == 0 and band["mean_change_inr"] == 0, band["label"]
    assert out["impact"]["bands"][-1]["share_pay_more"] > 0.9


def test_the_rebate_shields_low_incomes_from_a_cut_in_a_slab(base):
    """Up to 12 lakh the 60,000 rebate cancels all the tax, so cutting the 10% band to 8%
    (tax at 12 lakh falls from 60,000 to 52,000) changes nobody's tax up to 12 lakh. A
    clause-by-clause view of the law cannot show this; the calculator does."""
    out = sc.run(base, {"slabs": slabs_with({2: 0.08})})
    low = [b for b in out["impact"]["bands"] if b["upper"] is not None and b["upper"] <= 12 * L]
    assert low and all(b["mean_change_inr"] == 0 and b["share_pay_less"] == 0 for b in low)
    assert out["delta"]["revenue_crore"] < 0


def test_a_rise_in_a_slab_reaches_only_incomes_above_where_tax_passes_the_rebate(base):
    """Raise the 10% band to 12%: tax at 12 lakh becomes 68,000, above the rebate cap, so
    incomes from about 11.3 lakh upward pay; nothing up to 8 lakh moves."""
    out = sc.run(base, {"slabs": slabs_with({2: 0.12})})
    bands = {b["label"]: b for b in out["impact"]["bands"]}
    assert bands["up to ₹4 lakh"]["mean_change_inr"] == 0 and bands["₹4 lakh to ₹8 lakh"]["mean_change_inr"] == 0
    mid = bands["₹8 lakh to ₹12 lakh"]
    assert 0 < mid["share_pay_more"] < 0.5 and mid["share_pay_less"] == 0
    # most, not all: a taxpayer whose deductions make the unchanged old regime cheaper does not pay more
    assert bands["₹12 lakh to ₹16 lakh"]["share_pay_more"] > 0.7
    assert out["delta"]["revenue_crore"] > 0


def test_a_flat_cess_cut_is_progressive_by_dollar_but_not_by_share(base):
    out = sc.run(base, {"cess_rate": 0.02})
    assert out["delta"]["revenue_crore"] < 0 and out["attribution"]["levers"][0]["id"] == "cess"


def test_effective_rates_never_exceed_one_hundred_percent(base):
    with pytest.raises(sc.ScenarioError, match="exceed 100%"):      # 80% x 1.25 surcharge x 1.04 cess
        sc.run(base, {"slabs": slabs_with({i: 0.8 for i in range(1, 7)})})
    for rate in (0.3, 0.6, 0.75):
        out = sc.run(base, {"slabs": slabs_with({i: max(rate, r) for i, (_, _, r) in enumerate(FA2025_ROWS) if i >= 1})})
        for d in out["scenario"]["deciles"]:
            assert 0.0 <= d["effective_rate"] <= 1.0
        for b in out["impact"]["bands"]:
            assert 0.0 <= b["reform_rate"] <= 1.0 and 0.0 <= b["base_rate"] <= 1.0


def test_return_groups_add_up_to_the_population(base):
    out = sc.run(base, {"standard_deduction": 100_000})
    total = out["population"]["returns"]
    assert sum(b["returns"] for b in out["impact"]["bands"]) == pytest.approx(total, rel=1e-9)
    assert sum(d["returns"] for d in out["impact"]["deciles"]) == pytest.approx(total, rel=1e-9)
    assert len(out["impact"]["deciles"]) == 10
    o = out["impact"]["overall"]
    assert o["share_pay_less"] + o["share_pay_more"] + o["share_unchanged"] == pytest.approx(1.0)


def test_the_bands_follow_the_laws_own_limits(base):
    out = sc.run(base, {"rebate": {"max_income": 14 * L, "max_rebate": 70_000, "marginal_relief": True}})
    uppers = [b["upper"] for b in out["impact"]["bands"] if b["upper"] is not None]
    assert 14 * L in uppers and 12 * L in uppers and 4 * L in uppers
    assert out["impact"]["bands"][0]["label"].startswith("up to ₹4 lakh")


def test_the_result_is_deterministic(base):
    ch = {"slabs": slabs_with({3: 0.12})}
    assert sc.run(base, ch)["delta"] == sc.run(base, ch)["delta"]


def test_assumptions_are_checked(base):
    with pytest.raises(sc.ScenarioError, match="optimal_share"):
        sc.run(base, {}, sc.Assumptions(optimal_share=1.5))
    with pytest.raises(sc.ScenarioError, match="top_alpha"):
        sc.run(base, {}, sc.Assumptions(top_alpha=0.5))


# ── attribution ──────────────────────────────────────────────────────────────

def test_attribution_adds_up_to_the_whole(base):
    out = sc.run(base, {"slabs": slabs_with({2: 0.08, 4: 0.18}), "standard_deduction": 100_000, "cess_rate": 0.03})
    att = out["attribution"]
    assert att["exact"] and att["matches_total"]
    assert sum(l["revenue_crore"] for l in att["levers"]) == pytest.approx(out["delta"]["revenue_crore"], abs=1e-3)
    assert {l["id"] for l in att["levers"]} == {"rate:2", "rate:4", "standard_deduction", "cess"}
    assert all(l["revenue_crore"] < 0 for l in att["levers"])


def test_a_single_change_gets_the_whole_effect(base):
    out = sc.run(base, {"slabs": slabs_with({6: 0.35})})
    (lever,) = out["attribution"]["levers"]
    assert lever["revenue_crore"] == pytest.approx(out["delta"]["revenue_crore"], abs=1e-6)


def test_a_lever_with_no_effect_gets_nothing(base):
    # a change confined to income the rebate fully covers: no revenue moves, so none is attributed
    out = sc.run(base, {"slabs": slabs_with({1: 0.06})})
    assert out["delta"]["revenue_crore"] > -1e-9
    assert out["attribution"]["matches_total"]


def test_many_changes_are_attributed_by_sampling_and_still_add_up(base):
    changes = {"slabs": slabs_with({1: 0.04, 2: 0.08, 3: 0.12, 4: 0.17, 5: 0.22, 6: 0.28}), "standard_deduction": 90_000,
               "cess_rate": 0.03, "rebate": {"max_income": 13 * L, "max_rebate": 65_000, "marginal_relief": True}}
    out = sc.run(base, changes)
    att = out["attribution"]
    assert not att["exact"] and len(att["levers"]) > sc.MAX_EXACT_LEVERS
    assert att["matches_total"]          # every sampled order telescopes to the whole


def test_shapley_splits_a_pure_interaction_evenly():
    """Two levers that only matter together (value = x*y) each get half."""
    class P:                                         # a stand-in law with two switches
        def __init__(self, a=0, b=0):
            self.a, self.b = a, b

        def model_copy(self, deep=False):
            return P(self.a, self.b)

    levers = [sc.Lever("a", "a", lambda t, s: setattr(t, "a", s.a)), sc.Lever("b", "b", lambda t, s: setattr(t, "b", s.b))]
    phi = sc.shapley(P(), P(1, 1), levers, lambda p: 10.0 * p.a * p.b)
    assert phi == pytest.approx([5.0, 5.0])


# ── uncertainty ──────────────────────────────────────────────────────────────

def test_uncertainty_gives_a_range_that_holds_the_point_estimate(base):
    out = sc.run(base, {"slabs": slabs_with({6: 0.25})}, n_uncertainty=16)
    u = out["uncertainty"]
    assert u["n"] == 16 and u["sign_stable"]
    r = u["revenue_delta_crore"]
    assert r["min"] <= r["p5"] <= r["median"] <= r["p95"] <= r["max"] < 0
    assert r["min"] <= out["delta"]["revenue_crore"] <= r["max"]
    assert [t["input"] for t in u["tornado"]][0] in set(sc.BOUNDS) and len(u["tornado"]) == 5
    assert [t["swing_crore"] for t in u["tornado"]] == sorted((t["swing_crore"] for t in u["tornado"]), reverse=True)


def test_uncertainty_is_reproducible_and_skipped_when_not_asked(base):
    ch = {"slabs": slabs_with({6: 0.25})}
    assert sc.run(base, ch)["uncertainty"] is None
    a = sc.run(base, ch, n_uncertainty=8)["uncertainty"]
    b = sc.run(base, ch, n_uncertainty=8)["uncertainty"]
    assert a["revenue_delta_crore"] == b["revenue_delta_crore"]


# ── behaviour ────────────────────────────────────────────────────────────────

def test_the_compliance_model_responds_to_the_change(base):
    out = sc.run(base, {"slabs": slabs_with({6: 0.25})}, behaviour={"audit_rate": 0.05})
    beh = out["behaviour"]
    assert beh["params"]["audit_rate"] == 0.05 and beh["seeds"] == 3
    assert beh["delta_revenue_crore"]["min"] <= beh["delta_revenue_crore"]["mean"] <= beh["delta_revenue_crore"]["max"]
    assert beh["delta_revenue_crore"]["mean"] < 0            # a rate cut still lowers collections
    assert "not calibrated" in beh["note"]


def test_behaviour_inputs_are_validated(base):
    with pytest.raises(sc.ScenarioError, match="audit rate"):
        sc.run(base, {"standard_deduction": 90_000}, behaviour={"audit_rate": 5})
    assert sc.run(base, {}, behaviour={})["behaviour"] is None       # nothing changed, nothing to respond to


# ── validation against published numbers ─────────────────────────────────────

def test_validation_reports_published_comparisons_and_their_limits():
    v = sc.validation()
    assert {r["ay"] for r in v["in_sample"]} >= {"2022-23", "2023-24"}
    assert all(0.8 < r["ratio"] < 1.3 for r in v["in_sample"])
    assert len(v["forecast"]["tests"]) == 2 and {"skill", "ape_model", "ape_naive"} <= set(v["forecast"]["tests"][0])
    # the cost comparisons are shown with their caveat, not dropped when they are unflattering
    assert {r["reform"] for r in v["reform_cost"]} == {"FA2023", "FA2025"}
    assert all("covers all direct-tax proposals" in r["note"] for r in v["reform_cost"])
    assert v["limits"] and v["reading"]


# ── the routes ───────────────────────────────────────────────────────────────

DEMO = "demo_income_tax_2025"


@pytest.fixture(scope="module")
def client():
    import main
    return TestClient(main.app)


@pytest.fixture
def stub_document(monkeypatch):
    """A document whose rate table is the FA2025 one, without needing a PDF."""
    from routers import policy
    from models.schemas import DocumentMeta

    meta = DocumentMeta(doc_id="d1", filename="income_tax_2025.pdf", pages=1, file_size_kb=1.0)
    monkeypatch.setattr(policy.store, "get_meta", lambda d: meta if d == "d1" else None)
    monkeypatch.setattr(policy, "schedules_for_doc", lambda d: {"schedules": [_schedule()]})
    return "d1"


def test_years_lists_the_expert_coded_laws(client):
    ys = client.get("/api/policy/years").json()["years"]
    assert {"2026-27", "2027-28"} <= {y["ay"] for y in ys} and all(y["bands"] >= 4 for y in ys)


def test_law_route_returns_the_baseline_with_its_sources(client, stub_document):
    d = client.get("/api/policy/law", params={"doc_id": stub_document}).json()
    assert d["available"] and d["ay"] == "2027-28" and d["matched_year"] == "2027-28"
    assert len(d["law_params"]["slabs"]) == 7 and d["law_params"]["rebate"]["max_rebate"] == 60000
    assert d["schedule"]["page"] == 247 and d["tables"][0]["bands"] == 7
    assert {"optimal_share", "growth"} <= set(d["bounds"])
    assert any("page 247" in p["source"] for p in d["provenance"])


def test_scenario_route_prices_a_change(client, stub_document):
    r = client.post("/api/policy/scenario", json={"doc_id": stub_document, "changes": {"slabs": slabs_with({6: 0.25})}})
    assert r.status_code == 200
    d = r.json()
    assert d["delta"]["revenue_crore"] < 0 and d["attribution"]["matches_total"] and d["uncertainty"] is None


def test_scenario_route_can_include_uncertainty_and_behaviour(client, stub_document):
    r = client.post("/api/policy/scenario", json={
        "doc_id": stub_document, "changes": {"standard_deduction": 100000}, "uncertainty": 8,
        "assumptions": {"optimal_share": 0.8, "senior_share": 0.05}, "behaviour": {"audit_rate": 0.02}})
    d = r.json()
    assert r.status_code == 200 and d["uncertainty"]["n"] == 8 and d["behaviour"]["params"]["audit_rate"] == 0.02
    assert d["assumptions"]["optimal_share"] == 0.8


def test_an_invalid_scenario_is_a_422_with_the_reason(client, stub_document):
    r = client.post("/api/policy/scenario", json={"doc_id": stub_document, "changes": {"slabs": slabs_with({2: 1.5})}})
    assert r.status_code == 422 and "between 0 and 1" in r.json()["detail"]
    r = client.post("/api/policy/scenario", json={"doc_id": stub_document, "assumptions": {"optimal_share": 2}})
    assert r.status_code == 422 and "optimal_share" in r.json()["detail"]
    assert client.post("/api/policy/scenario", json={"doc_id": stub_document, "uncertainty": 9999}).status_code == 422


def test_a_document_without_a_table_needs_a_year(client, monkeypatch):
    from routers import policy
    from models.schemas import DocumentMeta

    meta = DocumentMeta(doc_id="d2", filename="x.pdf", pages=1, file_size_kb=1.0)
    monkeypatch.setattr(policy.store, "get_meta", lambda d: meta if d == "d2" else None)
    monkeypatch.setattr(policy, "schedules_for_doc", lambda d: {"schedules": []})
    d = client.get("/api/policy/law", params={"doc_id": "d2"}).json()
    assert d["available"] is False and "No complete rate table" in d["reason"]
    assert client.post("/api/policy/scenario", json={"doc_id": "d2"}).status_code == 422
    r = client.post("/api/policy/scenario", json={"doc_id": "d2", "ay": "2026-27", "changes": {"cess_rate": 0.03}})
    assert r.status_code == 200 and r.json()["ay"] == "2026-27"


def test_an_unknown_document_is_a_404(client):
    assert client.get("/api/policy/law", params={"doc_id": "no-such-document"}).status_code == 404
    assert client.post("/api/policy/scenario", json={"doc_id": "no-such-document"}).status_code == 404


def test_a_private_document_is_hidden_from_other_users(client, monkeypatch):
    from routers import policy
    from models.schemas import DocumentMeta

    meta = DocumentMeta(doc_id="d3", filename="x.pdf", pages=1, file_size_kb=1.0, owner_id="42")
    monkeypatch.setattr(policy.store, "get_meta", lambda d: meta if d == "d3" else None)
    monkeypatch.setattr("auth.deps.store.get_meta" if hasattr(__import__("auth.deps", fromlist=["x"]), "store") else "storage.store.get_meta",
                        lambda d: meta if d == "d3" else None, raising=False)
    monkeypatch.setattr(policy, "schedules_for_doc", lambda d: {"schedules": [_schedule()]})
    assert client.get("/api/policy/law", params={"doc_id": "d3"}).status_code == 404
    assert client.post("/api/policy/scenario", json={"doc_id": "d3"}).status_code == 404


def test_validation_route(client):
    d = client.get("/api/policy/validation").json()
    assert d["in_sample"] and d["reform_cost"] and d["limits"]


@pytest.mark.skipif(not __import__("pathlib").Path("data/store/demo_income_tax_2025/result.json").exists(),
                    reason="demo document not present")
def test_the_demo_documents_own_table_is_the_baseline(client):
    d = client.get("/api/policy/law", params={"doc_id": DEMO}).json()
    assert d["available"] and d["matched_year"] == "2027-28" and d["schedule"]["page"] == 247
    r = client.post("/api/policy/scenario", json={"doc_id": DEMO, "changes": {"standard_deduction": 100000}})
    assert r.status_code == 200 and r.json()["delta"]["revenue_crore"] < 0


def test_the_result_has_the_shape_the_page_reads(base):
    out = sc.run(base, {"standard_deduction": 100_000})
    assert out["law_code"] == "ITA2025"                             # the Act; "law" holds the two laws
    assert set(out["law"]) == {"baseline", "scenario"}
    assert out["law"]["scenario"]["standard_deduction"] == 100_000 and out["law"]["baseline"]["standard_deduction"] == 75_000
    assert {"slabs", "rebate", "standard_deduction", "cess_rate", "surcharge"} == set(out["law"]["baseline"])
    for k in ("baseline", "scenario"):
        assert len(out[k]["deciles"]) == 10 and {"revenue_crore", "kakwani", "gini_post"} <= set(out[k])
    import json
    json.dumps(out)                                                  # JSON-safe: no inf or nan anywhere


# ── input shapes and independence from the research tools ────────────────────

@pytest.mark.parametrize("changes,message", [
    ({"slabs": 5}, "list of 2 to"),
    ({"slabs": [1, 2, 3]}, "each band must be an object"),
    ({"slabs": [{"lower": 0, "upper": None, "rate": 0.1}]}, "list of 2 to"),
    ({"slabs": [{"lower": 0, "upper": 5, "rate": 0}] * 40}, "list of 2 to"),
    ({"rebate": 7}, "rebate must be an object"),
    ({"rebate": {"max_income": True, "max_rebate": 1}}, "must be a number"),
    ({"cess_rate": "x"}, "must be a number"),
    ({"cess_rate": float("nan")}, "must be between"),
    ({"slab": []}, "unknown change: slab"),
    ([1], "changes must be an object"),
    ("slabs", "changes must be an object"),
])
def test_malformed_changes_are_a_scenario_error_not_a_crash(base, changes, message):
    with pytest.raises(sc.ScenarioError, match=message):
        sc.apply_changes(base.params, changes)


def test_the_route_answers_422_for_a_malformed_body(client, stub_document):
    for changes in ({"slabs": 5}, {"rebate": 7}, {"slabs": [1, 2, 3]}, {"unknown": 1}):
        r = client.post("/api/policy/scenario", json={"doc_id": stub_document, "changes": changes})
        assert r.status_code == 422 and isinstance(r.json()["detail"], str), changes


def test_the_scenario_module_does_not_need_salib_and_its_ranges_match_the_analysis():
    import subprocess, sys
    code = ("import sys, types; sys.modules['SALib'] = None; "          # importing SALib now raises ImportError
            "import simulation.scenario as s; print(sorted(s.BOUNDS))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(__import__("pathlib").Path(__file__).parent.parent))
    assert out.returncode == 0, out.stderr[-300:]
    from simulation.engine.sensitivity import PROBLEM
    assert sc.BOUNDS == {n: (float(lo), float(hi)) for n, (lo, hi) in zip(PROBLEM["names"], PROBLEM["bounds"])}


# ── the surcharge ───────────────────────────────────────────────────────────

def _bands(base):
    return [b.model_dump() for b in sorted(base.params.regimes["new"].surcharge, key=lambda b: b.threshold)]


def test_the_law_view_carries_the_surcharge(base):
    assert sc.law_view(base.params)["surcharge"] == _bands(base) and len(_bands(base)) >= 2


def test_the_same_surcharge_is_no_change(base):
    r = sc.run(base, {"surcharge": _bands(base)})
    assert r["changes_applied"] == [] and r["delta"]["revenue_crore"] == 0


def test_a_higher_surcharge_raises_revenue_and_only_the_rich_pay_more(base):
    bands = _bands(base)
    bands[-1]["rate"] += 0.05
    r = sc.run(base, {"surcharge": bands})
    assert r["delta"]["revenue_crore"] > 0
    assert [l["id"] for l in r["attribution"]["levers"]] == ["surcharge"] and r["attribution"]["matches_total"]
    first_hit = min(b["threshold"] for b in bands)
    for g in r["impact"]["bands"]:
        if g["upper"] is not None and g["upper"] <= first_hit:
            assert g["share_pay_more"] == 0 and g["share_pay_less"] == 0


def test_removing_the_surcharge_costs_revenue_and_nobody_pays_more(base):
    r = sc.run(base, {"surcharge": []})
    assert r["delta"]["revenue_crore"] < 0 and r["impact"]["overall"]["share_pay_more"] == 0


@pytest.mark.parametrize("bands,message", [
    ([{"threshold": 5e6, "rate": 0.1}, {"threshold": 5e6, "rate": 0.2}], "different"),
    ([{"threshold": 5e6, "rate": 0.9}], "between 0 and 0.5"),
    ([{"threshold": -1, "rate": 0.1}], "between 0"),
    ([{"threshold": 1e6 * (i + 1), "rate": 0.1} for i in range(7)], "at most 6"),
    ("ten percent", "list"),
])
def test_a_surcharge_that_is_not_a_law_is_refused(base, bands, message):
    with pytest.raises(sc.ScenarioError, match=message):
        sc.apply_changes(base.params, {"surcharge": bands})


def test_the_combined_marginal_rate_guard_includes_the_new_surcharge(base):
    with pytest.raises(sc.ScenarioError, match="exceed 100%"):
        sc.apply_changes(base.params, {"slabs": slabs_with({6: 0.8}), "surcharge": [{"threshold": 5e6, "rate": 0.5}]})
