"use client";
import { Bot, Quote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import ConfidenceGauge from "./ConfidenceGauge";
import { tokens, alpha } from "@/lib/tokens";
import type { LLMCausalRule } from "@/types";

const FIELD_STYLES = [
  { key: "condition", label: "Condition", color: tokens.status.info },
  { key: "action", label: "Action / Obligation", color: tokens.status.success },
  { key: "consequence", label: "Consequence / Penalty", color: tokens.status.error },
] as const;

/** Structured Phi-3.5-mini extraction rendered as an editorial card. */
export default function LLMExtractionCard({ rule }: { rule: LLMCausalRule }) {
  if (rule.is_causal == null) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-status-error font-mono">LLM output could not be parsed</p>
        {rule.parse_error && (
          <p className="text-[10px] text-text-dim font-mono mt-2 break-all">{rule.parse_error}</p>
        )}
      </div>
    );
  }

  return (
    <div className="glass-card p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <Bot className="w-4 h-4 text-accent-primary" />
          <div>
            <p className="text-sm font-display text-text-primary">
              {rule.is_causal ? "Causal rule extracted" : "No causal rule found"}
            </p>
            <p className="text-[10px] font-mono text-text-dim mt-0.5">
              {rule.model} · {rule.extraction_time_ms}ms
            </p>
          </div>
        </div>
        <ConfidenceGauge value={rule.confidence} label="LLM confidence" size={110} />
      </div>

      {rule.is_causal && (
        <div className="space-y-3">
          {FIELD_STYLES.map(({ key, label, color }) => {
            const value = rule[key];
            if (!value) return null;
            return (
              <div
                key={key}
                className="rounded-r border-l-2 pl-3 py-2"
                style={{ borderColor: color, background: alpha(color, 0.06) }}
              >
                <p className="text-[9px] font-mono uppercase tracking-[0.18em] mb-1" style={{ color }}>
                  {label}
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">{value}</p>
              </div>
            );
          })}

          {rule.actors.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="kicker !text-[9px] mr-1">Actors</span>
              {rule.actors.map((actor) => (
                <Badge key={actor} entity="ACTOR">{actor}</Badge>
              ))}
            </div>
          )}
          {rule.thresholds.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="kicker !text-[9px] mr-1">Thresholds</span>
              {rule.thresholds.map((threshold) => (
                <Badge key={threshold} entity="THRESHOLD">{threshold}</Badge>
              ))}
            </div>
          )}
        </div>
      )}

      {rule.reasoning && (
        <blockquote className="relative border-t border-border pt-4">
          <Quote className="absolute -top-0 right-0 w-4 h-4 text-text-dim/50 mt-4" />
          <p className="font-display italic text-sm text-text-secondary leading-relaxed pr-8">
            “{rule.reasoning}”
          </p>
          <footer className="text-[10px] font-mono text-text-dim mt-2">— the model’s own reasoning</footer>
        </blockquote>
      )}
    </div>
  );
}
