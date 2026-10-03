"""Rule-vs-rule scoring used for annotator agreement and system evaluation."""
from eval.v2.scoring import NormItem, NormRule, cohen_kappa, compare, match_rules

ITEM = {"item_id": "x", "start": 1000}


def rule(mod, action=None, subject=None, conds=(), effects=()):
    spans = {"action": [action] if action else [], "subject": [subject] if subject else [],
             "consequence": [], "conditions": list(conds), "exceptions": [], "cross_refs": []}
    return NormRule(mod, spans, list(effects))


def test_identical_items_score_perfectly():
    g = NormItem("x", False, [rule("obligation", (10, 40), (0, 9), [(41, 60)],
                                   [("fee", {"per_day": 100, "max_amount": 5000})])])
    res = compare([g], [g])
    assert res["rules"]["f1"] == 1.0 and res["modality"]["accuracy"] == 1.0
    assert res["spans"]["action"]["strict"]["f1"] == 1.0
    assert res["effects"]["numeric_exact"] == 1.0


def test_relaxed_spans_and_wrong_numbers():
    g = NormItem("x", False, [rule("obligation", (10, 40), effects=[("fee", {"per_day": 100, "max_amount": 5000})])])
    p = NormItem("x", False, [rule("prohibition", (12, 40), effects=[("fee", {"per_day": 1, "max_amount": 5000})])])
    res = compare([g], [p])
    assert res["rules"]["f1"] == 1.0
    assert res["modality"]["accuracy"] == 0.0
    assert res["spans"]["action"]["strict"]["f1"] == 0.0 and res["spans"]["action"]["relaxed"]["f1"] == 1.0
    assert res["effects"]["kinds"]["f1"] == 1.0 and res["effects"]["numeric_exact"] == 0.5


def test_missing_and_extra_rules():
    g = NormItem("x", False, [rule("obligation", (0, 10)), rule("prohibition", (20, 30))])
    p = NormItem("x", False, [rule("obligation", (0, 10)), rule("power", (50, 60))])
    res = compare([g], [p])
    assert (res["rules"]["tp"], res["rules"]["fp"], res["rules"]["fn"]) == (1, 1, 1)


def test_rate_tables_match_by_effect_kind():
    g = rule("obligation", effects=[("slab_row", {"lower": 0, "upper": 4e5, "rate": 0.0})])
    p = rule("definition", effects=[("slab_row", {"lower": 0, "upper": 4e5, "rate": 0.0})])
    assert match_rules([g], [p]) == [(0, 0)]


def test_kappa():
    assert cohen_kappa([("a", "a"), ("b", "b"), ("a", "a"), ("b", "b")]) == 1.0
    assert cohen_kappa([("a", "b"), ("b", "a")]) < 0
    assert cohen_kappa([]) is None
