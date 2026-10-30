"""
Policy scenarios on the statute's own rate schedule.

The sandbox's first mode (simulation/model.py) turns every extracted clause into a
levy on an illustrative population. This one starts from the law: the income-tax
rate table is read from the document (pipeline/schedules.py), a baseline law is
built from it, the user changes the law (a rate, a threshold, the rebate, the
standard deduction, the cess), and the same statutory calculator and the same
population that reproduce the published tax statistics (simulation/rac,
simulation/population) price the change.

Baseline    the document's slab table is the new-regime schedule. Everything the
            table cannot say (rebate, standard deduction, surcharge, cess, the old
            regime) comes from the expert coding of the assessment year whose table
            it is, and each parameter says which. If the table is no year's table,
            the document's slabs are used and the rest comes from the latest year.
Scenario    a set of changes to that baseline, validated (a complete schedule,
            rates between 0 and 1, no combined marginal rate over 100%).
Outcomes    revenue, taxpayers paying, effective rate by income decile and by the
            law's own income bands, who pays more and who pays less, Gini, Kakwani
            and Suits indices; each as baseline, scenario and difference.
Attribution the revenue effect split over the individual changes by Shapley value
            (exact up to 8 changes, sampled beyond), so the parts add to the whole.
Uncertainty the population assumptions the published statistics do not pin down
            (how many taxpayers pick the cheaper regime, the size of Chapter VI-A
            deductions, the shape of the top income tail, the share of seniors,
            income growth) are varied over the ranges of the global sensitivity
            analysis; the effect is reported as a range, with a one-at-a-time
            tornado that says which assumption matters.
Behaviour   optionally, the compliance model (simulation/behaviour) is run under
            both laws, so the revenue effect includes a change in evasion.

Scope (the same as the calculator's): resident individuals, income at normal rates.
It is a static model of one year's tax: no change in labour supply or avoidance
beyond the optional compliance model.
"""
import itertools
import math
from dataclasses import dataclass, field, replace
from functools import lru_cache
from types import SimpleNamespace
from typing import Callable, Optional

import numpy as np

from simulation.backtest.run import ANNOUNCED_COST, Settings, age, forecast_protocol, in_sample, income_year, macro, reform_cost
from simulation.behaviour import compliance
from simulation.engine.outcomes import summarise
from simulation.engine.sensitivity import PROBLEM
from simulation.engine.static import StaticResult, simulate
from simulation.population.taxpayers import Population, build
from simulation.rac import gold
from simulation.rac.types import PITParams, Rebate, Slab
from simulation.translate.assemble import build_schedule

CRORE = 1e7
LAKH = 1e5
BASE_POP_AY = "2023-24"                    # the latest year with published tax statistics
DEFAULT_GROWTH = Settings().nominal_growth_after_2023_24
BOUNDS = {n: (float(lo), float(hi)) for n, (lo, hi) in zip(PROBLEM["names"], PROBLEM["bounds"])}
NO_CHANGE = 0.5                            # rupees: a change smaller than this is no change
MAX_EXACT_LEVERS = 8
HIGH_MARGINAL = 0.6


class ScenarioError(ValueError):
    """A scenario that is not a law: the message says why."""


# ── numbers for people ──────────────────────────────────────────────────────

def inr(x: float) -> str:
    """₹ amount as the law writes it, in lakh and crore."""
    x = float(x)
    if abs(x) >= CRORE:
        return f"₹{x / CRORE:g} crore"
    if abs(x) >= LAKH:
        return f"₹{x / LAKH:g} lakh"
    return f"₹{x:,.0f}"


def pct(rate: float) -> str:
    return f"{rate * 100:g}%"


# ── assumptions about the population ────────────────────────────────────────

@dataclass(frozen=True)
class Assumptions:
    """What the published statistics do not say, as the model needs it."""
    optimal_share: float = 1.0               # share of taxpayers choosing the cheaper regime
    via_scale: float = 1.0                   # Chapter VI-A deductions × this
    top_alpha: Optional[float] = None        # Pareto shape of the open top income band; None = from the band's mean
    senior_share: float = 0.0                # share of taxpayers aged 60-80
    growth: float = DEFAULT_GROWTH           # nominal income growth beyond the published series

    def checked(self) -> "Assumptions":
        limits = {"optimal_share": (0.0, 1.0), "via_scale": (0.0, 3.0), "senior_share": (0.0, 1.0),
                  "growth": (-0.2, 0.5)}
        for name, (lo, hi) in limits.items():
            v = getattr(self, name)
            if not lo <= v <= hi:
                raise ScenarioError(f"{name} must be between {lo:g} and {hi:g}")
        if self.top_alpha is not None and not 1.05 <= self.top_alpha <= 10.0:
            raise ScenarioError("top_alpha must be between 1.05 and 10")
        return self

    def as_dict(self) -> dict:
        return {"optimal_share": self.optimal_share, "via_scale": self.via_scale, "top_alpha": self.top_alpha,
                "senior_share": self.senior_share, "growth": self.growth}


@lru_cache(maxsize=1)
def _macro() -> dict:
    return macro()


@lru_cache(maxsize=64)
def _base_population(via_scale: float, top_alpha: Optional[float]) -> Population:
    return build(BASE_POP_AY, via_scale=via_scale, top_alpha=top_alpha)


def population(ay: str, a: Assumptions) -> Population:
    """The latest observed taxpayer population, aged to the income year of `ay` by
    nominal GDP (extrapolated at `a.growth` beyond the published series)."""
    M = _macro()
    base_fy, target_fy = income_year(BASE_POP_AY), income_year(ay)
    if target_fy in M:
        f = M[target_fy]["gdp"] / M[base_fy]["gdp"]
    else:
        last = max(M)
        f = M[last]["gdp"] / M[base_fy]["gdp"] * (1 + a.growth) ** (int(target_fy[:4]) - int(last[:4]))
    return age(_base_population(a.via_scale, a.top_alpha), f, 1.0, ay)


def _simulate(law: PITParams, pop: Population, a: Assumptions) -> StaticResult:
    return simulate(law, pop, a.optimal_share, senior_share=a.senior_share)


# ── the baseline law ────────────────────────────────────────────────────────

@dataclass
class Baseline:
    params: PITParams
    ay: str                                    # assessment year of the calculator's law
    source: str                                # "document" | "expert"
    title: str
    matched_year: Optional[str]                # the expert-coded year whose table the document's is
    provenance: list[dict] = field(default_factory=list)
    review: list[str] = field(default_factory=list)
    schedule: Optional[dict] = None            # the document's table (page, heading, rows)

    def public(self) -> dict:
        new = self.params.regimes["new"]
        return {
            "ay": self.ay, "law": self.params.law, "source": self.source, "title": self.title,
            "matched_year": self.matched_year, "review": self.review, "provenance": self.provenance,
            "schedule": ({"page": self.schedule["page"], "heading": self.schedule["heading"],
                          "assessment_year": self.schedule.get("assessment_year")} if self.schedule else None),
            "law_params": law_view(self.params),
            "regimes": list(self.params.regimes), "default_regime": self.params.default_regime,
            "old_regime_slabs": ([s.model_dump() for s in self.params.regimes["old"].slabs["below_60"]]
                                 if "old" in self.params.regimes else None),
            "surcharge": [b.model_dump() for b in new.surcharge],
        }


def law_view(p: PITParams) -> dict:
    new = p.regimes["new"]
    return {
        "slabs": [s.model_dump() for s in new.slabs["below_60"]],
        "rebate": new.rebate.model_dump() if new.rebate else None,
        "standard_deduction": new.standard_deduction,
        "cess_rate": p.cess_rate,
    }


def _slab_key(slabs: list[Slab]) -> list[tuple]:
    return [(round(s.lower), None if s.upper is None else round(s.upper), round(s.rate, 6)) for s in slabs]


def usable_schedules(schedules: list[dict]) -> list[dict]:
    """The document's tables that are complete rate schedules (the checks passed)."""
    return [{**s, "index": i} for i, s in enumerate(schedules)
            if s.get("check", {}).get("ok") and len([r for r in s.get("rows", []) if r.get("rate") is not None]) >= 3]


def document_slabs(schedule: dict) -> tuple[Optional[list[Slab]], Optional[str]]:
    rows = [SimpleNamespace(lower=r["lower"], upper=r["upper"], rate=r["rate"])
            for r in schedule["rows"] if r.get("rate") is not None]
    return build_schedule(rows)


def _cit(p: PITParams, path: str) -> str:
    c = p.citations.get(path)
    return f"{c.statute} {c.provision}".strip() if c else "expert coding"


def _provenance(p: PITParams, ay: str, slabs: list[Slab], schedule: dict, matched: Optional[str]) -> list[dict]:
    new = p.regimes["new"]
    rows = [{
        "parameter": "Tax slabs", "value": f"{len(slabs)} bands, {pct(slabs[0].rate)} to {pct(slabs[-1].rate)}",
        "source": f"Read from the document, page {schedule['page']}",
        "check": (f"Matches the expert coding of AY {matched} ({_cit(p, 'regimes.new.slabs')})" if matched else
                  "Not any expert-coded year's table: the document's is used as read"),
        "from_document": True,
    }]
    if new.rebate:
        r = new.rebate
        rows.append({"parameter": "Rebate", "from_document": False,
                     "value": f"up to {inr(r.max_rebate)} where income is at most {inr(r.max_income)}"
                              + (", with marginal relief" if r.marginal_relief else ""),
                     "source": f"Expert coding, AY {ay}: {_cit(p, 'regimes.new.rebate')}", "check": ""})
    rows.append({"parameter": "Standard deduction", "from_document": False, "value": inr(new.standard_deduction),
                 "source": f"Expert coding, AY {ay}: {_cit(p, 'regimes.new.standard_deduction')}", "check": ""})
    if new.surcharge:
        rows.append({"parameter": "Surcharge", "from_document": False,
                     "value": ", ".join(f"{pct(b.rate)} above {inr(b.threshold)}" for b in new.surcharge),
                     "source": f"Expert coding, AY {ay}: {_cit(p, 'regimes.new.surcharge')}", "check": ""})
    rows.append({"parameter": "Health and education cess", "from_document": False, "value": pct(p.cess_rate),
                 "source": f"Expert coding, AY {ay}: {_cit(p, 'cess_rate')}", "check": ""})
    if "old" in p.regimes:
        rows.append({"parameter": "Old regime", "from_document": False,
                     "value": "unchanged by a scenario; each taxpayer files under the regime that costs less",
                     "source": f"Expert coding, AY {ay}", "check": ""})
    return rows


def baseline_from_schedule(schedule: dict, title: str = "", prefer_law: Optional[str] = None) -> Baseline:
    """The baseline law for a document whose rate table is `schedule` (one entry of
    pipeline.schedules.find_schedules)."""
    slabs, why = document_slabs(schedule)
    if slabs is None:
        raise ScenarioError(f"The table on page {schedule['page']} is not a complete rate schedule: {why}")
    G = gold.build_gold()
    key = _slab_key(slabs)
    same = sorted(ay for ay, p in G.items() if "new" in p.regimes and _slab_key(p.regimes["new"].slabs["below_60"]) == key)
    review: list[str] = []
    if same:
        preferred = [ay for ay in same if G[ay].law == prefer_law] if prefer_law else []
        ay = (preferred or same)[0]
        params = G[ay].model_copy(deep=True)
        matched: Optional[str] = ay
        if len(same) > 1 and not preferred:
            review.append(f"The same table applies in AY {', '.join(same)}; AY {ay} is used for the other parameters.")
    else:
        ay = max(a for a, p in G.items() if "new" in p.regimes)
        params = G[ay].model_copy(deep=True)
        params.regimes["new"].slabs = {"below_60": slabs}
        params.regimes["new"].same_for_all_ages = True
        matched = None
        review.append(f"The document's table is not the table of any expert-coded year. Its slabs are used as read; the "
                      f"rebate, standard deduction, surcharge and cess are those of AY {ay} and may not be this "
                      f"document's: check them in the law panel.")
    return Baseline(params=params, ay=ay, source="document", title=title or f"Rate table, page {schedule['page']}",
                    matched_year=matched, provenance=_provenance(params, ay, slabs, schedule, matched), review=review,
                    schedule=schedule)


def baseline_from_expert(ay: str) -> Baseline:
    """The expert coding of one assessment year, for a document with no rate table."""
    G = gold.build_gold()
    if ay not in G or "new" not in G[ay].regimes:
        raise ScenarioError(f"No expert-coded law with a new regime for AY {ay}")
    params = G[ay].model_copy(deep=True)
    slabs = params.regimes["new"].slabs["below_60"]
    fake = {"page": 0}
    prov = _provenance(params, ay, slabs, fake, ay)
    prov[0].update(source=f"Expert coding, AY {ay}: {_cit(params, 'regimes.new.slabs')}", check="", from_document=False)
    return Baseline(params=params, ay=ay, source="expert", title=f"Expert-coded law, AY {ay}", matched_year=ay,
                    provenance=prov, review=["No rate table from a document: this is the expert coding of the law."])


# ── a scenario: changes to the baseline ─────────────────────────────────────

def _num(v, what: str, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ScenarioError(f"{what} must be a number")
    if not math.isfinite(x) or not lo <= x <= hi:
        raise ScenarioError(f"{what} must be between {lo:g} and {hi:g}")
    return x


def apply_changes(base: PITParams, changes: dict) -> tuple[PITParams, list[str]]:
    """The baseline with `changes` applied, or a ScenarioError saying why it is not a law.

    changes: {"slabs": [{lower, upper, rate}, ...], "rebate": {max_income, max_rebate, marginal_relief} | None,
              "standard_deduction": x, "cess_rate": x}; a key left out stays as in the baseline."""
    p = base.model_copy(deep=True)
    new = p.regimes["new"]
    changes = changes or {}
    if changes.get("slabs") is not None:
        rows = []
        for i, r in enumerate(changes["slabs"]):
            upper = r.get("upper")
            rows.append(SimpleNamespace(
                lower=_num(r.get("lower"), f"band {i + 1} lower limit", 0, 1e11),
                upper=None if upper is None else _num(upper, f"band {i + 1} upper limit", 0, 1e11),
                rate=_num(r.get("rate"), f"band {i + 1} rate", 0, 1)))
        slabs, why = build_schedule(rows)
        if slabs is None:
            raise ScenarioError(f"The slab schedule is not complete: {why}")
        new.slabs, new.same_for_all_ages = {"below_60": slabs}, True
    if "rebate" in changes:
        r = changes["rebate"]
        new.rebate = None if r is None else Rebate(
            max_income=_num(r.get("max_income"), "rebate income limit", 0, 1e11),
            max_rebate=_num(r.get("max_rebate"), "rebate amount", 0, 1e11),
            marginal_relief=bool(r.get("marginal_relief", False)))
    if changes.get("standard_deduction") is not None:
        new.standard_deduction = _num(changes["standard_deduction"], "standard deduction", 0, 1e9)
    if changes.get("cess_rate") is not None:
        p.cess_rate = _num(changes["cess_rate"], "cess rate", 0, 0.2)
    top = max(s.rate for s in new.slabs["below_60"])
    surcharge = max((b.rate for b in new.surcharge), default=0.0)
    if top * (1 + surcharge) * (1 + p.cess_rate) > 1.0:
        raise ScenarioError("The highest combined marginal rate (slab, surcharge and cess) would exceed 100%")
    notes = []
    if top * (1 + surcharge) * (1 + p.cess_rate) > HIGH_MARGINAL:
        notes.append(f"The highest combined marginal rate is {pct(top * (1 + surcharge) * (1 + p.cess_rate))}.")
    return p, notes


# ── levers: the individual changes a scenario is made of ────────────────────

@dataclass
class Lever:
    id: str
    label: str
    copy: Callable[[PITParams, PITParams], None]           # copy this lever's value from the 2nd law into the 1st


def levers(base: PITParams, reform: PITParams) -> list[Lever]:
    out: list[Lever] = []
    bn, rn = base.regimes["new"], reform.regimes["new"]
    bs, rs = bn.slabs["below_60"], rn.slabs["below_60"]

    def slab_copy(i, fields):
        def f(target: PITParams, source: PITParams):
            t, s = target.regimes["new"].slabs["below_60"], source.regimes["new"].slabs["below_60"]
            if "rate" in fields:
                t[i].rate = s[i].rate
            if "upper" in fields:
                t[i].upper, t[i + 1].lower = s[i].upper, s[i + 1].lower
        return f

    if len(bs) == len(rs):
        for i, (a, b) in enumerate(zip(bs, rs)):
            if abs(a.rate - b.rate) > 1e-9:
                out.append(Lever(f"rate:{i}", f"Rate of band {i + 1}: {pct(a.rate)} to {pct(b.rate)}", slab_copy(i, ("rate",))))
            if i < len(bs) - 1 and (a.upper != b.upper):
                out.append(Lever(f"upper:{i}", f"Limit between bands {i + 1} and {i + 2}: {inr(a.upper)} to {inr(b.upper)}",
                                 slab_copy(i, ("upper",))))
    elif _slab_key(bs) != _slab_key(rs):
        def whole(target, source):
            target.regimes["new"].slabs = {"below_60": [s.model_copy() for s in source.regimes["new"].slabs["below_60"]]}
        out.append(Lever("slabs", f"Slab schedule: {len(bs)} bands to {len(rs)}", whole))
    if bn.rebate != rn.rebate:
        def reb(target, source):
            target.regimes["new"].rebate = source.regimes["new"].rebate.model_copy() if source.regimes["new"].rebate else None
        what = ("removed" if rn.rebate is None else
                f"up to {inr(rn.rebate.max_rebate)} to income of {inr(rn.rebate.max_income)}" if bn.rebate is None else
                f"{inr(bn.rebate.max_rebate)} up to {inr(bn.rebate.max_income)} to {inr(rn.rebate.max_rebate)} up to {inr(rn.rebate.max_income)}")
        out.append(Lever("rebate", f"Rebate: {what}", reb))
    if abs(bn.standard_deduction - rn.standard_deduction) > NO_CHANGE:
        out.append(Lever("standard_deduction", f"Standard deduction: {inr(bn.standard_deduction)} to {inr(rn.standard_deduction)}",
                         lambda t, s: setattr(t.regimes["new"], "standard_deduction", s.regimes["new"].standard_deduction)))
    if abs(base.cess_rate - reform.cess_rate) > 1e-9:
        out.append(Lever("cess", f"Cess: {pct(base.cess_rate)} to {pct(reform.cess_rate)}",
                         lambda t, s: setattr(t, "cess_rate", s.cess_rate)))
    return out


def shapley(base: PITParams, reform: PITParams, ls: list[Lever], value: Callable[[PITParams], float],
            seed: int = 7, permutations: int = 240) -> list[float]:
    """Each lever's average marginal effect on `value` over all orders in which the
    levers could be applied. The values add up to value(reform) - value(base). Exact
    up to MAX_EXACT_LEVERS levers; averaged over random orders beyond."""
    k = len(ls)
    if k == 0:
        return []
    cache: dict[frozenset, float] = {}

    def v(members: frozenset) -> float:
        if members not in cache:
            p = base.model_copy(deep=True)
            for j in members:
                ls[j].copy(p, reform)
            cache[members] = value(p)
        return cache[members]

    phi = [0.0] * k
    if k <= MAX_EXACT_LEVERS:
        fact = math.factorial
        for i in range(k):
            others = [j for j in range(k) if j != i]
            for r in range(k):
                weight = fact(r) * fact(k - r - 1) / fact(k)
                for s in itertools.combinations(others, r):
                    phi[i] += weight * (v(frozenset(s) | {i}) - v(frozenset(s)))
        return phi
    rng = np.random.default_rng(seed)
    for _ in range(permutations):
        order = rng.permutation(k)
        seen: frozenset = frozenset()
        for i in order:
            phi[i] += v(seen | {int(i)}) - v(seen)
            seen = seen | {int(i)}
    return [x / permutations for x in phi]


# ── outcomes ────────────────────────────────────────────────────────────────

def _brief(res: StaticResult) -> dict:
    s = summarise(res)
    return {
        "revenue_crore": s["revenue"] / CRORE, "taxpayers_with_tax": s["taxpayers_with_tax"], "returns": s["returns"],
        "gini_pre": s["gini_pre"], "gini_post": s["gini_post"], "kakwani": s["kakwani"],
        "reynolds_smolensky": s["reynolds_smolensky"], "suits": s["suits"], "new_regime_share": s["new_regime_share"],
        "deciles": [{"decile": d["decile"], "tax_crore": d["tax"] / CRORE, "income_crore": d["income"] / CRORE,
                     "effective_rate": d["effective_rate"], "income_upper": d["income_upper"]} for d in s["deciles"]],
    }


def _impact(b: StaticResult, r: StaticResult, edges: list[float], labels: list[str]) -> list[dict]:
    """Who pays more and who pays less, for groups of returns by gross total income."""
    change = r.tax - b.tax
    out = []
    for label, lo, hi in zip(labels, edges[:-1], edges[1:]):
        m = (b.gti > lo) & (b.gti <= hi)
        w = b.weight[m]
        total = float(w.sum())
        if total <= 0:
            continue
        c = change[m]
        income = float((b.gti[m] * w).sum())
        out.append({
            "label": label, "lower": None if math.isinf(lo) else lo, "upper": None if math.isinf(hi) else hi,
            "returns": total,
            "share_pay_less": float(w[c < -NO_CHANGE].sum() / total), "share_pay_more": float(w[c > NO_CHANGE].sum() / total),
            "mean_change_inr": float((c * w).sum() / total),
            "base_tax_crore": float((b.tax[m] * w).sum() / CRORE), "reform_tax_crore": float((r.tax[m] * w).sum() / CRORE),
            "base_rate": float((b.tax[m] * w).sum() / income) if income > 0 else 0.0,
            "reform_rate": float((r.tax[m] * w).sum() / income) if income > 0 else 0.0,
        })
    return out


def _band_edges(base: PITParams, reform: PITParams) -> tuple[list[float], list[str]]:
    """The law's own income bands: every slab limit and rebate limit of either law, and the surcharge thresholds."""
    cuts = {0.0}
    for p in (base, reform):
        n = p.regimes["new"]
        cuts |= {s.upper for s in n.slabs["below_60"] if s.upper}
        if n.rebate:
            cuts.add(n.rebate.max_income)
        cuts |= {b.threshold for b in n.surcharge}
    cuts = sorted(c for c in cuts if c > 0)
    # a band is not worth showing when it is a sliver next to its neighbour
    keep = [c for i, c in enumerate(cuts) if i == 0 or c >= cuts[i - 1] * 1.04]
    edges = [0.0] + keep + [math.inf]
    labels = [f"up to {inr(edges[1])}"] + [f"{inr(a)} to {inr(b)}" for a, b in zip(edges[1:-2], edges[2:-1])] + \
             [f"above {inr(edges[-2])}"]
    return edges, labels


def _decile_edges(res: StaticResult) -> tuple[list[float], list[str]]:
    o = np.argsort(res.gti, kind="stable")
    cum = np.cumsum(res.weight[o]) / res.weight.sum()
    cuts = [float(res.gti[o][np.searchsorted(cum, d / 10)]) for d in range(1, 10)]
    return [-math.inf] + cuts + [math.inf], [f"Decile {d}" for d in range(1, 11)]


def _stat(values: list[float]) -> dict:
    v = np.asarray(values, dtype=float)
    return {"p5": float(np.percentile(v, 5)), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)),
            "min": float(v.min()), "max": float(v.max())}


def _effect(base: PITParams, reform: PITParams, ay: str, a: Assumptions) -> tuple[float, float]:
    """(revenue change in ₹ crore, change in the Kakwani index) under assumptions `a`."""
    pop = population(ay, a)
    b, r = _simulate(base, pop, a), _simulate(reform, pop, a)
    from simulation.engine.outcomes import concentration, gini

    def kak(x: StaticResult) -> float:
        return concentration(x.tax, x.weight, x.gti) - gini(x.gti, x.weight)

    return (r.revenue() - b.revenue()) / CRORE, kak(r) - kak(b)


def uncertainty(base: PITParams, reform: PITParams, ay: str, a: Assumptions, n: int = 64, seed: int = 11) -> dict:
    """How the revenue effect moves with the population assumptions. A Latin hypercube
    over their ranges (those of the global sensitivity analysis) gives the range; one
    assumption at a time at its two ends gives the tornado."""
    from scipy.stats import qmc

    names = list(BOUNDS)
    lows, highs = [BOUNDS[k][0] for k in names], [BOUNDS[k][1] for k in names]
    X = qmc.scale(qmc.LatinHypercube(d=len(names), seed=seed).random(n), lows, highs)
    rev, kak = [], []
    for x in X:
        ai = Assumptions(**dict(zip(names, map(float, x))))
        d_rev, d_kak = _effect(base, reform, ay, ai)
        rev.append(d_rev)
        kak.append(d_kak)
    point = _effect(base, reform, ay, a)[0]
    tornado = []
    for name in names:
        lo_a, hi_a = replace(a, **{name: BOUNDS[name][0]}), replace(a, **{name: BOUNDS[name][1]})
        lo, hi = _effect(base, reform, ay, lo_a)[0], _effect(base, reform, ay, hi_a)[0]
        tornado.append({"input": name, "low_value": BOUNDS[name][0], "high_value": BOUNDS[name][1],
                        "at_low_crore": lo, "at_high_crore": hi, "swing_crore": abs(hi - lo)})
    tornado.sort(key=lambda t: -t["swing_crore"])
    sign = np.sign(point)
    return {"n": n, "ranges": {k: list(v) for k, v in BOUNDS.items()}, "revenue_delta_crore": _stat(rev),
            "kakwani_delta": _stat(kak), "tornado": tornado,
            "sign_stable": bool(sign != 0 and all(np.sign(r) == sign for r in rev))}


# ── behaviour ───────────────────────────────────────────────────────────────

BEHAVIOUR_LIMITS = {"audit_rate": (0.0005, 0.25), "penalty_rate": (0.0, 5.0), "morale": (0.02, 0.95)}
BEHAVIOUR_AGENTS = 3000
BEHAVIOUR_SEEDS = (1, 2, 3)


def behaviour_response(base: PITParams, reform: PITParams, pop: Population, overrides: dict) -> dict:
    """Run the compliance model under each law (same agents and seeds), so the revenue
    effect includes how evasion responds. Reported as a difference between the laws,
    because the level of the modelled tax gap is not calibrated."""
    kw = {}
    for name, (lo, hi) in BEHAVIOUR_LIMITS.items():
        if overrides.get(name) is not None:
            kw[name] = _num(overrides[name], name.replace("_", " "), lo, hi)
    bp = compliance.BehaviourParams(steps=40, burn_in=20, **kw)
    pairs = []
    for seed in BEHAVIOUR_SEEDS:
        pairs.append((compliance.run(base, pop, bp, BEHAVIOUR_AGENTS, seed), compliance.run(reform, pop, bp, BEHAVIOUR_AGENTS, seed)))

    def mean(rows, key):
        return float(np.mean([r[key] for r in rows]))

    b_rows, r_rows = [p[0] for p in pairs], [p[1] for p in pairs]
    deltas = [r["revenue_crore"] - b["revenue_crore"] for b, r in pairs]
    return {
        "params": {"audit_rate": bp.audit_rate, "penalty_rate": bp.penalty_rate, "morale": bp.morale},
        "agents": BEHAVIOUR_AGENTS, "seeds": len(BEHAVIOUR_SEEDS),
        "baseline": {k: mean(b_rows, k) for k in ("revenue_crore", "tax_gap", "evaders")},
        "reform": {k: mean(r_rows, k) for k in ("revenue_crore", "tax_gap", "evaders")},
        "delta_revenue_crore": {"mean": float(np.mean(deltas)), "min": float(min(deltas)), "max": float(max(deltas))},
        "delta_tax_gap": float(np.mean([r["tax_gap"] - b["tax_gap"] for b, r in pairs])),
        "note": "A stylised compliance model (docs/ODD+D.md): its parameters are illustrative and its level of "
                "evasion is not calibrated. Read the difference between the two laws, not the level.",
    }


# ── a scenario run ──────────────────────────────────────────────────────────

def run(baseline: Baseline, changes: dict, a: Assumptions = Assumptions(), behaviour: Optional[dict] = None,
        n_uncertainty: int = 0) -> dict:
    a = a.checked()
    reform, notes = apply_changes(baseline.params, changes)
    ay = baseline.ay
    pop = population(ay, a)
    b, r = _simulate(baseline.params, pop, a), _simulate(reform, pop, a)
    bs, rs = _brief(b), _brief(r)
    delta = {
        "revenue_crore": rs["revenue_crore"] - bs["revenue_crore"],
        "revenue_pct": (rs["revenue_crore"] / bs["revenue_crore"] - 1.0) if bs["revenue_crore"] else 0.0,
        "taxpayers_with_tax": rs["taxpayers_with_tax"] - bs["taxpayers_with_tax"],
        **{k: rs[k] - bs[k] for k in ("gini_post", "kakwani", "reynolds_smolensky", "suits")},
    }
    change = r.tax - b.tax
    w = b.weight
    overall = {"share_pay_less": float(w[change < -NO_CHANGE].sum() / w.sum()),
               "share_pay_more": float(w[change > NO_CHANGE].sum() / w.sum())}
    overall["share_unchanged"] = 1.0 - overall["share_pay_less"] - overall["share_pay_more"]
    d_edges, d_labels = _decile_edges(b)
    band_edges, band_labels = _band_edges(baseline.params, reform)
    ls = levers(baseline.params, reform)
    warnings = list(notes)
    if not ls:
        warnings.append("This scenario is the baseline: nothing has been changed.")
    attribution = None
    if ls:
        phi = shapley(baseline.params, reform, ls, lambda p: _simulate(p, pop, a).revenue() / CRORE)
        total = sum(phi)
        attribution = {
            "exact": len(ls) <= MAX_EXACT_LEVERS, "total_crore": total,
            "matches_total": bool(abs(total - delta["revenue_crore"]) <= 1e-6 * max(1.0, abs(delta["revenue_crore"])) + 1e-3),
            "levers": sorted(({"id": l.id, "label": l.label, "revenue_crore": p} for l, p in zip(ls, phi)),
                             key=lambda x: -abs(x["revenue_crore"])),
        }
    out = {
        "ay": ay, "law_code": baseline.params.law, "assumptions": a.as_dict(), "changes_applied": [l.label for l in ls],
        "population": {"ay": pop.ay, "returns": float(pop.weight.sum()), "points": int(len(pop.gti)),
                       "base_year": BASE_POP_AY},
        "baseline": bs, "scenario": rs, "delta": delta,
        "impact": {"overall": overall, "deciles": _impact(b, r, d_edges, d_labels),
                   "bands": _impact(b, r, band_edges, band_labels)},
        "attribution": attribution,
        "law": {"baseline": law_view(baseline.params), "scenario": law_view(reform)},
        "uncertainty": uncertainty(baseline.params, reform, ay, a, n_uncertainty) if n_uncertainty and ls else None,
        "behaviour": behaviour_response(baseline.params, reform, pop, behaviour) if behaviour is not None and ls else None,
        "warnings": warnings,
        "scope": "Resident individuals, income at normal rates; a static model of one year's tax.",
    }
    return out


# ── validation: how well does this machinery reproduce published numbers? ───

IN_SAMPLE_AYS = ("2019-20", "2020-21", "2022-23", "2023-24")
_validation_cache: dict = {}


def validation() -> dict:
    """The model against published statistics and Budget speeches, computed from the
    code and data in this repository (cached for the life of the process)."""
    if _validation_cache:
        return _validation_cache
    rows = []
    for ay in IN_SAMPLE_AYS:
        try:
            r = in_sample(ay)
        except (KeyError, FileNotFoundError):
            continue
        rows.append({"ay": ay, "simulated_crore": r["simulated_revenue_crore"], "reported_crore": r["reported_tax_payable_crore"],
                     "ratio": r["ratio"], "band_share_l1": r["tax_band_share_l1"],
                     "simulated_taxpayers": r["simulated_taxpayers"], "reported_taxpayers": r["reported_taxpayers"]})
    fc = forecast_protocol()
    tests = [{"base_ay": t["base_ay"], "target_ay": t["target_ay"], "predicted_crore": t["predicted_crore"],
              "observed_crore": t["observed_crore"], "naive_crore": t["naive_crore"], "ape_model": t["ape_model"],
              "ape_naive": t["ape_naive"], "skill": t["skill"]} for t in fc["test"]]
    reforms = []
    for name in ANNOUNCED_COST:
        c = reform_cost(name)
        reforms.append({"reform": name, "simulated_cost_crore": c["simulated_cost_crore"],
                        "announced_cost_crore": c["announced_cost_crore"], "ratio": c["ratio_to_announced"],
                        "source": c["announced_source"], "note": c["note"]})
    _validation_cache.update({
        "in_sample": rows, "forecast": {"method": fc["chosen_method"], "tests": tests},
        "reform_cost": reforms,
        "reading": [
            "In-sample: the expert law of each year applied to that year's published taxpayer population, against the "
            "tax payable reported for individuals. A ratio near 1 means the calculator and population reproduce the total.",
            "Forecast: a population aged by GDP and filer growth, with the next law, against the reported tax payable; "
            "skill compares it with a naive forecast (positive beats it). Held-out pairs only.",
            "Reform cost: the simulated cost of a Finance Act's personal-tax changes against the Budget speech. The "
            "announced figure covers every direct-tax proposal, so the simulated cost is expected to differ; the "
            "ratio is shown, not hidden.",
        ],
        "limits": [
            "Normal-rate income of resident individuals; special-rate capital gains and non-residents are outside the calculator.",
            "The population reproduces published bands exactly but its shape inside a band, and the Chapter VI-A deductions, are modelled.",
            "Static: no response of labour supply, saving or avoidance (except the optional compliance model).",
        ],
    })
    return _validation_cache
