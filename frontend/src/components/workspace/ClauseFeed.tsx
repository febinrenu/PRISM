"use client";
import { useRef, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Loader2, X, ListTree, ChevronRight } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import ClauseCard from "./ClauseCard";
import type { Clause } from "@/types";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";

const ALL_LABELS = ["OBLIGATION", "PENALTY", "RIGHT", "THRESHOLD", "ACTOR", "BENEFICIARY"] as const;
type EntityLabel = (typeof ALL_LABELS)[number];

const isSection = (h: string) => /^s\.\S/.test(h);

/** Outline of the statute from each clause's AST hierarchy:
 *  top level = chapter / schedule (or "Sections" when the Act has none),
 *  second level = section (or the schedule's part / paragraph). */
function buildOutline(clauses: Clause[]) {
  const tops = new Map<string, { scope: string[]; count: number; children: Map<string, { scope: string[]; count: number }> }>();
  for (const c of clauses) {
    const h = c.section_hierarchy ?? [];
    if (h.length === 0) continue;
    const hasTop = !isSection(h[0]);
    const top = hasTop ? h[0] : "Sections";
    const topScope = hasTop ? [h[0]] : [];
    const child = hasTop ? h[1] : h[0];
    if (!tops.has(top)) tops.set(top, { scope: topScope, count: 0, children: new Map() });
    const t = tops.get(top)!;
    t.count += 1;
    if (child) {
      const key = child;
      const scope = hasTop ? [h[0], child] : [child];
      const entry = t.children.get(key) ?? { scope, count: 0 };
      entry.count += 1;
      t.children.set(key, entry);
    }
  }
  return Array.from(tops.entries());
}

export default function ClauseFeed() {
  const {
    clauses, stage, totalClauses, processedCount,
    selectedClauseId, setSelectedClauseId,
    highlightedEntityKey, setHighlightedEntityKey,
    selectedClauseIds, setSelectedClauseIds,
  } = useDocumentStore();

  const [search, setSearch] = useState("");
  const [scope, setScope] = useState<string[] | null>(null);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const outline = useMemo(() => buildOutline(clauses), [clauses]);
  const [activeLabels, setActiveLabels] = useState<Set<EntityLabel>>(new Set());
  const feedRef = useRef<HTMLDivElement>(null);
  const isProcessing = stage === "ner" || stage === "parsing" || stage === "segmentation";

  useEffect(() => {
    if (isProcessing && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [clauses.length, isProcessing]);

  const toggleLabel = (label: EntityLabel) => {
    setActiveLabels((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const MAX_VISIBLE = isProcessing ? 80 : clauses.length;
  const visibleClauses = clauses.slice(0, MAX_VISIBLE);

  const filtered: Clause[] = visibleClauses.filter((c) => {
    if (selectedClauseIds.size > 0 && !selectedClauseIds.has(c.clause_id)) return false;
    if (scope && scope.length > 0 && !scope.every((s, i) => (c.section_hierarchy ?? [])[i] === s)) return false;
    if (search && !c.text.toLowerCase().includes(search.toLowerCase())) return false;
    if (highlightedEntityKey) {
      const [label, text] = highlightedEntityKey.split("::");
      const hasEntity = c.entities.some(
        (e) => e.label === label && e.text.toLowerCase() === text?.toLowerCase()
      );
      if (!hasEntity) return false;
    }
    if (activeLabels.size > 0) {
      const hasLabel = c.entities.some((e) => activeLabels.has(e.label as EntityLabel));
      if (!hasLabel) return false;
    }
    return true;
  });

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex-shrink-0 px-4 pt-4 pb-3 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-display font-semibold text-sm text-text-primary">Clauses</h3>
            <p className="text-[11px] font-mono mt-0.5 text-text-muted">
              {isProcessing
                ? `Processing ${processedCount} of ${totalClauses}…`
                : `${filtered.length} of ${clauses.length} clauses${clauses.length > MAX_VISIBLE ? ` (showing ${MAX_VISIBLE})` : ""}`}
            </p>
          </div>
          {isProcessing && (
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}>
              <Loader2 className="w-4 h-4 text-accent-primary" />
            </motion.div>
          )}
        </div>

        {/* UMAP lasso selection chip */}
        {selectedClauseIds.size > 0 && (
          <div className="mb-3">
            <span
              className="inline-flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full"
              style={{
                background: alpha(tokens.accent.primary, 0.1),
                border: `1px solid ${alpha(tokens.accent.primary, 0.35)}`,
                color: tokens.accent.bright,
              }}
            >
              {selectedClauseIds.size} selected from UMAP
              <button
                onClick={() => setSelectedClauseIds(new Set<string>())}
                className="transition-opacity hover:opacity-70"
                title="Clear UMAP selection"
                aria-label="Clear UMAP selection"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          </div>
        )}

        {/* Structure outline */}
        {outline.length > 0 && (
          <div className="mb-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOutlineOpen((o) => !o)}
                aria-expanded={outlineOpen}
                className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1 rounded-md border border-border text-text-secondary hover:text-text-primary hover:border-accent-primary/40 transition-colors"
              >
                <ListTree className="w-3.5 h-3.5" /> Structure
              </button>
              {scope && scope.length > 0 && (
                <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded-md bg-accent-primary/10 text-accent-bright min-w-0">
                  <span className="truncate">{scope.join(" › ")}</span>
                  <button onClick={() => setScope(null)} aria-label="Show all clauses" className="hover:opacity-70">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
            </div>
            {outlineOpen && (
              <nav aria-label="Statute structure" className="mt-2 max-h-64 overflow-y-auto rounded-md border border-border bg-bg-surface/60 py-1 text-[12px]">
                {outline.map(([top, t]) => (
                  <details key={top} open={outline.length === 1} className="group">
                    <summary className="flex items-center gap-1 px-2 py-1 cursor-pointer list-none hover:bg-bg-elevated">
                      <ChevronRight className="w-3 h-3 text-text-muted transition-transform group-open:rotate-90" />
                      <button
                        onClick={(e) => { e.preventDefault(); if (t.scope.length) setScope(t.scope); }}
                        className="flex-1 text-left truncate text-text-primary"
                      >
                        {top}
                      </button>
                      <span className="text-text-muted tabular-nums">{t.count}</span>
                    </summary>
                    <ul className="pl-6 pr-2">
                      {Array.from(t.children.entries()).map(([name, ch]) => (
                        <li key={name}>
                          <button
                            onClick={() => setScope(ch.scope)}
                            className={`w-full flex justify-between gap-2 py-0.5 text-left hover:text-text-primary ${
                              scope && scope.join("|") === ch.scope.join("|") ? "text-accent-bright" : "text-text-secondary"}`}
                          >
                            <span className="truncate font-mono">{name}</span>
                            <span className="text-text-muted tabular-nums">{ch.count}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}
              </nav>
            )}
          </div>
        )}

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search clauses…"
            className="w-full pl-8 pr-8 py-2 rounded-lg text-sm placeholder:text-text-muted outline-none transition-colors bg-bg-surface/80 border border-border focus:border-accent-primary/40 text-text-primary"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors text-text-muted"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Entity label filters */}
        <div className="flex flex-wrap gap-1.5">
          {ALL_LABELS.map((label) => {
            const colors = ENTITY_COLORS[label];
            const active = activeLabels.has(label);
            const count = clauses.reduce(
              (n, c) => n + c.entities.filter((e) => e.label === label).length, 0
            );
            if (count === 0) return null;
            return (
              <button
                key={label}
                onClick={() => toggleLabel(label)}
                className="entity-pill transition-all duration-150"
                style={{
                  background: active ? colors.bg : alpha(tokens.bg.elevated, 0.5),
                  color: active ? colors.text : tokens.text.muted,
                  borderColor: active ? colors.border : tokens.border.DEFAULT,
                }}
              >
                {label}
                <span className="ml-1 opacity-60">{count}</span>
              </button>
            );
          })}
          {(activeLabels.size > 0 || highlightedEntityKey) && (
            <button
              onClick={() => {
                setActiveLabels(new Set());
                setHighlightedEntityKey(null);
              }}
              className="entity-pill transition-colors bg-transparent text-text-muted border-border"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Clause list */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto px-4 py-3 space-y-2 min-h-0"
      >
        {clauses.length === 0 && !isProcessing && (
          <div className="flex flex-col items-center justify-center h-48 text-text-muted">
            <p className="font-mono text-sm">No clauses yet</p>
          </div>
        )}

        <AnimatePresence mode="popLayout">
          {filtered.map((clause) => (
            <ClauseCard
              key={clause.clause_id}
              clause={clause}
              isSelected={selectedClauseId === clause.clause_id}
              onSelect={() => setSelectedClauseId(
                selectedClauseId === clause.clause_id ? null : clause.clause_id
              )}
            />
          ))}
        </AnimatePresence>

        {/* Shimmer while processing */}
        {isProcessing && (
          <>
            {[1, 2].map((n) => (
              <div key={n} className="rounded-xl p-4 space-y-3 border border-border">
                <div className="shimmer h-3 rounded w-1/3" />
                <div className="shimmer h-3 rounded w-full" />
                <div className="shimmer h-3 rounded w-4/5" />
                <div className="flex gap-2 mt-2">
                  <div className="shimmer h-5 rounded-full w-20" />
                  <div className="shimmer h-5 rounded-full w-16" />
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
