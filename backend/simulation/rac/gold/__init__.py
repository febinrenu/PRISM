"""
Expert-coded personal income-tax parameters, AY 2020-21 to tax year 2026-27.

Coded by the authors from the Finance Acts and the Income-tax Act 2025, with
the statute and provision behind every parameter. These are the reference
("gold") parameters against which extracted rules are compared; a second
coder codes the same years independently (see docs/expert_coding_form.md)
and agreement is reported.

The slab tables and rebate limits were cross-checked against the parsed
corpus text (tests/test_pit_gold.py verifies each new-regime table row by
row against the Finance Act table it cites).
"""
import json
from pathlib import Path

from simulation.rac.types import Citation, PITParams, Rebate, RegimeSchedule, Slab, SurchargeBand

L = 100_000      # one lakh
CR = 10_000_000  # one crore

GOLD_DIR = Path(__file__).parent

# ── shared schedules ────────────────────────────────────────────────────────

_OLD_SLABS = {
    "below_60": [Slab(lower=0, upper=2.5 * L, rate=0.0), Slab(lower=2.5 * L, upper=5 * L, rate=0.05),
                 Slab(lower=5 * L, upper=10 * L, rate=0.20), Slab(lower=10 * L, rate=0.30)],
    "60_to_80": [Slab(lower=0, upper=3 * L, rate=0.0), Slab(lower=3 * L, upper=5 * L, rate=0.05),
                 Slab(lower=5 * L, upper=10 * L, rate=0.20), Slab(lower=10 * L, rate=0.30)],
    "80_plus": [Slab(lower=0, upper=5 * L, rate=0.0), Slab(lower=5 * L, upper=10 * L, rate=0.20),
                Slab(lower=10 * L, rate=0.30)],
}

_SURCHARGE_FULL = [SurchargeBand(threshold=50 * L, rate=0.10), SurchargeBand(threshold=1 * CR, rate=0.15),
                   SurchargeBand(threshold=2 * CR, rate=0.25), SurchargeBand(threshold=5 * CR, rate=0.37)]
# From AY 2024-25 the new regime's surcharge may not exceed 25%.
_SURCHARGE_CAPPED = [SurchargeBand(threshold=50 * L, rate=0.10), SurchargeBand(threshold=1 * CR, rate=0.15),
                     SurchargeBand(threshold=2 * CR, rate=0.25)]


def _table(*rows):
    """(upper_limit_or_None, rate) pairs → contiguous slabs from zero."""
    slabs, lower = [], 0.0
    for upper, rate in rows:
        slabs.append(Slab(lower=lower, upper=upper, rate=rate))
        lower = upper if upper is not None else lower
    return slabs


_NEW_FA2020 = _table((2.5 * L, 0.0), (5 * L, 0.05), (7.5 * L, 0.10), (10 * L, 0.15),
                     (12.5 * L, 0.20), (15 * L, 0.25), (None, 0.30))
_NEW_FA2023 = _table((3 * L, 0.0), (6 * L, 0.05), (9 * L, 0.10), (12 * L, 0.15), (15 * L, 0.20), (None, 0.30))
_NEW_FA2024 = _table((3 * L, 0.0), (7 * L, 0.05), (10 * L, 0.10), (12 * L, 0.15), (15 * L, 0.20), (None, 0.30))
_NEW_FA2025 = _table((4 * L, 0.0), (8 * L, 0.05), (12 * L, 0.10), (16 * L, 0.15), (20 * L, 0.20),
                     (24 * L, 0.25), (None, 0.30))


def _old(rebate=Rebate(max_income=5 * L, max_rebate=12_500), sd=50_000.0) -> RegimeSchedule:
    return RegimeSchedule(slabs=_OLD_SLABS, standard_deduction=sd, rebate=rebate,
                          surcharge=_SURCHARGE_FULL, allows_chapter_via_deductions=True)


def _new(slabs, sd, rebate, surcharge) -> RegimeSchedule:
    return RegimeSchedule(slabs={"below_60": slabs}, same_for_all_ages=True, standard_deduction=sd,
                          rebate=rebate, surcharge=surcharge, allows_chapter_via_deductions=False)


def _c(statute, provision, note=""):
    return Citation(statute=statute, provision=provision, note=note)


_OLD_CITES = {
    "regimes.old.slabs": _c("FA{fa}/enacted", "First Schedule, Part {part}, Paragraph A",
                            "Rates for individuals: below 60, 60-80 and 80+ age bands."),
    "regimes.old.rebate": _c("FA2019 (No. 7 of 2019)", "s.8 amending s.87A",
                             "Rebate up to Rs. 12,500 where total income does not exceed Rs. 5 lakh, from AY 2020-21."),
    "regimes.old.standard_deduction": _c("FA2019 (No. 7 of 2019)", "amending s.16(ia)",
                                         "Rs. 50,000 standard deduction on salary from AY 2020-21."),
    "regimes.old.surcharge": _c("FA2019N2/enacted", "s.2 and First Schedule Part I Para A",
                                "10% / 15% / 25% / 37% above Rs. 50 lakh / 1 / 2 / 5 crore."),
    "cess_rate": _c("FA2018 (No. 13 of 2018)", "s.2(11)-(12)", "Health and Education Cess at 4% of tax plus surcharge."),
}


def _with_old_cites(cites: dict, fa: str, part: str) -> dict:
    out = {}
    for k, v in _OLD_CITES.items():
        out[k] = Citation(statute=v.statute.format(fa=fa), provision=v.provision.format(part=part), note=v.note)
    out.update(cites)
    return out


def build_gold() -> dict[str, PITParams]:
    g: dict[str, PITParams] = {}

    g["2020-21"] = PITParams(
        ay="2020-21", regimes={"old": _old()}, default_regime="old",
        citations=_with_old_cites({}, "2020", "I"),
    )
    # Part I of a year's Finance Act gives that year's assessment rates and
    # Part III the next year's; the old-regime schedule did not change over
    # this period. FA 2021, FA 2022 and the interim FA 2024 are not in the
    # corpus, so those years cite the corpus Act that carries the same rates.
    for ay, fa, part in (("2021-22", "2020", "III"), ("2022-23", "2023", "I"), ("2023-24", "2023", "I")):
        g[ay] = PITParams(
            ay=ay, default_regime="old",
            regimes={"old": _old(),
                     "new": _new(_NEW_FA2020, 0.0, Rebate(max_income=5 * L, max_rebate=12_500), _SURCHARGE_FULL)},
            citations=_with_old_cites({
                "regimes.new.slabs": _c("FA2020/enacted", "s.53 inserting s.115BAC(1)", "Optional concessional regime from AY 2021-22."),
                "regimes.new.rebate": _c("ITA1961", "s.87A", "The s.87A rebate applied to income under s.115BAC as well."),
                "regimes.new.standard_deduction": _c("FA2020/enacted", "s.53 inserting s.115BAC(2)(i)",
                                                     "No standard deduction under the concessional regime before AY 2024-25."),
            }, fa, part),
        )
    g["2022-23"].citations["regimes.old.slabs"] = _c(
        "FA2022 (No. 6 of 2022)", "First Schedule, Part I, Paragraph A",
        "Not in the corpus; identical rates are printed in FA2023 Part I for AY 2023-24.")
    g["2024-25"] = PITParams(
        ay="2024-25", default_regime="new",
        regimes={"old": _old(),
                 "new": _new(_NEW_FA2023, 50_000.0, Rebate(max_income=7 * L, max_rebate=25_000, marginal_relief=True),
                             _SURCHARGE_CAPPED)},
        citations=_with_old_cites({
            "regimes.new.slabs": _c("FA2023/enacted", "s.52 inserting s.115BAC(1A)", "New default regime table."),
            "regimes.new.rebate": _c("FA2023/enacted", "s.44 inserting proviso to s.87A",
                                     "Up to Rs. 25,000 where total income does not exceed Rs. 7 lakh, with marginal relief."),
            "regimes.new.standard_deduction": _c("FA2023/enacted", "amendment to s.16(ia)",
                                                 "Rs. 50,000 standard deduction allowed under s.115BAC(1A)."),
            "regimes.new.surcharge": _c("FA2023/enacted", "s.2, provisos capping surcharge at 25% under s.115BAC(1A)"),
            "default_regime": _c("FA2023/enacted", "s.52 inserting s.115BAC(1A) and (6)", "New regime applies unless the person opts out."),
        }, "2023", "III"),
    )
    g["2025-26"] = PITParams(
        ay="2025-26", default_regime="new",
        regimes={"old": _old(),
                 "new": _new(_NEW_FA2024, 75_000.0, Rebate(max_income=7 * L, max_rebate=25_000, marginal_relief=True),
                             _SURCHARGE_CAPPED)},
        citations=_with_old_cites({
            "regimes.new.slabs": _c("FA2024N2/enacted", "s.37 substituting s.115BAC(1A)(ii)"),
            "regimes.new.rebate": _c("FA2023/enacted", "s.44 proviso to s.87A (unchanged)"),
            "regimes.new.standard_deduction": _c("FA2024N2/enacted", "s.10 inserting proviso to s.16(ia)",
                                                 "Rs. 75,000 under s.115BAC(1A)(ii)."),
            "regimes.new.surcharge": _c("FA2024N2/enacted", "s.2 and First Schedule Part I"),
            "default_regime": _c("FA2023/enacted", "s.115BAC(1A) as inserted"),
        }, "2025", "I"),
    )
    g["2026-27"] = PITParams(
        ay="2026-27", default_regime="new",
        regimes={"old": _old(),
                 "new": _new(_NEW_FA2025, 75_000.0, Rebate(max_income=12 * L, max_rebate=60_000, marginal_relief=True),
                             _SURCHARGE_CAPPED)},
        citations=_with_old_cites({
            "regimes.new.slabs": _c("FA2025/enacted", "s.25 inserting s.115BAC(1A)(iii)"),
            "regimes.new.rebate": _c("FA2025/enacted", "s.20 amending s.87A",
                                     "Up to Rs. 60,000 where total income does not exceed Rs. 12 lakh, with marginal relief; "
                                     "not available against special-rate income (second proviso)."),
            "regimes.new.standard_deduction": _c("FA2024N2/enacted", "s.10 proviso to s.16(ia)"),
            "regimes.new.surcharge": _c("FA2025/enacted", "s.2 and First Schedule Part I"),
            "default_regime": _c("FA2023/enacted", "s.115BAC(1A) as inserted"),
        }, "2026", "I"),
    )
    # Tax year 2026-27 is the first under the Income-tax Act 2025; keyed by the
    # assessment year that follows it for continuity with the series.
    g["2027-28"] = PITParams(
        ay="2027-28", law="ITA2025", default_regime="new",
        regimes={"old": _old(rebate=Rebate(max_income=5 * L, max_rebate=12_500)),
                 "new": _new(_NEW_FA2025, 75_000.0, Rebate(max_income=12 * L, max_rebate=60_000, marginal_relief=True),
                             _SURCHARGE_CAPPED)},
        citations={
            "regimes.new.slabs": _c("ITA2025/amended_fa2026", "s.202(1) Table"),
            "regimes.new.rebate": _c("ITA2025/amended_fa2026", "s.156(2)-(3)"),
            "regimes.old.rebate": _c("ITA2025/amended_fa2026", "s.156(1)"),
            "regimes.new.standard_deduction": _c("ITA2025/amended_fa2026", "Schedule on salary deductions, Sl. No. 2(a)"),
            "regimes.old.standard_deduction": _c("ITA2025/amended_fa2026", "Schedule on salary deductions, Sl. No. 2(b)"),
            "regimes.old.slabs": _c("FA2026/enacted", "First Schedule, Part I, Paragraph A"),
            "regimes.old.surcharge": _c("FA2026/enacted", "First Schedule, Part I"),
            "regimes.new.surcharge": _c("FA2026/enacted", "First Schedule, Part I (25% cap for s.202(1) income)"),
            "default_regime": _c("ITA2025/amended_fa2026", "s.202(1)-(2)"),
            "cess_rate": _c("FA2026/enacted", "s.2, Health and Education Cess"),
        },
    )
    return g


def export_json(directory: Path = GOLD_DIR) -> list[Path]:
    paths = []
    for ay, params in build_gold().items():
        p = directory / f"pit_ay{ay.replace('-', '_')}.json"
        p.write_text(json.dumps(params.model_dump(), indent=2), encoding="utf-8")
        paths.append(p)
    return paths


def load(ay: str) -> PITParams:
    p = GOLD_DIR / f"pit_ay{ay.replace('-', '_')}.json"
    return PITParams.model_validate_json(p.read_text(encoding="utf-8"))
