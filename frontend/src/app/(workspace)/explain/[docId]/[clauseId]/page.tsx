"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, CircleOff, FlaskConical, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useExplanation } from "@/hooks/useExplanation";
import LIMEHeatmap from "@/components/explain/LIMEHeatmap";
import TokenBarChart from "@/components/explain/TokenBarChart";
import AttentionCard from "@/components/explain/AttentionCard";
import LLMExtractionCard from "@/components/explain/LLMExtractionCard";
import DeepReasoningCard from "@/components/explain/DeepReasoningCard";
import RuleVsLLMTable from "@/components/explain/RuleVsLLMTable";
import DocContextBar from "@/components/shell/DocContextBar";
import { Breadcrumbs } from "@/components/shell/PageHeader";
import { Callout } from "@/components/ui/kit";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { cn } from "@/lib/utils";
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
  const filename = useDocumentStore((st) => (st.docId === docId ? st.filename : null));

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { clause: found } = await api.getClause(docId, clauseId);
        if (cancelled) return;
        setClause(found);
      } catch (error) {
        if (!cancelled)
          setClauseError(
            error instanceof Error && /not found/i.test(error.message)
              ? "This clause is not in the document."
              : error instanceof Error
                ? error.message
                : "Failed to load clause"
          );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId, clauseId]);

  const section = clause?.section_hierarchy?.length
    ? `§${clause.section_hierarchy.join(".")}`
    : `clause ${clauseId.split("_").pop()}`;

  return (
    <div>
      <DocContextBar docId={docId} filename={filename} view="explain">
        <div role="group" aria-label="Explanation mode" className="flex overflow-hidden rounded-[4px] border border-border-light">
          {(["proxy", "llm"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={cn(
                "px-3 py-1.5 text-[13px] transition-colors",
                mode === m ? "bg-contrast text-on-contrast" : "text-text-muted hover:text-text-primary"
              )}
              title={
                m === "proxy"
                  ? "Explains the rule-based classifier: about a second"
                  : "Every LIME sample is classified by the configured language model: a minute or more"
              }
            >
              {m === "proxy" ? "Rule-based (fast)" : "Language model"}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={rerun}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Rerun
        </button>
      </DocContextBar>

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Breadcrumbs
          className="mb-6"
          items={[
            { label: "Workspace", href: `/analyze/${docId}` },
            { label: section },
            { label: "Explanation" },
          ]}
        />
        <div className="kicker mb-3">Explanation</div>
        <h1 className="max-w-3xl font-serif text-headline text-text-primary">Why this reading of {section}?</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
          LIME rewrites the clause hundreds of ways and watches the classifier respond: highlighted words push the clause
          toward a condition → consequence reading or away from it.
          {mode === "proxy" && " This mode explains the rule-based classifier, not the language model."}
        </p>
        <Callout tone="warn" className="mt-6 max-w-3xl" title="Read these as commentary, not proof">
          In the research evaluation, the spans models cite as evidence were no more faithful than random spans of the same
          length, and attention weights are not explanations. Use these views to probe a reading, not to certify it.
        </Callout>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
          {/* Left: LIME heatmap */}
          <section className="space-y-4">
            <div className="glass-card p-6 min-h-[280px]">
              <div className="flex items-center justify-between mb-4">
                <span className="kicker !text-micro">Token attribution</span>
                {state.status === "complete" && !state.explanation.not_applicable && (
                  <span className="text-micro font-mono text-text-dim flex items-center gap-2">
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

              {(state.status === "loading" || (state.status === "complete" && !clause && !clauseError)) && <HeatmapSkeleton />}
              {state.status === "running" && (
                <div className="flex flex-col items-center justify-center py-14 gap-4">
                  <Loader2 className="w-6 h-6 text-accent-primary animate-spin" />
                  <p className="text-xs font-mono text-text-muted">
                    Classifying perturbation {state.done} of {state.total} with the language model…
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
                <OfflineState label="Explanations are unavailable: the analysis server could not be reached." />
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
                <span className="kicker !text-micro block mb-4">Most influential tokens</span>
                <TokenBarChart topTokens={state.explanation.top_tokens} />
              </div>
            )}

            {clause && clause.clause_type !== "table" && (
              <AttentionCard docId={docId} clauseId={clauseId} clauseText={clause.text} />
            )}
          </section>

          {/* Right: LLM extraction breakdown */}
          <section className="space-y-4">
            {clauseError && <OfflineState label={clauseError} />}
            {!clause && !clauseError && (
              <div className="glass-card space-y-3 p-6" aria-busy="true" aria-label="Loading the clause">
                <HeatmapSkeleton />
              </div>
            )}
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
                <p className="text-sm text-text-secondary">No model extraction for this clause yet.</p>
                <p className="text-[13px] text-text-muted">
                  Extraction runs first on the highest-impact clauses. To include this one, open the workspace&apos;s LLM tab and
                  choose &ldquo;Every clause&rdquo;.
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
                    <p className="text-[14px] text-text-primary">Try this clause in the policy sandbox</p>
                    <p className="text-[12px] text-text-dim">An illustrative simulation, pre-filtered to this rule</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-dim ml-auto group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </>
            )}
          </section>
        </div>
      </div>
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
