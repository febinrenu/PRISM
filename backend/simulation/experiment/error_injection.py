"""
Which kinds of extraction error change a policy conclusion?

A controlled complement to the system runs. Each typed error is injected
into the expert law at one target of a provision set (as if one provision
had been misread in that way) and the pre-registered conclusions are
recomputed. The operators mirror the errors observed in system outputs
(a dropped top band, a missing marginal-relief clause) and the classic
misreadings of Indian statutory numbers (lakh vs crore, a rate read from the
wrong column, the previous year's table).

Output: per reform × target × error type, the flip rate, revenue error,
decile-rate distance, and the flips' persistence over population draws.
"""
from typing import Callable, Optional

from simulation.experiment.harness import _previous_ay
from simulation.experiment.provision_sets import PROVISION_SETS
from simulation.rac import gold
from simulation.rac.types import PITParams, Rebate, Slab

Operator = Callable[[PITParams, str], Optional[PITParams]]


def _slabs(p: PITParams, target: str) -> list[Slab]:
    regime = target.split(".")[0]
    parts = target.split(".")
    age = parts[2] if len(parts) > 2 else "below_60"
    return list(p.regimes[regime].slabs_for(age))  # type: ignore[arg-type]


def _set_slabs(p: PITParams, target: str, slabs: list[Slab]) -> PITParams:
    q = p.model_copy(deep=True)
    regime = target.split(".")[0]
    parts = target.split(".")
    sched = q.regimes[regime]
    if len(parts) > 2 and not sched.same_for_all_ages:
        sched.slabs[parts[2]] = slabs  # type: ignore[index]
    elif len(parts) > 2:
        sched.slabs = {a: list(sched.slabs["below_60"]) for a in ("below_60", "60_to_80", "80_plus")}
        sched.same_for_all_ages = False
        sched.slabs[parts[2]] = slabs  # type: ignore[index]
    else:
        sched.slabs = {"below_60": slabs}
        sched.same_for_all_ages = True
    return q


# ── slab-table operators ────────────────────────────────────────────────────

def drop_top_band(p, t):
    s = _slabs(p, t)
    if len(s) < 3:
        return None
    s = s[:-1]
    s[-1] = Slab(lower=s[-1].lower, upper=None, rate=s[-1].rate)
    return _set_slabs(p, t, s)


def drop_middle_band(p, t):
    s = _slabs(p, t)
    if len(s) < 4:
        return None
    i = len(s) // 2
    merged = Slab(lower=s[i - 1].lower, upper=s[i].upper, rate=s[i - 1].rate)
    return _set_slabs(p, t, s[:i - 1] + [merged] + s[i + 1:])


def shift_bound_one_lakh(p, t):
    s = _slabs(p, t)
    if len(s) < 2:
        return None
    i = len(s) // 2 - 1 if len(s) > 2 else 0
    new_b = s[i].upper + 100_000
    if s[i + 1].upper is not None and new_b >= s[i + 1].upper:
        return None
    s[i] = Slab(lower=s[i].lower, upper=new_b, rate=s[i].rate)
    s[i + 1] = Slab(lower=new_b, upper=s[i + 1].upper, rate=s[i + 1].rate)
    return _set_slabs(p, t, s)


def off_by_one_rupee(p, t):
    """'From Rs. 3,00,001' read as a band starting at 3,00,001 (should be harmless)."""
    s = _slabs(p, t)
    if len(s) < 2:
        return None
    s[0] = Slab(lower=s[0].lower, upper=s[0].upper + 1, rate=s[0].rate)
    s[1] = Slab(lower=s[0].upper, upper=s[1].upper, rate=s[1].rate)
    return _set_slabs(p, t, s)


def lakh_crore_confusion(p, t):
    """The first positive-rate band's upper bound read in crore instead of lakh (×100)."""
    s = _slabs(p, t)
    i = next((k for k, b in enumerate(s) if b.rate > 0 and b.upper is not None), None)
    if i is None:
        return None
    hi = s[i].upper * 100
    rest = [b for b in s[i + 1:] if b.upper is None or b.upper > hi]
    if not rest:
        return None
    s2 = s[:i] + [Slab(lower=s[i].lower, upper=hi, rate=s[i].rate)]
    s2 += [Slab(lower=hi, upper=rest[0].upper, rate=rest[0].rate)] + rest[1:]
    return _set_slabs(p, t, s2)


def rate_from_adjacent_row(p, t):
    """One middle band's rate read from the row below."""
    s = _slabs(p, t)
    if len(s) < 3:
        return None
    i = len(s) // 2
    s[i] = Slab(lower=s[i].lower, upper=s[i].upper, rate=s[i + 1].rate)
    return _set_slabs(p, t, s)


def previous_year_table(p, t):
    prev = _previous_ay(p.ay)
    if prev == p.ay:
        return None
    G = gold.build_gold()
    regime = t.split(".")[0]
    if regime not in G[prev].regimes:
        return None
    return _set_slabs(p, t, _slabs(G[prev], t))


# ── rebate operators ────────────────────────────────────────────────────────

def _rebate(p, t) -> Optional[Rebate]:
    return p.regimes[t.split(".")[0]].rebate


def _set_rebate(p, t, r: Optional[Rebate]) -> PITParams:
    q = p.model_copy(deep=True)
    q.regimes[t.split(".")[0]].rebate = r
    return q


def drop_marginal_relief(p, t):
    r = _rebate(p, t)
    if r is None or not r.marginal_relief:
        return None
    return _set_rebate(p, t, Rebate(max_income=r.max_income, max_rebate=r.max_rebate, marginal_relief=False))


def drop_rebate(p, t):
    return _set_rebate(p, t, None) if _rebate(p, t) is not None else None


def previous_year_rebate(p, t):
    prev = _previous_ay(p.ay)
    G = gold.build_gold()
    regime = t.split(".")[0]
    if prev == p.ay or regime not in G[prev].regimes:
        return None
    old = G[prev].regimes[regime].rebate
    return _set_rebate(p, t, old.model_copy() if old else None)


def rebate_amount_misread(p, t):
    """Maximum rebate read from the limit's neighbour: the old amount with the new limit."""
    r = _rebate(p, t)
    prev = _previous_ay(p.ay)
    G = gold.build_gold()
    regime = t.split(".")[0]
    if r is None or prev == p.ay or regime not in G[prev].regimes or G[prev].regimes[regime].rebate is None:
        return None
    old = G[prev].regimes[regime].rebate
    if old.max_rebate == r.max_rebate:
        return None
    return _set_rebate(p, t, Rebate(max_income=r.max_income, max_rebate=old.max_rebate, marginal_relief=r.marginal_relief))


def other_regime_rebate(p, t):
    """The rebate the same Act grants under the other regime (a scoping error:
    s.156(1) vs s.156(2) of the Income-tax Act 2025)."""
    regime = t.split(".")[0]
    other = "old" if regime == "new" else "new"
    if other not in p.regimes or p.regimes[other].rebate is None:
        return None
    r = p.regimes[other].rebate
    if r == _rebate(p, t):
        return None
    return _set_rebate(p, t, r.model_copy())


# ── standard deduction ──────────────────────────────────────────────────────

def previous_year_standard_deduction(p, t):
    prev = _previous_ay(p.ay)
    G = gold.build_gold()
    regime = t.split(".")[0]
    if prev == p.ay or regime not in G[prev].regimes:
        return None
    old = G[prev].regimes[regime].standard_deduction
    if old == p.regimes[regime].standard_deduction:
        return None
    q = p.model_copy(deep=True)
    q.regimes[regime].standard_deduction = old
    return q


OPERATORS: dict[str, tuple[str, Operator]] = {
    "drop_top_band": ("slabs", drop_top_band),
    "drop_middle_band": ("slabs", drop_middle_band),
    "shift_bound_1_lakh": ("slabs", shift_bound_one_lakh),
    "off_by_one_rupee": ("slabs", off_by_one_rupee),
    "lakh_crore_confusion": ("slabs", lakh_crore_confusion),
    "rate_from_adjacent_row": ("slabs", rate_from_adjacent_row),
    "previous_year_table": ("slabs", previous_year_table),
    "drop_marginal_relief": ("rebate", drop_marginal_relief),
    "drop_rebate": ("rebate", drop_rebate),
    "previous_year_rebate": ("rebate", previous_year_rebate),
    "rebate_amount_misread": ("rebate", rebate_amount_misread),
    "other_regime_rebate": ("rebate", other_regime_rebate),
    "previous_year_standard_deduction": ("standard_deduction", previous_year_standard_deduction),
}


def run(n_draws: int = 32, progress=print) -> list[dict]:
    from simulation.backtest.run import population_for
    from simulation.experiment.attribution import _Evaluator
    from simulation.experiment.harness import baseline
    from simulation.experiment.stats import robustness

    G = gold.build_gold()
    rows = []
    for set_name, spec in PROVISION_SETS.items():
        ay = spec["ay"]
        expert = G[ay]
        pop = population_for(ay)
        ev = _Evaluator(expert, baseline(expert, ay, pop), pop)
        for target in spec["targets"]:
            field = target.split(".")[1]
            for name, (kind, op) in OPERATORS.items():
                if kind != field:
                    continue
                injected = op(expert, target)
                if injected is None or injected.canonical_hash() == expert.canonical_hash():
                    continue
                d = ev(injected)
                rob = robustness({"set": set_name, "system": name, "ay": ay, "complete": True,
                                  "params": injected.model_dump(mode="json"),
                                  "population": {"conclusions_expert": ev.exp_c, "flipped": d["flipped"],
                                                 "flip_rate": d["flips"] / len(ev.exp_c)}}, n_draws)
                persist = list(rob["persistence"].values())
                rows.append({
                    "set": set_name, "target": target, "error": name,
                    "flip_rate": d["flips"] / len(ev.exp_c), "flipped": d["flipped"],
                    "revenue_error_crore": d["revenue_error_crore"], "decile_rate_l1": d["decile_rate_l1"],
                    "min_persistence": min(persist) if persist else None,
                    "noise_floor_mean": rob["noise_floor_mean"],
                })
                progress(f"{set_name:20s} {target:22s} {name:32s} flips {rows[-1]['flip_rate']:.2f} "
                         f"revenue error {d['revenue_error_crore']:>12,.0f} cr")
    return rows
