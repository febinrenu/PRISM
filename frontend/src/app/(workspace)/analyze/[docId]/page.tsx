"use client";

import { useState } from "react";
import Link from "next/link";
import { Panel as RPanel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Network, RefreshCw } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { useAnalysisSession } from "@/hooks/useAnalysisSession";
import { useLLMExtraction } from "@/hooks/useLLMExtraction";
import ProcessingOverlay from "@/components/workspace/ProcessingOverlay";
import ClauseFeed from "@/components/workspace/ClauseFeed";
import AnalyticsTabs from "@/components/workspace/analytics/AnalyticsTabs";
import PDFViewerPanel from "@/components/workspace/PDFViewerPanel";
import DocContextBar from "@/components/shell/DocContextBar";
import { StatusTag } from "@/components/ui/kit";
import { cn } from "@/lib/utils";
import ReadingNotice from "@/components/workspace/ReadingNotice";
import DeleteDocumentButton from "@/components/workspace/DeleteDocumentButton";
import { useRouter } from "next/navigation";

function Handle() {
  return (
    <PanelResizeHandle className="group relative w-px bg-border outline-none data-[resize-handle-state=drag]:bg-signal data-[resize-handle-state=hover]:bg-border-glow">
      <span className="absolute inset-y-0 -left-1.5 -right-1.5" aria-hidden />
    </PanelResizeHandle>
  );
}

const MOBILE_TABS = [
  ["clauses", "Clauses"],
  ["analysis", "Analysis"],
  ["document", "Document"],
] as const;

export default function AnalyzePage({ params }: { params: { docId: string } }) {
  const { docId } = params;
  const { stage, filename, clauses, stats, llmStage, llmProcessed, llmTotal } = useDocumentStore();
  const [mobileTab, setMobileTab] = useState<(typeof MOBILE_TABS)[number][0]>("clauses");

  const router = useRouter();
  const [run, setRun] = useState(0);
  const [confirming, setConfirming] = useState(false);
  useAnalysisSession(docId, run);
  // the demo is the shared reference; the backend refuses to re-analyse it
  const canReanalyse = !docId.startsWith("demo_");
  // Hydrates cached model extractions into clause cards; re-attaches to a
  // live extraction job if one is running server-side.
  useLLMExtraction(docId);

  const isComplete = stage === "complete";
  const entityCount = stats?.total_entities ?? clauses.reduce((n, c) => n + c.entities.length, 0);
  const causalCount = stats?.causal_patterns_found ?? clauses.reduce((n, c) => n + c.causal_patterns.length, 0);
  const figures: [string, number | string][] = [
    ["clauses", clauses.length],
    ["entities", entityCount],
    ["condition → consequence", causalCount],
    ["pages", stats?.total_pages ?? "–"],
  ];
  const status = isComplete ? "complete" : stage === "idle" ? "pending" : stage === "error" ? "error" : "processing";

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col overflow-hidden">
      <ProcessingOverlay />
      <DocContextBar docId={docId} filename={filename} view="analyze" status={<StatusTag status={status} />}>
        {isComplete && (
          <dl className="hidden items-center gap-5 xl:flex">
            {figures.map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-1.5">
                <dd className="font-mono text-[13px] text-text-primary">{typeof v === "number" ? v.toLocaleString("en-IN") : v}</dd>
                <dt className="text-[12px] text-text-muted">{k}</dt>
              </div>
            ))}
            {stats?.domain && stats.domain !== "General Legislation" && (
              <div className="text-[12px] text-text-muted" title="A keyword guess, not a classification">
                reads as <span className="text-text-secondary">{stats.domain}</span>
              </div>
            )}
          </dl>
        )}
        {isComplete && (
          <Link
            href={`/provenance/${docId}`}
            className="hidden h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary md:inline-flex"
          >
            <Network className="h-3.5 w-3.5" /> Graph
          </Link>
        )}
        {(isComplete || stage === "error") && canReanalyse && (
          <div className="flex items-center gap-1.5">
            {confirming ? (
              <>
                <span className="hidden text-[12px] text-text-muted sm:inline">Replace these results?</span>
                <button
                  type="button"
                  onClick={() => {
                    setConfirming(false);
                    setRun((r) => r + 1);
                  }}
                  className="inline-flex h-8 items-center rounded-[4px] bg-signal px-3 text-[13px] font-medium text-ink hover:bg-signal-soft"
                >
                  Re-analyse
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="inline-flex h-8 items-center rounded-[4px] px-2 text-[13px] text-text-muted hover:text-text-primary"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                title="Run the whole pipeline again on this PDF"
                className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Re-analyse
              </button>
            )}
            {!confirming && (
              <DeleteDocumentButton docId={docId} name={filename ?? undefined} onDeleted={() => router.push("/start")} />
            )}
          </div>
        )}
      </DocContextBar>

      {isComplete && <ReadingNotice reading={stats?.reading} />}

      {llmStage === "running" && (
        <div role="status" className="flex shrink-0 items-center gap-3 border-b border-border bg-status-info/[0.06] px-4 py-2 sm:px-6">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-status-info" aria-hidden />
          <span className="text-[13px] text-status-info">
            A language model is reading clauses into rules ({llmProcessed} of {llmTotal || "…"})
          </span>
          <span className="h-1 max-w-[240px] flex-1 overflow-hidden rounded-full bg-ink-700">
            <span
              className="block h-full bg-status-info transition-[width] duration-500"
              style={{ width: llmTotal ? `${(llmProcessed / llmTotal) * 100}%` : "4%" }}
            />
          </span>
        </div>
      )}

      {/* Desktop: three resizable panes, sizes remembered. */}
      <div className="hidden min-h-0 flex-1 lg:flex">
        <PanelGroup direction="horizontal" autoSaveId="prism-analyze" className="min-h-0 flex-1">
          <RPanel defaultSize={28} minSize={12} collapsible collapsedSize={0} order={1} className="flex min-h-0 flex-col">
            <PDFViewerPanel docId={docId} />
          </RPanel>
          <Handle />
          <RPanel defaultSize={30} minSize={20} order={2} className="flex min-h-0 flex-col">
            <ClauseFeed />
          </RPanel>
          <Handle />
          <RPanel defaultSize={42} minSize={28} order={3} className="flex min-h-0 flex-col">
            <AnalyticsTabs />
          </RPanel>
        </PanelGroup>
      </div>

      {/* Narrow screens: one pane at a time. */}
      <div className="flex min-h-0 flex-1 flex-col lg:hidden">
        <div role="tablist" aria-label="Workspace panes" className="flex shrink-0 border-b border-border">
          {MOBILE_TABS.map(([id, label]) => (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={mobileTab === id}
              onClick={() => setMobileTab(id)}
              className={cn("relative flex-1 py-2.5 text-[14px]", mobileTab === id ? "text-text-primary" : "text-text-muted")}
            >
              {label}
              {mobileTab === id && <span aria-hidden className="absolute inset-x-6 bottom-0 h-[2px] bg-signal" />}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="flex min-h-0 flex-1 flex-col">
          {mobileTab === "clauses" && <ClauseFeed />}
          {mobileTab === "analysis" && <AnalyticsTabs />}
          {mobileTab === "document" && <PDFViewerPanel docId={docId} />}
        </div>
      </div>
    </div>
  );
}
