"use client";
import { useMemo, useState } from "react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { Zap, Lock, Cpu, ChevronDown, ChevronUp, ArrowRight, AlertTriangle, Filter } from "lucide-react";
import type { RiskTier } from "@/types";
import { tokens, alpha, riskStyle } from "@/lib/tokens";

// ─── Pattern config ───────────────────────────────────────────────────────────

const PATTERN_CONFIG: Record<string, {
  icon: string;
  label: string;
  bg: string;
  text: string;
  border: string;
  condLabel: string;
  actionLabel: string;
}> = {
  IF_THEN: {
    icon: "→",
    label: "IF → THEN",
    bg: alpha(tokens.accent.primary, 0.1),
    text: tokens.accent.bright,
    border: alpha(tokens.accent.primary, 0.3),
    condLabel: "IF",
    actionLabel: "THEN",
  },
  CONDITION_ACTION: {
    icon: "⊢",
    label: "CONDITION → ACTION",
    bg: alpha(tokens.risk.MEDIUM.base, 0.1),
    text: tokens.risk.MEDIUM.text,
    border: alpha(tokens.risk.MEDIUM.base, 0.3),
    condLabel: "CONDITION",
    actionLabel: "ACTION",
  },
  PENALTY_TRIGGER: {
    icon: "⚡",
    label: "PENALTY TRIGGER",
    bg: alpha(tokens.entity.PENALTY.base, 0.1),
    text: tokens.entity.PENALTY.text,
    border: alpha(tokens.entity.PENALTY.base, 0.3),
    condLabel: "OFFENCE",
    actionLabel: "CONSEQUENCE",
  },
};

function riskCfg(tier: RiskTier): { bg: string; border: string; text: string } {
  const { base, text } = riskStyle(tier);
  return { bg: alpha(base, 0.12), border: alpha(base, 0.35), text };
}

const RISK_CONFIG: Record<RiskTier, { bg: string; border: string; text: string; icon?: React.ReactNode }> = {
  CRITICAL: riskCfg("CRITICAL"),
  HIGH:     riskCfg("HIGH"),
  MEDIUM:   riskCfg("MEDIUM"),
  LOW:      riskCfg("LOW"),
};

const RISK_ORDER: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

// ─── Text cleaning helpers ────────────────────────────────────────────────────

function cleanSpan(text: string): string {
  return text
    .replace(/\s+/g, " ")
    .replace(/^[\s,;.\-–—]+/, "")
    .replace(/[\s,;]+$/, "")
    .replace(/^\d+[\s.)\-]+/, "")
    .replace(/\b(provided that|subject to|notwithstanding)\b/gi, "")
    .trim();
}

function truncate(text: string, max: number): string {
  const cleaned = cleanSpan(text);
  if (cleaned.length <= max) return cleaned;
  const cut = cleaned.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > max * 0.7 ? cut.slice(0, lastSpace) : cut) + "…";
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function PatternBadge({ type }: { type: string }) {
  const cfg = PATTERN_CONFIG[type] || PATTERN_CONFIG.IF_THEN;
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full"
      style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}` }}
    >
      {cfg.icon} {cfg.label}
    </span>
  );
}

function RiskBadge({ tier }: { tier: RiskTier }) {
  const cfg = RISK_CONFIG[tier];
  return (
    <span
      className="inline-flex items-center gap-1 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase tracking-wider"
      style={{ background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}` }}
    >
      {tier === "CRITICAL" && <AlertTriangle className="w-2.5 h-2.5" />}
      {tier}
    </span>
  );
}

function ImpactBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  let color: string = tokens.status.success;
  if (pct >= 85) color = tokens.status.error;
  else if (pct >= 65) color = tokens.status.warning;
  else if (pct >= 45) color = tokens.status.info;

  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] font-mono text-text-muted">Impact</span>
      <div className="flex-1 h-[3px] rounded-full bg-bg-elevated/60">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-[9px] font-mono w-6 text-right" style={{ color }}>{pct}%</span>
    </div>
  );
}

function SpanBlock({
  label,
  text,
  accentColor,
  bgColor,
  borderColor,
}: {
  label: string;
  text: string;
  accentColor: string;
  bgColor: string;
  borderColor: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const cleaned = cleanSpan(text);
  const short = truncate(cleaned, 160);
  const isLong = cleaned.length > 160;

  return (
    <div
      className="rounded-xl p-3 space-y-1.5"
      style={{ background: bgColor, border: `1px solid ${borderColor}` }}
    >
      <div className="flex items-center justify-between">
        <span
          className="text-[9px] font-mono font-bold uppercase tracking-widest"
          style={{ color: accentColor }}
        >
          {label}
        </span>
        {isLong && (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded((x) => !x); }}
            className="flex items-center gap-0.5 text-[9px] font-mono transition-opacity opacity-60 hover:opacity-100"
            style={{ color: accentColor }}
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? "less" : "more"}
          </button>
        )}
      </div>
      <p className="text-xs leading-relaxed text-text-secondary">
        {expanded ? cleaned : short}
      </p>
    </div>
  );
}

function FadeSlideIn({ children, index }: { children: React.ReactNode; index: number }) {
  return (
    <div
      style={{
        animation: `fadeSlideIn 0.25s ease-out ${index * 0.04}s both`,
      }}
    >
      {children}
    </div>
  );
}

function CausalCard({ p, index }: { p: any; index: number }) {
  const cfg = PATTERN_CONFIG[p.pattern_type] || PATTERN_CONFIG.IF_THEN;
  const condText = cleanSpan(p.condition_span);
  const actionText = cleanSpan(p.action_span);

  if (condText.length < 15 && actionText.length < 15) return null;

  return (
    <FadeSlideIn index={index}>
      <div className="rounded-2xl overflow-hidden border border-border bg-bg-surface/60">
        {/* Card header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-bg-deep/40">
          <div className="flex items-center gap-2 flex-wrap">
            <PatternBadge type={p.pattern_type} />
            <RiskBadge tier={p.risk_tier} />
          </div>
          <span className="text-[10px] font-mono text-text-muted">
            {p.section ? `§ ${p.section}` : `p.${p.page}`}
          </span>
        </div>

        {/* Condition and action */}
        <div className="p-4 space-y-3">
          <SpanBlock
            label={cfg.condLabel}
            text={p.condition_span}
            accentColor={tokens.accent.primary}
            bgColor={alpha(tokens.accent.primary, 0.06)}
            borderColor={alpha(tokens.accent.primary, 0.15)}
          />

          <div className="flex justify-center">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[9px] font-mono uppercase tracking-wider bg-bg-deep/60 border border-border text-text-muted">
              <ArrowRight className="w-2.5 h-2.5" />
              implies
            </div>
          </div>

          <SpanBlock
            label={cfg.actionLabel}
            text={p.action_span}
            accentColor={tokens.status.success}
            bgColor={alpha(tokens.status.success, 0.06)}
            borderColor={alpha(tokens.status.success, 0.15)}
          />

          {/* Impact bar */}
          <ImpactBar score={p.impact_score ?? 0.5} />

          {/* Why it was flagged — deterministic rationale from the backend */}
          {p.explanation && (
            <div className="flex items-start gap-2 mt-1 pt-2.5 border-t border-border">
              <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 bg-accent-primary/15 border border-accent-primary/30">
                <span className="text-[8px] font-bold text-accent-primary">i</span>
              </div>
              <p className="text-[11px] leading-relaxed text-text-secondary">
                {p.explanation}
              </p>
            </div>
          )}
        </div>
      </div>
    </FadeSlideIn>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function CausalTab() {
  const { clauses } = useDocumentStore();
  const [riskFilter, setRiskFilter] = useState<RiskTier | "ALL">("ALL");

  const patterns = useMemo(() => {
    return clauses
      .flatMap((c) =>
        c.causal_patterns.map((p) => ({
          ...p,
          page: c.page,
          section: c.section_hierarchy.join("."),
          clauseText: c.text.slice(0, 200),
        }))
      )
      // Drop patterns whose spans clean down to almost nothing — CausalCard
      // won't render them, so counting them would overstate the total.
      .filter((p) => cleanSpan(p.condition_span).length >= 15 || cleanSpan(p.action_span).length >= 15);
  }, [clauses]);

  const filtered = useMemo(() => {
    if (riskFilter === "ALL") return patterns;
    return patterns.filter((p) => p.risk_tier === riskFilter);
  }, [patterns, riskFilter]);

  // Group by risk tier for summary counts
  const riskCounts = useMemo(() => {
    const c: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    patterns.forEach((p) => { c[p.risk_tier] = (c[p.risk_tier] || 0) + 1; });
    return c;
  }, [patterns]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    patterns.forEach((p) => { c[p.pattern_type] = (c[p.pattern_type] || 0) + 1; });
    return c;
  }, [patterns]);

  if (patterns.length === 0) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex flex-col items-center justify-center py-12 rounded-2xl border border-dashed border-border">
          <Zap className="w-8 h-8 mb-3 opacity-30 text-accent-primary" />
          <p className="font-mono text-sm text-text-muted">No causal patterns detected yet</p>
          <p className="text-xs mt-1 text-text-dim">
            Patterns appear after NER + causal analysis completes
          </p>
        </div>
        <Phase2Banner />
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* ── Summary row ── */}
      <div className="flex items-center gap-4 p-4 rounded-2xl bg-accent-primary/5 border border-accent-primary/20">
        <Zap className="w-5 h-5 flex-shrink-0 text-accent-primary" />
        <div className="flex-1 min-w-0">
          <p className="font-display font-bold text-lg text-text-primary">
            {patterns.length} causal structures
          </p>
          <p className="text-xs mt-0.5 text-text-secondary">
            Rule-based detection · Phase 2 adds Phi-3.5-mini LLM reasoning
          </p>
        </div>
        {/* Risk counts */}
        <div className="flex gap-2 flex-wrap justify-end">
          {RISK_ORDER.map((tier) => riskCounts[tier] > 0 && (
            <div
              key={tier}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-lg cursor-pointer transition-opacity"
              style={{
                background: RISK_CONFIG[tier].bg,
                border: `1px solid ${RISK_CONFIG[tier].border}`,
                color: RISK_CONFIG[tier].text,
                opacity: riskFilter !== "ALL" && riskFilter !== tier ? 0.4 : 1,
              }}
              onClick={() => setRiskFilter(riskFilter === tier ? "ALL" : tier)}
            >
              {tier === "CRITICAL" && <AlertTriangle className="w-2.5 h-2.5" />}
              {riskCounts[tier]}× {tier}
            </div>
          ))}
        </div>
      </div>

      {/* ── Risk filter bar ── */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-bg-surface/80 border border-border">
        <Filter className="w-3.5 h-3.5 flex-shrink-0 text-text-muted" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
          Filter by risk:
        </span>
        <div className="flex gap-1.5 flex-wrap">
          <button
            onClick={() => setRiskFilter("ALL")}
            className="text-[10px] font-mono px-2 py-0.5 rounded-full transition-all"
            style={{
              background: riskFilter === "ALL" ? alpha(tokens.accent.primary, 0.15) : "transparent",
              border: "1px solid",
              borderColor: riskFilter === "ALL" ? alpha(tokens.accent.primary, 0.4) : tokens.border.DEFAULT,
              color: riskFilter === "ALL" ? tokens.accent.primary : tokens.text.muted,
            }}
          >
            All ({patterns.length})
          </button>
          {RISK_ORDER.map((tier) => riskCounts[tier] > 0 && (
            <button
              key={tier}
              onClick={() => setRiskFilter(riskFilter === tier ? "ALL" : tier)}
              className="text-[10px] font-mono px-2 py-0.5 rounded-full transition-all"
              style={{
                background: riskFilter === tier ? RISK_CONFIG[tier].bg : "transparent",
                border: "1px solid",
                borderColor: riskFilter === tier ? RISK_CONFIG[tier].border : tokens.border.DEFAULT,
                color: riskFilter === tier ? RISK_CONFIG[tier].text : tokens.text.muted,
              }}
            >
              {tier} ({riskCounts[tier]})
            </button>
          ))}
        </div>
        {/* Pattern type breakdown */}
        <div className="ml-auto flex gap-2">
          {Object.entries(typeCounts).map(([type, count]) => {
            const cfg = PATTERN_CONFIG[type];
            return (
              <span key={type} className="text-[10px] font-mono" style={{ color: cfg?.text || tokens.text.secondary }}>
                {cfg?.icon} {count}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── How to read ── */}
      <div className="flex items-start gap-3 p-3 rounded-xl text-xs bg-bg-surface/80 border border-border">
        <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 bg-accent-primary/15 border border-accent-primary/30">
          <span className="text-[9px] font-bold text-accent-primary">i</span>
        </div>
        <p className="text-text-secondary">
          Each card shows a logical relationship — an IF/CONDITION triggering a THEN/ACTION.
          Risk tier (<strong className="text-status-error">CRITICAL</strong> →{" "}
          <strong className="text-status-success">LOW</strong>) reflects severity based on
          penalty keywords, imprisonment clauses, and monetary amounts.
          Click risk badges above to filter.
        </p>
      </div>

      {/* ── Pattern cards ── */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 rounded-2xl border border-dashed border-border">
            <p className="font-mono text-sm text-text-muted">
              No {riskFilter} risk patterns
            </p>
          </div>
        ) : (
          filtered.map((p, i) => (
            <CausalCard key={i} p={p} index={i} />
          ))
        )}
      </div>

      <Phase2Banner />

      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0);   }
        }
      `}</style>
    </div>
  );
}

function Phase2Banner() {
  return (
    <div className="rounded-2xl p-5 bg-entity-actor/5 border border-entity-actor/15">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 bg-entity-actor/10 border border-entity-actor/20">
          <Lock className="w-4 h-4" style={{ color: tokens.entity.ACTOR.text }} />
        </div>
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Cpu className="w-3.5 h-3.5" style={{ color: tokens.entity.ACTOR.text }} />
            <p className="font-semibold text-sm text-text-primary">Phase 2: LLM Causal Extraction</p>
          </div>
          <p className="text-xs leading-relaxed text-text-secondary">
            Current: rule-based regex detection — fast but limited to known sentence patterns.
            Phase 2 uses <strong className="text-accent-primary">Phi-3.5-mini</strong> with LIME explainability to understand
            complex multi-hop causal chains, nested conditionals, and implicit obligations.
          </p>
        </div>
      </div>
    </div>
  );
}
