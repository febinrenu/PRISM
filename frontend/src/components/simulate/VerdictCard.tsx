"use client";
import { forwardRef } from "react";
import { motion } from "framer-motion";
import { Download, Loader2 } from "lucide-react";
import { alpha, tokens } from "@/lib/tokens";
import { formatRupees } from "./SimulationCharts";
import type { PolicyVerdict, SimulationStep } from "@/types";

const VERDICT_STYLE: Record<PolicyVerdict, { color: string; emoji: string; title: string }> = {
  progressive: { color: tokens.status.success, emoji: "🟢", title: "Progressive" },
  neutral: { color: tokens.status.warning, emoji: "🟡", title: "Neutral" },
  regressive: { color: tokens.status.error, emoji: "🔴", title: "Regressive" },
};

interface Props {
  verdict: PolicyVerdict;
  steps: SimulationStep[];
  nRules: number;
  rulesSource: "llm" | "rule_based";
  narrative?: string | null;
  effectiveRateLow?: number | null;
  effectiveRateHigh?: number | null;
  exporting: boolean;
  onExport: () => void;
}

/** Post-simulation verdict with the backend-generated, data-grounded narrative. */
const VerdictCard = forwardRef<HTMLDivElement, Props>(function VerdictCard(
  { verdict, steps, nRules, rulesSource, narrative, effectiveRateLow, effectiveRateHigh, exporting, onExport },
  ref
) {
  const style = VERDICT_STYLE[verdict];
  const first = steps[0];
  const last = steps[steps.length - 1];
  if (!first || !last) return null;

  // Effective-rate basis — the statutory-incidence signal the verdict derives from.
  // Prefer the backend-provided figures; fall back to the final step's per-type rate.
  const lowRate = effectiveRateLow ?? last.effective_rate_by_type?.low_income ?? null;
  const highRate = effectiveRateHigh ?? last.effective_rate_by_type?.high_income ?? null;

  // Fall back to a template paragraph only when the backend narrative is absent.
  const lowBurden = last.avg_burden_by_type.low_income;
  const giniDelta = last.gini_coefficient - first.gini_coefficient;
  const insight =
    narrative ??
    `The ${nRules} ${rulesSource === "llm" ? "LLM-extracted" : "rule-based"} policy rules produce ` +
      `an average burden of ${formatRupees(lowBurden)} on low-income households over ${steps.length} simulated months, ` +
      `with the relative-burden Gini coefficient moving from ${first.gini_coefficient.toFixed(2)} to ${last.gini_coefficient.toFixed(2)} ` +
      `(${giniDelta >= 0 ? "+" : ""}${giniDelta.toFixed(3)}) — ${
        verdict === "regressive"
          ? "indicating regressive policy impact concentrating cost on those least able to bear it."
          : verdict === "progressive"
          ? "indicating redistributive policy impact."
          : "indicating a broadly neutral distributional impact."
      }`;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-8"
      style={{ borderColor: alpha(style.color, 0.35) }}
    >
      <div className="flex flex-col md:flex-row md:items-center gap-6">
        <div className="flex-shrink-0">
          <p className="kicker !text-[9px] mb-2">Simulation verdict</p>
          <p className="font-display text-5xl leading-none" style={{ color: style.color }}>
            {style.emoji} {style.title}
          </p>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-secondary leading-relaxed">{insight}</p>
          {lowRate != null && highRate != null && (
            <p className="mt-3 text-[11px] font-mono text-text-muted">
              Effective-rate basis:{" "}
              <span style={{ color: tokens.agent.low_income }}>
                low-income {(lowRate * 100).toFixed(1)}%
              </span>{" "}
              vs{" "}
              <span style={{ color: tokens.agent.high_income }}>
                high-income {(highRate * 100).toFixed(1)}%
              </span>
            </p>
          )}
        </div>
        <button
          onClick={onExport}
          disabled={exporting}
          className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-lg border border-accent-primary/40 bg-accent-primary/10 text-accent-primary text-[11px] font-mono font-semibold uppercase tracking-wider hover:bg-accent-primary/20 transition-colors disabled:opacity-50"
        >
          {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          {exporting ? "Rendering…" : "Export impact report"}
        </button>
      </div>
    </motion.div>
  );
});

export default VerdictCard;
