"""
Phase 2/3, Module C — socioeconomic agents (Mesa 3.x API).

Five agent types spanning India's socioeconomic spectrum. Each agent evaluates
every active policy rule per step: if the rule applies to it, it either complies
(paying the compliance cost) or risks the penalty, based on its compliance
tendency, financial buffer, and the relative burden of the rule.

Two capacity-to-pay notions are tracked and kept deliberately separate:
  - ability_to_pay  : what a levy is felt against (disposable income for
                      households, margin for firms) — the AFFORDABILITY lens.
  - income (gross)  : used for the statutory EFFECTIVE-RATE incidence verdict.

All tunable constants live in simulation.params (single audited source).
"""
from mesa import Agent

from simulation.params import (
    AgentType,
    BASE_COMPLIANCE_COST,
    BETA_A,
    BETA_B,
    BETA_MEAN,
    BUFFER_DEPLETION_PER_BURDEN,
    BUFFER_MAX,
    BUFFER_MIN,
    BUFFER_RANGES,
    BUFFER_RECOVERY_PER_STEP,
    COMPLIANCE_TENDENCY_MAX,
    COMPLIANCE_TENDENCY_MEAN,
    COMPLIANCE_TENDENCY_MIN,
    DECISION_NOISE,
    DISPOSABLE_FLOOR_FRACTION,
    PROFIT_MARGIN,
    STRESS_BUFFER_COEFF,
    SUBSISTENCE_FLOOR,
    is_household,
)

# Re-export AgentType so existing `from simulation.agents import AgentType`
# imports keep working with the now-canonical params.AgentType.
__all__ = ["AgentType", "PolicyAgent", "INCOME_RANGES", "SUBSISTENCE_FLOOR"]


# Legacy annual income sampling ranges (₹) per agent type — used only when
# SIM_CALIBRATION="legacy". The calibrated log-normal path lives in
# calibration.py and is the default.
INCOME_RANGES: dict[AgentType, tuple[float, float]] = {
    AgentType.LOW_INCOME_HOUSEHOLD: (1.0e5, 3.0e5),
    AgentType.MIDDLE_INCOME_HOUSEHOLD: (3.0e5, 15.0e5),
    AgentType.HIGH_INCOME_HOUSEHOLD: (15.0e5, 1.0e7),
    AgentType.SMALL_BUSINESS: (5.0e5, 5.0e7),
    AgentType.LARGE_CORPORATE: (1.0e9, 1.0e10),
}


class PolicyAgent(Agent):
    """One household or firm responding to extracted policy rules."""

    def __init__(self, model, agent_type: AgentType):
        super().__init__(model)
        self.agent_type = agent_type
        self.is_household = is_household(agent_type)

        # ── Income ─────────────────────────────────────────────────────────
        if getattr(model, "calibration_mode", "nsso") == "legacy":
            import math
            low, high = INCOME_RANGES[agent_type]
            u = model.random.random()  # log-uniform within the bracket
            self.income = math.exp(math.log(low) + u * (math.log(high) - math.log(low)))
        else:
            from simulation.calibration import sample_income
            self.income = sample_income(agent_type, model.random)

        # ── Ability to pay ───────────────────────────────────────────────────
        # Households: income left after subsistence (floored so it never hits 0).
        # Firms: a share of turnover representing margin — NOT turnover minus a
        # household subsistence figure (which was meaningless for a corporation).
        if self.is_household:
            self.ability_to_pay = max(
                self.income - SUBSISTENCE_FLOOR, self.income * DISPOSABLE_FLOOR_FRACTION
            )
        else:
            self.ability_to_pay = self.income * PROFIT_MARGIN[agent_type]
        # Kept as an alias for backwards-compatible references; semantically it is
        # "ability to pay" for both classes now.
        self.disposable_income = self.ability_to_pay

        # ── Compliance behaviour ─────────────────────────────────────────────
        mean = COMPLIANCE_TENDENCY_MEAN[agent_type]
        raw = model.random.betavariate(BETA_A, BETA_B)  # skewed draw
        self.compliance_tendency = max(
            COMPLIANCE_TENDENCY_MIN, min(COMPLIANCE_TENDENCY_MAX, raw * mean / BETA_MEAN)
        )

        b_low, b_high = BUFFER_RANGES[agent_type]
        self.financial_buffer = model.random.uniform(b_low, b_high)
        self.baseline_buffer = self.financial_buffer  # buffer recovers toward this

        # ── Accounting ───────────────────────────────────────────────────────
        self.is_compliant = True
        self.paid_compliance = 0.0  # ₹ paid complying (→ government revenue)
        self.paid_penalty = 0.0     # ₹ paid in penalties (→ government revenue)
        self.compliance_history: list[bool] = []
        self.compliance_ratio = 1.0

        # ── Q-learning state (used only when model.adaptive) ─────────────────
        self.q_table: dict[tuple, list[float]] = {}
        self.epsilon = getattr(model, "Q_EPSILON_START", 0.30)

    # `cumulative_burden` == everything this agent has paid (compliance +
    # penalties). A property so revenue accounting can never drift from burden.
    @property
    def cumulative_burden(self) -> float:
        return self.paid_compliance + self.paid_penalty

    # ── rule evaluation ──────────────────────────────────────────────────────

    def _rule_applies(self, rule) -> bool:
        if self.agent_type.value not in rule.affected_agent_types:
            return False
        if rule.threshold_value is not None and rule.threshold_kind == "amount":
            # Monetary thresholds gate applicability by income/turnover.
            return self.income >= rule.threshold_value
        return True

    def evaluate_policy_rule(self, rule) -> bool:
        """Evaluate one applicable rule for this (monthly) step. Returns True if
        the agent complied. Dispatches to the Q-learning policy when the model
        is adaptive, else the static tendency rule."""
        if getattr(self.model, "adaptive", False):
            return self._evaluate_adaptive(rule)
        return self._evaluate_static(rule)

    def _burden_score(self, annual_cost: float) -> float:
        """The bill measured against monthly ability-to-pay. Against gross income
        a flat rule is a constant for everyone; against ability-to-pay it bites
        those with less slack harder — the affordability signal the agent feels."""
        return annual_cost / max(self.ability_to_pay / 12.0, 1.0)

    def _evaluate_static(self, rule) -> bool:
        annual_cost = rule.compliance_cost_for(self.income)
        monthly_cost = annual_cost / 12.0
        burden_score = self._burden_score(annual_cost)

        stress = 1.0 / (1.0 + STRESS_BUFFER_COEFF * self.financial_buffer)
        noise = self.model.random.uniform(-DECISION_NOISE, DECISION_NOISE)

        if self.compliance_tendency + noise > burden_score * stress:
            self.paid_compliance += monthly_cost
            return True

        # Non-compliance: risk of being caught and penalized this step.
        if self.model.random.random() < rule.penalty_probability:
            self.paid_penalty += rule.penalty_amount_for(self.income) / 12.0
        return False

    # ── Q-learning policy ─────────────────────────────────────────────────────

    def _q_state(self, rule, burden_score: float) -> tuple:
        """Discretize (burden, buffer, enforcement) into a small state space."""
        if burden_score < 0.05:
            b = 0
        elif burden_score < 0.15:
            b = 1
        elif burden_score < 0.40:
            b = 2
        else:
            b = 3
        fb = 0 if self.financial_buffer < 1.0 else (1 if self.financial_buffer < 6.0 else 2)
        pp = rule.penalty_probability
        e = 0 if pp < 0.3 else (1 if pp < 0.6 else 2)
        return (b, fb, e)

    def _q_values(self, state: tuple) -> list[float]:
        """Q-values [comply, defect] for a state, lazily initialized from the
        static compliance tendency so the untrained policy ≈ the static model."""
        if state not in self.q_table:
            self.q_table[state] = [self.compliance_tendency, 1.0 - self.compliance_tendency]
        return self.q_table[state]

    def _evaluate_adaptive(self, rule) -> bool:
        annual_cost = rule.compliance_cost_for(self.income)
        monthly_cost = annual_cost / 12.0
        burden_score = self._burden_score(annual_cost)

        state = self._q_state(rule, burden_score)
        q = self._q_values(state)

        # ε-greedy action selection (comply=0, defect=1)
        if self.model.random.random() < self.epsilon:
            action = self.model.random.randint(0, 1)
        else:
            action = 0 if q[0] >= q[1] else 1

        if action == 0:  # comply — pay the cost
            self.paid_compliance += monthly_cost
            reward = -burden_score
            complied = True
        else:  # defect — free unless caught, then a heavier penalty
            if self.model.random.random() < rule.penalty_probability:
                self.paid_penalty += rule.penalty_amount_for(self.income) / 12.0
                reward = -2.0 * burden_score
            else:
                reward = 0.0
            complied = False

        # Q-learning update. Buffer dynamics (see step()) couple steps into a
        # genuine MDP, so the discounted bootstrap on the next state's best value
        # is meaningful rather than a degenerate bandit.
        best_next = max(q)
        q[action] += self.model.q_alpha * (reward + self.model.q_gamma * best_next - q[action])
        return complied

    # ── buffer dynamics ────────────────────────────────────────────────────
    def _update_buffer(self, burden_paid_this_step: float) -> None:
        """Paying burden depletes the savings buffer; it recovers slowly toward
        the agent's baseline each month. This inter-step coupling is what makes
        the adaptive model a real MDP (state at t+1 depends on the action at t)."""
        monthly_capacity = max(self.ability_to_pay / 12.0, 1.0)
        depletion = BUFFER_DEPLETION_PER_BURDEN * (burden_paid_this_step / monthly_capacity)
        recovered = BUFFER_RECOVERY_PER_STEP * (self.baseline_buffer - self.financial_buffer)
        self.financial_buffer = max(
            BUFFER_MIN, min(BUFFER_MAX, self.financial_buffer - depletion + recovered)
        )

    def step(self) -> None:
        applicable = [r for r in self.model.active_rules if self._rule_applies(r)]
        before = self.cumulative_burden
        if not applicable:
            self.compliance_ratio = 1.0
            self.is_compliant = True
        else:
            complied = sum(1 for rule in applicable if self.evaluate_policy_rule(rule))
            self.compliance_ratio = complied / len(applicable)
            self.is_compliant = self.compliance_ratio >= 0.8
        self.compliance_history.append(self.is_compliant)

        self._update_buffer(self.cumulative_burden - before)

        # Decay exploration over the run so behavior settles as agents learn.
        if getattr(self.model, "adaptive", False):
            self.epsilon = max(
                getattr(self.model, "q_epsilon_min", 0.02),
                self.epsilon * getattr(self.model, "q_epsilon_decay", 0.93),
            )
