"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Download, Search, X, Zap } from "lucide-react";
import { toPng } from "html-to-image";
import { api } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/types";
import ProvenanceGraph from "@/components/provenance/ProvenanceGraph";
import NodeDetailPanel from "@/components/provenance/NodeDetailPanel";
import DocContextBar from "@/components/shell/DocContextBar";
import { ErrorState, Skeleton, inputClass } from "@/components/ui/kit";
import { NODE_TYPE_COLORS } from "@/lib/colors";
import { cssHex, tokens } from "@/lib/tokens";
import { cn } from "@/lib/utils";

// the 3D view loads only when asked for (three.js stays out of the page's bundle)
const ProvenanceStrata = dynamic(() => import("@/components/three/ProvenanceStrata"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 animate-pulse bg-bg-surface/40" aria-label="Loading the 3D view" />,
});

const TYPE_ORDER = ["document", "chapter", "section", "clause", "entity", "causal"] as const;
const TYPE_LABEL: Record<string, string> = {
  document: "document",
  chapter: "chapters",
  section: "sections",
  clause: "clauses",
  entity: "entities",
  causal: "rules",
};

export default function ProvenancePage({ params }: { params: { docId: string } }) {
  const { docId } = params;
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [filename, setFilename] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState(true);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [causalOnly, setCausalOnly] = useState(false);
  const [nodeSearch, setNodeSearch] = useState("");
  const [view, setView] = useState<"tree" | "strata">("tree");
  const [webgl, setWebgl] = useState(false);
  useEffect(() => {
    try {
      setWebgl(!!document.createElement("canvas").getContext("webgl2"));
    } catch {
      setWebgl(false);
    }
  }, []);

  useEffect(() => {
    api
      .getGraph(docId)
      .then((data) => {
        setGraphNodes(data.nodes);
        setGraphEdges(data.edges);
        setFilename(data.nodes.find((n) => n.type === "document")?.label ?? null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [docId]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    graphNodes.forEach((n) => (c[n.type] = (c[n.type] || 0) + 1));
    return c;
  }, [graphNodes]);

  const toggleType = (type: string) =>
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });

  const exportPng = async () => {
    const el = document.getElementById("provenance-canvas");
    if (!el) return;
    const dataUrl = await toPng(el, { backgroundColor: cssHex("bg-base") || tokens.ink[900] });
    const a = document.createElement("a");
    a.download = `prism-provenance-${docId.slice(0, 12)}.png`;
    a.href = dataUrl;
    a.click();
  };

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col overflow-hidden">
      <DocContextBar docId={docId} filename={filename} view="provenance">
        {webgl && (
          <div role="group" aria-label="Graph view" className="flex overflow-hidden rounded-[4px] border border-border-light">
            {(["tree", "strata"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={cn("px-3 py-1.5 text-[13px] transition-colors", view === v ? "bg-contrast text-on-contrast" : "text-text-muted hover:text-text-primary")}
              >
                {v === "tree" ? "Tree" : "Strata 3D"}
              </button>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={exportPng}
          disabled={loading || !!error || view === "strata"}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary disabled:opacity-40"
        >
          <Download className="h-3.5 w-3.5" /> PNG
        </button>
      </DocContextBar>

      {!loading && !error && graphNodes.length > 0 && (
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border px-4 py-2 sm:px-6">
          <span className="mr-1 text-[12px] text-text-dim">Show</span>
          {TYPE_ORDER.filter((t) => typeCounts[t] && t !== "document").map((type) => {
            const on = !hiddenTypes.has(type);
            return (
              <button
                key={type}
                type="button"
                aria-pressed={on}
                onClick={() => toggleType(type)}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12.5px] transition-colors",
                  on ? "border-border-light text-text-primary" : "border-border text-text-dim line-through"
                )}
              >
                <span className="h-2 w-2 rounded-full" style={{ background: NODE_TYPE_COLORS[type] }} aria-hidden />
                {TYPE_LABEL[type]}
                <span className="font-mono text-[12px] text-text-dim">{typeCounts[type].toLocaleString("en-IN")}</span>
              </button>
            );
          })}
          <span className="mx-1 h-4 w-px bg-border" aria-hidden />
          <button
            type="button"
            aria-pressed={causalOnly}
            onClick={() => setCausalOnly((v) => !v)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12.5px] transition-colors",
              causalOnly ? "border-signal/50 bg-signal/10 text-text-primary" : "border-border text-text-muted hover:text-text-primary"
            )}
            title="Only clauses that contain a condition → consequence rule, and their ancestors"
          >
            <Zap className="h-3.5 w-3.5" /> Rules only
          </button>
          <div className="relative ml-auto w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-dim" aria-hidden />
            <input
              value={nodeSearch}
              onChange={(e) => setNodeSearch(e.target.value)}
              placeholder="Find a clause or entity"
              aria-label="Find a node"
              className={cn(inputClass, "h-8 py-1 pl-8 pr-8 text-[13px]")}
            />
            {nodeSearch && (
              <button
                type="button"
                onClick={() => setNodeSearch("")}
                aria-label="Clear search"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      <div id="provenance-canvas" className="relative min-h-0 flex-1 overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex flex-col gap-3 p-10" aria-label="Loading graph">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <ErrorState title="The graph could not load" message={error} onRetry={() => window.location.reload()} />
          </div>
        )}
        {!loading && !error && graphNodes.length > 0 && view === "strata" && (
          <ProvenanceStrata
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            hiddenTypes={hiddenTypes}
            selectedId={selectedNode?.id ?? null}
            onNodeSelect={setSelectedNode}
          />
        )}
        {!loading && !error && graphNodes.length > 0 && view === "tree" && (
          <ProvenanceGraph
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            onNodeSelect={setSelectedNode}
            hiddenTypes={hiddenTypes}
            causalOnly={causalOnly}
            nodeSearch={nodeSearch}
            selectedId={selectedNode?.id ?? null}
          />
        )}

        <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} docId={docId} />

        {showIntro && view === "tree" && !loading && !error && graphNodes.length > 0 && (
          <div className="absolute left-4 top-4 z-raised max-w-sm rounded-[6px] border border-border-light bg-bg-surface/95 p-4 shadow-lift backdrop-blur-md">
            <button
              type="button"
              onClick={() => setShowIntro(false)}
              aria-label="Dismiss"
              className="absolute right-2.5 top-2.5 text-text-dim hover:text-text-primary"
            >
              <X className="h-4 w-4" />
            </button>
            <p className="pr-6 font-serif text-[20px] leading-tight text-text-primary">Every finding, back to its words</p>
            <p className="mt-2 text-[13px] leading-relaxed text-text-secondary">
              Read left to right: the document, its chapters, their clauses, and what was found in each clause. Click a node
              to open it and see why it was extracted; branches with many children open thirty at a time.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
