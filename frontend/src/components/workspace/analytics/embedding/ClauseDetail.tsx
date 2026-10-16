"use client";

import Link from "next/link";
import { ArrowUpRight, GitBranch, X } from "lucide-react";
import { ENTITY_COLORS } from "@/lib/colors";
import { alpha, tokens } from "@/lib/tokens";
import type { Clause } from "@/types";
import { CONF_DOT, ENTITY_MEANING, RISK_COLOR, colorOf, type MapPoint } from "./model";

/**
 * The selected clause: its text, tags and patterns, what its neighbourhood
 * on the map has in common, and its nearest clauses.
 */
export default function ClauseDetail({
  docId,
  clause,
  point,
  neighbours,
  onPick,
  onClose,
}: {
  docId: string;
  clause: Clause;
  point: MapPoint;
  neighbours: { clause: Clause; dist: number; label: string }[];
  onPick: (id: string) => void;
  onClose: () => void;
}) {
  const same = neighbours.filter((n) => n.label === point.label).length;
  return (
    <aside className="flex max-h-full w-full flex-col gap-4 overflow-y-auto rounded-[8px] border border-border bg-bg-deep/95 p-4 lg:w-[280px] lg:shrink-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-micro uppercase tracking-widest text-text-muted">Clause · page {clause.page}</p>
          <p className="mt-0.5 font-mono text-micro text-text-secondary">{clause.section_hierarchy?.length ? `§${clause.section_hierarchy.join(".")}` : "—"}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="mt-0.5 text-text-dim hover:text-text-primary">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="max-h-32 overflow-y-auto rounded-[6px] border border-border bg-bg-surface/80 px-2.5 py-2 text-[13px] leading-relaxed text-text-secondary">
        {clause.text}
      </p>

      <div className="rounded-[6px] border border-border bg-bg-surface/60 p-3">
        <p className="font-mono text-micro uppercase tracking-widest text-text-dim">Its neighbourhood</p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">
          Position comes from the meaning of the whole clause: nearby dots use similar language.{" "}
          {point.label === "NONE" ? (
            <>This clause has no tagged entity.</>
          ) : (
            <>
              {same} of its {neighbours.length} nearest clauses also lead with{" "}
              <span style={{ color: colorOf(point.label) }}>{point.label.toLowerCase()}</span>.
            </>
          )}
        </p>
      </div>

      {clause.entities.length > 0 && (
        <div>
          <p className="mb-1.5 font-mono text-micro uppercase tracking-widest text-text-dim">Tagged entities ({clause.entities.length})</p>
          <div className="flex flex-wrap gap-1">
            {clause.entities.slice(0, 10).map((e, i) => {
              const ec = (ENTITY_COLORS as Record<string, { bg: string; text: string; border: string }>)[e.label];
              const conf = (e as { confidence?: string }).confidence ?? "MEDIUM";
              return (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-micro"
                  style={{ background: ec?.bg ?? alpha(tokens.accent.primary, 0.12), color: ec?.text ?? tokens.text.secondary, border: `1px solid ${ec?.border ?? tokens.border.DEFAULT}` }}
                  title={`${ENTITY_MEANING[e.label] ?? e.label} · ${conf.toLowerCase()} confidence`}
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: CONF_DOT[conf]?.bg }} aria-hidden />
                  {e.text.slice(0, 18)}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {clause.causal_patterns.length > 0 && (
        <div>
          <p className="mb-1.5 font-mono text-micro uppercase tracking-widest text-text-dim">Condition → consequence</p>
          <div className="space-y-1">
            {clause.causal_patterns.slice(0, 3).map((cp, i) => (
              <div key={i} className="flex items-center gap-1.5 rounded border border-border bg-bg-surface/80 px-2 py-1 font-mono text-micro">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: RISK_COLOR[cp.risk_tier] }} aria-hidden />
                <span style={{ color: RISK_COLOR[cp.risk_tier] }}>{cp.risk_tier.toLowerCase()}</span>
                <span className="text-text-muted">·</span>
                <span className="text-text-secondary">{cp.pattern_type.replace("_", " ").toLowerCase()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {neighbours.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5">
            <GitBranch className="h-3 w-3 text-text-dim" aria-hidden />
            <p className="font-mono text-micro uppercase tracking-widest text-text-dim">Nearest clauses</p>
          </div>
          <div className="space-y-1.5">
            {neighbours.map(({ clause: nc, dist, label }) => (
              <button
                key={nc.clause_id}
                type="button"
                onClick={() => onPick(nc.clause_id)}
                className="w-full rounded-[6px] border border-border bg-bg-surface/70 p-2 text-left transition-colors hover:border-border-light"
              >
                <div className="mb-0.5 flex items-center justify-between font-mono text-micro">
                  <span className="flex items-center gap-1.5 text-text-muted">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: colorOf(label) }} aria-hidden />
                    p.{nc.page}
                  </span>
                  <span className="text-text-dim">dist {dist.toFixed(2)}</span>
                </div>
                <p className="text-[12px] leading-snug text-text-secondary">{nc.text.slice(0, 70)}…</p>
              </button>
            ))}
          </div>
        </div>
      )}

      <Link
        href={`/explain/${docId}/${clause.clause_id}`}
        className="inline-flex items-center gap-1.5 text-[13px] text-text-primary underline decoration-border-light underline-offset-4 hover:decoration-signal"
      >
        Why this reading <ArrowUpRight className="h-3.5 w-3.5" />
      </Link>
    </aside>
  );
}
