"""
Assemble income-tax parameters from extracted rules.

One assembler serves every system (expert, rules, each language model), so
any difference in simulated outcomes is caused by the rules, not by the
translation. The experimental design names which provision supplies which
parameter (a *target*); the assembler reads that provision's effects of the
matching kind and nothing else:

    new.slabs | old.slabs.<age_band>   ← slab_row effects (a complete schedule)
    new.rebate | old.rebate            ← rebate effect
    new.standard_deduction | old.…     ← standard_deduction effect
    new.surcharge | old.surcharge      ← surcharge_band effects (+ surcharge_cap)
    cess                               ← cess effect

Delta mode starts from the expert parameters of the previous year and
replaces only the targeted parameters (how a Finance Act reads: it amends).
A target that cannot be filled — no effect of the right kind, or a slab
schedule with gaps, overlaps or no open top band — becomes a ReviewItem and
the result is marked incomplete. Nothing is filled in with a default.
"""
from dataclasses import dataclass, field
from typing import Optional

from models.rules import Cess, LegalRule, Rebate as RebateEffect, SlabRow, StandardDeduction, SurchargeBand as SBEffect, SurchargeCap
from simulation.rac.types import PITParams, Rebate, RegimeSchedule, Slab, SurchargeBand

TOLERANCE = 1.0   # rupees: "From Rs. 3,00,001" continues a band ending at 3,00,000


@dataclass
class ReviewItem:
    target: str
    provision: str
    reason: str


@dataclass
class AssemblyResult:
    params: PITParams
    complete: bool
    review: list[ReviewItem] = field(default_factory=list)
    filled: dict[str, str] = field(default_factory=dict)   # target → provision it came from


def _same_ay(value: Optional[str], ay: str) -> bool:
    """'2025-26', '2025-2026', 'AY 2025-26' all name assessment year 2025-26."""
    if not value:
        return False
    import re
    m = re.search(r"(20\d\d)\s*[-–/]\s*(?:20)?(\d\d)", str(value))
    return bool(m) and f"{m.group(1)}-{m.group(2)}" == ay


def _effects(rules: list[LegalRule], kind, regime: Optional[str] = None) -> list:
    """Effects of one kind; for a regime-specific target, only those stated
    for that regime or for both (s.156 of the 2025 Act grants one rebate under
    each regime in the same section)."""
    return [e for r in rules for e in r.effects
            if isinstance(e, kind) and (regime is None or getattr(e, "regime", "both") in (regime, "both"))]


def build_schedule(rows: list[SlabRow]) -> tuple[Optional[list[Slab]], Optional[str]]:
    """Contiguous schedule from slab rows, or (None, reason)."""
    if not rows:
        return None, "no slab rows"
    rows = sorted(rows, key=lambda r: (r.lower, r.upper if r.upper is not None else float("inf")))
    # Drop exact duplicates (a model may repeat a row).
    uniq = []
    for r in rows:
        if not uniq or (r.lower, r.upper, r.rate) != (uniq[-1].lower, uniq[-1].upper, uniq[-1].rate):
            uniq.append(r)
    rows = uniq
    if abs(rows[0].lower) > TOLERANCE:
        return None, f"schedule does not start at zero (first band starts at {rows[0].lower:,.0f})"
    slabs = []
    for i, r in enumerate(rows):
        lower = 0.0 if i == 0 else slabs[-1].upper
        if i > 0 and (slabs[-1].upper is None or abs(r.lower - slabs[-1].upper) > TOLERANCE):
            return None, f"gap or overlap between bands at {r.lower:,.0f}"
        if r.upper is not None and r.upper <= lower:
            return None, f"band ending at {r.upper:,.0f} is empty"
        if not 0.0 <= r.rate <= 1.0:
            return None, f"rate {r.rate} outside 0-1"
        slabs.append(Slab(lower=lower, upper=r.upper, rate=r.rate))
    if slabs[-1].upper is not None:
        return None, "no open top band"
    if any(b.rate < a.rate for a, b in zip(slabs, slabs[1:])):
        return None, "rates decrease with income"
    return slabs, None


def assemble(rules_by_provision: dict[str, list[LegalRule]], targets: dict[str, str],
             base: PITParams, ay: str) -> AssemblyResult:
    """targets: {target: provision node_id}. Starts from `base` (delta mode)."""
    params = base.model_copy(deep=True)
    params.ay = ay
    params.citations = {}
    review: list[ReviewItem] = []
    filled: dict[str, str] = {}

    for target, provision in targets.items():
        rules = rules_by_provision.get(provision, [])
        parts = target.split(".")
        regime = parts[0] if parts[0] in ("new", "old") else None
        if regime is not None and regime not in params.regimes:
            review.append(ReviewItem(target, provision, f"{regime} regime does not exist in {ay}"))
            continue
        sched: Optional[RegimeSchedule] = params.regimes.get(regime) if regime else None

        if len(parts) >= 2 and parts[1] == "slabs":
            rows = _effects(rules, SlabRow, regime)
            # A provision can carry tables for several years (FA 2024 (No. 2)
            # s.37 substitutes one table for AY 2024-25 and another for
            # 2025-26). Rows scoped to this year win; unscoped rows are used
            # only when no row names the year.
            scoped = [r for r in rows if _same_ay(r.applies_to_ay, ay)]
            if scoped:
                rows = scoped
            elif any(r.applies_to_ay for r in rows):
                rows = [r for r in rows if not r.applies_to_ay]
            slabs, why = build_schedule(rows)
            if slabs is None:
                review.append(ReviewItem(target, provision, why or "no schedule"))
                continue
            if regime == "new" or (len(parts) == 2):
                sched.slabs = {"below_60": slabs}
                sched.same_for_all_ages = True
            else:
                age = parts[2]
                if sched.same_for_all_ages:
                    base_slabs = sched.slabs["below_60"]
                    sched.slabs = {a: list(base_slabs) for a in ("below_60", "60_to_80", "80_plus")}
                    sched.same_for_all_ages = False
                sched.slabs[age] = slabs  # type: ignore[index]
        elif len(parts) >= 2 and parts[1] == "rebate":
            rebs = _effects(rules, RebateEffect, regime)
            if not rebs:
                review.append(ReviewItem(target, provision, "no rebate effect"))
                continue
            r = rebs[0]
            sched.rebate = Rebate(max_income=r.max_income, max_rebate=r.max_rebate, marginal_relief=r.marginal_relief)
        elif len(parts) >= 2 and parts[1] == "standard_deduction":
            sds = _effects(rules, StandardDeduction, regime)
            if not sds:
                review.append(ReviewItem(target, provision, "no standard deduction effect"))
                continue
            sched.standard_deduction = sds[0].amount
        elif len(parts) >= 2 and parts[1] == "surcharge":
            bands = sorted(_effects(rules, SBEffect, regime), key=lambda b: b.threshold)
            if not bands:
                review.append(ReviewItem(target, provision, "no surcharge bands"))
                continue
            caps = _effects(rules, SurchargeCap, regime)
            cap = min((c.max_rate for c in caps), default=None)
            sched.surcharge = [SurchargeBand(threshold=b.threshold, rate=min(b.rate, cap) if cap is not None else b.rate)
                               for b in bands]
        elif target == "cess":
            cs = _effects(rules, Cess)
            if not cs:
                review.append(ReviewItem(target, provision, "no cess effect"))
                continue
            params.cess_rate = cs[0].rate
        else:
            review.append(ReviewItem(target, provision, f"unknown target {target}"))
            continue
        filled[target] = provision

    return AssemblyResult(params=params, complete=not review, review=review, filled=filled)
