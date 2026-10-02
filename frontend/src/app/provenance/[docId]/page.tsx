"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, AlertCircle, X, GitBranch, Layers, Network, Zap, Search } from "lucide-react";
import { toPng } from "html-to-image";
import { api } from "@/lib/api";
import type { GraphNode, GraphEdge } from "@/types";
import ProvenanceGraph from "@/components/provenance/ProvenanceGraph";
import NodeDetailPanel from "@/components/provenance/NodeDetailPanel";
import { NODE_TYPE_COLORS } from "@/lib/colors";
import PrismMark from "@/components/brand/PrismMark";
import { tokens, alpha } from "@/lib/tokens";

const TYPE_ORDER = ["document", "chapter", "section", "clause", "entity", "causal"] as const;

export default function ProvenancePage({
  params,
}: {
  params: { docId: string };
}) {
  const { docId } = params;
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState(true);
  // Filter toolbar state
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [causalOnly, setCausalOnly] = useState(false);
  const [nodeSearch, setNodeSearch] = useState("");

  const toggleType = (type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  useEffect(() => {
    api
      .getGraph(docId)
      .then((data) => {
        setGraphNodes(data.nodes);
        setGraphEdges(data.edges);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [docId]);

  const handleExport = async () => {
    const container = document.getElementById("provenance-container");
    if (!container) return;
    try {
      const dataUrl = await toPng(container, { backgroundColor: tokens.bg.base });
      const link = document.createElement("a");
      link.download = `prism-provenance-${docId.slice(0, 8)}.png`;
      link.href = dataUrl;
      link.click();
    } catch (e) {
      console.error("Export failed:", e);
    }
  };

  const typeCounts: Record<string, number> = {};
  graphNodes.forEach((n) => { typeCounts[n.type] = (typeCounts[n.type] || 0) + 1; });

  return (
    <div className="h-screen flex flex-col overflow-hidden app-shell bg-bg-base">
      <div className="gradient-orb-1" style={{ opacity: 0.32 }} />
      <div className="gradient-orb-3" style={{ opacity: 0.2 }} />
      {/* Navbar */}
      <nav className="content-layer flex-shrink-0 flex items-center justify-between px-4 py-2.5 z-10 bg-bg-deep/90 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-3">
          <Link
            href={`/analyze/${docId}`}
            className="flex items-center gap-1.5 text-xs font-mono transition-colors text-text-muted hover:text-text-primary"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Analysis
          </Link>
          <div className="w-px h-4 bg-border" />
          <div className="flex items-center gap-2">
            <PrismMark size={24} />
            <span className="font-display font-semibold text-sm text-text-primary">Provenance Explorer</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2.5">
            {Object.entries(typeCounts).map(([type, count]) => (
              <div key={type} className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted">
                <div className="w-2 h-2 rounded-full" style={{ background: NODE_TYPE_COLORS[type] || tokens.accent.primary }} />
                <span>{type} ({count})</span>
              </div>
            ))}
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors border border-border text-text-muted hover:text-text-primary bg-bg-surface/70"
          >
            <Download className="w-3.5 h-3.5" />
            Export PNG
          </button>
        </div>
      </nav>

      {/* Filter toolbar */}
      {!loading && !error && graphNodes.length > 0 && (
        <div className="content-layer flex-shrink-0 flex flex-wrap items-center gap-2 px-4 py-2 z-10 bg-bg-deep/80 backdrop-blur-md border-b border-border">
          <span className="text-[9px] font-mono uppercase tracking-widest text-text-dim">
            Filter
          </span>
          {TYPE_ORDER.filter((type) => typeCounts[type]).map((type) => {
            const isDocument = type === "document";
            const active = isDocument || !hiddenTypes.has(type);
            const color = NODE_TYPE_COLORS[type] ?? tokens.accent.primary;
            return (
              <button
                key={type}
                onClick={isDocument ? undefined : () => toggleType(type)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono transition-colors"
                style={{
                  background: active ? alpha(color, 0.12) : "transparent",
                  border: `1px solid ${active ? alpha(color, 0.45) : tokens.border.DEFAULT}`,
                  color: active ? color : tokens.text.dim,
                  cursor: isDocument ? "default" : "pointer",
                }}
                title={isDocument ? "Document root is always visible" : `Toggle ${type} nodes`}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: active ? color : tokens.text.dim }}
                />
                {type}
                <span className="opacity-60">{typeCounts[type]}</span>
              </button>
            );
          })}
          <div className="w-px h-4 bg-border" />
          <button
            onClick={() => setCausalOnly((v) => !v)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono transition-colors"
            style={{
              background: causalOnly ? alpha(tokens.node.causal, 0.15) : "transparent",
              border: `1px solid ${causalOnly ? alpha(tokens.node.causal, 0.5) : tokens.border.DEFAULT}`,
              color: causalOnly ? tokens.node.causal : tokens.text.muted,
            }}
            title="Show only causal chains: causal nodes, their clauses, and ancestors"
          >
            <Zap className="w-3 h-3" />
            Causal only
          </button>
          <div className="relative ml-auto">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted" />
            <input
              value={nodeSearch}
              onChange={(e) => setNodeSearch(e.target.value)}
              placeholder="Search nodes…"
              className="w-48 pl-7 pr-7 py-1.5 rounded-lg text-xs font-mono placeholder:text-text-muted outline-none transition-colors bg-bg-surface/80 border border-border focus:border-accent-primary/40 text-text-primary"
            />
            {nodeSearch && (
              <button
                onClick={() => setNodeSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                aria-label="Clear node search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Graph */}
      <div id="provenance-container" className="content-layer flex-1 relative overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-bg-base">
            <div className="text-center text-text-muted">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3 text-accent-primary" />
              <p className="text-sm font-mono">Loading provenance graph…</p>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-bg-base">
            <div className="rounded-2xl p-8 max-w-sm text-center bg-bg-surface border border-border">
              <AlertCircle className="w-8 h-8 mx-auto mb-3 text-status-error" />
              <p className="text-sm mb-2 text-text-secondary">Failed to load graph</p>
              <p className="text-xs mb-4 text-text-muted">{error}</p>
              <Link href={`/analyze/${docId}`} className="text-xs text-accent-primary">
                ← Back to analysis
              </Link>
            </div>
          </div>
        )}

        {!loading && !error && graphNodes.length > 0 && (
          <ProvenanceGraph
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            onNodeSelect={setSelectedNode}
            hiddenTypes={hiddenTypes}
            causalOnly={causalOnly}
            nodeSearch={nodeSearch}
          />
        )}

        <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} docId={docId} />

        {/* Intro banner — dismissible */}
        {showIntro && !loading && !error && graphNodes.length > 0 && (
          <div
            className="absolute top-4 left-1/2 z-30 rounded-2xl p-5 max-w-lg w-full bg-bg-deep/95 border border-border"
            style={{
              transform: "translateX(-50%)",
              boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
            }}
          >
            <button
              onClick={() => setShowIntro(false)}
              className="absolute top-3 right-3 p-1 rounded-lg text-text-dim hover:text-text-primary"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-accent-primary/10 border border-accent-primary/30">
                <Network className="w-5 h-5 text-accent-primary" />
              </div>
              <div className="flex-1 min-w-0 pr-4">
                <p className="font-display font-bold text-sm mb-1 text-text-primary">
                  Knowledge Provenance Graph
                </p>
                <p className="text-xs leading-relaxed mb-3 text-text-secondary">
                  This graph traces every legal relationship extracted from the document.
                  Each row represents a level of abstraction — from the document root down
                  to individual causal rules.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { icon: Layers,     color: tokens.accent.primary,  label: "Document → Chapter → Section", desc: "Structural hierarchy" },
                    { icon: GitBranch,  color: tokens.text.secondary,  label: "Section → Clause",              desc: "Text segments" },
                    { icon: Network,    color: tokens.status.success,  label: "Clause → Entity",                desc: "Named legal concepts" },
                    { icon: Zap,        color: tokens.status.warning,  label: "Clause → Causal",                desc: "IF-THEN rule patterns" },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-start gap-2 p-2 rounded-xl bg-bg-surface/70 border border-border"
                    >
                      <item.icon className="w-3 h-3 mt-0.5 flex-shrink-0" style={{ color: item.color }} />
                      <div>
                        <p className="text-[9px] font-semibold" style={{ color: item.color }}>{item.label}</p>
                        <p className="text-[9px] font-mono text-text-dim">{item.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] font-mono mt-3 text-text-muted">
                  Click any node to see what it is, why it matters, and how it connects to the rest of the document.
                </p>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && (
          <div className="absolute bottom-4 right-4 rounded-xl px-4 py-3 text-xs font-mono space-y-1 bg-bg-surface/90 border border-border">
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-1.5 h-1.5 rounded-full bg-accent-primary" />
              <span>{graphNodes.length} nodes</span>
            </div>
            <div className="flex items-center gap-2 text-text-muted">
              <div className="w-1.5 h-1.5 rounded-full bg-status-warning" />
              <span>{graphEdges.length} edges</span>
            </div>
            <div className="pt-1 text-[9px] uppercase tracking-wider text-text-dim border-t border-border">
              Click node · reasoning panel opens
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
