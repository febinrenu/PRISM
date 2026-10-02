"""
Phase 2 Module C — Mesa simulation endpoints.

POST /api/simulate/{doc_id}          → validate config, return simulation_id
GET  /api/simulate/{doc_id}/stream   → SSE: one event per simulation step
GET  /api/simulate/{doc_id}/results  → persisted SimulationResult
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.schemas import SimulationConfig
from simulation.model import PRISMSimulationModel
from simulation.params import param_table
from simulation.rules import build_simulation_rules
from simulation.runner import finalize, iter_simulation, new_simulation_id
from storage import store

router = APIRouter()

# simulation_id → pending run definition (config + rules). Insertion-ordered;
# capped so abandoned runs (client never opens the stream) can't grow forever.
_pending: dict[str, dict] = {}

_MAX_AGENTS = 5000
_MAX_STEPS = 200
_MAX_PENDING = 64


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _rule_dict(r) -> dict:
    return {
        "clause_id": r.clause_id,
        "description": r.description,
        "threshold_value": r.threshold_value,
        "threshold_kind": r.threshold_kind,
        "rate_percent": r.rate_percent,
        "marginal": getattr(r, "marginal", False),
        "full_base": getattr(r, "full_base", False),
        "penalty_probability": round(r.penalty_probability, 3),
        "affected_agent_types": r.affected_agent_types,
        "source": r.source,
        "matched_template": getattr(r, "matched_template", None),
        "match_score": getattr(r, "match_score", None),
    }


@router.get("/simulate/params")
async def simulation_params():
    """The full table of model assumptions/parameters (value + rationale +
    sourced/illustrative tag) powering the UI transparency panel — so nothing
    about the economics is hidden."""
    return {"params": param_table()}


@router.get("/simulate/{doc_id}/rules")
async def list_simulation_rules(doc_id: str):
    """List the executable rules for a document WITHOUT allocating a run.
    Returns an empty list (200) — not an error — when a document simply has
    no causal rules, so the UI can show a calm empty state."""
    result = store.get_result(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")
    rules, rules_source = build_simulation_rules(result)
    return {
        "doc_id": doc_id,
        "rules_source": rules_source,
        "count": len(rules),
        "rules": [_rule_dict(r) for r in rules],
    }


@router.post("/simulate/{doc_id}")
async def create_simulation(doc_id: str, config: Optional[SimulationConfig] = None):
    result = store.get_result(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")

    config = config or SimulationConfig()

    n_agents = sum(max(0, int(v)) for v in config.agent_config.values())
    if n_agents == 0:
        raise HTTPException(status_code=422, detail="Agent population is zero.")
    if n_agents > _MAX_AGENTS:
        raise HTTPException(status_code=422, detail=f"Agent population exceeds {_MAX_AGENTS}.")
    if not (1 <= config.n_steps <= _MAX_STEPS):
        raise HTTPException(status_code=422, detail=f"n_steps must be 1–{_MAX_STEPS}.")

    rules, rules_source = build_simulation_rules(result, config.rule_clause_ids)
    if not rules:
        raise HTTPException(
            status_code=422,
            detail="No causal rules available to simulate. Run the analysis "
                   "(and optionally LLM extraction) first.",
        )

    # Surface (don't silently drop) any requested clause ids that produced no
    # executable rule — otherwise the user thinks they simulated something they
    # didn't.
    unmatched_rule_ids: list[str] = []
    if config.rule_clause_ids:
        built = {r.clause_id for r in rules}
        unmatched_rule_ids = [cid for cid in config.rule_clause_ids if cid not in built]

    # Evict the oldest abandoned pending run(s) so the map stays bounded.
    while len(_pending) >= _MAX_PENDING:
        _pending.pop(next(iter(_pending)))

    simulation_id = new_simulation_id()
    _pending[simulation_id] = {
        "doc_id": doc_id,
        "config": config,
        "rules": rules,
        "rules_source": rules_source,
    }

    return {
        "simulation_id": simulation_id,
        "doc_id": doc_id,
        "n_agents": n_agents,
        "n_steps": config.n_steps,
        "active_rules": [r.clause_id for r in rules],
        "rules_source": rules_source,
        "rules": [_rule_dict(r) for r in rules],
        "unmatched_rule_ids": unmatched_rule_ids,
        "status": "ready",
    }


@router.get("/simulate/{doc_id}/stream")
async def stream_simulation(doc_id: str, simulation_id: str):
    pending = _pending.pop(simulation_id, None)
    if pending is None or pending["doc_id"] != doc_id:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found (already run or never created).")

    config: SimulationConfig = pending["config"]
    rules = pending["rules"]
    rules_source = pending["rules_source"]
    n_agents = sum(max(0, int(v)) for v in config.agent_config.values())

    async def event_generator():
        loop = asyncio.get_running_loop()
        # Model construction + stepping is fast (thousands of agents × ≤200
        # steps) but still CPU work — build off-loop to be safe.
        model = await loop.run_in_executor(
            None,
            lambda: PRISMSimulationModel(
                rules, config.agent_config, config.seed,
                calibration_mode=config.calibration_mode, adaptive=config.adaptive
            ),
        )

        steps = []
        iterator = iter_simulation(model, config.n_steps)
        while True:
            step = await loop.run_in_executor(None, lambda: next(iterator, None))
            if step is None:
                break
            steps.append(step)
            yield _sse({"step": step.step, "metrics": step.model_dump()})
            await asyncio.sleep(0.05)  # pacing for frontend chart animation

        eff_low, eff_high = model.effective_rate_gap()
        result = finalize(
            simulation_id, doc_id, rules, rules_source, config, steps, n_agents,
            verdict=model.regressivity_verdict(), eff_low=eff_low, eff_high=eff_high,
        )
        yield _sse({
            "stage": "sim_complete",
            "simulation_id": simulation_id,
            "final_gini": result.final_gini,
            "final_compliance_rate": result.final_compliance_rate,
            "final_revenue": result.final_revenue,
            "effective_rate_low": result.effective_rate_low,
            "effective_rate_high": result.effective_rate_high,
            "policy_verdict": result.policy_verdict,
            "narrative": result.narrative,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/simulate/{doc_id}/results")
async def get_simulation_results(doc_id: str, simulation_id: Optional[str] = None):
    if simulation_id is None:
        sims = store.list_simulations(doc_id)
        if not sims:
            raise HTTPException(status_code=404, detail="No simulations for this document.")
        simulation_id = sims[-1]  # most recent

    result = store.load_simulation(doc_id, simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found.")
    return result


def _lime_summary(doc_id: str, clause_id: str) -> Optional[dict]:
    """Cheapest available cached LIME explanation for a clause: prefer the
    faithful (llm) mode, fall back to the fast proxy. Returns just the top
    tokens + fidelity so the drill-down stays lightweight."""
    for mode in ("llm", "proxy"):
        cached = store.load_lime(doc_id, clause_id, mode)
        if cached is not None:
            return {
                "mode": mode,
                "top_tokens": cached.get("top_tokens", [])[:8],
                "prediction": cached.get("prediction"),
                "fidelity": cached.get("fidelity"),
            }
    return None


@router.get("/simulate/{doc_id}/provenance")
async def simulation_provenance(doc_id: str, simulation_id: Optional[str] = None):
    """The headline provenance chain: for a completed simulation, join each
    active rule back to its causal rule → source clause (text + page + bbox) →
    LLM extraction → cached LIME explanation. Pure read/join over persisted
    data; nothing is recomputed and no model is run."""
    result = store.get_result(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis results for {doc_id}.")

    if simulation_id is None:
        sims = store.list_simulations(doc_id)
        if not sims:
            raise HTTPException(status_code=404, detail="No simulations for this document.")
        simulation_id = sims[-1]

    sim = store.load_simulation(doc_id, simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found.")

    # Re-derive the executable rule detail for exactly the clauses this run used.
    rules, _ = build_simulation_rules(result, sim.active_rules)
    rules_by_clause = {r.clause_id: r for r in rules}
    clauses_by_id = {c.clause_id: c for c in result.clauses}

    chain = []
    for clause_id in sim.active_rules:
        clause = clauses_by_id.get(clause_id)
        rule = rules_by_clause.get(clause_id)
        if clause is None:
            continue
        chain.append({
            "clause_id": clause_id,
            "rule": _rule_dict(rule) if rule is not None else None,
            "matched_template": getattr(rule, "matched_template", None) if rule else None,
            "match_score": getattr(rule, "match_score", None) if rule else None,
            "clause": {
                "page": clause.page,
                "bbox": clause.bbox,
                "text": clause.text,
                "section_hierarchy": clause.section_hierarchy,
                "clause_type": clause.clause_type,
            },
            "llm_extraction": clause.llm_extraction.model_dump() if clause.llm_extraction else None,
            "lime_available": clause.lime_available,
            "lime": _lime_summary(doc_id, clause_id),
        })

    return {
        "doc_id": doc_id,
        "simulation_id": simulation_id,
        "policy_verdict": sim.policy_verdict,
        "final_gini": sim.final_gini,
        "final_compliance_rate": sim.final_compliance_rate,
        "rules_source": sim.rules_source,
        "chain": chain,
    }
