"""
Provision sets: the experimental design of the headline study.

Each set is one assessment year's change in the personal income-tax law.
It names the statute provisions that carry the change and the parameter each
one determines. Every system extracts rules from exactly these provisions;
all other parameters come from the expert coding of the same year, so a
difference in outcomes is attributable to the extracted provisions alone.

Targets are statute AST paths; a path also covers the units below it (a
long schedule paragraph is split into one unit per rate row).
"""
PROVISION_SETS: dict[str, dict] = {
    "FA2020_new_regime": {
        "ay": "2021-22", "statute": ("FA2020", "enacted"),
        "description": "Finance Act 2020 introduces the optional concessional regime (s.115BAC).",
        "targets": {"new.slabs": "FA2020/s53/q1/s115BAC/(1)"},
    },
    "FA2020_old_schedule": {
        "ay": "2020-21", "statute": ("FA2020", "enacted"),
        "description": "First Schedule Part I Paragraph A: old-regime rates by age band.",
        "targets": {"old.slabs.below_60": "FA2020/schFIRST/ptI/paraA/(I)",
                    "old.slabs.60_to_80": "FA2020/schFIRST/ptI/paraA/(II)",
                    "old.slabs.80_plus": "FA2020/schFIRST/ptI/paraA/(III)"},
    },
    "FA2023_new_default": {
        "ay": "2024-25", "statute": ("FA2023", "enacted"),
        "description": "Finance Act 2023: new default regime table (s.115BAC(1A)) and the Rs. 7 lakh rebate (s.87A proviso).",
        "targets": {"new.slabs": "FA2023/s52/(A)", "new.rebate": "FA2023/s44"},
    },
    "FA2024N2_budget": {
        "ay": "2025-26", "statute": ("FA2024N2", "enacted"),
        "description": "Finance (No. 2) Act 2024: substituted (1A) with separate tables for AY 2024-25 and 2025-26; "
                       "Rs. 75,000 standard deduction.",
        "targets": {"new.slabs": "FA2024N2/s37", "new.standard_deduction": "FA2024N2/s10"},
    },
    "FA2025_rebate_12L": {
        "ay": "2026-27", "statute": ("FA2025", "enacted"),
        "description": "Finance Act 2025: new slab table and the Rs. 12 lakh / Rs. 60,000 rebate.",
        "targets": {"new.slabs": "FA2025/s25", "new.rebate": "FA2025/s20"},
    },
    # Old-regime rate tables restated by each year's Finance Act (First
    # Schedule, Part I, Paragraph A: one item per age band). The rates are
    # unchanged since AY 2020-21, so these test whether a system reads the
    # restatement exactly — a change it invents flips the year's conclusions.
    "FA2023_old_schedule": {
        "ay": "2023-24", "statute": ("FA2023", "enacted"),
        "description": "Finance Act 2023, First Schedule Part I Para A: old-regime rates by age band.",
        "targets": {"old.slabs.below_60": "FA2023/schFIRST/ptI/paraA/(I)",
                    "old.slabs.60_to_80": "FA2023/schFIRST/ptI/paraA/(II)",
                    "old.slabs.80_plus": "FA2023/schFIRST/ptI/paraA/(III)"},
    },
    "FA2024N2_old_schedule": {
        "ay": "2024-25", "statute": ("FA2024N2", "enacted"),
        "description": "Finance (No. 2) Act 2024, First Schedule Part I Para A: old-regime rates by age band.",
        "targets": {"old.slabs.below_60": "FA2024N2/schFIRST/ptI/paraA/(I)",
                    "old.slabs.60_to_80": "FA2024N2/schFIRST/ptI/paraA/(II)",
                    "old.slabs.80_plus": "FA2024N2/schFIRST/ptI/paraA/(III)"},
    },
    "FA2025_old_schedule": {
        "ay": "2025-26", "statute": ("FA2025", "enacted"),
        "description": "Finance Act 2025, First Schedule Part I Para A: old-regime rates by age band.",
        "targets": {"old.slabs.below_60": "FA2025/schFIRST/ptI/paraA/(I)",
                    "old.slabs.60_to_80": "FA2025/schFIRST/ptI/paraA/(II)",
                    "old.slabs.80_plus": "FA2025/schFIRST/ptI/paraA/(III)"},
    },
    "FA2026_old_schedule_ITA2025": {
        "ay": "2027-28", "statute": ("FA2026", "enacted"),
        "description": "Finance Act 2026, First Schedule Part I-B (income-tax under the 2025 Act) Para A: "
                       "old-regime rates by age band for tax year 2026-27.",
        "targets": {"old.slabs.below_60": "FA2026/schFIRST/ptI/subB/paraA/(I)",
                    "old.slabs.60_to_80": "FA2026/schFIRST/ptI/subB/paraA/(II)",
                    "old.slabs.80_plus": "FA2026/schFIRST/ptI/subB/paraA/(III)"},
    },
    "ITA2025_new_act": {
        "ay": "2027-28", "statute": ("ITA2025", "amended_fa2026"),
        "description": "Income-tax Act 2025 (in force from tax year 2026-27): the s.202(1) default-regime table "
                       "and the s.156 rebates, re-enacted in new drafting with no change in rates. A system that "
                       "reads a change into the re-enactment flips the 'no revenue change' conclusion.",
        "targets": {"new.slabs": "ITA2025/s202/(1)", "new.rebate": "ITA2025/s156"},
    },
}


def units_for(path: str, units: list) -> list:
    """Units at `path` or below it."""
    return [u for u in units if u.path == path or u.path.startswith(path + "/")]


# ── held-out sets (pre-registered) ──────────────────────────────────────────
# Provisions that were not opened while the structured condition (rebuilt
# tables, schema decoding, repair) and the number checks were built on the
# reforms above. They are fixed here, and committed, before any system is
# run on them; no rule, prompt or check may be changed after their results
# are seen.
#
# Each Finance Act's Part III restates the old-regime rate schedules that
# apply to the following year's tax deducted at source and advance tax, so
# its expert value is the next assessment year's old-regime schedule. FA 2026
# Part I-A states the 1961 Act schedules for AY 2026-27 (Part I-B was used
# above). Left out, for reasons fixed before any run:
#   - FA 2025 Part III and FA 2026 Part III: the parser merges item (III)
#     with its neighbour, so no provision path holds one table;
#   - FA 2026 Part I-A item (III): its node also holds the next paragraph's table;
#   - surcharge provisions: they set separate rates for dividend and capital
#     gains income, which the expert coding (normal rates only) leaves out,
#     so a faithful reading would be scored as wrong.
#
# Hypothesis: with rebuilt tables, schema decoding and one repair, each
# system keeps every conclusion on at least as many held-out reforms as with
# the canonical text alone (the headline condition, greedy), and its numbers
# are found in their own quotes at least as often.
HELD_OUT_SETS: dict[str, dict] = {
    "HO_FA2019N2_partIII": {
        "ay": "2020-21", "statute": ("FA2019N2", "enacted"),
        "description": "Finance (No. 2) Act 2019, First Schedule Part III Para A: old-regime rates for FY 2019-20.",
        "targets": {"old.slabs.below_60": "FA2019N2/schFIRST/ptIII/paraA/(I)",
                    "old.slabs.60_to_80": "FA2019N2/schFIRST/ptIII/paraA/(II)",
                    "old.slabs.80_plus": "FA2019N2/schFIRST/ptIII/paraA/(III)"},
    },
    "HO_FA2020_partIII": {
        "ay": "2021-22", "statute": ("FA2020", "enacted"),
        "description": "Finance Act 2020, First Schedule Part III Para A: old-regime rates for FY 2020-21.",
        "targets": {"old.slabs.below_60": "FA2020/schFIRST/ptIII/paraA/(I)",
                    "old.slabs.60_to_80": "FA2020/schFIRST/ptIII/paraA/(II)",
                    "old.slabs.80_plus": "FA2020/schFIRST/ptIII/paraA/(III)"},
    },
    "HO_FA2023_partIII": {
        "ay": "2024-25", "statute": ("FA2023", "enacted"),
        "description": "Finance Act 2023, First Schedule Part III Para A: old-regime rates for FY 2023-24.",
        "targets": {"old.slabs.below_60": "FA2023/schFIRST/ptIII/paraA/(I)",
                    "old.slabs.60_to_80": "FA2023/schFIRST/ptIII/paraA/(II)",
                    "old.slabs.80_plus": "FA2023/schFIRST/ptIII/paraA/(III)"},
    },
    "HO_FA2024N2_partIII": {
        "ay": "2025-26", "statute": ("FA2024N2", "enacted"),
        "description": "Finance (No. 2) Act 2024, First Schedule Part III Para A: old-regime rates for FY 2024-25.",
        "targets": {"old.slabs.below_60": "FA2024N2/schFIRST/ptIII/paraA/(I)",
                    "old.slabs.60_to_80": "FA2024N2/schFIRST/ptIII/paraA/(II)",
                    "old.slabs.80_plus": "FA2024N2/schFIRST/ptIII/paraA/(III)"},
    },
    "HO_FA2026_partIA": {
        "ay": "2026-27", "statute": ("FA2026", "enacted"),
        "description": "Finance Act 2026, First Schedule Part I-A Para A (the 1961 Act): old-regime rates for "
                       "AY 2026-27, items (I) and (II).",
        "targets": {"old.slabs.below_60": "FA2026/schFIRST/ptI/subA/paraA/(I)",
                    "old.slabs.60_to_80": "FA2026/schFIRST/ptI/subA/paraA/(II)"},
    },
}


def spec(set_name: str) -> dict:
    """A provision set's design, headline or held-out."""
    return PROVISION_SETS.get(set_name) or HELD_OUT_SETS[set_name]
