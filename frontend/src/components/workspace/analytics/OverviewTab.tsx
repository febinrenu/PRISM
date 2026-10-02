"use client";
import { useMemo } from "react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";
import { AlertTriangle, Globe, TrendingUp, ShieldAlert } from "lucide-react";
import type { RiskTier } from "@/types";

const ENTITY_LABELS = ["OBLIGATION", "PENALTY", "RIGHT", "THRESHOLD", "ACTOR", "BENEFICIARY"] as const;

const RISK_COLORS: Record<RiskTier, string> = {
  CRITICAL: tokens.risk.CRITICAL.text,
  HIGH:     tokens.risk.HIGH.text,
  MEDIUM:   tokens.risk.MEDIUM.text,
  LOW:      tokens.risk.LOW.text,
};

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl p-4 bg-bg-surface/70 border border-border">
      <p className="text-[10px] font-mono uppercase tracking-widest mb-1 text-text-muted">{label}</p>
      <p className="font-display font-bold text-2xl" style={{ color: color || tokens.text.primary }}>{value}</p>
      {sub && <p className="text-[11px] mt-0.5 text-text-muted">{sub}</p>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl p-3 text-xs shadow-xl bg-bg-base border border-border">
      <p className="font-mono mb-1 text-text-secondary">{label}</p>
      <p className="font-bold text-text-primary">{payload[0].value}</p>
    </div>
  );
};

export default function OverviewTab() {
  const { clauses, stats } = useDocumentStore();

  const entityData = useMemo(() => {
    const counts: Record<string, number> = {};
    clauses.forEach((c) => c.entities.forEach((e) => { counts[e.label] = (counts[e.label] || 0) + 1; }));
    return ENTITY_LABELS
      .filter((l) => counts[l] > 0)
      .map((l) => ({ name: l, value: counts[l], color: ENTITY_COLORS[l]?.hex || tokens.accent.primary }));
  }, [clauses]);

  const sectionData = useMemo(() => {
    const counts: Record<string, number> = {};
    clauses.forEach((c) => {
      const key = c.section_hierarchy[0] || `p.${c.page}`;
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [clauses]);

  const mostComplex = useMemo(() => {
    if (!clauses.length) return null;
    return clauses.reduce((a, b) => a.complexity_score > b.complexity_score ? a : b);
  }, [clauses]);

  const causalCount = useMemo(
    () => clauses.reduce((n, c) => n + c.causal_patterns.length, 0),
    [clauses]
  );

  // Risk distribution
  const riskCounts = useMemo(() => {
    const c: Record<RiskTier, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    clauses.forEach((clause) => {
      clause.causal_patterns.forEach((p) => {
        c[p.risk_tier] = (c[p.risk_tier] || 0) + 1;
      });
    });
    return c;
  }, [clauses]);

  // Confidence distribution
  const confCounts = useMemo(() => {
    return stats?.entity_confidence_counts || (() => {
      const c = { HIGH: 0, MEDIUM: 0, LOW: 0 };
      clauses.forEach((clause) => {
        clause.entities.forEach((e) => { c[e.confidence] = (c[e.confidence] || 0) + 1; });
      });
      return c;
    })();
  }, [clauses, stats]);

  const domain = stats?.domain;

  if (clauses.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted">
        <p className="font-mono text-sm">Waiting for analysis…</p>
      </div>
    );
  }

  const totalRisk = Object.values(riskCounts).reduce((a, b) => a + b, 0);
  const totalConf = Object.values(confCounts).reduce((a, b) => a + b, 0);

  return (
    <div className="p-4 space-y-4">
      {/* Domain badge */}
      {domain && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-entity-actor/10 border border-entity-actor/20">
          <Globe className="w-4 h-4 flex-shrink-0" style={{ color: tokens.entity.ACTOR.text }} />
          <div>
            <p className="text-[9px] font-mono uppercase tracking-widest text-text-muted">Detected Domain</p>
            <p className="font-semibold text-sm" style={{ color: tokens.entity.ACTOR.text }}>{domain}</p>
          </div>
          <div className="ml-auto text-[9px] font-mono px-2 py-1 rounded-lg bg-entity-actor/10 border border-entity-actor/20"
            style={{ color: tokens.entity.ACTOR.text }}>
            AUTO-DETECTED
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Clauses"  value={clauses.length}    sub="total extracted" />
        <StatCard label="Entities" value={stats?.total_entities ?? entityData.reduce((s, d) => s + d.value, 0)} sub="tagged" color={tokens.accent.primary} />
        <StatCard label="Causal"   value={causalCount}       sub="IF→THEN patterns" color={tokens.status.warning} />
        <StatCard label="Pages"    value={stats?.total_pages ?? "—"} sub="processed" />
      </div>

      {/* Risk distribution */}
      {totalRisk > 0 && (
        <div className="rounded-xl p-4 bg-bg-surface/70 border border-border">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="w-3.5 h-3.5 text-status-error" />
            <p className="text-xs font-mono uppercase tracking-widest text-text-muted">Risk Distribution</p>
          </div>
          <div className="space-y-2">
            {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as RiskTier[]).map((tier) => {
              const count = riskCounts[tier] || 0;
              if (count === 0) return null;
              const pct = Math.round((count / totalRisk) * 100);
              return (
                <div key={tier} className="flex items-center gap-2">
                  <span className="text-[9px] font-mono w-16 text-right" style={{ color: RISK_COLORS[tier] }}>
                    {tier}
                  </span>
                  <div className="flex-1 h-2 rounded-full bg-bg-deep">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${pct}%`, background: RISK_COLORS[tier] }}
                    />
                  </div>
                  <span className="text-[9px] font-mono w-8" style={{ color: RISK_COLORS[tier] }}>
                    {count}×
                  </span>
                </div>
              );
            })}
          </div>
          {riskCounts.CRITICAL > 0 && (
            <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-status-error/10 border border-status-error/20">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-status-error" />
              <span className="text-status-error">
                {riskCounts.CRITICAL} critical risk{riskCounts.CRITICAL !== 1 ? "s" : ""} detected — review penalty triggers
              </span>
            </div>
          )}
        </div>
      )}

      {/* Entity distribution donut */}
      {entityData.length > 0 && (
        <div className="rounded-xl p-4 bg-bg-surface/70 border border-border">
          <p className="text-xs font-mono uppercase tracking-widest mb-3 text-text-muted">Entity Distribution</p>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={120} height={120}>
              <PieChart>
                <Pie
                  data={entityData}
                  cx="50%" cy="50%"
                  innerRadius={32} outerRadius={55}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {entityData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1.5">
              {entityData.map((d) => (
                <div key={d.name} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
                    <span className="text-[10px] font-mono text-text-secondary">{d.name}</span>
                  </div>
                  <span className="text-[10px] font-mono text-text-muted">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Confidence breakdown */}
      {totalConf > 0 && (
        <div className="rounded-xl p-4 bg-bg-surface/70 border border-border">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-3.5 h-3.5 text-status-success" />
            <p className="text-xs font-mono uppercase tracking-widest text-text-muted">
              Extraction Confidence
            </p>
          </div>
          <div className="flex gap-3">
            {(["HIGH", "MEDIUM", "LOW"] as const).map((conf) => {
              const count = confCounts[conf] || 0;
              const pct = Math.round((count / totalConf) * 100);
              const color = conf === "HIGH" ? tokens.status.success : conf === "MEDIUM" ? tokens.status.warning : tokens.text.muted;
              return (
                <div key={conf} className="flex-1 text-center">
                  <div className="text-lg font-display font-bold" style={{ color }}>{pct}%</div>
                  <div className="text-[9px] font-mono uppercase text-text-muted">{conf}</div>
                  <div className="text-[9px] font-mono mt-0.5 text-text-dim">{count}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bar chart */}
      {sectionData.length > 0 && (
        <div className="rounded-xl p-4 bg-bg-surface/70 border border-border">
          <p className="text-xs font-mono uppercase tracking-widest mb-3 text-text-muted">Clauses per Section</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={sectionData} barSize={14}>
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: tokens.text.muted, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: alpha(tokens.accent.primary, 0.07) }} />
              <Bar dataKey="count" fill={tokens.accent.primary} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Most complex clause */}
      {mostComplex && (
        <div className="rounded-xl p-4 bg-accent-primary/5 border border-accent-primary/15">
          <p className="text-[10px] font-mono uppercase tracking-widest mb-2 text-accent-primary">
            Most Dense Clause
          </p>
          <p className="text-xs leading-relaxed line-clamp-3 text-text-secondary">{mostComplex.text}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px] font-mono text-text-muted">
              §{mostComplex.section_hierarchy.join(".")} · p.{mostComplex.page}
            </span>
            <span className="ml-auto text-[10px] font-mono text-accent-primary">
              {mostComplex.entities.length} entities
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
