"""
Phase 2/3, Module C — PRISM socioeconomic simulation model (Mesa 3.x).

Mesa 3 removed mesa.time schedulers: agents are activated via
`model.agents.shuffle_do("step")`, and DataCollector is unchanged.

Two distributional lenses are reported and kept deliberately distinct:
  - Effective tax rate (burden / GROSS income) per household band — the
    textbook statutory-incidence measure. The regressivity verdict is derived
    from THIS (a falling effective rate as income rises = regressive), so the
    verdict is an empirical finding, not an artefact of the denominator.
  - Relative burden (burden / ability-to-pay) — an affordability lens, and the
    basis of the household Gini. Useful, but secondary to the verdict.
"""
from mesa import Model
from mesa.datacollection import DataCollector

from simulation.agents import AgentType, PolicyAgent
from simulation.params import (
    EFFECTIVE_RATE_PROGRESSIVE_RATIO,
    EFFECTIVE_RATE_REGRESSIVE_RATIO,
    HOUSEHOLD_TYPES,
    Q_ALPHA,
    Q_EPSILON_DECAY,
    Q_EPSILON_MIN,
    Q_EPSILON_START,
    Q_GAMMA,
)
from simulation.rules import SimulationRule


def _gini(values: list[float]) -> float:
    """Gini coefficient of a distribution (0 = equal). Clamped to [0, 1] — the
    ordered-rank formula can return a tiny negative for near-uniform inputs."""
    n = len(values)
    if n == 0:
        return 0.0
    total = sum(values)
    if total <= 0:
        return 0.0
    ordered = sorted(values)
    weighted = sum(i * b for i, b in enumerate(ordered, 1))
    g = (2.0 * weighted) / (n * total) - (n + 1.0) / n
    return max(0.0, min(1.0, g))


class PRISMSimulationModel(Model):
    # Q-learning hyper-parameters (tabular; buffer dynamics make it a real MDP)
    Q_ALPHA = Q_ALPHA
    Q_GAMMA = Q_GAMMA
    Q_EPSILON_START = Q_EPSILON_START
    Q_EPSILON_DECAY = Q_EPSILON_DECAY
    Q_EPSILON_MIN = Q_EPSILON_MIN

    def __init__(
        self,
        policy_rules: list[SimulationRule],
        agent_config: dict[str, int],
        seed: int = 42,
        calibration_mode: str | None = None,
        adaptive: bool = True,
    ):
        super().__init__(seed=seed)
        self.active_rules = policy_rules
        self.adaptive = adaptive
        self.q_alpha = self.Q_ALPHA
        self.q_gamma = self.Q_GAMMA
        self.q_epsilon_decay = self.Q_EPSILON_DECAY
        self.q_epsilon_min = self.Q_EPSILON_MIN

        # "nsso" (calibrated log-normal) vs "legacy" (log-uniform ranges).
        if calibration_mode is None:
            try:
                from config import SIM_CALIBRATION
                calibration_mode = SIM_CALIBRATION
            except Exception:
                calibration_mode = "nsso"
        self.calibration_mode = calibration_mode

        for type_key, count in agent_config.items():
            agent_type = AgentType(type_key)
            for _ in range(max(0, int(count))):
                PolicyAgent(self, agent_type)

        self.datacollector = DataCollector(
            model_reporters={
                "compliance_rate": self._compliance_rate,
                "gini_coefficient": self._gini_coefficient,
                "avg_burden_low": lambda m: m._avg_burden(AgentType.LOW_INCOME_HOUSEHOLD),
                "avg_burden_middle": lambda m: m._avg_burden(AgentType.MIDDLE_INCOME_HOUSEHOLD),
                "avg_burden_high": lambda m: m._avg_burden(AgentType.HIGH_INCOME_HOUSEHOLD),
                "avg_burden_sme": lambda m: m._avg_burden(AgentType.SMALL_BUSINESS),
                "avg_burden_corp": lambda m: m._avg_burden(AgentType.LARGE_CORPORATE),
                "policy_burden_index": self._policy_burden_index,
                "compliance_by_type": self._compliance_by_type,
                "effective_rate_by_type": self._effective_rate_by_type,
                "revenue_total": self._revenue_total,
                "revenue_compliance": self._revenue_compliance,
                "revenue_penalty": self._revenue_penalty,
                "revenue_by_type": self._revenue_by_type,
                "mean_q_gap": self._mean_q_gap,
            }
        )

    # ── metrics ──────────────────────────────────────────────────────────────

    @staticmethod
    def _compliance_rate(model: "PRISMSimulationModel") -> float:
        """Mean share of applicable rules complied with across agents."""
        agents = list(model.agents)
        if not agents:
            return 1.0
        return sum(a.compliance_ratio for a in agents) / len(agents)

    def _households(self) -> list:
        hh = {t.value for t in HOUSEHOLD_TYPES}
        return [a for a in self.agents if a.agent_type.value in hh]

    @staticmethod
    def _gini_coefficient(model: "PRISMSimulationModel") -> float:
        """Gini of relative burden (burden / ability-to-pay) across HOUSEHOLDS
        only. Households and firms are not commensurable on one inequality
        scale, so firms are excluded; this is an affordability-dispersion
        measure among households, distinct from the incidence verdict."""
        households = model._households()
        if not households:
            return 0.0
        return _gini([
            a.cumulative_burden / max(a.ability_to_pay, 1.0) for a in households
        ])

    def _avg_burden(self, agent_type: AgentType) -> float:
        members = [a for a in self.agents if a.agent_type == agent_type]
        if not members:
            return 0.0
        return sum(a.cumulative_burden for a in members) / len(members)

    @staticmethod
    def _policy_burden_index(model: "PRISMSimulationModel") -> float:
        """Mean burden-to-ability-to-pay ratio across households (affordability)."""
        households = model._households()
        if not households:
            return 0.0
        return sum(
            a.cumulative_burden / max(a.ability_to_pay, 1.0) for a in households
        ) / len(households)

    @staticmethod
    def _compliance_by_type(model: "PRISMSimulationModel") -> dict[str, float]:
        out: dict[str, float] = {}
        for agent_type in AgentType:
            members = [a for a in model.agents if a.agent_type == agent_type]
            out[agent_type.value] = (
                sum(a.compliance_ratio for a in members) / len(members) if members else 1.0
            )
        return out

    @staticmethod
    def _effective_rate_by_type(model: "PRISMSimulationModel") -> dict[str, float]:
        """Effective rate = cumulative burden / GROSS income, per type. This is
        the statutory-incidence measure the verdict is derived from."""
        out: dict[str, float] = {}
        for agent_type in AgentType:
            members = [a for a in model.agents if a.agent_type == agent_type]
            out[agent_type.value] = (
                sum(a.cumulative_burden / max(a.income, 1.0) for a in members) / len(members)
                if members else 0.0
            )
        return out

    @staticmethod
    def _revenue_compliance(model: "PRISMSimulationModel") -> float:
        return sum(a.paid_compliance for a in model.agents)

    @staticmethod
    def _revenue_penalty(model: "PRISMSimulationModel") -> float:
        return sum(a.paid_penalty for a in model.agents)

    @staticmethod
    def _revenue_total(model: "PRISMSimulationModel") -> float:
        """Government revenue = sum of agent payments. Equals aggregate burden
        by construction (cumulative_burden = paid_compliance + paid_penalty)."""
        return sum(a.cumulative_burden for a in model.agents)

    @staticmethod
    def _revenue_by_type(model: "PRISMSimulationModel") -> dict[str, float]:
        out: dict[str, float] = {t.value: 0.0 for t in AgentType}
        for a in model.agents:
            out[a.agent_type.value] += a.cumulative_burden
        return out

    @staticmethod
    def _mean_q_gap(model: "PRISMSimulationModel") -> float:
        """Mean |Q(comply) − Q(defect)| across agents' learned states — a proxy
        for how decisively the adaptive population has converged on a policy.
        0.0 for static (non-adaptive) runs (no Q-tables)."""
        gaps = []
        for a in model.agents:
            q = getattr(a, "q_table", None)
            if q:
                gaps.extend(abs(v[0] - v[1]) for v in q.values())
        return round(sum(gaps) / len(gaps), 4) if gaps else 0.0

    def effective_rate_gap(self) -> tuple[float, float]:
        """(low_income effective rate, high_income effective rate) — the two
        numbers the verdict compares. Exposed so the narrative/UI can cite
        exactly what drove the finding."""
        rates = self._effective_rate_by_type(self)
        return rates[AgentType.LOW_INCOME_HOUSEHOLD.value], rates[AgentType.HIGH_INCOME_HOUSEHOLD.value]

    def regressivity_verdict(self) -> str:
        """Incidence test on the EFFECTIVE TAX RATE (burden / gross income) of
        low- vs high-income households. A regressive tax takes a larger share of
        a poor household's income than a rich one's — the standard definition,
        and independent of the ability-to-pay denominator, so the verdict is a
        finding rather than a foregone conclusion."""
        low, high = self.effective_rate_gap()
        if low <= 0.0 and high <= 0.0:
            return "neutral"
        if high <= 0.0:
            return "regressive"  # only the poor pay anything
        ratio = low / high
        if ratio > EFFECTIVE_RATE_REGRESSIVE_RATIO:
            return "regressive"
        if ratio < EFFECTIVE_RATE_PROGRESSIVE_RATIO:
            return "progressive"
        return "neutral"

    # ── stepping ─────────────────────────────────────────────────────────────

    def step(self) -> None:
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)
