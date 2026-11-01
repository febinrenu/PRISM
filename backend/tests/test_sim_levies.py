"""Clause dynamics must not make up money: a rate is a levy on income only when the clause says so, and a
clause that states no sum and no rate charges nobody."""
import pytest

from simulation import templates
from simulation.model import PRISMSimulationModel
from simulation.rules import (
    SimulationRule, percent_is_income_levy, settle_pricing, settle_rate, states_money,
)
from simulation.runner import build_narrative, iter_simulation

AGENTS = {"low_income": 40, "middle_income": 30, "high_income": 20, "small_business": 10, "large_corporate": 2}


def test_templates_do_not_invent_a_rate_the_clause_does_not_state():
    plain = "the tax shall be paid in four instalments during the year"
    for extract in (templates._advance_tax, templates._cess, templates._interest):
        assert "rate_percent" not in extract(plain, {})
    assert templates._withholding("tax shall be deducted at source", {})["rate_percent"] is None
    assert templates._turnover_levy("a levy on the turnover of the company", {})["rate_percent"] is None


def test_a_stated_rate_on_income_is_a_levy():
    text = "tax shall be charged at the rate of 30% on income exceeding Rs. 10,00,000"
    assert percent_is_income_levy(text)
    r = settle_pricing(settle_rate(SimulationRule(clause_id="c", description="d", rate_percent=30.0, marginal=True), text), text)
    assert r.rate_percent == 30.0 and r.priced and r.rate_note is None


@pytest.mark.parametrize("text", [
    "simple interest at 1% per month on the amount unpaid",
    "a penalty of 200% of the tax sought to be evaded",
    "cess at 4% on the amount of income-tax",
    "15% of the advance tax is payable by the 15th of June in the first instalment",
])
def test_a_percentage_that_is_not_a_rate_of_tax_on_income_is_set_aside(text):
    assert not percent_is_income_levy(text)
    r = settle_pricing(settle_rate(SimulationRule(clause_id="c", description="d", rate_percent=1.0, marginal=True), text), text)
    assert r.rate_percent is None and not r.marginal and not r.priced and "flat obligation" in r.rate_note


def test_a_template_for_interest_or_a_cess_never_leaves_a_levy_behind():
    rule = SimulationRule(clause_id="c", description="d", rate_percent=15.0, matched_template="advance_tax_installment")
    settle_rate(rule, "the assessee shall pay 15% on income")
    assert rule.rate_percent is None and rule.rate_note


def test_a_clause_with_no_sum_and_no_rate_is_not_priced():
    text = "the Assessing Officer shall record the reasons in writing"
    assert not states_money(text)
    assert not settle_pricing(SimulationRule(clause_id="c", description="d"), text).priced
    assert states_money("a fee of Rs. 5,000 is payable")


def test_an_unpriced_rule_charges_nobody_and_does_not_drag_compliance():
    rules = [SimulationRule(clause_id="free", description="no money", priced=False)]
    m = PRISMSimulationModel(rules, AGENTS, seed=3, adaptive=False)
    last = list(iter_simulation(m, 12))[-1]
    assert last.revenue_total == 0.0
    assert all(v == 0.0 for v in last.effective_rate_by_type.values())
    assert last.compliance_rate == 1.0


def test_the_narrative_says_how_many_rules_charge_anything():
    levy = SimulationRule(clause_id="a", description="levy", rate_percent=10.0, full_base=True)
    free = SimulationRule(clause_id="b", description="free", priced=False,
                          rate_note="The clause states 1%, but it is next to interest.")
    m = PRISMSimulationModel([levy, free], AGENTS, seed=3, adaptive=False)
    steps = list(iter_simulation(m, 12))
    low, high = m.effective_rate_gap()
    text = build_narrative([levy, free], "llm", steps, m.regressivity_verdict(), low, high)
    assert "1 charge a stated rate on income" in text and "1 charge nothing" in text
    assert "interest, a penalty, a cess or an instalment" in text


def test_a_run_with_no_levy_says_it_is_not_a_finding_about_the_tax():
    fixed = SimulationRule(clause_id="a", description="fee", base_compliance_cost=3000.0)
    m = PRISMSimulationModel([fixed], AGENTS, seed=3, adaptive=False)
    steps = list(iter_simulation(m, 12))
    low, high = m.effective_rate_gap()
    text = build_narrative([fixed], "llm", steps, m.regressivity_verdict(), low, high)
    assert "says nothing about this document's tax rates" in text


def test_the_verdict_says_what_it_rests_on():
    from simulation.runner import verdict_basis
    levy = SimulationRule(clause_id="a", description="levy", rate_percent=10.0)
    fixed = SimulationRule(clause_id="b", description="fee")
    free = SimulationRule(clause_id="c", description="none", priced=False)
    assert verdict_basis([levy, fixed, free]) == "income_rates"
    assert verdict_basis([fixed, free]) == "fixed_sums"
    assert verdict_basis([free]) == "nothing_charged"


def test_the_narrative_has_no_markdown_the_page_would_show_raw():
    levy = SimulationRule(clause_id="a", description="levy", rate_percent=10.0, full_base=True)
    m = PRISMSimulationModel([levy], AGENTS, seed=3, adaptive=False)
    steps = list(iter_simulation(m, 12))
    low, high = m.effective_rate_gap()
    assert "**" not in build_narrative([levy], "llm", steps, m.regressivity_verdict(), low, high)
