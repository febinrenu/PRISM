"use client";
import { useEffect, useRef, useMemo, useState } from "react";
import * as d3 from "d3";
import { X, Sparkles, Info, GitBranch, Layers, Lasso } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";

// ── Per-entity-cluster explanations ──────────────────────────────────────────
const CLUSTER_REASON: Record<string, string> = {
  OBLIGATION:
    "This clause clusters with obligation-heavy provisions. UMAP detected that its semantic fingerprint — duty-imposing language like 'shall', 'must', 'required' — is similar to surrounding sections that impose legal duties.",
  PENALTY:
    "This clause lands in the penalty cluster. Its language around fines, imprisonment, and punishable consequences shares semantic space with other enforcement and sanction provisions.",
  RIGHT:
    "This clause clusters with rights-granting sections. UMAP placed it near provisions that confer entitlements, exemptions, or legal protections to identified parties.",
  THRESHOLD:
    "This clause clusters with threshold-defining provisions. Its numeric limits, monetary values, and qualifying conditions align semantically with other boundary-setting clauses.",
  ACTOR:
    "This clause clusters with actor-definition sections. It shares semantic space with provisions naming authorities, offices, or parties responsible for enforcement.",
  BENEFICIARY:
    "This clause clusters with beneficiary provisions. UMAP placed it near sections dealing with concessions, exemptions, or protections granted to specific categories of persons.",
  NONE: "This clause has no dominant entity type. Its position reflects overall semantic similarity to its neighbours — likely a definitional, transitional, or introductory provision.",
};

const ENTITY_MEANING: Record<string, string> = {
  OBLIGATION:  "A legal duty — requires the subject to act or refrain",
  PENALTY:     "A punishable consequence — fine, imprisonment, or liability",
  RIGHT:       "An entitlement or protection granted to a party",
  THRESHOLD:   "A numeric limit, monetary value, or qualifying condition",
  ACTOR:       "An authority, office, or responsible party",
  BENEFICIARY: "A party receiving an exemption, benefit, or protection",
};

const CONF_DOT: Record<string, { bg: string; label: string }> = {
  HIGH:   { bg: tokens.status.success, label: "High confidence" },
  MEDIUM: { bg: tokens.status.warning, label: "Medium confidence" },
  LOW:    { bg: tokens.text.muted,     label: "Low confidence" },
};

const RISK_COLOR: Record<string, string> = {
  CRITICAL: tokens.risk.CRITICAL.text,
  HIGH:     tokens.risk.HIGH.text,
  MEDIUM:   tokens.risk.MEDIUM.text,
  LOW:      tokens.risk.LOW.text,
};

// ── Nearest-clause computation ────────────────────────────────────────────────
function getNearestClauses(
  selected: { id: string; x: number; y: number },
  all: { id: string; x: number; y: number }[],
  k = 3
) {
  return all
    .filter((p) => p.id !== selected.id)
    .map((p) => ({
      ...p,
      dist: Math.hypot(p.x - selected.x, p.y - selected.y),
    }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, k);
}

// ── Point-in-polygon (ray casting) ────────────────────────────────────────────
function pointInPolygon(x: number, y: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

// ── Main component ────────────────────────────────────────────────────────────
export default function EmbeddingTab() {
  const svgRef = useRef<SVGSVGElement>(null);
  const { clauses, stage, setSelectedClauseId, selectedClauseIds, setSelectedClauseIds } =
    useDocumentStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showUmapInfo, setShowUmapInfo] = useState(false);
  const [lassoMode, setLassoMode] = useState(false);

  const points = useMemo(
    () =>
      clauses
        .filter((c) => c.embedding_2d)
        .map((c) => ({
          id: c.clause_id,
          x: c.embedding_2d![0],
          y: c.embedding_2d![1],
          page: c.page,
          text: c.text,
          dominantLabel: c.entities[0]?.label ?? "NONE",
        })),
    [clauses]
  );

  const selectedPoint = useMemo(
    () => points.find((p) => p.id === selectedId) ?? null,
    [points, selectedId]
  );

  const selectedClause = useMemo(
    () => (selectedId ? clauses.find((c) => c.clause_id === selectedId) ?? null : null),
    [clauses, selectedId]
  );

  const nearestPoints = useMemo(
    () => (selectedPoint ? getNearestClauses(selectedPoint, points) : []),
    [selectedPoint, points]
  );

  const nearestClauses = useMemo(
    () =>
      nearestPoints
        .map((np) => ({
          clause: clauses.find((c) => c.clause_id === np.id)!,
          dist: np.dist,
        }))
        .filter((n) => n.clause),
    [nearestPoints, clauses]
  );

  // ── D3 scatter ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!svgRef.current || points.length < 2) return;
    const svgEl = svgRef.current;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    const W = svgEl.clientWidth || 320;
    const H = svgEl.clientHeight || 260;
    const pad = 28;

    const xExt = d3.extent(points, (d) => d.x) as [number, number];
    const yExt = d3.extent(points, (d) => d.y) as [number, number];
    const xScale = d3.scaleLinear().domain(xExt).range([pad, W - pad]);
    const yScale = d3.scaleLinear().domain(yExt).range([H - pad, pad]);

    const g = svg.append("g");
    // d3 persists the zoom transform on the DOM node — re-apply after redraw.
    g.attr("transform", d3.zoomTransform(svgEl).toString());
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.4, 10])
      .on("zoom", (ev) => g.attr("transform", ev.transform));
    if (lassoMode) {
      // Lasso owns the pointer — detach pan/zoom listeners entirely.
      svg.on(".zoom", null);
    } else {
      svg.call(zoom);
    }

    // Subtle grid
    g.append("g")
      .selectAll("line")
      .data(xScale.ticks(5))
      .join("line")
      .attr("x1", (d) => xScale(d))
      .attr("x2", (d) => xScale(d))
      .attr("y1", pad)
      .attr("y2", H - pad)
      .attr("stroke", tokens.border.DEFAULT)
      .attr("stroke-width", 1);
    g.append("g")
      .selectAll("line")
      .data(yScale.ticks(5))
      .join("line")
      .attr("y1", (d) => yScale(d))
      .attr("y2", (d) => yScale(d))
      .attr("x1", pad)
      .attr("x2", W - pad)
      .attr("stroke", tokens.border.DEFAULT)
      .attr("stroke-width", 1);

    // Glow rings for nearest neighbours
    if (selectedId && nearestPoints.length) {
      g.selectAll(".ring")
        .data(nearestPoints)
        .join("circle")
        .attr("class", "ring")
        .attr("cx", (d) => xScale(d.x))
        .attr("cy", (d) => yScale(d.y))
        .attr("r", 12)
        .attr("fill", "none")
        .attr("stroke", alpha(tokens.accent.primary, 0.25))
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "3 2");
    }

    // Tooltip
    const tooltip = d3
      .select("body")
      .append("div")
      .style("position", "fixed")
      .style("pointer-events", "none")
      .style("background", tokens.bg.base)
      .style("border", `1px solid ${tokens.border.DEFAULT}`)
      .style("border-radius", "10px")
      .style("padding", "8px 12px")
      .style("font-size", "11px")
      .style("color", tokens.text.secondary)
      .style("max-width", "220px")
      .style("line-height", "1.5")
      .style("z-index", "9999")
      .style("opacity", "0")
      .style("font-family", "JetBrains Mono, monospace");

    // Dots
    g.selectAll("circle.dot")
      .data(points)
      .join("circle")
      .attr("class", "dot")
      .attr("cx", (d) => xScale(d.x))
      .attr("cy", (d) => yScale(d.y))
      .attr("r", (d) => (d.id === selectedId ? 7 : 5))
      .attr("fill", (d) => (ENTITY_COLORS as any)[d.dominantLabel]?.hex ?? tokens.accent.primary)
      .attr("fill-opacity", (d) => (d.id === selectedId ? 1 : selectedId ? 0.35 : 0.75))
      .attr("stroke", (d) =>
        d.id === selectedId
          ? tokens.text.primary
          : selectedClauseIds.has(d.id)
          ? tokens.accent.bright
          : (ENTITY_COLORS as any)[d.dominantLabel]?.hex ?? tokens.accent.primary
      )
      .attr("stroke-opacity", (d) => (d.id === selectedId ? 0.9 : selectedClauseIds.has(d.id) ? 1 : 0.3))
      .attr("stroke-width", (d) => (d.id === selectedId ? 2 : selectedClauseIds.has(d.id) ? 2 : 1))
      .style("cursor", "pointer")
      .on("mouseenter", function (event, d) {
        if (d.id !== selectedId) d3.select(this).attr("r", 7).attr("fill-opacity", 1);
        tooltip
          .style("opacity", "1")
          .style("left", `${event.clientX + 14}px`)
          .style("top", `${event.clientY - 12}px`)
          .html(
            `<span style="color:${tokens.text.primary};font-weight:600">p.${d.page}</span>  ` +
            `<span style="color:${tokens.accent.primary};font-size:9px">${d.dominantLabel}</span><br/>` +
            `<span style="color:${tokens.text.secondary}">${d.text.slice(0, 90)}…</span>`
          );
      })
      .on("mousemove", function (event) {
        tooltip
          .style("left", `${event.clientX + 14}px`)
          .style("top", `${event.clientY - 12}px`);
      })
      .on("mouseleave", function (_, d) {
        if (d.id !== selectedId) d3.select(this).attr("r", 5).attr("fill-opacity", selectedId ? 0.35 : 0.75);
        tooltip.style("opacity", "0");
      })
      .on("click", (_ev, d) => {
        setSelectedId((prev) => (prev === d.id ? null : d.id));
        setSelectedClauseId(d.id);
      });

    // Lasso overlay — freehand polygon selection, tested in screen space
    if (lassoMode) {
      const lassoPath = svg
        .append("path")
        .attr("fill", alpha(tokens.accent.primary, 0.08))
        .attr("stroke", tokens.accent.primary)
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "5 3")
        .attr("pointer-events", "none");

      const overlay = svg
        .append("rect")
        .attr("width", W)
        .attr("height", H)
        .attr("fill", "transparent")
        .style("cursor", "crosshair")
        .style("touch-action", "none");

      let lassoPts: [number, number][] = [];
      let drawing = false;

      overlay
        .on("pointerdown", (ev: PointerEvent) => {
          drawing = true;
          lassoPts = [d3.pointer(ev, svgEl) as [number, number]];
          (ev.target as Element).setPointerCapture?.(ev.pointerId);
        })
        .on("pointermove", (ev: PointerEvent) => {
          if (!drawing) return;
          lassoPts.push(d3.pointer(ev, svgEl) as [number, number]);
          lassoPath.attr("d", `M${lassoPts.map((p) => p.join(",")).join("L")}Z`);
        })
        .on("pointerup pointercancel", () => {
          if (!drawing) return;
          drawing = false;
          lassoPath.attr("d", null);
          if (lassoPts.length < 3) {
            // Click with no drag → clear selection
            setSelectedClauseIds(new Set<string>());
            lassoPts = [];
            return;
          }
          // Points are drawn inside the zoomed <g>; apply the active zoom
          // transform so the hit-test happens in the same (screen) space as
          // the lasso polygon.
          const t = d3.zoomTransform(svgEl);
          const ids = points
            .filter((d) => {
              const [sx, sy] = t.apply([xScale(d.x), yScale(d.y)]);
              return pointInPolygon(sx, sy, lassoPts);
            })
            .map((d) => d.id);
          setSelectedClauseIds(new Set(ids));
          lassoPts = [];
        });
    }

    return () => {
      tooltip.remove();
    };
  }, [points, selectedId, nearestPoints, setSelectedClauseId, lassoMode, selectedClauseIds, setSelectedClauseIds]);

  if (points.length < 2) {
    // Once analysis is complete but no 2D coords arrived, UMAP was skipped or
    // failed (non-fatal) — say so instead of spinning "Waiting…" forever.
    const done = stage === "complete";
    const message =
      points.length === 1
        ? "Need at least 2 clauses for UMAP"
        : done
        ? "2D projection unavailable for this document."
        : "Waiting for embeddings…";
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-2 text-text-muted">
        <Layers className="w-7 h-7 opacity-30" />
        <p className="font-mono text-sm">{message}</p>
        {done && points.length === 0 && (
          <p className="font-mono text-[10px] text-text-dim max-w-xs text-center leading-relaxed">
            The semantic scatter needs the UMAP projection, which didn’t complete for this
            document. All other analysis is available.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-xs font-mono uppercase tracking-widest text-text-muted">
            UMAP 2D Semantic Map
          </p>
          <button
            onClick={() => setShowUmapInfo((v) => !v)}
            className={showUmapInfo ? "text-accent-primary" : "text-text-dim"}
          >
            <Info className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          {selectedClauseIds.size > 0 && (
            <button
              onClick={() => setSelectedClauseIds(new Set<string>())}
              className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full transition-colors"
              style={{
                background: alpha(tokens.accent.primary, 0.1),
                border: `1px solid ${alpha(tokens.accent.primary, 0.35)}`,
                color: tokens.accent.bright,
              }}
              title="Clear lasso selection"
            >
              {selectedClauseIds.size} selected · Clear
            </button>
          )}
          <button
            onClick={() => setLassoMode((v) => !v)}
            className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full transition-colors"
            style={{
              background: lassoMode ? alpha(tokens.accent.primary, 0.15) : "transparent",
              border: `1px solid ${lassoMode ? alpha(tokens.accent.primary, 0.5) : tokens.border.DEFAULT}`,
              color: lassoMode ? tokens.accent.primary : tokens.text.muted,
            }}
            title={lassoMode ? "Lasso on — drag to select, click to clear" : "Enable lasso selection"}
          >
            <Lasso className="w-3 h-3" />
            Lasso
          </button>
          <p className="text-[10px] font-mono text-text-dim">
            {lassoMode
              ? `${points.length} clauses · drag to select`
              : `${points.length} clauses · scroll to zoom · click to explore`}
          </p>
        </div>
      </div>

      {/* UMAP explainer strip */}
      {showUmapInfo && (
        <div className="rounded-xl p-4 space-y-2 bg-accent-primary/5 border border-accent-primary/20">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-accent-primary" />
            <p className="text-xs font-semibold text-text-primary">
              What is UMAP?
            </p>
          </div>
          <p className="text-xs leading-relaxed text-text-secondary">
            UMAP (Uniform Manifold Approximation and Projection) compresses each
            clause&apos;s 384-dimensional semantic embedding into 2D. Clauses that are
            semantically similar — using similar legal language and concepts — appear
            closer together. Clusters of dots represent thematic groups: penalty
            clauses, rights provisions, obligation sections, etc.
          </p>
          <p className="text-xs text-text-muted">
            Colour = dominant entity type detected in that clause. Click any dot to
            see why it&apos;s positioned there, its full content, and its nearest semantic
            neighbours.
          </p>
        </div>
      )}

      {/* Main split: scatter + panel */}
      <div className="flex gap-3" style={{ alignItems: "flex-start" }}>
        {/* Scatter */}
        <div className="rounded-xl overflow-hidden flex-1 min-w-0 border border-border bg-bg-deep/80">
          <svg ref={svgRef} className="w-full" style={{ height: 280 }} />
        </div>

        {/* Detail panel */}
        {selectedClause && selectedPoint && (
          <div
            className="rounded-xl overflow-y-auto flex-shrink-0 space-y-4 bg-bg-deep/95 border border-border"
            style={{
              width: 260,
              maxHeight: 280,
              padding: "14px",
            }}
          >
            {/* Panel header */}
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[9px] font-mono uppercase tracking-widest text-text-muted">
                  Clause · Page {selectedClause.page}
                </p>
                <p className="text-[10px] font-mono mt-0.5 text-text-secondary">
                  {selectedClause.section_hierarchy?.slice(-1)[0] ?? "—"}
                </p>
              </div>
              <button
                onClick={() => setSelectedId(null)}
                className="flex-shrink-0 mt-0.5 text-text-dim hover:text-text-primary"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Full text */}
            <div>
              <p className="text-[9px] font-mono uppercase tracking-widest mb-1.5 text-text-dim">
                Full text
              </p>
              <p
                className="text-[11px] leading-relaxed text-text-secondary bg-bg-surface/80 border border-border"
                style={{
                  borderRadius: 8,
                  padding: "8px 10px",
                  maxHeight: 110,
                  overflowY: "auto",
                }}
              >
                {selectedClause.text}
              </p>
            </div>

            {/* Entities */}
            {selectedClause.entities.length > 0 && (
              <div>
                <p className="text-[9px] font-mono uppercase tracking-widest mb-1.5 text-text-dim">
                  Legal entities ({selectedClause.entities.length})
                </p>
                <div className="flex flex-wrap gap-1">
                  {selectedClause.entities.slice(0, 10).map((e, i) => {
                    const ec = (ENTITY_COLORS as any)[e.label];
                    const conf = (e as any).confidence ?? "MEDIUM";
                    const dot = CONF_DOT[conf];
                    return (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded"
                        style={{
                          background: ec?.bg ?? alpha(tokens.accent.primary, 0.12),
                          color: ec?.text ?? tokens.text.secondary,
                          border: `1px solid ${ec?.border ?? alpha(tokens.accent.primary, 0.3)}`,
                        }}
                        title={ENTITY_MEANING[e.label] + ` · ${conf} confidence`}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{ background: dot.bg }}
                        />
                        {e.text.slice(0, 18)}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Causal patterns */}
            {selectedClause.causal_patterns.length > 0 && (
              <div>
                <p className="text-[9px] font-mono uppercase tracking-widest mb-1.5 text-text-dim">
                  Causal patterns
                </p>
                <div className="space-y-1">
                  {selectedClause.causal_patterns.slice(0, 3).map((cp, i) => {
                    const tier = (cp as any).risk_tier ?? "LOW";
                    return (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-[9px] font-mono px-2 py-1 rounded bg-bg-surface/80 border border-border"
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{ background: RISK_COLOR[tier] ?? tokens.accent.primary }}
                        />
                        <span style={{ color: RISK_COLOR[tier] ?? tokens.accent.primary }}>
                          {tier}
                        </span>
                        <span className="text-text-muted">·</span>
                        <span className="text-text-secondary">
                          {cp.pattern_type.replace("_", " ")}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Why this position */}
            <div className="rounded-xl p-3 space-y-1.5 bg-accent-primary/5 border border-accent-primary/15">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-accent-primary" />
                <p className="text-[9px] font-mono uppercase tracking-widest text-accent-primary">
                  Why here?
                </p>
              </div>
              <p className="text-[10px] leading-relaxed text-text-secondary">
                {CLUSTER_REASON[selectedPoint.dominantLabel]}
              </p>
            </div>

            {/* Nearest semantic neighbours */}
            {nearestClauses.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <GitBranch className="w-3 h-3 text-text-dim" />
                  <p className="text-[9px] font-mono uppercase tracking-widest text-text-dim">
                    Nearest semantic clauses
                  </p>
                </div>
                <div className="space-y-1.5">
                  {nearestClauses.map(({ clause: nc, dist }) => (
                    <button
                      key={nc.clause_id}
                      onClick={() => {
                        setSelectedId(nc.clause_id);
                        setSelectedClauseId(nc.clause_id);
                      }}
                      className="w-full text-left rounded-lg p-2 transition-all bg-bg-surface/70 border border-border"
                    >
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-[9px] font-mono text-text-muted">
                          p.{nc.page}
                        </span>
                        <span className="text-[9px] font-mono text-text-dim">
                          dist {dist.toFixed(2)}
                        </span>
                      </div>
                      <p className="text-[10px] leading-snug text-text-secondary">
                        {nc.text.slice(0, 65)}…
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 items-center">
        {Object.entries(ENTITY_COLORS)
          .filter(([label]) => points.some((p) => p.dominantLabel === label))
          .map(([label, colors]: [string, any]) => (
            <div key={label} className="flex items-center gap-1.5">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: colors.hex }}
              />
              <span
                className="text-[10px] font-mono text-text-muted"
                title={ENTITY_MEANING[label]}
              >
                {label}
              </span>
            </div>
          ))}
        {!selectedId && (
          <span className="ml-auto text-[9px] font-mono text-text-dim">
            ↑ click any dot to explore
          </span>
        )}
      </div>
    </div>
  );
}
