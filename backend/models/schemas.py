from pydantic import BaseModel, Field
from typing import Literal, Optional


class Entity(BaseModel):
    label: Literal["OBLIGATION", "RIGHT", "PENALTY", "THRESHOLD", "ACTOR", "BENEFICIARY"]
    text: str
    start: int
    end: int
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


class CausalPattern(BaseModel):
    pattern_type: Literal["IF_THEN", "CONDITION_ACTION", "PENALTY_TRIGGER"]
    condition_span: str
    action_span: str
    confidence: float
    source_clause_id: str
    risk_tier: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "LOW"
    impact_score: float = 0.5  # 0.0 – 1.0
    # Deterministic human-readable rationale for WHY this was flagged (which
    # structure matched, which risk signals fired). "" for pre-existing results.
    explanation: str = ""


class LLMCausalRule(BaseModel):
    """Structured causal rule extracted by the local LLM (Phase 2, Module B)."""
    is_causal: Optional[bool] = None  # None = extraction failed to parse
    condition: Optional[str] = None
    action: Optional[str] = None
    consequence: Optional[str] = None
    actors: list[str] = []
    thresholds: list[str] = []
    confidence: float = 0.0
    reasoning: str = ""
    extraction_time_ms: int = 0
    model: str = ""
    parse_error: Optional[str] = None


class LIMEToken(BaseModel):
    token: str
    weight: float  # positive = pushes toward causal
    normalized_weight: float  # |weight| / max|weight|, 0.0 – 1.0
    position: int  # char position of this occurrence in the clause text


class Clause(BaseModel):
    clause_id: str
    doc_id: str
    page: int
    section_hierarchy: list[str]
    text: str
    char_start: int
    char_end: int
    bbox: Optional[list[float]] = None  # [x0, y0, x1, y1] normalized 0-1
    entities: list[Entity] = []
    causal_patterns: list[CausalPattern] = []
    embedding_2d: Optional[list[float]] = None  # [x, y] UMAP
    complexity_score: float = 0.0
    clause_type: Literal["prose", "table"] = "prose"  # tables skip prose analysis
    # Phase 2
    llm_extraction: Optional[LLMCausalRule] = None
    extraction_method: Literal["rule_based", "llm", "both", "conflict"] = "rule_based"
    lime_available: bool = False


class DocumentMeta(BaseModel):
    doc_id: str
    filename: str
    pages: int
    file_size_kb: float
    status: Literal["pending", "processing", "complete", "error"] = "pending"
    pdf_path: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    type: Literal["document", "chapter", "section", "clause", "entity", "causal"]
    label: str
    data: dict


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AnalysisResult(BaseModel):
    doc_id: str
    clauses: list[Clause]
    graph: GraphData
    stats: dict


# --- Phase 2: simulation (Module C) ---

class SimulationConfig(BaseModel):
    agent_config: dict[str, int] = Field(
        default={
            "low_income": 500,
            "middle_income": 300,
            "high_income": 150,
            "small_business": 100,
            "large_corporate": 20,
        }
    )
    n_steps: int = 50
    rule_clause_ids: Optional[list[str]] = None  # None = all available rules
    seed: int = 42
    # Q-learning adaptive agents (Module C novelty). When true, agents learn a
    # comply/defect policy over the run instead of re-deciding from a fixed
    # tendency each step. Kept toggleable so static-vs-adaptive is an ablation.
    adaptive: bool = True
    # Income calibration: "nsso" (calibrated log-normal) or "legacy"
    # (log-uniform ranges). None → backend default (config.SIM_CALIBRATION).
    calibration_mode: Optional[Literal["nsso", "legacy"]] = None


class SimulationStep(BaseModel):
    step: int
    compliance_rate: float
    gini_coefficient: float
    avg_burden_by_type: dict[str, float]
    policy_burden_index: float
    compliance_by_type: dict[str, float]
    # Statutory incidence: effective rate = burden / gross income, per type.
    effective_rate_by_type: dict[str, float] = {}
    # Government revenue collected so far (₹).
    revenue_total: float = 0.0
    revenue_compliance: float = 0.0
    revenue_penalty: float = 0.0
    revenue_by_type: dict[str, float] = {}
    mean_q_gap: float = 0.0  # adaptive-agent learning convergence (0 for static)


class SimulationResult(BaseModel):
    simulation_id: str
    doc_id: str
    n_agents: int
    n_steps: int
    active_rules: list[str]  # clause_ids
    rules_source: Literal["llm", "rule_based"]
    steps: list[SimulationStep]
    final_gini: float
    final_compliance_rate: float
    policy_verdict: Literal["progressive", "neutral", "regressive"]
    # Verdict basis (effective-rate incidence) + revenue, surfaced so the
    # finding is auditable rather than a bare label.
    effective_rate_low: float = 0.0
    effective_rate_high: float = 0.0
    final_revenue: float = 0.0
    narrative: str = ""  # backend-generated, data-grounded explanation
    config: SimulationConfig
