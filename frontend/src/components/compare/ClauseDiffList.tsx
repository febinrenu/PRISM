"use client";
import { useMemo } from "react";
import { diffWords } from "diff";
import { FilePlus2, FileMinus2, FileDiff } from "lucide-react";
import { tokens, alpha } from "@/lib/tokens";
import type { Clause } from "@/types";

export type DiffKind = "added" | "removed" | "modified";

export interface DiffRow {
  id: string;
  kind: DiffKind;
  clauseA: Clause | null;
  clauseB: Clause | null;
  similarity?: number;
}

const KIND_META: Record<DiffKind, { color: string; label: string; Icon: typeof FileDiff }> = {
  modified: { color: tokens.diff.modified, label: "Modified", Icon: FileDiff },
  added: { color: tokens.diff.added, label: "Added in B", Icon: FilePlus2 },
  removed: { color: tokens.diff.removed, label: "Removed", Icon: FileMinus2 },
};

const PREVIEW_CHARS = 140;

function preview(text: string): string {
  return text.length > PREVIEW_CHARS ? `${text.slice(0, PREVIEW_CHARS).trimEnd()}…` : text;
}

/** Word-level diff of clause A vs clause B text — deletions struck through in
 *  the removed tint, insertions in the added (blue) tint. Clamped to a preview
 *  unless the row is selected. */
function WordDiff({ a, b, expanded }: { a: string; b: string; expanded: boolean }) {
  const parts = useMemo(() => diffWords(a, b), [a, b]);
  return (
    <p
      className={`text-[11px] leading-relaxed ${expanded ? "" : "line-clamp-3"}`}
      style={{ wordBreak: "break-word" }}
    >
      {parts.map((part, i) =>
        part.removed ? (
          <del
            key={i}
            className="line-through"
            style={{
              color: tokens.diff.removed,
              background: alpha(tokens.diff.removed, 0.12),
              borderRadius: 2,
            }}
          >
            {part.value}
          </del>
        ) : part.added ? (
          <span
            key={i}
            style={{
              color: tokens.diff.added,
              background: alpha(tokens.diff.added, 0.14),
              borderRadius: 2,
            }}
          >
            {part.value}
          </span>
        ) : (
          <span key={i} className="text-text-secondary">
            {part.value}
          </span>
        )
      )}
    </p>
  );
}

function DiffRowItem({
  row,
  selected,
  onSelect,
}: {
  row: DiffRow;
  selected: boolean;
  onSelect: (row: DiffRow) => void;
}) {
  const meta = KIND_META[row.kind];
  const page = row.clauseB?.page ?? row.clauseA?.page;
  const sourceClause = row.kind === "added" ? row.clauseB : row.clauseA;

  return (
    <button
      onClick={() => onSelect(row)}
      className="w-full text-left rounded-xl px-3.5 py-3 transition-colors border"
      style={{
        background: alpha(meta.color, selected ? 0.14 : 0.05),
        borderColor: alpha(meta.color, selected ? 0.55 : 0.18),
      }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <meta.Icon className="w-3 h-3 flex-shrink-0" style={{ color: meta.color }} />
        <span
          className="text-[9px] font-mono uppercase tracking-widest"
          style={{ color: meta.color }}
        >
          {meta.label}
        </span>
        {row.kind === "modified" && row.similarity != null && (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded-full border"
            style={{
              color: meta.color,
              borderColor: alpha(meta.color, 0.4),
              background: alpha(meta.color, 0.1),
            }}
          >
            {Math.round(row.similarity * 100)}% similar
          </span>
        )}
        <span className="ml-auto text-[9px] font-mono text-text-dim">
          {page != null ? `p.${page}` : ""}
        </span>
      </div>

      {row.kind === "modified" && row.clauseA && row.clauseB ? (
        <WordDiff a={row.clauseA.text} b={row.clauseB.text} expanded={selected} />
      ) : sourceClause ? (
        <p className="text-[11px] leading-relaxed text-text-secondary">
          {selected ? sourceClause.text : preview(sourceClause.text)}
        </p>
      ) : (
        <p className="text-[11px] font-mono text-text-dim">clause text unavailable</p>
      )}
    </button>
  );
}

/** Scrollable center column of the diff arena — every non-matched clause,
 *  grouped by change type. Clicking a row selects it and pages both PDF panes
 *  to the clause. */
export default function ClauseDiffList({
  rows,
  selectedRowId,
  onSelect,
}: {
  rows: DiffRow[];
  selectedRowId: string | null;
  onSelect: (row: DiffRow) => void;
}) {
  const counts = useMemo(() => {
    const c = { modified: 0, added: 0, removed: 0 };
    rows.forEach((r) => c[r.kind]++);
    return c;
  }, [rows]);

  return (
    <div className="glass-card flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-xs font-display font-medium text-text-primary">Clause changes</span>
        <div className="flex items-center gap-2">
          {(Object.keys(KIND_META) as DiffKind[]).map((kind) => (
            <span
              key={kind}
              className="text-[9px] font-mono"
              style={{ color: KIND_META[kind].color }}
            >
              {counts[kind]} {kind}
            </span>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {rows.length === 0 ? (
          <p className="text-[11px] font-mono text-text-muted text-center py-10 leading-relaxed">
            No clause-level differences detected —
            <br />
            the documents match clause for clause.
          </p>
        ) : (
          rows.map((row) => (
            <DiffRowItem
              key={row.id}
              row={row}
              selected={row.id === selectedRowId}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </div>
  );
}
