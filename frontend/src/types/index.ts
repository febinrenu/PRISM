export type EntityLabel =
  | "OBLIGATION"
  | "RIGHT"
  | "PENALTY"
  | "THRESHOLD"
  | "ACTOR"
  | "BENEFICIARY";

export type EntityConfidence = "HIGH" | "MEDIUM" | "LOW";

export interface Entity {
  label: EntityLabel;
  text: string;
  start: number;
  end: number;
  confidence: EntityConfidence;
}

export type PatternType = "IF_THEN" | "CONDITION_ACTION" | "PENALTY_TRIGGER";
export type RiskTier = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface CausalPattern {
  pattern_type: PatternType;
  condition_span: string;
  action_span: string;
  confidence: number;
  source_clause_id: string;
  risk_tier: RiskTier;
  impact_score: number;
  explanation?: string;  // deterministic rationale for why it was flagged
}

export type ExtractionMethod = "rule_based" | "llm" | "both" | "conflict" | "failed";

export interface LLMCausalRule {
  is_causal: boolean | null;
  condition: string | null;
  action: string | null;
  consequence: string | null;
  actors: string[];
  thresholds: string[];
  confidence: number;
  reasoning: string;
  extraction_time_ms: number;
  model: string;
  parse_error?: string | null;
  /** amounts and rates the reading states that the clause text does not */
  unsupported_numbers?: string[];
}

export interface Clause {
  clause_id: string;
  doc_id: string;
  page: number;
  section_hierarchy: string[];
  text: string;
  char_start: number;
  char_end: number;
  bbox?: [number, number, number, number];
  entities: Entity[];
  causal_patterns: CausalPattern[];
  embedding_2d?: [number, number];
  complexity_score: number;
  clause_type?: "prose" | "table";
  llm_extraction?: LLMCausalRule | null;
  extraction_method?: ExtractionMethod;
  lime_available?: boolean;
}

export interface DocumentMeta {
  doc_id: string;
  filename: string;
  pages: number;
  file_size_kb: number;
  status: "pending" | "processing" | "complete" | "error";
  owner_id?: string | null;   // null: shared (anonymous upload or demo)
}

export interface GraphNode {
  id: string;
  type: "document" | "chapter" | "section" | "clause" | "entity" | "causal";
  label: string;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export type ProcessingStage =
  | "idle"
  | "parsing"
  | "segmentation"
  | "ner"
  | "embedding"
  | "graph"
  | "complete"
  | "error";

export interface EmbeddingUpdate {
  clause_id: string;
  embedding_2d: [number, number];
}

export interface SSEEvent {
  stage: ProcessingStage | "embeddings_update";
  message?: string;
  progress?: number;
  current?: number;
  total?: number;
  pages?: number;
  clause?: Clause;
  doc_id?: string;
  stats?: AnalysisStats;
  updates?: EmbeddingUpdate[];
}

export interface AnalysisStats {
  total_clauses: number;
  total_entities: number;
  entity_type_counts: Partial<Record<EntityLabel, number>>;
  entity_confidence_counts?: { HIGH: number; MEDIUM: number; LOW: number };
  causal_patterns_found: number;
  causal_risk_counts?: { CRITICAL: number; HIGH: number; MEDIUM: number; LOW: number };
  total_pages: number;
  graph_nodes: number;
  graph_edges: number;
  most_complex_clause_id?: string;
  domain?: string;
  /** How each page's text was read (absent on results from before it was recorded). */
  reading?: ReadingSummary;
}

export interface ReadingSummary {
  pages: number;
  /** pages read from the PDF's text layer */
  text: number;
  /** pages whose fonts had no text map, decoded from the fonts' glyph names (exact) */
  decoded: number;
  /** pages read by OCR (scans, or text that could not be decoded) */
  ocr: number;
  /** pages with no usable text and no OCR available */
  unreadable: number;
  ocr_pages: number[];
  unreadable_pages: number[];
  ocr_confidence: number | null;
  ocr_available: boolean | null;
}

export interface EmbeddingPoint {
  clause_id: string;
  x: number;
  y: number;
  dominant_entity: EntityLabel | "NONE";
  entity_count: number;
  text_preview: string;
  page: number;
}

// ─── Intelligence API types ────────────────────────────────────────────────

export interface SearchHit {
  clause_id: string;
  score: number;
  page: number;
  section: string;
  text: string;
  text_preview: string;
  entities: Entity[];
  causal_count: number;
  risk_tier: RiskTier;
}

export interface SearchResult {
  doc_id: string;
  query: string;
  hits: SearchHit[];
  answer: string;
  total_searched: number;
}

export interface ReportSummary {
  doc_id: string;
  filename: string;
  domain: string;
  generated_at: string;
  executive_summary: {
    total_clauses: number;
    total_entities: number;
    causal_patterns: number;
    critical_risks: number;
    high_risks: number;
    total_pages: number;
    domain: string;
  };
  causal_analysis: {
    total: number;
    by_type: Record<PatternType, number>;
    risk_matrix: Record<RiskTier, CausalPattern[]>;
  };
  compliance_checklist: Array<{
    priority: RiskTier;
    item: string;
    action: string;
  }>;
  entity_counts?: Record<string, number>;
  key_obligations?: Array<{
    clause_id: string;
    page: number;
    section: string;
    text_preview: string;
    obligation_phrases: string[];
    has_penalty: boolean;
  }>;
  graph_summary?: { nodes: number; edges: number };
}

export interface ClauseDiff {
  matched: number;
  modified: Array<{ clause_a_id: string; clause_b_id: string; similarity: number }>;
  added: string[];
  removed: string[];
  thresholds: { matched: number; modified: number };
}

export interface CompareResult {
  doc_a: { doc_id: string; filename: string; clauses: number; entities: number; domain: string; risk_counts: Record<RiskTier, number> };
  doc_b: { doc_id: string; filename: string; clauses: number; entities: number; domain: string; risk_counts: Record<RiskTier, number> };
  entity_delta: Record<EntityLabel, { only_in_a: string[]; only_in_b: string[]; shared: string[]; count_a: number; count_b: number }>;
  obligation_summary: { obligations_in_a: number; obligations_in_b: number; delta: number };
  risk_comparison: { a: Record<RiskTier, number>; b: Record<RiskTier, number>; delta: Record<RiskTier, number> };
  clause_diff?: ClauseDiff | null;
  new_entities?: Array<{ label: EntityLabel; text: string; clause_id: string }>;
  new_causal_rules?: Array<LLMCausalRule & { clause_id: string }>;
}

// ─── Phase 2: LLM extraction stream ───────────────────────────────────────

export interface LLMExtractionSummary {
  selected: number;
  causal_found: number;
  failed: number;
  agreement: { both: number; llm_only: number; rule_only: number; neither: number; conflict: number };
  total_time_ms?: number;
}

export type LLMStreamEvent =
  | { stage: "llm_started"; doc_id: string; total_candidates: number; selected: number; capped: boolean; cached: number; model: string }
  | { stage: "llm_clause"; clause_id: string; status: "processing" }
  | { stage: "llm_clause"; clause_id: string; status: "done"; current: number; total: number; progress: number; from_cache: boolean; extraction_method: ExtractionMethod; extraction: LLMCausalRule }
  | { stage: "llm_clause"; clause_id: string; status: "error"; error: string; current: number; total: number; progress: number }
  | { stage: "llm_complete"; doc_id: string; summary: LLMExtractionSummary }
  | { stage: "error"; message: string };

// ─── Phase 2: LIME explainability ─────────────────────────────────────────

export interface LIMEToken {
  token: string;
  weight: number;
  normalized_weight: number;
  position: number;
}

export interface LIMEExplanation {
  status?: "complete" | "running";
  clause_id: string;
  mode: "proxy" | "llm";
  num_samples: number;
  model: string;
  prediction: { is_causal: boolean; p_causal: number } | null;
  lime_tokens: LIMEToken[];
  top_tokens: Array<[string, number]>;
  fidelity?: number | null;  // local-surrogate R² (LIME explanation quality)
  elapsed_ms: number;
  cached: boolean;
  not_applicable?: "table";  // clause is tabular data, not analyzed as prose
  message?: string;
}

// ─── Phase 2: simulation ──────────────────────────────────────────────────

export type AgentTypeKey =
  | "low_income"
  | "middle_income"
  | "high_income"
  | "small_business"
  | "large_corporate";

export type CalibrationMode = "nsso" | "legacy";

export interface SimulationConfig {
  agent_config: Record<AgentTypeKey, number>;
  n_steps: number;
  rule_clause_ids?: string[] | null;
  seed?: number;
  adaptive?: boolean;  // Q-learning adaptive agents (Module C novelty)
  calibration_mode?: CalibrationMode | null;
}

export interface SimulationRuleInfo {
  clause_id: string;
  description: string;
  threshold_value: number | null;
  threshold_kind?: "amount" | "percent" | "duration" | null;
  rate_percent: number | null;
  marginal?: boolean;
  full_base?: boolean;
  penalty_probability: number;
  affected_agent_types: string[];
  source: "llm" | "rule_based";
  matched_template?: string | null;
  match_score?: number | null;
}

// Model-assumptions transparency table (GET /api/simulate/params)
export interface SimParam {
  key: string;
  label: string;
  value: unknown;
  rationale: string;
  tag: "sourced" | "illustrative";
  group: string;
}

// ─── Phase 2+: provenance drill-down (finding → rule → clause → LLM → LIME) ──

export interface ProvenanceLink {
  clause_id: string;
  rule: SimulationRuleInfo | null;
  matched_template?: string | null;
  match_score?: number | null;
  clause: {
    page: number;
    bbox?: [number, number, number, number] | null;
    text: string;
    section_hierarchy: string[];
    clause_type?: "prose" | "table";
  };
  llm_extraction: LLMCausalRule | null;
  lime_available: boolean;
  lime: {
    mode: "proxy" | "llm";
    top_tokens: Array<[string, number]>;
    prediction: { is_causal: boolean; p_causal: number } | null;
    fidelity?: number | null;
  } | null;
}

export interface SimulationProvenance {
  doc_id: string;
  simulation_id: string;
  policy_verdict: PolicyVerdict;
  final_gini: number;
  final_compliance_rate: number;
  rules_source: "llm" | "rule_based";
  chain: ProvenanceLink[];
}

export interface SimulationCreated {
  simulation_id: string;
  doc_id: string;
  n_agents: number;
  n_steps: number;
  active_rules: string[];
  rules_source: "llm" | "rule_based";
  rules: SimulationRuleInfo[];
  unmatched_rule_ids?: string[];
  status: "ready";
}

export interface SimulationStep {
  step: number;
  compliance_rate: number;
  gini_coefficient: number;
  avg_burden_by_type: Record<AgentTypeKey, number>;
  policy_burden_index: number;
  compliance_by_type: Record<AgentTypeKey, number>;
  // Statutory incidence: effective rate = burden / gross income, per type.
  effective_rate_by_type?: Record<AgentTypeKey, number>;
  // Government revenue collected so far (₹).
  revenue_total?: number;
  revenue_compliance?: number;
  revenue_penalty?: number;
  revenue_by_type?: Record<AgentTypeKey, number>;
  mean_q_gap?: number;
}

export type PolicyVerdict = "progressive" | "neutral" | "regressive";

export interface SimulationResult {
  simulation_id: string;
  doc_id: string;
  n_agents: number;
  n_steps: number;
  active_rules: string[];
  rules_source: "llm" | "rule_based";
  steps: SimulationStep[];
  final_gini: number;
  final_compliance_rate: number;
  policy_verdict: PolicyVerdict;
  effective_rate_low?: number;
  effective_rate_high?: number;
  final_revenue?: number;
  narrative?: string;
  config: SimulationConfig;
}

/** One saved sandbox run, as listed (no per-step data). */
export interface SimulationRunSummary {
  simulation_id: string;
  created_at: string;
  n_agents: number;
  n_steps: number;
  n_rules: number;
  rules_source: "llm" | "rule_based";
  policy_verdict: PolicyVerdict;
  final_gini: number;
  final_compliance_rate: number;
  final_revenue: number;
  adaptive: boolean;
  calibration_mode: string;
}

// ─── Phase 3, Module D: RAG assistant ─────────────────────────────────────

export interface LLMBackendInfo {
  backend: string;
  kind: "ollama" | "groq";
  model: string;
  cloud: boolean;
  configured: boolean;
  /** The backend tried when the configured one fails, if there is one. */
  fallback?: { kind: "ollama" | "groq"; model: string } | null;
}

export interface RAGCitation {
  index: number;
  doc_id: string;
  doc_name: string;
  clause_id: string;
  section: string;
  heading?: string;
  page: number;
  similarity: number | null;
  rerank_score?: number | null;
  text: string;
  text_preview: string;
  entity_types: string[];
  /** "statute": a passage of a parsed Act; "clause": a clause of an analysed document. */
  kind?: "clause" | "statute";
  /** "section": fetched by the section number the question named; "search": retrieved. */
  match?: "search" | "section";
  statute_key?: string | null;
  node_path?: string | null;
  /** The passage was shortened to fit the model's window. */
  cut?: boolean;
}

export interface CorpusDoc {
  doc_id: string;
  doc_name: string;
  clauses: number;
  causal: number;
  kind?: "statute" | "document";
}

export interface CorpusStats {
  total_clauses: number;
  documents: CorpusDoc[];
  collection: string;
  /** Statutes still being indexed in the background. */
  indexing?: number;
}

/** How an answer fared: every claim checked and supported, some flagged, or not in the corpus. */
export type AnswerState = "answered" | "partial" | "not_found";

export interface AnswerClaim {
  text: string;
  sources: number[];
  status: "supported" | "unsupported" | "uncited";
  issues: string[];
}

export interface BackendUsed {
  backend: string;
  model: string;
  fell_back: boolean;
  reason: string | null;
}

export interface RAGPlan {
  question: string;
  /** The follow-up as a standalone question, when it needed one. */
  standalone: string | null;
  intent: "ask" | "lookup" | "compare";
  sections: string[];
  acts: string[];
}

export interface RAGVerdict {
  state: AnswerState;
  grounded: boolean;
  abstained: boolean;
  cited_sources: number[];
  invalid_citations: number[];
  unsupported_numbers: string[];
  claims: AnswerClaim[];
  n_supported: number;
  n_claims: number;
  /** Statements that carry no citation (counted, not necessarily wrong). */
  n_uncited?: number;
  /** Statements with a figure or quotation that conflicts with the cited text. */
  n_conflicts?: number;
}

export type RAGStreamEvent =
  | ({ stage: "plan" } & RAGPlan)
  | {
      stage: "retrieval"; citations: RAGCitation[]; retrieval_confidence: number; n_sources: number;
      backend: LLMBackendInfo; exact_match?: boolean; gated?: boolean;
    }
  | { stage: "token"; token: string }
  | { stage: "revising"; reason: string }
  | { stage: "replace"; answer: string }
  | { stage: "warning"; message: string }
  | ({
      stage: "done"; answer: string; n_sources: number; retrieval_confidence: number; exact_match?: boolean;
      backend_used?: BackendUsed | null; latency_ms?: { search?: number; first_token?: number; total?: number };
      revised?: boolean; standalone?: string | null;
    } & RAGVerdict)
  | { stage: "error"; message: string };

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: RAGCitation[];
  retrievalConfidence?: number;
  exactMatch?: boolean;
  /** Retrieval was too weak to answer: the citations are only the closest passages. */
  gated?: boolean;
  plan?: RAGPlan;
  verdict?: RAGVerdict;
  backendUsed?: BackendUsed | null;
  latencyMs?: { search?: number; first_token?: number; total?: number };
  revised?: boolean;
  revising?: string;
  streaming?: boolean;
  error?: string;
  warning?: string;
}

// ─── Policy sandbox, statute mode: scenarios on the document's own rate table ──

export interface PolicySlab {
  lower: number;
  upper: number | null;
  rate: number;
}

export interface PolicyRebate {
  max_income: number;
  max_rebate: number;
  marginal_relief: boolean;
}

export interface PolicyLawParams {
  slabs: PolicySlab[];
  rebate: PolicyRebate | null;
  standard_deduction: number;
  cess_rate: number;
}

export interface PolicyProvenanceRow {
  parameter: string;
  value: string;
  source: string;
  check: string;
  from_document: boolean;
}

export interface PolicyTable {
  index: number;
  page: number;
  heading: string;
  assessment_year: string | null;
  bands: number;
}

export interface PolicyLaw {
  available: true;
  ay: string;
  law: string;
  source: "document" | "expert";
  title: string;
  matched_year: string | null;
  review: string[];
  provenance: PolicyProvenanceRow[];
  schedule: { page: number; heading: string; assessment_year: string | null } | null;
  law_params: PolicyLawParams;
  regimes: string[];
  default_regime: string;
  surcharge: { threshold: number; rate: number }[];
  tables: PolicyTable[];
  selected_table: number | null;
  bounds: Record<string, [number, number]>;
  behaviour_limits: Record<string, [number, number]>;
}

export interface PolicyLawUnavailable {
  available: false;
  reason: string;
  tables: PolicyTable[];
  bounds: Record<string, [number, number]>;
}

export interface PolicyYear {
  ay: string;
  law: string;
  default_regime: string;
  bands: number;
  top_rate: number;
}

export interface PolicyChanges {
  slabs?: PolicySlab[];
  rebate?: PolicyRebate | null;
  standard_deduction?: number;
  cess_rate?: number;
}

export interface PolicyAssumptions {
  optimal_share: number;
  via_scale: number;
  top_alpha: number | null;
  senior_share: number;
  growth: number;
}

export interface PolicyBehaviourInput {
  audit_rate?: number | null;
  penalty_rate?: number | null;
  morale?: number | null;
}

export interface PolicyScenarioRequest {
  doc_id?: string | null;
  ay?: string | null;
  schedule?: number | null;
  changes: PolicyChanges;
  assumptions: PolicyAssumptions;
  behaviour?: PolicyBehaviourInput | null;
  uncertainty: number;
}

export interface PolicyOutcome {
  revenue_crore: number;
  taxpayers_with_tax: number;
  returns: number;
  gini_pre: number;
  gini_post: number;
  kakwani: number;
  reynolds_smolensky: number;
  suits: number;
  new_regime_share: number;
  deciles: { decile: number; tax_crore: number; income_crore: number; effective_rate: number; income_upper: number | null }[];
}

export interface PolicyImpactGroup {
  label: string;
  lower: number | null;
  upper: number | null;
  returns: number;
  share_pay_less: number;
  share_pay_more: number;
  mean_change_inr: number;
  base_tax_crore: number;
  reform_tax_crore: number;
  base_rate: number;
  reform_rate: number;
}

export interface PolicyLever {
  id: string;
  label: string;
  revenue_crore: number;
}

export interface PolicyRange {
  p5: number;
  median: number;
  p95: number;
  min: number;
  max: number;
}

export interface PolicyUncertainty {
  n: number;
  ranges: Record<string, [number, number]>;
  revenue_delta_crore: PolicyRange;
  kakwani_delta: PolicyRange;
  sign_stable: boolean;
  tornado: { input: string; low_value: number; high_value: number; at_low_crore: number; at_high_crore: number; swing_crore: number }[];
}

export interface PolicyBehaviour {
  params: { audit_rate: number; penalty_rate: number; morale: number };
  agents: number;
  seeds: number;
  baseline: { revenue_crore: number; tax_gap: number; evaders: number };
  reform: { revenue_crore: number; tax_gap: number; evaders: number };
  delta_revenue_crore: { mean: number; min: number; max: number };
  delta_tax_gap: number;
  note: string;
}

export interface PolicyScenarioResult {
  ay: string;
  /** Which Act the assessment year falls under ("ITA1961" or "ITA2025"). */
  law_code: string;
  assumptions: PolicyAssumptions;
  changes_applied: string[];
  population: { ay: string; returns: number; points: number; base_year: string };
  baseline: PolicyOutcome;
  scenario: PolicyOutcome;
  delta: {
    revenue_crore: number;
    revenue_pct: number;
    taxpayers_with_tax: number;
    gini_post: number;
    kakwani: number;
    reynolds_smolensky: number;
    suits: number;
  };
  impact: {
    overall: { share_pay_less: number; share_pay_more: number; share_unchanged: number };
    deciles: PolicyImpactGroup[];
    bands: PolicyImpactGroup[];
  };
  attribution: { exact: boolean; total_crore: number; matches_total: boolean; levers: PolicyLever[] } | null;
  law: { baseline: PolicyLawParams; scenario: PolicyLawParams };
  uncertainty: PolicyUncertainty | null;
  behaviour: PolicyBehaviour | null;
  warnings: string[];
  scope: string;
}

export interface PolicyValidation {
  in_sample: {
    ay: string;
    simulated_crore: number;
    reported_crore: number;
    ratio: number;
    band_share_l1: number;
    simulated_taxpayers: number;
    reported_taxpayers: number;
  }[];
  forecast: {
    method: string;
    tests: {
      base_ay: string;
      target_ay: string;
      predicted_crore: number;
      observed_crore: number;
      naive_crore: number;
      ape_model: number;
      ape_naive: number;
      skill: number | null;
    }[];
  };
  reform_cost: {
    reform: string;
    simulated_cost_crore: number;
    announced_cost_crore: number;
    ratio: number;
    source: string;
    note: string;
  }[];
  reading: string[];
  limits: string[];
}

// ─── Phase 3, Module F: auth + dashboard + admin ──────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  role: "user" | "researcher" | "admin";
  created_at: string;
}

export interface DashboardData {
  user: AuthUser;
  api_key: string;
  rate_limit: string;
  usage_total: number;
  /** Calls in the last hour, the window the rate limit counts. */
  usage_hour?: number;
  quota_per_hour: number;
  documents: Array<{ doc_id: string; doc_name: string; status: string; created_at: string }>;
  simulations: Array<{ doc_id: string; config: string; results: string; created_at: string }>;
}

export interface AdminMetrics {
  users: number;
  documents: number;
  user_documents: number;
  simulations: number;
  api_calls_total: number;
  llm_backend: LLMBackendInfo;
  storage: { backend: string; bucket: string | null };
  corpus: CorpusStats;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
  doc_count: number;
  api_calls: number;
}

// Deep on-demand clause reasoning (GET /api/explain/{doc}/{clause}/deep-reasoning)
export interface DeepReasoning {
  status?: "complete" | "running";
  clause_id: string;
  reasoning: string;
  model?: string;
  generation_time_ms?: number;
  cached?: boolean;
  not_applicable?: "table";
}
