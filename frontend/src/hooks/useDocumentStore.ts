"use client";
import { create } from "zustand";
import type {
  AnalysisStats,
  Clause,
  ExtractionMethod,
  LLMCausalRule,
  LLMExtractionSummary,
  ProcessingStage,
} from "@/types";

type LLMStage = "idle" | "running" | "complete" | "error";

interface DocumentState {
  docId: string | null;
  filename: string | null;
  pages: number;
  stage: ProcessingStage;
  progress: number;
  stageMessage: string;
  totalClauses: number;
  processedCount: number;
  clauses: Clause[];
  stats: AnalysisStats | null;
  /** true when state was loaded from REST (already-analyzed doc) — no overlay */
  hydrated: boolean;
  // Phase 2 — LLM extraction stream state
  llmStage: LLMStage;
  llmProcessed: number;
  llmTotal: number;
  llmSummary: LLMExtractionSummary | null;
  // UI state
  selectedClauseId: string | null;
  highlightedEntityKey: string | null;
  selectedClauseIds: Set<string>;
  currentPdfPage: number;

  // Actions
  setDocId: (id: string, filename: string, pages: number) => void;
  setStage: (stage: ProcessingStage, message?: string, progress?: number) => void;
  addClause: (clause: Clause) => void;
  addClauses: (clauses: Clause[]) => void;
  updateClauseEmbeddings: (updates: { clause_id: string; embedding_2d: [number, number] }[]) => void;
  setProcessedCount: (current: number, total: number) => void;
  setStats: (stats: AnalysisStats) => void;
  hydrate: (clauses: Clause[], stats: AnalysisStats) => void;
  resetClauses: () => void;
  mergeLLMExtraction: (clauseId: string, extraction: LLMCausalRule, method: ExtractionMethod) => void;
  setLLMStage: (stage: LLMStage) => void;
  setLLMProgress: (processed: number, total: number) => void;
  setLLMSummary: (summary: LLMExtractionSummary | null) => void;
  setSelectedClauseId: (id: string | null) => void;
  setHighlightedEntityKey: (key: string | null) => void;
  setSelectedClauseIds: (ids: Set<string>) => void;
  setPdfPage: (page: number) => void;
  reset: () => void;
}

const initialState = {
  docId: null,
  filename: null,
  pages: 0,
  stage: "idle" as ProcessingStage,
  progress: 0,
  stageMessage: "",
  totalClauses: 0,
  processedCount: 0,
  clauses: [] as Clause[],
  stats: null,
  hydrated: false,
  llmStage: "idle" as LLMStage,
  llmProcessed: 0,
  llmTotal: 0,
  llmSummary: null,
  selectedClauseId: null,
  highlightedEntityKey: null,
  selectedClauseIds: new Set<string>(),
  currentPdfPage: 1,
};

/** Append clauses, dropping any clause_id already present (SSE replays,
 *  reconnects, and hydration races are all dedupe-safe). */
function dedupeAppend(existing: Clause[], incoming: Clause[]): Clause[] {
  if (incoming.length === 0) return existing;
  const seen = new Set(existing.map((c) => c.clause_id));
  const fresh = incoming.filter((c) => {
    if (seen.has(c.clause_id)) return false;
    seen.add(c.clause_id);
    return true;
  });
  return fresh.length > 0 ? [...existing, ...fresh] : existing;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  ...initialState,

  setDocId: (id, filename, pages) =>
    set((s) =>
      s.docId === id
        ? { filename, pages }
        : { ...initialState, docId: id, filename, pages }
    ),

  setStage: (stage, message = "", progress = 0) =>
    set({ stage, stageMessage: message, progress }),

  addClause: (clause) =>
    set((s) => ({ clauses: dedupeAppend(s.clauses, [clause]) })),

  addClauses: (newClauses) =>
    set((s) => ({ clauses: dedupeAppend(s.clauses, newClauses) })),

  updateClauseEmbeddings: (updates) =>
    set((s) => {
      const embMap = new Map(updates.map((u) => [u.clause_id, u.embedding_2d]));
      return {
        clauses: s.clauses.map((c) =>
          embMap.has(c.clause_id)
            ? { ...c, embedding_2d: embMap.get(c.clause_id)! }
            : c
        ),
      };
    }),

  setProcessedCount: (current, total) =>
    set({ processedCount: current, totalClauses: total }),

  setStats: (stats) => set({ stats }),

  hydrate: (clauses, stats) =>
    set({
      clauses,
      stats,
      stage: "complete",
      progress: 100,
      stageMessage: "Loaded from analysis store",
      hydrated: true,
      totalClauses: clauses.length,
      processedCount: clauses.length,
    }),

  resetClauses: () =>
    set({ clauses: [], processedCount: 0, selectedClauseId: null, selectedClauseIds: new Set() }),

  mergeLLMExtraction: (clauseId, extraction, method) =>
    set((s) => ({
      clauses: s.clauses.map((c) =>
        c.clause_id === clauseId
          ? { ...c, llm_extraction: extraction, extraction_method: method }
          : c
      ),
    })),

  setLLMStage: (llmStage) => set({ llmStage }),
  setLLMProgress: (llmProcessed, llmTotal) => set({ llmProcessed, llmTotal }),
  setLLMSummary: (llmSummary) => set({ llmSummary }),

  setSelectedClauseId: (id) =>
    set((s) => {
      const clause = id ? s.clauses.find((c) => c.clause_id === id) : undefined;
      // Selecting a clause also navigates the PDF viewer to its page.
      return { selectedClauseId: id, ...(clause ? { currentPdfPage: clause.page } : {}) };
    }),

  setHighlightedEntityKey: (key) => set({ highlightedEntityKey: key }),

  setSelectedClauseIds: (ids) => set({ selectedClauseIds: ids }),

  setPdfPage: (page) => set({ currentPdfPage: page }),

  reset: () => set(initialState),
}));
