"use client";
import { alpha, tokens } from "@/lib/tokens";
import ExpandableText from "@/components/ui/ExpandableText";
import type { Clause } from "@/types";

/**
 * Side-by-side comparison: what the Phase 1 rule engine found vs what
 * Phi-3.5-mini extracted. A real causal/not-causal disagreement is
 * highlighted; mere presence/absence of a field is not treated as one.
 */
export default function RuleVsLLMTable({ clause }: { clause: Clause }) {
  if (clause.clause_type === "table") {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-text-secondary">Tabular data — not analyzed as a prose clause.</p>
        <p className="text-[10px] text-text-dim font-mono mt-2">
          Causal extraction and token attribution apply to prose clauses only.
        </p>
      </div>
    );
  }

  const rule = clause.llm_extraction;
  const patterns = clause.causal_patterns;

  // Distinguish the three LLM outcomes so a clause that was never sent to the
  // model isn't mislabeled as a failure.
  let llmCausal: string;
  if (rule == null) llmCausal = "not run";
  else if (rule.is_causal == null) llmCausal = "failed to parse";
  else if (rule.is_causal) llmCausal = "causal";
  else llmCausal = "not causal";

  // A genuine disagreement: both extractors reached a definite verdict and
  // they conflict on whether the clause is causal.
  const causalDisagree =
    rule?.is_causal != null && (patterns.length > 0) !== rule.is_causal;

  const rows = [
    {
      dimension: "Causal structure",
      ruleBased: patterns.length > 0 ? `${patterns.length} pattern(s): ${patterns.map((p) => p.pattern_type).join(", ")}` : "none detected",
      llm: llmCausal,
      disagree: causalDisagree,
      expandable: false,
    },
    {
      dimension: "Condition",
      ruleBased: patterns[0]?.condition_span || "—",
      llm: rule?.condition || "—",
      disagree: false,
      expandable: true,
    },
    {
      dimension: "Consequence / action",
      ruleBased: patterns[0]?.action_span || "—",
      llm: rule?.consequence || rule?.action || "—",
      disagree: false,
      expandable: true,
    },
    {
      dimension: "Confidence",
      ruleBased: patterns[0] ? `${Math.round(patterns[0].confidence * 100)}% (pattern specificity)` : "—",
      llm: rule && rule.is_causal != null ? `${Math.round(rule.confidence * 100)}% (model self-report)` : "—",
      disagree: false,
      expandable: false,
    },
  ];

  return (
    <div className="glass-card overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-2.5 kicker !text-[9px]">Dimension</th>
            <th className="text-left px-4 py-2.5 kicker !text-[9px]">Rule-based · Phase 1</th>
            <th className="text-left px-4 py-2.5 kicker !text-[9px]">Phi-3.5-mini · Phase 2</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.dimension}
              className="border-b border-border last:border-0"
              style={row.disagree ? { background: alpha(tokens.status.warning, 0.06) } : undefined}
            >
              <td className="px-4 py-3 font-mono text-[10px] text-text-muted whitespace-nowrap align-top">
                {row.dimension}
                {row.disagree && (
                  <span className="block mt-1 text-[9px]" style={{ color: tokens.status.warning }}>
                    ▲ disagreement
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-text-secondary leading-relaxed align-top">
                {row.expandable ? <ExpandableText text={row.ruleBased} max={140} /> : row.ruleBased}
              </td>
              <td className="px-4 py-3 text-text-secondary leading-relaxed align-top">
                {row.expandable ? <ExpandableText text={row.llm} max={140} /> : row.llm}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
