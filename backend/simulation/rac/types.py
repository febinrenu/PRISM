"""
Parameters of the personal income-tax schedule for one assessment year.

The same structure is filled by the expert gold files (rac/gold/) and by the
assembler from extracted rules, so the calculator never knows where its
numbers came from. Every parameter can carry a citation; `canonical_hash()`
identifies a parameter set independent of citations and key order.
"""
import hashlib
import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

AgeBand = Literal["below_60", "60_to_80", "80_plus"]
AGE_BANDS: tuple[AgeBand, ...] = ("below_60", "60_to_80", "80_plus")


class Citation(BaseModel):
    statute: str                       # "FA2025/enacted", "ITA2025/amended_fa2026", "FA2019"
    provision: str                     # "s.25 inserting s.115BAC(1A)(iii)", "First Schedule Part I Para A"
    node_id: Optional[str] = None      # statute AST node, when the statute is in the corpus
    note: str = ""


class Slab(BaseModel):
    lower: float                       # tax applies to income above `lower` …
    upper: Optional[float] = None      # … up to `upper` (None = no ceiling)
    rate: float                        # fraction


class Rebate(BaseModel):
    max_income: float
    max_rebate: float
    marginal_relief: bool = False      # tax payable capped at (total income − max_income)


class SurchargeBand(BaseModel):
    threshold: float                   # applies when total income exceeds this
    rate: float                        # fraction of income-tax


class RegimeSchedule(BaseModel):
    # Slabs per age band. A regime with the same slabs for every age lists
    # them under "below_60" only and sets `same_for_all_ages`.
    slabs: dict[AgeBand, list[Slab]]
    same_for_all_ages: bool = False
    standard_deduction: float = 0.0    # on salary income
    rebate: Optional[Rebate] = None
    surcharge: list[SurchargeBand] = Field(default_factory=list)
    allows_chapter_via_deductions: bool = True

    def slabs_for(self, age: AgeBand) -> list[Slab]:
        if self.same_for_all_ages:
            return self.slabs["below_60"]
        return self.slabs[age]


class PITParams(BaseModel):
    """Personal income-tax parameters for one assessment year (or, under the
    Income-tax Act 2025, the assessment year following the tax year)."""
    ay: str                            # "2026-27"
    law: str = "ITA1961"               # which Act the year falls under
    regimes: dict[Literal["old", "new"], RegimeSchedule]
    default_regime: Literal["old", "new"] = "old"
    cess_rate: float = 0.04
    scope: str = "resident individual; income at normal rates"
    citations: dict[str, Citation] = Field(default_factory=dict)   # param path → source

    def canonical_hash(self) -> str:
        """Hash of the economically meaningful parameters only (citations and
        scope notes excluded), so two coders' parameter sets compare equal
        exactly when they would compute the same tax."""
        payload = self.model_dump(exclude={"citations", "scope"})
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def diff(self, other: "PITParams") -> list[str]:
        """Parameter paths whose values differ (used for coder agreement and
        for attributing simulated divergence to individual parameters)."""
        a = _flatten(self.model_dump(exclude={"citations", "scope"}))
        b = _flatten(other.model_dump(exclude={"citations", "scope"}))
        return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _flatten(obj, prefix: str = "") -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out
