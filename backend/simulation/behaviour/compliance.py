"""
Behavioural appendix: income-tax compliance as an agent-based model.

Taxpayers drawn from the calibrated population decide each period how much
of their income to conceal. The law enters twice: the tax schedule (the same
statutory calculator as the static microsimulation) and the penalty for
concealed income (Income-tax Act 2025, s.439: 50% of the tax on
under-reported income, 200% where it results from misreporting; deliberate
concealment is misreporting). Both can come from the expert coding or from
a system's extraction, so the appendix asks the paper's question of a
behavioural prediction. The model is documented in docs/ODD+D.md.

Decision (Allingham–Sandmo with tax morale). Agent i with income Y conceals
a share h of its evadable income E (salaried income is reported by the
employer, so only a small share of it is evadable). With declared income D,
evaded tax G = T(Y) − T(D), penalty rate θ, subjective audit probability p̂
and morale cost χᵢ·((1 − w) + w·n)·G: χᵢ is the agent's tax morale, drawn
from a Beta distribution with mean `morale` (with one common χ compliance
would be all or nothing); a share w of it is social, scaled by the
neighbours' average honesty n, and the rest intrinsic (Myles and Naylor's
social-custom model) (n = average honesty of the neighbours, 1 − their mean
concealed share):

    not audited  c = Y − T(D) − χ·n·G
    audited      c = Y − T(Y) − θ·G − χ·n·G
    choose h ∈ {0, 0.1, …, 1} maximising (1 − p̂)·u(c_n) + p̂·u(c_a),  u CRRA(ρ)

Each period every agent is audited with probability p; an agent's subjective
probability moves towards the audit rate it observes among itself and its
network neighbours (small world, neighbours close in income).
"""
from dataclasses import dataclass, field, replace
from typing import Optional

import mesa
import networkx as nx
import numpy as np

from simulation.rac.pit import liability
from simulation.rac.types import PITParams

H_GRID = np.round(np.linspace(0.0, 1.0, 11), 2)


@dataclass(frozen=True)
class BehaviourParams:
    penalty_rate: float = 2.0          # θ: s.439(10), misreporting
    audit_rate: float = 0.01           # p: share of returns examined per period
    initial_belief: float = 0.03       # p̂ at the start (taxpayers overestimate audit risk)
    belief_weight: float = 0.2         # λ: weight of this period's observation in p̂
    risk_aversion: float = 2.0         # ρ (CRRA)
    morale: float = 0.3                # mean of χᵢ: psychic cost per rupee evaded, scaled by the neighbours' honesty
    morale_concentration: float = 4.0  # Beta(m·k, (1−m)·k): spread of tax morale across agents
    norm_weight: float = 0.5           # w: share of morale that depends on the neighbours' honesty
    salaried_evadable: float = 0.05    # share of salaried income that is not third-party reported
    neighbours: int = 6
    rewiring: float = 0.1
    steps: int = 60
    burn_in: int = 30


class Taxpayer(mesa.Agent):
    """One taxpayer; its numeric state lives in the model's arrays (index i)
    so that decisions are computed for all agents at once."""

    def __init__(self, model: "ComplianceModel", i: int):
        super().__init__(model)
        self.i = i

    @property
    def concealed_share(self) -> float:
        return float(self.model.h[self.i])


class ComplianceModel(mesa.Model):
    def __init__(self, law: PITParams, pop, params: BehaviourParams = BehaviourParams(), n_agents: int = 10_000,
                 seed: int = 0):
        super().__init__(rng=seed)
        self.law, self.p = law, params
        rng = np.random.default_rng(seed)
        self.np_rng = rng
        prob = pop.weight / pop.weight.sum()
        idx = rng.choice(len(pop.gti), size=n_agents, p=prob)
        order = np.argsort(pop.gti[idx], kind="stable")          # agents ordered by income
        idx = idx[order]
        self.weight = np.full(n_agents, pop.weight.sum() / n_agents)
        self.gti = pop.gti[idx]
        share = pop.salaried_share[idx] if pop.salaried_share is not None else np.zeros(n_agents)
        self.salaried = rng.random(n_agents) < share
        self.deductions = pop.gti[idx] * pop.via_share[idx]
        self.embedded_sd = pop.embedded_standard_deduction
        for i in range(n_agents):
            Taxpayer(self, i)
        # Small-world network over the income-ordered agents: neighbours are
        # close in income, with some long-range ties.
        g = nx.watts_strogatz_graph(n_agents, params.neighbours, params.rewiring, seed=seed)
        self.adj = nx.to_scipy_sparse_array(g, nodelist=range(n_agents), format="csr", dtype=float)
        self.degree = np.asarray(self.adj.sum(axis=1)).ravel()
        self.belief = np.full(n_agents, params.initial_belief)
        m = min(max(params.morale, 1e-3), 1 - 1e-3)
        k = params.morale_concentration
        self.morale = rng.beta(m * k, (1 - m) * k, size=n_agents)
        self.h = np.zeros(n_agents)
        self.true_tax = self._tax(np.zeros(n_agents))
        self._tax_grid = np.stack([self._tax(np.full(n_agents, h)) for h in H_GRID], axis=1)
        self.history: list[dict] = []

    # tax owed on the income declared when a share h of evadable income is concealed
    def _tax(self, h: np.ndarray) -> np.ndarray:
        evadable = np.where(self.salaried, self.p.salaried_evadable, 1.0)
        kept = 1.0 - h * evadable
        salary = np.where(self.salaried, (self.gti + self.embedded_sd) * kept, 0.0)
        other = np.where(self.salaried, 0.0, self.gti * kept)
        taxes = [liability(self.law, r, salary, other, self.deductions * kept).total_tax for r in self.law.regimes]
        return np.minimum.reduce(taxes) if len(taxes) > 1 else taxes[0]

    def _utility(self, c: np.ndarray) -> np.ndarray:
        rho = self.p.risk_aversion
        c = np.maximum(c, 1.0)
        return np.log(c) if abs(rho - 1.0) < 1e-9 else c ** (1 - rho) / (1 - rho)

    def _neighbour_honesty(self) -> np.ndarray:
        honest_sum = self.adj @ (1.0 - self.h)
        return np.where(self.degree > 0, honest_sum / np.maximum(self.degree, 1), 1.0)

    def step(self) -> None:
        p = self.p
        income = self.gti + np.where(self.salaried, self.embedded_sd, 0.0)
        n = self._neighbour_honesty()[:, None]
        evaded = self.true_tax[:, None] - self._tax_grid                     # G for every h
        morale = self.morale[:, None] * ((1 - p.norm_weight) + p.norm_weight * n) * evaded
        c_clean = income[:, None] - self._tax_grid - morale
        c_audit = income[:, None] - self.true_tax[:, None] - p.penalty_rate * evaded - morale
        b = self.belief[:, None]
        eu = (1 - b) * self._utility(c_clean) + b * self._utility(c_audit)
        self.h = H_GRID[np.argmax(eu, axis=1)]                              # ties: least concealment
        audited = self.np_rng.random(len(self.h)) < p.audit_rate
        seen = (audited + self.adj @ audited.astype(float)) / (1.0 + self.degree)
        self.belief = (1 - p.belief_weight) * self.belief + p.belief_weight * seen
        declared_tax = self._tax_grid[np.arange(len(self.h)), np.searchsorted(H_GRID, self.h)]
        gap = self.true_tax - declared_tax
        collected = declared_tax + audited * (gap + p.penalty_rate * gap)
        owed = float((self.true_tax * self.weight).sum())
        liable = self.true_tax > 0
        self.history.append({
            "tax_gap": float((gap * self.weight).sum()) / owed if owed else 0.0,
            "evaders": float((self.h[liable] > 0).mean()) if liable.any() else 0.0,
            "revenue_crore": float((collected * self.weight).sum()) / 1e7,
            "mean_belief": float(self.belief.mean()),
        })

    def run(self) -> dict:
        for _ in range(self.p.steps):
            self.step()
        tail = self.history[self.p.burn_in:]
        deciles = np.array_split(np.arange(len(self.h)), 10)            # agents are ordered by income
        gap_by_decile = []
        for d in deciles:
            owed = (self.true_tax[d] * self.weight[d]).sum()
            declared = self._tax_grid[d, np.searchsorted(H_GRID, self.h[d])]
            gap_by_decile.append(float(((self.true_tax[d] - declared) * self.weight[d]).sum() / owed) if owed else 0.0)
        return {
            "tax_gap": float(np.mean([h["tax_gap"] for h in tail])),
            "evaders": float(np.mean([h["evaders"] for h in tail])),
            "revenue_crore": float(np.mean([h["revenue_crore"] for h in tail])),
            "mean_belief": float(np.mean([h["mean_belief"] for h in tail])),
            "gap_salaried": self._gap(self.salaried), "gap_other": self._gap(~self.salaried),
            "gap_by_decile": gap_by_decile,
            "history": self.history,
        }

    def _gap(self, mask: np.ndarray) -> float:
        owed = (self.true_tax[mask] * self.weight[mask]).sum()
        declared = self._tax_grid[mask, :][np.arange(mask.sum()), np.searchsorted(H_GRID, self.h[mask])]
        return float(((self.true_tax[mask] - declared) * self.weight[mask]).sum() / owed) if owed else 0.0


def run(law: PITParams, pop, params: BehaviourParams = BehaviourParams(), n_agents: int = 10_000,
        seed: int = 0) -> dict:
    return ComplianceModel(law, pop, params, n_agents, seed).run()
