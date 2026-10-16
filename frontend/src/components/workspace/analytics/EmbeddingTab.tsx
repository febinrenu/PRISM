"use client";

import { useMemo, useState } from "react";
import { Info, Lasso, Layers } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { ENTITY_COLORS } from "@/lib/colors";
import { cn } from "@/lib/utils";
import ClauseDetail from "./embedding/ClauseDetail";
import UmapCanvas from "./embedding/UmapCanvas";
import { ENTITY_MEANING, colorOf, nearest, toPoints } from "./embedding/model";

/**
 * The semantic map: every clause's sentence embedding projected to 2D with
 * UMAP, coloured by its first tagged entity. Pan, zoom, click a clause to see
 * its neighbourhood, or lasso a group to select it across the workspace.
 */
export default function EmbeddingTab() {
  const { docId, clauses, stage, setSelectedClauseId, selectedClauseIds, setSelectedClauseIds } = useDocumentStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [info, setInfo] = useState(false);
  const [lasso, setLasso] = useState(false);

  const points = useMemo(() => toPoints(clauses), [clauses]);
  const byId = useMemo(() => new Map(clauses.map((c) => [c.clause_id, c])), [clauses]);
  const point = useMemo(() => points.find((p) => p.id === selectedId) ?? null, [points, selectedId]);
  const near = useMemo(() => (point ? nearest(point, points) : []), [point, points]);
  const neighbourIds = useMemo(() => new Set(near.map((n) => n.id)), [near]);
  const labels = useMemo(() => Array.from(new Set(points.map((p) => p.label))), [points]);

  const select = (id: string | null) => {
    setSelectedId(id);
    if (id) setSelectedClauseId(id);
  };

  if (points.length < 2) {
    const done = stage === "complete";
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-2 text-text-muted">
        <Layers className="h-7 w-7 opacity-30" />
        <p className="font-mono text-sm">
          {points.length === 1 ? "The map needs at least two clauses." : done ? "No 2D projection for this document." : "Waiting for embeddings…"}
        </p>
        {done && points.length === 0 && (
          <p className="max-w-xs text-center font-mono text-micro leading-relaxed text-text-dim">
            The projection did not complete for this document. Every other analysis is available.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="font-mono text-xs uppercase tracking-widest text-text-muted">Semantic map</p>
          <button
            type="button"
            onClick={() => setInfo((v) => !v)}
            aria-expanded={info}
            aria-label="What is this map?"
            className={info ? "text-accent-primary" : "text-text-dim hover:text-text-primary"}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          {selectedClauseIds.size > 0 && (
            <button
              type="button"
              onClick={() => setSelectedClauseIds(new Set<string>())}
              className="rounded-full border border-accent-primary/35 bg-accent-primary/10 px-2 py-0.5 font-mono text-micro text-accent-bright"
            >
              {selectedClauseIds.size} selected · clear
            </button>
          )}
          <button
            type="button"
            onClick={() => setLasso((v) => !v)}
            aria-pressed={lasso}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-micro transition-colors",
              lasso ? "border-accent-primary/50 bg-accent-primary/15 text-accent-primary" : "border-border text-text-muted hover:text-text-primary"
            )}
            title={lasso ? "Lasso on: drag around clauses to select them" : "Select a group of clauses by drawing around them"}
          >
            <Lasso className="h-3 w-3" /> Lasso
          </button>
          <p className="hidden font-mono text-micro text-text-dim sm:block">
            {points.length.toLocaleString("en-IN")} clauses · {lasso ? "drag to select" : "scroll to zoom · click to explore"}
          </p>
        </div>
      </div>

      {info && (
        <div className="rounded-[8px] border border-accent-primary/20 bg-accent-primary/5 p-4 text-[13px] leading-relaxed text-text-secondary">
          Each clause&apos;s sentence embedding (384 dimensions, all-MiniLM-L6-v2) is projected to two with UMAP, so
          clauses that use similar language sit close together. Colour is the clause&apos;s first tagged entity, not a
          cluster the projection found. Distances are only meaningful locally.
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <div className="min-h-[300px] min-w-0 flex-1 overflow-hidden rounded-[8px] border border-border bg-bg-deep/80">
          <UmapCanvas
            points={points}
            selectedId={selectedId}
            neighbourIds={neighbourIds}
            selectedIds={selectedClauseIds}
            lasso={lasso}
            onSelect={select}
            onLasso={setSelectedClauseIds}
          />
        </div>
        {point && byId.get(point.id) && docId && (
          <ClauseDetail
            docId={docId}
            clause={byId.get(point.id)!}
            point={point}
            neighbours={near.filter((n) => byId.has(n.id)).map((n) => ({ clause: byId.get(n.id)!, dist: n.dist, label: n.label }))}
            onPick={select}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {Object.keys(ENTITY_COLORS)
          .concat("NONE")
          .filter((l) => labels.includes(l))
          .map((l) => (
            <div key={l} className="flex items-center gap-1.5" title={ENTITY_MEANING[l]}>
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: colorOf(l) }} aria-hidden />
              <span className="font-mono text-micro lowercase text-text-muted">{l === "NONE" ? "no entity" : l}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
