"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  GitBranch,
  FileText,
  CheckCircle2,
  BarChart3,
  Zap,
  Network,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { useAnalysisSession } from "@/hooks/useAnalysisSession";
import { useLLMExtraction } from "@/hooks/useLLMExtraction";
import ProcessingOverlay from "@/components/workspace/ProcessingOverlay";
import ClauseFeed from "@/components/workspace/ClauseFeed";
import AnalyticsTabs from "@/components/workspace/analytics/AnalyticsTabs";
import PDFViewerPanel from "@/components/workspace/PDFViewerPanel";
import PrismMark from "@/components/brand/PrismMark";
import { tokens } from "@/lib/tokens";

export default function AnalyzePage({
  params,
}: {
  params: { docId: string };
}) {
  const { docId } = params;
  const { stage, filename, clauses, stats, llmStage, llmProcessed, llmTotal } = useDocumentStore();
  const [pdfOpen, setPdfOpen] = useState(true);

  useAnalysisSession(docId);
  // Hydrates cached Phi-3.5 extractions into clause cards; re-attaches to
  // a live extraction job if one is running server-side.
  useLLMExtraction(docId);

  const isComplete = stage === "complete";
  const isActive = stage !== "idle";
  const entityCount = stats?.total_entities ?? clauses.reduce((n, c) => n + c.entities.length, 0);
  const causalCount = stats?.causal_patterns_found ?? clauses.reduce((n, c) => n + c.causal_patterns.length, 0);

  return (
    <div className="h-screen flex flex-col overflow-hidden app-shell bg-bg-base">
      <ProcessingOverlay />
      <div className="gradient-orb-1" style={{ opacity: 0.36 }} />
      <div className="gradient-orb-2" style={{ opacity: 0.3 }} />
      <div className="noise-overlay" style={{ opacity: 0.05 }} />

      <nav className="content-layer flex-shrink-0 flex items-center justify-between px-5 py-3 z-10 bg-bg-deep/90 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs font-mono transition-all duration-200 group text-text-muted hover:text-text-primary"
          >
            <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" />
            Back
          </Link>

          <div className="w-px h-4 bg-border" />

          <div className="flex items-center gap-2.5">
            <PrismMark size={28} />
            <span className="font-display font-bold text-sm text-text-primary">
              PRISM
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-accent-primary border border-accent-primary/35 bg-accent-primary/10">
              Analysis
            </span>
          </div>

          {filename && (
            <>
              <div className="w-px h-4 bg-border" />
              <div className="flex items-center gap-1.5 max-w-[220px]">
                <FileText className="w-3 h-3 flex-shrink-0 text-text-muted" />
                <span className="text-[11px] font-mono truncate text-text-secondary">
                  {filename}
                </span>
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          <AnimatePresence>
            {isComplete && (
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-3"
              >
                <div className="flex items-center gap-1.5 text-[11px] font-mono text-status-success">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Complete
                </div>
                {stats?.domain && (
                  <span
                    className="text-[10px] font-mono px-2 py-1 rounded-lg bg-entity-actor/10 border border-entity-actor/25"
                    style={{ color: tokens.entity.ACTOR.text }}
                  >
                    {stats.domain}
                  </span>
                )}
                <Link
                  href={`/compare?a=${docId}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 bg-status-success/10 border border-status-success/25 text-status-success"
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  Compare
                </Link>
                <Link
                  href={`/provenance/${docId}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 bg-accent-primary/10 hover:bg-accent-primary/20 border border-accent-primary/35 text-accent-primary"
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  Knowledge Graph
                </Link>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </nav>

      <AnimatePresence>
        {isComplete && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="content-layer flex-shrink-0 flex items-center gap-0 overflow-hidden border-b border-border bg-bg-surface/70"
          >
            {[
              { icon: FileText, label: "Clauses", value: clauses.length, color: tokens.text.primary },
              { icon: Network, label: "Entities", value: entityCount, color: tokens.accent.primary },
              { icon: Zap, label: "Causal", value: causalCount, color: tokens.status.warning },
              { icon: BarChart3, label: "Pages", value: stats?.total_pages ?? "-", color: tokens.text.secondary },
              ...(stats?.causal_risk_counts?.CRITICAL
                ? [{ icon: Zap, label: "Critical", value: stats.causal_risk_counts.CRITICAL, color: tokens.status.error }]
                : []),
            ].map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.label} className="flex items-center gap-2 px-5 py-2.5 border-r border-border">
                  <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: s.color }} />
                  <span className="font-display font-bold text-base" style={{ color: s.color }}>
                    {s.value}
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
                    {s.label}
                  </span>
                </div>
              );
            })}
            <div className="ml-auto px-5 py-2.5 text-[10px] font-mono text-text-dim">
              {stats?.graph_nodes ?? 0} graph nodes · {stats?.graph_edges ?? 0} edges
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Phase 2 banner — live LLM extraction status */}
      <AnimatePresence>
        {llmStage === "running" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="content-layer flex-shrink-0 flex items-center gap-3 px-5 py-2 border-b border-border overflow-hidden"
            style={{ background: "rgba(158,185,204,0.06)" }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-status-info animate-pulse" />
            <span className="text-[11px] font-mono text-status-info">
              Phase 2 active — Phi-3.5-mini extracting causal rules ({llmProcessed}/{llmTotal || "…"})
            </span>
            <div className="flex-1 max-w-[240px] h-1 rounded-full bg-bg-elevated overflow-hidden">
              <div
                className="h-full bg-status-info transition-all duration-500"
                style={{ width: llmTotal ? `${(llmProcessed / llmTotal) * 100}%` : "4%" }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3-column workspace: PDF (collapsible) | clause feed | analytics */}
      <motion.div
        className="content-layer flex-1 flex overflow-hidden"
        initial={{ opacity: 0 }}
        animate={{ opacity: isActive ? 1 : 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
      >
        <div
          className="flex-shrink-0 flex flex-col overflow-hidden border-r border-border transition-[width] duration-300"
          style={{ width: pdfOpen ? "min(30vw, 460px)" : "44px" }}
        >
          {pdfOpen ? (
            <div className="flex flex-col h-full min-h-0">
              <div className="flex-1 min-h-0">
                <PDFViewerPanel docId={docId} />
              </div>
              <button
                onClick={() => setPdfOpen(false)}
                className="flex-shrink-0 flex items-center justify-center gap-1.5 py-1.5 border-t border-border text-[10px] font-mono text-text-dim hover:text-text-secondary transition-colors"
              >
                <PanelLeftClose className="w-3 h-3" /> Collapse
              </button>
            </div>
          ) : (
            <button
              onClick={() => setPdfOpen(true)}
              className="h-full w-full flex flex-col items-center justify-center gap-2 text-text-dim hover:text-accent-primary hover:bg-bg-elevated transition-colors"
              title="Open document viewer"
            >
              <PanelLeftOpen className="w-4 h-4" />
              <span
                className="text-[10px] font-mono uppercase tracking-widest"
                style={{ writingMode: "vertical-rl" }}
              >
                Document
              </span>
            </button>
          )}
        </div>
        <div className="flex-shrink-0 flex flex-col overflow-hidden border-r border-border w-[340px] xl:w-[400px]">
          <ClauseFeed />
        </div>
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <AnalyticsTabs />
        </div>
      </motion.div>
    </div>
  );
}
