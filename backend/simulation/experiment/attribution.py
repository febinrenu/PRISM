"""
Which extracted provisions cause the divergence from the expert?

The players are the targets of a provision set (each target is filled from
one statute provision). A coalition S takes the system's value for the
targets in S and the expert's value for the rest; the value of a coalition is
a divergence measure of the resulting law from the expert law:

    revenue_error_crore   system revenue change − expert revenue change
    decile_rate_l1        L1 distance of decile effective rates
    flips                 number of pre-registered conclusions that differ

Exact Shapley values over the targets that differ (at most a handful per
set, so all 2^n coalitions are evaluated). By construction they sum to the
divergence of the full system law. The minimal restoring set is the smallest
set of targets that, replaced by the expert's reading, removes every flip.
"""
from itertools import combinations
from math import factorial

import numpy as np

from simulation.rac.types import PITParams

MEASURES = ("revenue_error_crore", "decile_rate_l1", "flips")


def apply_target(dst: PITParams, src: PITParams, target: str) -> None:
    """Copy the parameter(s) named by `target` from src into dst (in place)."""
    parts = target.split(".")
    if target == "cess":
        dst.cess_rate = src.cess_rate
        return
    regime, field = parts[0], parts[1]
    d, s = dst.regimes[regime], src.regimes[regime]
    if field == "slabs":
        if len(parts) == 2 or regime == "new":
            d.slabs = {k: list(v) for k, v in s.slabs.items()}
            d.same_for_all_ages = s.same_for_all_ages
        else:
            age = parts[2]
            if d.same_for_all_ages:
                d.slabs = {a: list(d.slabs["below_60"]) for a in ("below_60", "60_to_80", "80_plus")}
                d.same_for_all_ages = False
            d.slabs[age] = list(s.slabs_for(age))  # type: ignore[index]
    elif field == "rebate":
        d.rebate = s.rebate.model_copy() if s.rebate else None
    elif field == "standard_deduction":
        d.standard_deduction = s.standard_deduction
    elif field == "surcharge":
        d.surcharge = [b.model_copy() for b in s.surcharge]
    else:
        raise ValueError(f"unknown target {target}")


def _differs(expert: PITParams, system: PITParams, target: str) -> bool:
    probe = expert.model_copy(deep=True)
    apply_target(probe, system, target)
    return probe.canonical_hash() != expert.canonical_hash()


def hybrid(expert: PITParams, system: PITParams, coalition) -> PITParams:
    p = expert.model_copy(deep=True)
    for t in coalition:
        apply_target(p, system, t)
    return p


class _Evaluator:
    """Divergence of a parameter set from the expert on one population,
    relative to the same 'before' law the conclusions use."""

    def __init__(self, expert: PITParams, before, pop):
        from simulation.engine.outcomes import decile_rates
        from simulation.engine.static import simulate
        from simulation.experiment.conclusions import conclusions

        self._simulate, self._decile_rates, self._conclusions = simulate, decile_rates, conclusions
        self.pop, self.before = pop, before
        self.exp_after = simulate(expert, pop)
        self.exp_c = conclusions(before, self.exp_after, self.exp_after)
        self.exp_deciles = decile_rates(self.exp_after)
        self._cache: dict[str, dict] = {}

    def __call__(self, params: PITParams) -> dict:
        h = params.canonical_hash()
        if h not in self._cache:
            after = self._simulate(params, self.pop)
            c = self._conclusions(self.before, after, self.exp_after)
            ds = self._decile_rates(after)
            self._cache[h] = {
                "revenue_error_crore": (after.revenue() - self.exp_after.revenue()) / 1e7,
                "decile_rate_l1": float(sum(abs(a["effective_rate"] - b["effective_rate"])
                                            for a, b in zip(self.exp_deciles, ds))),
                "flips": float(sum(self.exp_c[k] != c.get(k) for k in self.exp_c)),
                "flipped": sorted(k for k in self.exp_c if self.exp_c[k] != c.get(k)),
            }
        return self._cache[h]


def shapley(players: list[str], value) -> dict[str, dict[str, float]]:
    """Exact Shapley values of `value(coalition) -> {measure: float}`."""
    n = len(players)
    phi = {p: {m: 0.0 for m in MEASURES} for p in players}
    for p in players:
        others = [q for q in players if q != p]
        for size in range(n):
            w = factorial(size) * factorial(n - size - 1) / factorial(n)
            for S in combinations(others, size):
                with_p, without = value(S + (p,)), value(S)
                for m in MEASURES:
                    phi[p][m] += w * (with_p[m] - without[m])
    return phi


def attribute(expert: PITParams, system: PITParams, targets: dict[str, str], before, pop,
              failed: set[str] = frozenset()) -> dict:
    """Shapley attribution of the system's divergence to its targets.

    `failed` targets could not be assembled (they hold the expert value in
    `system`); they are reported, not attributed — the run has no conclusion
    for them."""
    ev = _Evaluator(expert, before, pop)
    players = [t for t in targets if t not in failed and _differs(expert, system, t)]
    value = lambda S: ev(hybrid(expert, system, S))  # noqa: E731
    total = value(tuple(players))
    phi = shapley(players, value)

    restoring = None
    if total["flips"] > 0:
        for size in range(1, len(players) + 1):
            for R in combinations(players, size):
                keep = tuple(t for t in players if t not in R)
                if value(keep)["flips"] == 0:
                    restoring = list(R)
                    break
            if restoring is not None:
                break

    return {
        "players": [{"target": t, "provision": targets[t], **{m: phi[t][m] for m in MEASURES},
                     "alone": {m: value((t,))[m] for m in MEASURES}} for t in players],
        "identical_targets": [t for t in targets if t not in failed and t not in players],
        "failed_targets": sorted(failed),
        "total": {m: total[m] for m in MEASURES},
        "flipped": total["flipped"],
        "minimal_restoring_set": restoring,
        "efficiency_gap": {m: float(abs(sum(phi[t][m] for t in players) - total[m])) for m in MEASURES},
    }


def check_efficiency(result: dict, tol: float = 1e-6) -> bool:
    return all(np.isclose(v, 0.0, atol=tol) for v in result["efficiency_gap"].values())
