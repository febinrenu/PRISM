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
}


def units_for(path: str, units: list) -> list:
    """Units at `path` or below it."""
    return [u for u in units if u.path == path or u.path.startswith(path + "/")]
