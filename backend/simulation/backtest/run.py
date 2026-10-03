"""
Validation of the income-tax microsimulation against published outcomes.

1. In-sample reproduction: the expert law of year t applied to the taxpayer
   population of year t, compared with the tax payable reported by
   individuals in year t (Income Tax Return Statistics, table 2.11):
   total, and the distribution of returns over tax-payable bands.

2. Out-of-sample forecast: the AY 2020-21 population, aged to AY 2023-24 by
   nominal GDP growth (incomes) and growth in individual return filers
   (weights) — both external to the tax outcome — with AY 2023-24 law,
   against the tax payable reported for AY 2023-24. Skill is measured
   against a naive forecast: AY 2020-21 tax × nominal GDP growth.

3. Reform costing: the revenue cost of the Finance Act 2023 and Finance Act
   2025 changes (new law vs previous law on the same aged population), next
   to the cost the Finance Minister announced in the Budget speech.

Every input and target names its published source.
"""
import csv
from dataclasses import dataclass

import numpy as np

from config import BASE_DIR
from simulation.engine.outcomes import band_counts, summarise
from simulation.engine.static import simulate
from simulation.population.cbdt import load_targets
from simulation.population.taxpayers import Population, build
from simulation.rac import gold

MACRO = BASE_DIR / "simulation" / "population" / "targets" / "macro.csv"

# Budget speeches (indiabudget.gov.in), direct-tax revenue forgone as announced.
ANNOUNCED_COST = {
    "FA2023": {"crore": 37_000, "source": "Budget Speech 2023-24: 'revenue of about ₹38,000 crore – ₹37,000 crore "
                                           "in direct taxes and ₹1,000 crore in indirect taxes – will be forgone'"},
    "FA2025": {"crore": 100_000, "source": "Budget Speech 2025-26: 'revenue of about ₹1 lakh crore in direct taxes "
                                            "and ₹2600 crore in indirect taxes will be forgone'"},
}


def macro() -> dict[str, dict]:
    with open(MACRO, encoding="utf-8") as fh:
        return {r["financial_year"]: {"gdp": float(r["gdp_current_crore"]), "filers": float(r["individual_return_filers"])}
                for r in csv.DictReader(fh)}


def income_year(ay: str) -> str:
    """AY 2023-24 taxes income of financial year 2022-23."""
    y = int(ay[:4])
    return f"{y - 1}-{str(y)[2:]}"


def filing_year(ay: str) -> str:
    """Returns for AY 2023-24 are filed in financial year 2023-24."""
    return ay


def age(pop: Population, income_factor: float, weight_factor: float, ay: str) -> Population:
    return Population(ay=ay, gti=pop.gti * income_factor, weight=pop.weight * weight_factor,
                      via_share=pop.via_share, band=pop.band, bands=pop.bands,
                      salaried_share=pop.salaried_share,
                      embedded_standard_deduction=pop.embedded_standard_deduction)


@dataclass
class Settings:
    optimal_share: float = 1.0      # taxpayers choosing the cheaper regime
    via_scale: float = 1.0          # Chapter VI-A deductions × this
    nominal_growth_after_2023_24: float = 0.096   # GDP growth of FY 2023-24 (table 1.4), carried forward


def in_sample(ay: str, s: Settings = Settings()) -> dict:
    G = gold.build_gold()
    pop = build(ay, via_scale=s.via_scale)
    res = simulate(G[ay], pop, s.optimal_share)
    obs = load_targets(ay, "tax")
    obs_total = sum(r.total_inr for r in obs)
    pos = [r for r in obs if r.lower >= 0 and not (r.upper == 0.0)]
    bands = [(r.lower, r.upper) for r in pos]
    sim_counts = band_counts(res, bands)
    obs_counts = [r.returns for r in pos]
    sim_share = np.array(sim_counts) / max(sum(sim_counts), 1)
    obs_share = np.array(obs_counts) / max(sum(obs_counts), 1)
    return {
        "ay": ay, "simulated_revenue_crore": res.revenue() / 1e7, "reported_tax_payable_crore": obs_total / 1e7,
        "ratio": res.revenue() / obs_total,
        "simulated_taxpayers": res.taxpayers_with_tax(), "reported_taxpayers": sum(obs_counts),
        "tax_band_share_l1": float(np.abs(sim_share - obs_share).sum()),
        "summary": summarise(res),
    }


def forecast(base_ay: str = "2020-21", target_ay: str = "2023-24", s: Settings = Settings()) -> dict:
    M = macro()
    G = gold.build_gold()
    gdp_f = M[income_year(target_ay)]["gdp"] / M[income_year(base_ay)]["gdp"]
    filer_f = M[filing_year(target_ay)]["filers"] / M[filing_year(base_ay)]["filers"]
    pop = age(build(base_ay, via_scale=s.via_scale), gdp_f, filer_f, target_ay)
    pred = simulate(G[target_ay], pop, s.optimal_share).revenue()
    observed = sum(r.total_inr for r in load_targets(target_ay, "tax"))
    base_obs = sum(r.total_inr for r in load_targets(base_ay, "tax"))
    naive = base_obs * gdp_f
    err_model = abs(pred - observed) / observed
    err_naive = abs(naive - observed) / observed
    return {
        "base_ay": base_ay, "target_ay": target_ay, "income_factor": gdp_f, "weight_factor": filer_f,
        "predicted_crore": pred / 1e7, "observed_crore": observed / 1e7, "naive_crore": naive / 1e7,
        "ape_model": err_model, "ape_naive": err_naive,
        "skill": 1 - err_model / err_naive if err_naive > 0 else None,
    }


AGEING_METHODS = {
    # name: (income factor, weight factor) from GDP growth g and filer growth f
    "income_gdp": lambda g, f: (g, 1.0),
    "income_gdp_weights_filers": lambda g, f: (g, f),
    "income_gdp_per_filer_weights_filers": lambda g, f: (g / f, f),
}
SELECTION_PAIRS = [("2019-20", "2020-21"), ("2020-21", "2022-23")]
TEST_PAIRS = [("2022-23", "2023-24"), ("2020-21", "2023-24")]


def _forecast_with(method: str, base_ay: str, target_ay: str, s: Settings) -> dict:
    M = macro()
    G = gold.build_gold()
    g = M[income_year(target_ay)]["gdp"] / M[income_year(base_ay)]["gdp"]
    f = M[filing_year(target_ay)]["filers"] / M[filing_year(base_ay)]["filers"]
    inc_f, w_f = AGEING_METHODS[method](g, f)
    pop = age(build(base_ay, via_scale=s.via_scale), inc_f, w_f, target_ay)
    pred = simulate(G[target_ay], pop, s.optimal_share).revenue()
    observed = sum(r.total_inr for r in load_targets(target_ay, "tax"))
    naive = sum(r.total_inr for r in load_targets(base_ay, "tax")) * g
    return {"base_ay": base_ay, "target_ay": target_ay, "method": method,
            "predicted_crore": pred / 1e7, "observed_crore": observed / 1e7, "naive_crore": naive / 1e7,
            "ape_model": abs(pred - observed) / observed, "ape_naive": abs(naive - observed) / observed}


def forecast_protocol(s: Settings = Settings()) -> dict:
    """Choose the ageing method on the selection pairs only, then report the
    held-out test pairs with that method fixed (no test-year information is
    used for the choice)."""
    selection = {m: [_forecast_with(m, b, t, s) for b, t in SELECTION_PAIRS] for m in AGEING_METHODS}
    mean_ape = {m: float(np.mean([r["ape_model"] for r in rs])) for m, rs in selection.items()}
    chosen = min(mean_ape, key=mean_ape.get)
    tests = [_forecast_with(chosen, b, t, s) for b, t in TEST_PAIRS]
    for r in tests:
        r["skill"] = 1 - r["ape_model"] / r["ape_naive"] if r["ape_naive"] > 0 else None
    return {"selection_mean_ape": mean_ape, "chosen_method": chosen, "selection": selection, "test": tests}


def population_for(ay: str, s: Settings = Settings(), base_ay: str = "2023-24") -> Population:
    """The latest observed taxpayer population aged to `ay`'s income year by
    nominal GDP (extrapolated at the last observed growth rate beyond the
    published series)."""
    M = macro()
    base_fy, target_fy = income_year(base_ay), income_year(ay)
    if target_fy in M:
        f = M[target_fy]["gdp"] / M[base_fy]["gdp"]
    else:
        last = max(M)
        f = M[last]["gdp"] / M[base_fy]["gdp"] * (1 + s.nominal_growth_after_2023_24) ** (int(target_fy[:4]) - int(last[:4]))
    return age(build(base_ay, via_scale=s.via_scale), f, 1.0, ay)


def reform_cost(reform: str, s: Settings = Settings()) -> dict:
    """Revenue cost of a Finance Act's personal income-tax changes, both laws
    applied to the same population aged to the reform year."""
    M = macro()
    G = gold.build_gold()
    base_ay, (before, after) = {
        "FA2023": ("2023-24", ("2023-24", "2024-25")),
        "FA2025": ("2023-24", ("2025-26", "2026-27")),
    }[reform]
    pop = build(base_ay, via_scale=s.via_scale)
    base_fy = income_year(base_ay)
    target_fy = income_year(after)
    if target_fy in M:
        gdp_f = M[target_fy]["gdp"] / M[base_fy]["gdp"]
    else:
        last = max(M)
        years = int(target_fy[:4]) - int(last[:4])
        gdp_f = M[last]["gdp"] / M[base_fy]["gdp"] * (1 + s.nominal_growth_after_2023_24) ** years
    pop = age(pop, gdp_f, 1.0, after)
    rev_before = simulate(G[before], pop, s.optimal_share).revenue()
    rev_after = simulate(G[after], pop, s.optimal_share).revenue()
    announced = ANNOUNCED_COST[reform]
    cost = (rev_before - rev_after) / 1e7
    return {
        "reform": reform, "law_before": before, "law_after": after, "income_factor": gdp_f,
        "simulated_cost_crore": cost, "announced_cost_crore": announced["crore"],
        "ratio_to_announced": cost / announced["crore"], "announced_source": announced["source"],
        "note": "Simulated cost covers personal income-tax slab, rebate and standard-deduction changes only; "
                "the announced figure covers all direct-tax proposals of the Budget.",
    }
