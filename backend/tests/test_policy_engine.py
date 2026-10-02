"""Generic rule engine on real provisions: CGST s.47 late fee, a DPDP
Schedule penalty, defeasibility, executability, defeat-cycle detection."""
import pytest

from models.rules import Condition, Exception_, LegalRule, Penalty, Provenance
from policy.engine import RuleError, executability_rate, run, validate_expr

EXPERT = Provenance(extractor="expert")


def rule(rule_id, conditions, effects, defeats=(), modality="obligation"):
    return LegalRule(rule_id=rule_id, statute="TEST", provision=rule_id, modality=modality,
                     conditions=[Condition(expr=e) if not isinstance(e, Condition) else e for e in conditions],
                     effects=effects, defeats=list(defeats), provenance=EXPERT)


# CGST Act s.47(1): a registered person who fails to furnish a return by
# the due date pays a late fee of ₹100 per day, up to ₹5,000.
CGST_47 = rule(
    "cgst_s47_1",
    [{"op": "is", "var": "is_registered_person"},
     {"op": "is", "var": "failed_to_file_return"},
     {"op": "gt", "var": "days_late", "value": 0}],
    [Penalty(kind="fee", per_day=100, max_amount=5000, trigger="late filing")],
)

# DPDP Act Schedule item 1: failure to take reasonable security safeguards,
# penalty up to ₹250 crore (the Board fixes the amount; the cap is modelled).
DPDP_SCH_1 = rule(
    "dpdp_sch_1",
    [{"op": "is", "var": "is_data_fiduciary"}, {"op": "is", "var": "failed_security_safeguards"}],
    [Penalty(kind="penalty", amount=2_500_000_000, trigger="security safeguards")],
)


def test_cgst_late_fee_per_day_and_cap():
    facts = {"is_registered_person": True, "failed_to_file_return": True}
    assert run([CGST_47], {**facts, "days_late": 12}).amounts["cgst_s47_1"] == 1200
    assert run([CGST_47], {**facts, "days_late": 90}).amounts["cgst_s47_1"] == 5000
    assert run([CGST_47], {**facts, "days_late": 0}).applicable == []
    assert run([CGST_47], {"is_registered_person": False, "failed_to_file_return": True,
                           "days_late": 30}).applicable == []


def test_exception_defeats_parent_rule():
    waiver = rule(
        "waiver_nil_return",
        [{"op": "is", "var": "is_registered_person"}, {"op": "eq", "var": "tax_due", "value": 0}],
        [Penalty(kind="fee", per_day=20, max_amount=500, trigger="late filing")],
        defeats=["cgst_s47_1"],
    )
    facts = {"is_registered_person": True, "failed_to_file_return": True, "days_late": 30, "tax_due": 0}
    out = run([CGST_47, waiver], facts)
    assert out.defeated == ["cgst_s47_1"]
    assert out.amounts == {"waiver_nil_return": 500}
    # With tax due the exception does not apply and the parent rule stands.
    out = run([CGST_47, waiver], {**facts, "tax_due": 5000})
    assert out.applicable == ["cgst_s47_1"] and out.amounts["cgst_s47_1"] == 3000


def test_negated_condition():
    first_offence_only = rule(
        "first_offence", [{"op": "is", "var": "obstructed_officer"},
                          Condition(expr={"op": "is", "var": "is_first_offence"}, negated=True)],
        [Penalty(kind="penalty", amount=50_000)])
    assert run([first_offence_only], {"obstructed_officer": True, "is_first_offence": False}).total == 50_000
    assert run([first_offence_only], {"obstructed_officer": True, "is_first_offence": True}).total == 0


def test_non_executable_rules_are_reported_not_guessed():
    vague = rule("vague", [Condition(expr=None)], [Penalty(kind="penalty", amount=1000)])
    unknown_fact = rule("unknown", [{"op": "gt", "var": "number_of_lorries", "value": 3}],
                        [Penalty(kind="penalty", amount=1000)])
    out = run([vague, unknown_fact, DPDP_SCH_1], {"is_data_fiduciary": True, "failed_security_safeguards": True})
    assert set(out.non_executable) == {"vague", "unknown"}
    assert out.amounts == {"dpdp_sch_1": 2_500_000_000}
    assert executability_rate([vague, unknown_fact, DPDP_SCH_1]) == pytest.approx(1 / 3)


def test_defeat_cycle_is_rejected():
    a = rule("a", [{"op": "is", "var": "is_company"}], [Penalty(kind="fee", amount=1)], defeats=["b"])
    b = rule("b", [{"op": "is", "var": "is_company"}], [Penalty(kind="fee", amount=1)], defeats=["a"])
    with pytest.raises(RuleError):
        run([a, b], {"is_company": True})


def test_expression_validation():
    assert validate_expr({"op": "and", "args": [{"op": "is", "var": "is_company"}]}) == []
    assert "unknown fact" in validate_expr({"op": "gt", "var": "nope", "value": 1})[0]
    assert validate_expr({"op": "is", "var": "days_late"})  # 'is' needs a boolean fact
