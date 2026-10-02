"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, ChevronRight, CircleOff, FlaskConical, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useExplanation } from "@/hooks/useExplanation";
import LIMEHeatmap from "@/components/explain/LIMEHeatmap";
import TokenBarChart from "@/components/explain/TokenBarChart";
import AttentionCard from "@/components/explain/AttentionCard";
import LLMExtractionCard from "@/components/explain/LLMExtractionCard";
import DeepReasoningCard from "@/components/explain/DeepReasoningCard";
import RuleVsLLMTable from "@/components/explain/RuleVsLLMTable";
import PrismMark from "@/components/brand/PrismMark";
import type { Clause } from "@/types";

export default function ExplainPage({
  params,
}: {
  params: { docId: string; clauseId: string };
}) {
  const { docId, clauseId } = params;
  const [mode, setMode] = useState<"proxy" | "llm">("proxy");
  const [clause, setClause] = useState<Clause | null>(null);
  const [clauseError, setClauseError] = useState<string | null>(null);
  const { state, rerun } = useExplanation(docId, clauseId, mode);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { clauses } = await api.getClauses(docId);
        if (cancelled) return;
        const found = clauses.find((c) => c.clause_id === clauseId);
        if (!found) setClauseError("Clause not found in this document.");
        else setClause(found);
      } catch (error) {
        if (!cancelled) setClauseError(error instanceof Error ? error.message : "Failed to load clause");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId, clauseId]);

  const section = clause?.section_hierarchy?.length
    ? `§${clause.section_hierarchy.join(".")}`
    : clauseId.slice(-6);

  return (
    <div className="min-h-screen app-shell bg-bg-base">
      <div className="gradient-orb-1" style={{ opacity: 0.3 }} />
      <div className="gradient-orb-2" style={{ opacity: 0.25 }} />
      <div className="noise-overlay" />

      {/* Nav + breadcrumb */}
      <nav className="content-layer sticky top-0 z-20 flex items-center justify-between px-6 py-3 bg-bg-deep/90 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href={`/analyze/${docId}`}
            className="flex items-center gap-1.5 text-xs font-mono text-text-muted hover:text-text-primary transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" /> Workspace
          </Link>
          <div className="w-px h-4 bg-border" />
          <PrismMark size={24} />
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-text-muted min-w-0">
            <span className="truncate max-w-[140px]">Document</span>
            <ChevronRight className="w-3 h-3 flex-shrink-0" />
            <span>{section}</span>
            <ChevronRight className="w-3 h-3 flex-shrink-0" />
            <span className="text-accent-primary">Explainability</span>
          </div>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-border overflow-hidden">
            {(["proxy", "llm"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  mode === m
                    ? "bg-accent-primary/15 text-accent-primary"
                    : "text-text-dim hover:text-text-secondary"
                }`}
                title={
                  m === "proxy"
                    ? "Fast preview — explains the Phase 1 rule-based classifier (~1s)"
                    : "Faithful — every LIME sample is classified by Phi-3.5-mini (~1–3 min)"
                }
              >
                {m === "proxy" ? "Fast preview" : "LLM faithful"}
              </button>
            ))}
          </div>
          <button
            onClick={rerun}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-[10px] font-mono text-text-muted hover:text-accent-primary hover:border-accent-primary/40 transition-colors"
          >
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
      </nav>

      <main className="content-layer max-w-7xl mx-auto px-6 py-8">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-3 mb-2">
            <span className="h-px w-8 bg-accent-primary/60" />
            <span className="kicker">Explainability Studio</span>
          </div>
          <h1 className="font-display text-3xl md:text-4xl text-text-primary mb-1">
            Inside the model’s reading of {section}
          </h1>
          <p className="text-sm text-text-muted max-w-2xl leading-relaxed">
            LIME perturbs the clause hundreds of ways and watches the classifier respond — tokens
            tinted green push the clause toward a causal reading, red push away.
            {mode === "proxy" && (
              <span className="text-status-warning"> Fast preview explains the rule-based classifier, not the LLM.</span>
            )}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
          {/* Left: LIME heatmap */}
          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="space-y-4"
          >
            <div className="glass-card p-6 min-h-[280px]">
              <div className="flex items-center justify-between mb-4">
                <span className="kicker !text-[9px]">Token attribution</span>
                {state.status === "complete" && !state.explanation.not_applicable && (
                  <span className="text-[10px] font-mono text-text-dim flex items-center gap-2">
                    <span>
                      {state.explanation.mode} · {state.explanation.num_samples} samples ·{" "}
                      {state.explanation.cached ? "cached" : `${Math.round(state.explanation.elapsed_ms / 1000)}s`}
                    </span>
                    {typeof state.explanation.fidelity === "number" && (
                      <span
                        className="px-1.5 py-0.5 rounded border border-border text-text-muted"
                        title="LIME local-surrogate fidelity (R²): how faithfully these token weights explain the classifier near this clause"
                      >
                        fidelity {state.explanation.fidelity.toFixed(2)}
                      </span>
                    )}
                  </span>
                )}
              </div>

              {state.status === "loading" && <HeatmapSkeleton />}
              {state.status === "running" && (
                <div className="flex flex-col items-center justify-center py-14 gap-4">
                  <Loader2 className="w-6 h-6 text-accent-primary animate-spin" />
                  <p className="text-xs font-mono text-text-muted">
                    Classifying perturbation {state.done}/{state.total} with Phi-3.5-mini…
                  </p>
                  <div className="w-56 h-1 rounded-full bg-bg-elevated overflow-hidden">
                    <div
                      className="h-full bg-accent-primary transition-all duration-700"
                      style={{ width: state.total ? `${(state.done / state.total) * 100}%` : "5%" }}
                    />
                  </div>
                </div>
              )}
              {state.status === "offline" && (
                <OfflineState label="Explainability module offline — start the backend with Phase 2 enabled." />
              )}
              {state.status === "error" && <OfflineState label={state.message} />}
              {state.status === "complete" && state.explanation.not_applicable === "table" && (
                <OfflineState label={state.explanation.message || "Tabular data — not analyzed as a prose clause."} />
              )}
              {state.status === "complete" && !state.explanation.not_applicable && clause && (
                <LIMEHeatmap clauseText={clause.text} limeTokens={state.explanation.lime_tokens} />
              )}
            </div>

            {state.status === "complete" && !state.explanation.not_applicable && (
              <div className="glass-card p-6">
                <span className="kicker !text-[9px] block mb-4">Most influential tokens</span>
                <TokenBarChart topTokens={state.explanation.top_tokens} />
              </div>
            )}

            {clause && clause.clause_type !== "table" && (
              <AttentionCard docId={docId} clauseId={clauseId} clauseText={clause.text} />
            )}
          </motion.section>

          {/* Right: LLM extraction breakdown */}
          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16 }}
            className="space-y-4"
          >
            {clauseError && <OfflineState label={clauseError} />}
            {clause?.clause_type === "table" ? (
              <div className="glass-card p-6 text-center space-y-3">
                <Sparkles className="w-6 h-6 text-text-dim mx-auto" />
                <p className="text-sm text-text-secondary">Tabular data — not analyzed as a prose clause.</p>
                <p className="text-xs text-text-muted">
                  Causal extraction runs on prose clauses; tables are shown as-is for reference.
                </p>
              </div>
            ) : clause?.llm_extraction ? (
              <LLMExtractionCard rule={clause.llm_extraction} />
            ) : clause ? (
              <div className="glass-card p-6 text-center space-y-3">
                <Sparkles className="w-6 h-6 text-text-dim mx-auto" />
                <p className="text-sm text-text-secondary">This clause wasn’t selected for LLM extraction.</p>
                <p className="text-xs text-text-muted">
                  Phi-3.5-mini prioritizes clauses with an obligation or penalty. Run LLM extraction
                  from the workspace’s LLM tab (use “all” scope to include every clause).
                </p>
              </div>
            ) : null}

            {clause && clause.clause_type !== "table" && (
              <DeepReasoningCard docId={docId} clauseId={clauseId} />
            )}

            {clause && (
              <>
                <RuleVsLLMTable clause={clause} />
                <Link
                  href={`/simulate/${docId}?clause=${clauseId}`}
                  className="glass-card glass-card-hover p-4 flex items-center gap-3 group"
                >
                  <FlaskConical className="w-4 h-4 text-status-success" />
                  <div>
                    <p className="text-xs font-semibold text-text-primary">Simulate this clause’s impact</p>
                    <p className="text-[10px] font-mono text-text-dim">
                      Open the Simulation Theater pre-filtered to this rule
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-dim ml-auto group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </>
            )}
          </motion.section>
        </div>
      </main>
    </div>
  );
}

function HeatmapSkeleton() {
  return (
    <div className="space-y-2.5 py-2">
      {[92, 100, 96, 88, 72].map((width, i) => (
        <div key={i} className="shimmer h-4" style={{ width: `${width}%` }} />
      ))}
    </div>
  );
}

function OfflineState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
      <CircleOff className="w-6 h-6 text-text-dim" />
      <p className="text-xs font-mono text-text-muted max-w-xs leading-relaxed">{label}</p>
    </div>
  );
}
