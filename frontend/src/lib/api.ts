import type {
  Clause, GraphNode, GraphEdge, EmbeddingPoint, AnalysisStats,
  SearchResult, ReportSummary, CompareResult, DocumentMeta,
  ExtractionMethod, LIMEExplanation, LLMCausalRule, LLMExtractionSummary,
  SimulationConfig, SimulationCreated, SimulationResult, SimulationRuleInfo,
  SimulationProvenance, SimParam, DeepReasoning,
  CorpusStats, LLMBackendInfo, AuthUser, DashboardData, AdminMetrics, AdminUser,
} from "@/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Bearer token store (browser localStorage) for the JWT-backed auth flow. */
const TOKEN_KEY = "prism_token";
export const tokenStore = {
  get: () => (typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null),
  set: (t: string) => typeof window !== "undefined" && localStorage.setItem(TOKEN_KEY, t),
  clear: () => typeof window !== "undefined" && localStorage.removeItem(TOKEN_KEY),
};

function authHeaders(): Record<string, string> {
  const t = tokenStore.get();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/** Thrown when a Phase 2 endpoint is missing/unreachable — pages render a
 *  graceful "module offline" state instead of a crash. */
export class Phase2UnavailableError extends Error {
  constructor(message = "Phase 2 module unavailable") {
    super(message);
    this.name = "Phase2UnavailableError";
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

async function phase2Fetch<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, options);
  } catch {
    throw new Phase2UnavailableError("Backend unreachable");
  }
  if (res.status === 404 || res.status === 405 || res.status === 501) {
    // Endpoint 404s carry a JSON detail (doc not found) — module-missing
    // 404s don't. Treat "Not Found" plain responses as module-offline.
    const err = await res.clone().json().catch(() => null);
    if (!err || err.detail === "Not Found") throw new Phase2UnavailableError();
    throw new Error(err.detail);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  // ── Core ────────────────────────────────────────────────────────────────
  uploadPdf: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ doc_id: string; filename: string; pages: number; file_size_kb: number }>(
      "/api/upload",
      { method: "POST", body: form }
    );
  },

  triggerDemo: async () =>
    apiFetch<{ doc_id: string; filename: string; pages: number; message: string }>(
      "/api/demo",
      { method: "POST" }
    ),

  getClauses: async (docId: string) =>
    apiFetch<{ doc_id: string; clauses: Clause[] }>(`/api/clauses/${docId}`),

  getEntities: async (docId: string) =>
    apiFetch<{
      doc_id: string;
      entities: Array<{ label: string; text: string; clause_id: string; page: number }>;
      cooccurrence: Record<string, Record<string, number>>;
    }>(`/api/entities/${docId}`),

  getCausal: async (docId: string) =>
    apiFetch<{
      doc_id: string;
      patterns: Array<{
        pattern_type: string;
        condition_span: string;
        action_span: string;
        confidence: number;
        source_clause_id: string;
        risk_tier: string;
        impact_score: number;
        clause_page: number;
        clause_preview: string;
        section: string;
      }>;
      total: number;
    }>(`/api/causal/${docId}`),

  getEmbeddings: async (docId: string) =>
    apiFetch<{ doc_id: string; points: EmbeddingPoint[] }>(`/api/embeddings/${docId}`),

  getGraph: async (docId: string) =>
    apiFetch<{ doc_id: string; nodes: GraphNode[]; edges: GraphEdge[] }>(`/api/graph/${docId}`),

  getStats: async (docId: string) =>
    apiFetch<AnalysisStats & { doc_id: string }>(`/api/stats/${docId}`),

  listDocuments: async () =>
    apiFetch<{ documents: DocumentMeta[] }>("/api/documents"),

  health: async () => apiFetch<{ status: string }>("/health"),

  // ── Intelligence ────────────────────────────────────────────────────────
  search: async (docId: string, query: string, topK = 8) =>
    apiFetch<SearchResult>(`/api/search/${docId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    }),

  getReport: async (docId: string) =>
    apiFetch<ReportSummary>(`/api/report/${docId}`),

  downloadReport: (docId: string) => {
    window.open(`${API}/api/report/${docId}?fmt=html`, "_blank");
  },

  compare: async (docIdA: string, docIdB: string) =>
    apiFetch<CompareResult>("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id_a: docIdA, doc_id_b: docIdB }),
    }),

  getDomain: async (docId: string) =>
    apiFetch<{ doc_id: string; domain: string }>(`/api/domain/${docId}`),

  // ── Phase 2: LLM extraction ─────────────────────────────────────────────
  getLLMExtractions: async (docId: string) =>
    phase2Fetch<{
      doc_id: string;
      status: "idle" | "running" | "complete" | "error";
      progress: number;
      model: string | null;
      extractions: Array<{ clause_id: string; extraction: LLMCausalRule; extraction_method: ExtractionMethod }>;
      summary: LLMExtractionSummary | null;
    }>(`/api/clauses/${docId}/llm`),

  // ── Phase 2: LIME explainability ────────────────────────────────────────
  getExplanation: async (docId: string, clauseId: string, mode: "proxy" | "llm" = "proxy") =>
    phase2Fetch<LIMEExplanation & { status: "complete" | "running"; progress?: number; stream?: string }>(
      `/api/explain/${docId}/${clauseId}?mode=${mode}`
    ),

  // ── Phase 3: transformer attention (second XAI lens) ─────────────────────
  getAttention: async (docId: string, clauseId: string) =>
    phase2Fetch<LIMEExplanation & { explains?: string; status: "complete" }>(
      `/api/explain/${docId}/${clauseId}/attention`
    ),

  // ── Deep on-demand reasoning (rich multi-paragraph rationale) ────────────
  // 200 → { status:"complete", reasoning, ... }; 202 → { status:"running", stream }.
  getDeepReasoning: async (docId: string, clauseId: string, force = false) =>
    phase2Fetch<DeepReasoning & { status?: "complete" | "running"; stream?: string }>(
      `/api/explain/${docId}/${clauseId}/deep-reasoning${force ? "?force=true" : ""}`
    ),

  // ── Phase 2: simulation ─────────────────────────────────────────────────
  listSimulationRules: async (docId: string) =>
    phase2Fetch<{ doc_id: string; rules_source: "llm" | "rule_based"; count: number; rules: SimulationRuleInfo[] }>(
      `/api/simulate/${docId}/rules`
    ),

  createSimulation: async (docId: string, config: Partial<SimulationConfig>) =>
    phase2Fetch<SimulationCreated>(`/api/simulate/${docId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),

  getSimulationResults: async (docId: string, simulationId?: string) =>
    phase2Fetch<SimulationResult>(
      `/api/simulate/${docId}/results${simulationId ? `?simulation_id=${simulationId}` : ""}`
    ),

  getSimulationProvenance: async (docId: string, simulationId?: string) =>
    phase2Fetch<SimulationProvenance>(
      `/api/simulate/${docId}/provenance${simulationId ? `?simulation_id=${simulationId}` : ""}`
    ),

  // Model-assumptions transparency table.
  getSimulationParams: async () =>
    phase2Fetch<{ params: SimParam[] }>(`/api/simulate/params`),

  // ── Phase 3, Module D: RAG assistant ─────────────────────────────────────
  getBackend: async () => phase2Fetch<LLMBackendInfo>(`/api/rag/backend`),

  getCorpus: async () => phase2Fetch<CorpusStats>(`/api/rag/corpus`),

  ingestDoc: async (docId: string) =>
    phase2Fetch<{ doc_id: string; doc_name: string; indexed: number }>(
      `/api/rag/ingest/${docId}`,
      { method: "POST" }
    ),

  ingestAll: async () =>
    phase2Fetch<{ ingested: unknown[]; corpus: CorpusStats }>(`/api/rag/ingest-all`, {
      method: "POST",
    }),

  removeFromCorpus: async (docId: string) =>
    phase2Fetch<{ removed: string; corpus: CorpusStats }>(`/api/rag/corpus/${docId}`, {
      method: "DELETE",
    }),

  // ── Phase 3, Module F: auth + dashboard + admin ──────────────────────────
  register: async (email: string, password: string, name: string) =>
    phase2Fetch<{ token: string; user: AuthUser }>(`/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }),

  login: async (email: string, password: string) =>
    phase2Fetch<{ token: string; user: AuthUser }>(`/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  me: async () =>
    phase2Fetch<AuthUser>(`/api/auth/me`, { headers: authHeaders() }),

  dashboard: async () =>
    phase2Fetch<DashboardData>(`/api/auth/dashboard`, { headers: authHeaders() }),

  rotateApiKey: async () =>
    phase2Fetch<{ api_key: string }>(`/api/auth/api-key/rotate`, {
      method: "POST",
      headers: authHeaders(),
    }),

  adminMetrics: async () =>
    phase2Fetch<AdminMetrics>(`/api/admin/metrics`, { headers: authHeaders() }),

  adminUsers: async () =>
    phase2Fetch<{ users: AdminUser[] }>(`/api/admin/users`, { headers: authHeaders() }),

  adminSwitchBackend: async (backend: string) =>
    phase2Fetch<{ active: LLMBackendInfo }>(`/api/admin/backend`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ backend }),
    }),

  adminReindexCorpus: async () =>
    phase2Fetch<{ corpus: CorpusStats }>(`/api/admin/corpus/reindex`, {
      method: "POST",
      headers: authHeaders(),
    }),
};

export const SSE_URL = (docId: string, force = false) =>
  `${API}/api/analyze/${docId}${force ? "?force=true" : ""}`;
export const PDF_URL = (docId: string) => `${API}/api/pdf/${docId}`;
export const LLM_STREAM_URL = (docId: string, scope: "auto" | "all" = "auto") =>
  `${API}/api/analyze/${docId}/llm?scope=${scope}`;
export const EXPLAIN_STREAM_URL = (docId: string, clauseId: string, mode: "proxy" | "llm") =>
  `${API}/api/explain/${docId}/${clauseId}/stream?mode=${mode}`;
export const DEEP_REASONING_STREAM_URL = (docId: string, clauseId: string, force = false) =>
  `${API}/api/explain/${docId}/${clauseId}/deep-reasoning/stream${force ? "?force=true" : ""}`;
export const SIMULATE_STREAM_URL = (docId: string, simulationId: string) =>
  `${API}/api/simulate/${docId}/stream?simulation_id=${simulationId}`;
export const RAG_STREAM_URL = (q: string, docs: string[], strict: boolean) => {
  const params = new URLSearchParams({ q, strict: String(strict) });
  if (docs.length) params.set("docs", docs.join(","));
  return `${API}/api/rag/stream?${params.toString()}`;
};
