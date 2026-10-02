"use client";
import Link from "next/link";
import { useMemo } from "react";
import { Bot, CheckCheck, CircleSlash, Cpu, ExternalLink, Play, TriangleAlert } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { useLLMExtraction } from "@/hooks/useLLMExtraction";
import ExpandableText from "@/components/ui/ExpandableText";
import { alpha, tokens } from "@/lib/tokens";
import type { ExtractionMethod } from "@/types";

const METHOD_STYLE: Record<ExtractionMethod, { label: string; color: string; icon: typeof CheckCheck }> = {
  both: { label: "Agreement", color: tokens.status.success, icon: CheckCheck },
  llm: { label: "LLM only", color: tokens.status.info, icon: Bot },
  rule_based: { label: "Rules only", color: tokens.accent.primary, icon: Cpu },
  conflict: { label: "Conflict", color: tokens.status.warning, icon: TriangleAlert },
  failed: { label: "Parse failed", color: tokens.status.error, icon: CircleSlash },
};

/**
 * Phase 2 — side-by-side comparison of rule-based causal detection (Phase 1)
 * vs Phi-3.5-mini extraction (Phase 2), per clause.
 */
export default function LLMCompareTab() {
  const { docId, clauses, llmStage, llmProcessed, llmTotal, llmSummary, setSelectedClauseId } =
    useDocumentStore();
  const { start } = useLLMExtraction(docId);

  const extracted = useMemo(
    () => clauses.filter((c) => c.llm_extraction != null),
    [clauses]
  );

  if (llmStage === "idle" && extracted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
        <Bot className="w-10 h-10 text-text-dim" />
        <div>
          <p className="font-display text-lg text-text-primary">LLM extraction not run yet</p>
          <p className="text-xs text-text-muted mt-2 max-w-sm leading-relaxed">
            Phi-3.5-mini reads the highest-impact clauses and extracts structured causal
            rules — condition, action, consequence, actors, and thresholds — locally via Ollama.
          </p>
        </div>
        <button
          onClick={() => start("auto")}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-mono font-semibold uppercase tracking-wider bg-accent-primary/10 border border-accent-primary/40 text-accent-primary hover:bg-accent-primary/20 transition-colors"
        >
          <Play className="w-3.5 h-3.5" /> Run LLM Extraction
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Status bar */}
      <div className="glass-card p-4 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-accent-primary" />
          <span className="text-xs font-mono text-text-secondary">phi3.5 via Ollama</span>
        </div>
        {llmStage === "running" && (
          <div className="flex items-center gap-2 flex-1 min-w-[160px]">
            <div className="flex-1 h-1 rounded-full bg-bg-elevated overflow-hidden">
              <div
                className="h-full bg-accent-primary transition-all duration-500"
                style={{ width: llmTotal ? `${(llmProcessed / llmTotal) * 100}%` : "0%" }}
              />
            </div>
            <span className="text-[10px] font-mono text-text-muted whitespace-nowrap">
              {llmProcessed}/{llmTotal}
            </span>
          </div>
        )}
        {llmStage === "error" && (
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-status-error">
            <CircleSlash className="w-3.5 h-3.5" /> Extraction failed — is Ollama running?
          </span>
        )}
        {llmSummary && (
          <div className="flex items-center gap-3 text-[10px] font-mono text-text-muted ml-auto">
            <span style={{ color: tokens.status.success }}>◼ both {llmSummary.agreement.both}</span>
            <span style={{ color: tokens.status.info }}>◼ llm {llmSummary.agreement.llm_only}</span>
            <span style={{ color: tokens.accent.primary }}>◼ rules {llmSummary.agreement.rule_only}</span>
            <span style={{ color: tokens.status.warning }}>◼ conflict {llmSummary.agreement.conflict}</span>
          </div>
        )}
      </div>

      {/* Per-clause comparison */}
      <div className="space-y-3">
        {extracted.map((clause) => {
          const method = (clause.extraction_method ?? "rule_based") as ExtractionMethod;
          const style = METHOD_STYLE[method];
          const Icon = style.icon;
          const rule = clause.llm_extraction!;
          return (
            <div key={clause.clause_id} className="glass-card glass-card-hover p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <button
                  onClick={() => setSelectedClauseId(clause.clause_id)}
                  className="text-[10px] font-mono text-text-muted hover:text-accent-primary transition-colors"
                >
                  {clause.section_hierarchy.length > 0
                    ? `§${clause.section_hierarchy.join(".")}`
                    : clause.clause_id.slice(-6)}{" "}
                  · p.{clause.page}
                </button>
                <span
                  className="entity-pill border"
                  style={{
                    color: style.color,
                    borderColor: alpha(style.color, 0.4),
                    background: alpha(style.color, 0.12),
                  }}
                >
                  <Icon className="w-3 h-3" /> {style.label}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="space-y-1.5">
                  <p className="kicker !text-[9px]">Rule-based (Phase 1)</p>
                  {clause.causal_patterns.length > 0 ? (
                    clause.causal_patterns.slice(0, 2).map((p, i) => (
                      <p key={i} className="text-text-secondary leading-relaxed">
                        <span className="text-text-dim font-mono">[{p.pattern_type}]</span>{" "}
                        <ExpandableText text={p.condition_span} max={110} />
                      </p>
                    ))
                  ) : (
                    <p className="text-text-dim italic">No pattern detected</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <p className="kicker !text-[9px]">Phi-3.5-mini (Phase 2)</p>
                  {rule.is_causal ? (
                    <>
                      {rule.condition && (
                        <p className="text-text-secondary leading-relaxed">
                          <span className="font-mono" style={{ color: tokens.status.info }}>IF</span>{" "}
                          <ExpandableText text={rule.condition} max={110} />
                        </p>
                      )}
                      {(rule.consequence || rule.action) && (
                        <p className="text-text-secondary leading-relaxed">
                          <span className="font-mono" style={{ color: tokens.status.warning }}>THEN</span>{" "}
                          <ExpandableText text={rule.consequence || rule.action || ""} max={110} />
                        </p>
                      )}
                    </>
                  ) : rule.is_causal === false ? (
                    <p className="text-text-dim italic">LLM: not causal ({Math.round(rule.confidence * 100)}%)</p>
                  ) : (
                    <p className="text-status-error italic">Extraction failed to parse</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
                <span className="text-[10px] font-mono text-text-dim">
                  confidence {Math.round(rule.confidence * 100)}% · {rule.extraction_time_ms}ms
                </span>
                <Link
                  href={`/explain/${docId}/${clause.clause_id}`}
                  className="ml-auto flex items-center gap-1 text-[10px] font-mono text-accent-primary hover:text-accent-bright transition-colors"
                >
                  Explain this <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
