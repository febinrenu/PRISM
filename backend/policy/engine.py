"""
Evaluate executable LegalRules against a set of facts.

    expression := {"op": "and"|"or", "args": [expression, …]}
                | {"op": "not", "arg": expression}
                | {"op": "gt"|"ge"|"lt"|"le"|"eq"|"ne", "var": fact, "value": v}
                | {"op": "is", "var": bool_fact}            # fact is true

A rule applies when every condition evaluates true (a negated condition must
evaluate false). Rules listed in another applicable rule's `defeats` are
suppressed — this is how a proviso or exception overrides its parent. The
defeat graph must be acyclic.

Monetary effects (Penalty with kind penalty / fee / interest) are evaluated
to rupee amounts:

    amount           fixed sum
    per_day          × days_late
    rate             × the base named in `trigger` (default amount_involved)
    rate_per_month   × months_late × tax_unpaid
    max_amount       cap on the result
"""
from dataclasses import dataclass, field
from typing import Optional

from models.rules import LegalRule, Penalty
from policy.facts import FACTS, fact_type


class RuleError(ValueError):
    pass


_CMP = {
    "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
    "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
}


def validate_expr(expr: dict) -> list[str]:
    """Names of unknown facts / malformed nodes (empty = valid)."""
    problems: list[str] = []
    op = expr.get("op")
    if op in ("and", "or"):
        args = expr.get("args") or []
        if not args:
            problems.append(f"{op} without args")
        for a in args:
            problems.extend(validate_expr(a))
    elif op == "not":
        if "arg" not in expr:
            problems.append("not without arg")
        else:
            problems.extend(validate_expr(expr["arg"]))
    elif op in _CMP or op == "is":
        var = expr.get("var")
        if var not in FACTS:
            problems.append(f"unknown fact {var!r}")
        elif op == "is" and fact_type(var) != "bool":
            problems.append(f"'is' on non-boolean fact {var!r}")
        elif op in _CMP and "value" not in expr:
            problems.append(f"{op} on {var!r} without value")
    else:
        problems.append(f"unknown op {op!r}")
    return problems


def evaluate(expr: dict, facts: dict) -> bool:
    op = expr["op"]
    if op == "and":
        return all(evaluate(a, facts) for a in expr["args"])
    if op == "or":
        return any(evaluate(a, facts) for a in expr["args"])
    if op == "not":
        return not evaluate(expr["arg"], facts)
    if op == "is":
        return bool(facts.get(expr["var"], False))
    value = facts.get(expr["var"])
    if value is None:
        return False  # an absent fact never satisfies a comparison
    return _CMP[op](value, expr["value"])


def is_executable(rule: LegalRule) -> bool:
    """A rule is executable when it has at least one effect and every
    condition has a valid machine-readable expression."""
    if not rule.effects:
        return False
    for c in rule.conditions:
        if c.expr is None or validate_expr(c.expr):
            return False
    return True


def applies(rule: LegalRule, facts: dict) -> bool:
    for c in rule.conditions:
        if c.expr is None:
            return False
        result = evaluate(c.expr, facts)
        if result == c.negated:
            return False
    return True


def check_defeat_graph(rules: list[LegalRule]) -> None:
    ids = {r.rule_id for r in rules}
    graph = {r.rule_id: [d for d in r.defeats if d in ids] for r in rules}
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        for nxt in graph[node]:
            if state.get(nxt) == 1:
                raise RuleError("defeat cycle: " + " → ".join(path + [node, nxt]))
            if state.get(nxt) is None:
                visit(nxt, path + [node])
        state[node] = 2

    for r in graph:
        if state.get(r) is None:
            visit(r, [])


def penalty_amount(effect: Penalty, facts: dict) -> Optional[float]:
    total = 0.0
    used = False
    if effect.amount is not None:
        total += effect.amount
        used = True
    if effect.per_day is not None:
        total += effect.per_day * max(float(facts.get("days_late", 0)), 0.0)
        used = True
    if effect.rate is not None:
        base_name = effect.trigger if effect.trigger in FACTS else "amount_involved"
        total += effect.rate * float(facts.get(base_name, 0.0))
        used = True
    if effect.rate_per_month is not None:
        total += effect.rate_per_month * float(facts.get("months_late", 0)) * float(facts.get("tax_unpaid", 0.0))
        used = True
    if not used:
        return None
    if effect.max_amount is not None:
        total = min(total, effect.max_amount)
    return total


@dataclass
class Outcome:
    applicable: list[str] = field(default_factory=list)      # rule ids that apply
    defeated: list[str] = field(default_factory=list)        # applied but overridden
    amounts: dict[str, float] = field(default_factory=dict)  # rule id → rupees
    non_executable: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(self.amounts.values())


def run(rules: list[LegalRule], facts: dict) -> Outcome:
    check_defeat_graph(rules)
    out = Outcome()
    live = []
    for r in rules:
        if not is_executable(r):
            out.non_executable.append(r.rule_id)
            continue
        if applies(r, facts):
            live.append(r)
    defeated = {d for r in live for d in r.defeats}
    for r in live:
        if r.rule_id in defeated:
            out.defeated.append(r.rule_id)
            continue
        out.applicable.append(r.rule_id)
        for eff in r.effects:
            if isinstance(eff, Penalty):
                amt = penalty_amount(eff, facts)
                if amt is not None:
                    out.amounts[r.rule_id] = out.amounts.get(r.rule_id, 0.0) + amt
    return out


def executability_rate(rules: list[LegalRule]) -> float:
    return sum(is_executable(r) for r in rules) / len(rules) if rules else 0.0
