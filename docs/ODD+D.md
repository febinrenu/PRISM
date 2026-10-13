# Compliance model: ODD+D description

The behavioural appendix of the paper uses an agent-based model of
income-tax compliance (`backend/simulation/behaviour/`). It is described
here following the ODD+D protocol (Müller et al. 2013).

Run it with `python -m cli behaviour`. Results are written to
`data/experiments/behaviour.json`, and each model run is stored in
`behaviour_runs.jsonl`, so an interrupted experiment resumes.

## 1. Overview

### 1.1 Purpose

The paper asks whether rules extracted from statutes by language models
support the same policy conclusions as an expert's coding. The appendix
asks the same question of a behavioural prediction: the share of income tax
evaded (the tax gap) when taxpayers can conceal income. It treats two
parameters as legal inputs:
- the tax schedule;
- the penalty for concealed income, from the Income-tax Act 2025, s.439:
  - 50% of the tax on under-reported income (s.439(9));
  - 200% where the under-reporting results from misreporting (s.439(10)).

Deliberate concealment is misreporting, so the expert value is 200%.

The behavioural parameters are not identified by any published Indian data.
The model is therefore used comparatively: does reading the penalty
provision wrongly move the prediction by more or less than the uncertainty
in those parameters? Its levels are not forecasts.

### 1.2 Entities, state variables and scales

- **Taxpayer agents** (default N = 3,000; 10,000 in the convergence check).
  Agents are sampled with probability proportional to weight from the
  calibrated population of AY 2026-27, which reproduces the Income Tax
  Return Statistics. Each agent has:
  - gross total income;
  - whether it is salaried (Bernoulli with its income range's salaried
    share, from statistics table 2.2);
  - Chapter VI-A deductions;
  - tax morale χᵢ;
  - a subjective audit probability p̂ᵢ;
  - its current concealed share hᵢ.
- **Network:** a Watts–Strogatz small world (6 neighbours, rewiring 0.1)
  over agents ordered by income, so most neighbours have similar incomes.
- **Time:** discrete periods (tax years). There are 60 periods, and
  outcomes are averaged over the last 30.
- **Law:** expert parameters of AY 2026-27 (both regimes, statutory
  calculator), and the penalty rate θ.

### 1.3 Process overview and scheduling

Every period, in this order:
1. **Decide:** each agent chooses hᵢ (§2.2).
2. **Audit:** each agent is audited with probability p.
3. **Learn:** each agent updates p̂ᵢ from the audits it observes.
4. **Record** the period's outputs.

All agents act simultaneously, with decisions computed in one vectorised
step.

## 2. Design concepts

### 2.1 Theoretical and empirical background

- **Choice under risk:** the Allingham–Sandmo model, extended with tax
  morale as a social custom (Myles and Naylor 1996).
- **Third-party reporting:** salaried income is reported by the employer, so
  little of it can be concealed (Kleven et al. 2011).
- **Social share of morale:** behavioural tax-compliance models make part of
  the morale cost depend on others' compliance (Hashimzade et al. 2013).

### 2.2 Individual decision-making

An agent with income Y conceals a share h ∈ {0, 0.1, …, 1} of its evadable
income. The evadable income is the whole income if the agent is not
salaried, and `salaried_evadable` × Y if it is. With declared income D, the
evaded tax is G = T(Y) − T(D), where T is the statutory tax under the
cheaper regime. The agent chooses h to maximise

(1 − p̂)·u(Y − T(D) − M) + p̂·u(Y − T(Y) − θ·G − M),

where:
- M = χᵢ·((1 − w) + w·n)·G is the morale cost;
- n is the neighbours' average honesty (1 − their mean concealed share);
- w is the social share of morale;
- u is CRRA with relative risk aversion ρ.

### 2.3 Learning, sensing and prediction

Each period an agent observes the audits of itself and its neighbours, and
moves its belief p̂ towards the observed audit rate with weight λ. The
initial belief is above the true audit rate, because taxpayers overestimate
audit risk. There is no other learning: the tabular Q-learning of the
original proposal was dropped in favour of this transparent rule.

### 2.4 Interaction

Interaction is indirect, through the network. Neighbours' honesty scales the
social part of morale, and neighbours' audits inform beliefs.

### 2.5 Heterogeneity

Agents differ in:
- income (from the population);
- salaried status;
- deductions;
- tax morale, χᵢ ~ Beta(m·k, (1 − m)·k), with mean m and concentration
  k = 4. With one common χ, compliance would be all or nothing.

### 2.6 Stochasticity

The following are drawn from one seeded generator:
- the agent sample;
- salaried status;
- morale;
- the network;
- audits.

Experiments use common random numbers, so a comparison between two penalty
rates differs only in the rate.

### 2.7 Observation

The model records:
- the tax gap (weighted evaded tax ÷ tax owed, before penalties);
- the share of liable agents concealing any income;
- separate gaps for salaried and other taxpayers;
- the gap by income decile;
- revenue including penalties collected.

## 3. Details

### 3.1 Implementation

The model is written in Python with Mesa 3.5 (agents and scheduling), numpy
and scipy (vectorised decisions, with the network as a sparse adjacency
matrix), and networkx. A run of 3,000 agents over 60 periods takes about
0.1 s.

### 3.2 Initialisation and input data

The inputs are:
- the population of the static microsimulation, aged to AY 2026-27;
- the expert tax parameters;
- the behavioural parameters (defaults and ranges below).

| Parameter | Default | Range in the experiments |
|---|---|---|
| audit rate p | 0.01 | 0.002–0.03 |
| initial belief p̂₀ | 0.03 | 0.005–0.10 |
| belief weight λ | 0.2 | 0.05–0.5 |
| risk aversion ρ | 2 | 1–4 |
| mean tax morale m | 0.3 | 0–0.95 |
| social share of morale w | 0.5 | 0–1 |
| evadable share of salaries | 0.05 | 0–0.15 |
| penalty rate θ | 2.0 (s.439(10)) | 0.5–2.0 |

### 3.3 Experiments

- **Convergence:** the default parameters with 1,000, 3,000 and 10,000
  agents, 10 seeds each.
- **Paired:** 64 Latin-hypercube draws of the seven behavioural parameters.
  Each draw is run with θ = 2.0 (expert) and θ = 0.5 (the under-reporting
  rate applied to deliberate concealment).
- **Sobol:** total-order indices of the tax gap over all eight inputs
  (Saltelli sampling, 64 base samples).
- **Systems:** the penalty rate each extraction system reads from s.439(10).
  A system that reads none leaves the model without a penalty, so there is
  no conclusion for it.

### 3.4 Known limitations

- With realistic audit rates, Allingham–Sandmo agents without strong morale
  evade most non-salaried income. This is the well-known gap between that
  theory and observed compliance, and it is why the levels are not
  predictions.
- The model has no:
  - interest on evaded tax;
  - detection probability below one for audited agents;
  - distinction between under-reporting and misreporting by the agent.
