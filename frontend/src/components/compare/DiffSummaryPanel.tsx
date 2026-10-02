"use client";
import { useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Info, Sparkles, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { tokens, alpha, riskStyle } from "@/lib/tokens";
import type { CompareResult, EntityLabel, RiskTier } from "@/types";

const RISK_TIERS: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const HIGHLIGHT_LABELS: EntityLabel[] = ["OBLIGATION", "PENALTY"];

function DiffStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      className="rounded-xl px-4 py-3 text-center border"
      style={{ background: alpha(color, 0.08), borderColor: alpha(color, 0.25) }}
    >
      <p className="font-display text-2xl leading-none mb-1" style={{ color }}>
        {value}
      </p>
      <p className="text-[9px] font-mono uppercase tracking-widest text-text-muted">{label}</p>
    </div>
  );
}

/** Headline numbers of the comparison: clause diff counts, new obligations and
 *  penalties introduced in B, risk-tier deltas, and freshly extracted causal
 *  rules. */
export default function DiffSummaryPanel({ result }: { result: CompareResult }) {
  const cd = result.clause_diff;

  // New OBLIGATION / PENALTY entities appearing in B — prefer the backend's
  // dedicated `new_entities` payload, fall back to the entity delta.
  const newHighlights = useMemo(() => {
    if (result.new_entities && result.new_entities.length > 0) {
      return result.new_entities
        .filter((e) => HIGHLIGHT_LABELS.includes(e.label))
        .map((e) => ({ label: e.label, text: e.text }));
    }
    return HIGHLIGHT_LABELS.flatMap((label) =>
      (result.entity_delta[label]?.only_in_b ?? []).map((text) => ({ label, text }))
    );
  }, [result]);

  const newRules = result.new_causal_rules ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 space-y-5"
    >
      {/* Clause diff stat row */}
      {cd ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <DiffStat label="Matched" value={cd.matched} color={tokens.accent.primary} />
          <DiffStat label="Modified" value={cd.modified.length} color={tokens.diff.modified} />
          <DiffStat label="Added in B" value={cd.added.length} color={tokens.diff.added} />
          <DiffStat label="Removed" value={cd.removed.length} color={tokens.diff.removed} />
        </div>
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-bg-elevated/60 border border-border">
          <Info className="w-4 h-4 flex-shrink-0 text-text-muted" />
          <p className="text-xs font-mono text-text-muted">
            Clause-level diff unavailable — re-run analysis on both documents to enable it.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Risk delta chips */}
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-text-muted mb-2.5">
            Risk delta · A → B
          </p>
          <div className="flex flex-wrap gap-2">
            {RISK_TIERS.map((tier) => {
              const delta = result.risk_comparison.delta[tier];
              const { base, text } = riskStyle(tier);
              const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
              return (
                <span
                  key={tier}
                  className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1.5 rounded-lg border"
                  style={{
                    color: text,
                    background: alpha(base, 0.1),
                    borderColor: alpha(base, 0.3),
                  }}
                >
                  {tier}
                  <span className="text-text-dim">
                    {result.risk_comparison.a[tier]}→{result.risk_comparison.b[tier]}
                  </span>
                  <DeltaIcon className="w-3 h-3" />
                  <span className="font-bold">{delta > 0 ? `+${delta}` : delta}</span>
                </span>
              );
            })}
          </div>
        </div>

        {/* New obligations / penalties in B */}
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-text-muted mb-2.5">
            New obligations &amp; penalties in B
          </p>
          {newHighlights.length === 0 ? (
            <p className="text-[11px] font-mono text-text-dim">
              No new OBLIGATION or PENALTY entities introduced.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
              {newHighlights.map((h, i) => (
                <Badge key={`${h.text}-${i}`} entity={h.label} title={h.text}>
                  {h.text.length > 42 ? `${h.text.slice(0, 42)}…` : h.text}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* New causal rules */}
      {newRules.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <Sparkles className="w-3.5 h-3.5 text-accent-primary" />
            <p className="text-[10px] font-mono uppercase tracking-widest text-text-muted">
              New causal rules in B ({newRules.length})
            </p>
          </div>
          <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
            {newRules.map((rule, i) => (
              <div
                key={`${rule.clause_id}-${i}`}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-bg-elevated/50 border border-border text-[11px]"
              >
                <span className="text-text-secondary truncate flex-1 min-w-0">
                  {rule.condition ?? "—"}
                </span>
                <ArrowRight className="w-3 h-3 flex-shrink-0 text-accent-primary" />
                <span className="text-text-secondary truncate flex-1 min-w-0">
                  {rule.consequence ?? rule.action ?? "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
