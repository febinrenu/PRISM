"use client";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { alpha, tokens, type AgentType } from "@/lib/tokens";
import type { SimulationStep } from "@/types";

const AGENT_SERIES: Array<{ key: AgentType; label: string }> = [
  { key: "low_income", label: "Low income" },
  { key: "middle_income", label: "Middle income" },
  { key: "high_income", label: "High income" },
  { key: "small_business", label: "SME" },
  { key: "large_corporate", label: "Corporate" },
];

const AXIS_TICK = { fill: tokens.text.dim, fontSize: 10, fontFamily: "monospace" };
const TOOLTIP_STYLE = {
  background: tokens.bg.overlay,
  border: `1px solid ${tokens.border.light}`,
  borderRadius: 4,
  fontSize: 11,
  fontFamily: "monospace",
  color: tokens.text.secondary,
};
const GRID = alpha(tokens.accent.primary, 0.07);

/** Compliance over time — one line per agent type, extends live per SSE step. */
export function ComplianceChart({ steps }: { steps: SimulationStep[] }) {
  const data = steps.map((s) => ({
    step: s.step,
    ...Object.fromEntries(AGENT_SERIES.map(({ key }) => [key, (s.compliance_by_type[key] ?? 0) * 100])),
  }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS_TICK} stroke={GRID} />
        <YAxis domain={[0, 100]} tick={AXIS_TICK} stroke={GRID} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${Number(v).toFixed(1)}%`]} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} />
        {AGENT_SERIES.map(({ key, label }) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={label}
            stroke={tokens.agent[key]}
            strokeWidth={1.8}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Burden distribution — grouped bars sampled every 5 steps. */
export function BurdenChart({ steps }: { steps: SimulationStep[] }) {
  const sampled = steps.filter((s) => s.step % 5 === 4 || s.step === steps.length - 1);
  const data = sampled.map((s) => ({
    step: s.step + 1,
    ...Object.fromEntries(
      // log-scale axis: clamp to ≥1 so zero burdens don't break the chart
      AGENT_SERIES.map(({ key }) => [key, Math.max(1, Math.round(s.avg_burden_by_type[key] ?? 0))])
    ),
  }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: -6, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS_TICK} stroke={GRID} />
        <YAxis
          tick={AXIS_TICK}
          stroke={GRID}
          scale="log"
          domain={["auto", "auto"]}
          allowDataOverflow
          tickFormatter={formatRupees}
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [formatRupees(Number(v))]} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} />
        {AGENT_SERIES.map(({ key, label }) => (
          <Bar key={key} dataKey={key} name={label} fill={tokens.agent[key]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Gini trajectory — area recolors by the inequality zone it ends in. */
export function GiniChart({ steps }: { steps: SimulationStep[] }) {
  const data = steps.map((s) => ({ step: s.step, gini: s.gini_coefficient }));
  const latest = data[data.length - 1]?.gini ?? 0;
  const zone = latest > 0.4 ? tokens.status.error : latest < 0.3 ? tokens.status.success : tokens.status.warning;

  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="giniFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={alpha(zone, 0.4)} />
            <stop offset="100%" stopColor={alpha(zone, 0.02)} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS_TICK} stroke={GRID} />
        <YAxis domain={[0, 1]} tick={AXIS_TICK} stroke={GRID} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [Number(v).toFixed(3), "Gini"]} />
        <Area
          type="monotone"
          dataKey="gini"
          stroke={zone}
          strokeWidth={1.8}
          fill="url(#giniFill)"
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Household income bands only — where the statutory-incidence story lives. */
const BAND_SERIES: Array<{ key: AgentType; label: string }> = [
  { key: "low_income", label: "Low income" },
  { key: "middle_income", label: "Middle income" },
  { key: "high_income", label: "High income" },
];

/** Cumulative government revenue — stacked compliance vs penalty collection. */
export function RevenueChart({ steps }: { steps: SimulationStep[] }) {
  const data = steps
    .filter((s) => s.revenue_total != null)
    .map((s) => ({
      step: s.step,
      compliance: s.revenue_compliance ?? 0,
      penalty: s.revenue_penalty ?? 0,
    }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: -6, bottom: 0 }}>
        <defs>
          <linearGradient id="revComplianceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={alpha(tokens.status.success, 0.45)} />
            <stop offset="100%" stopColor={alpha(tokens.status.success, 0.04)} />
          </linearGradient>
          <linearGradient id="revPenaltyFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={alpha(tokens.status.error, 0.45)} />
            <stop offset="100%" stopColor={alpha(tokens.status.error, 0.04)} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS_TICK} stroke={GRID} />
        <YAxis tick={AXIS_TICK} stroke={GRID} tickFormatter={formatRupees} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [formatRupees(Number(v))]} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} />
        <Area
          type="monotone"
          dataKey="compliance"
          name="Compliance"
          stackId="rev"
          stroke={tokens.status.success}
          strokeWidth={1.6}
          fill="url(#revComplianceFill)"
          isAnimationActive={false}
        />
        <Area
          type="monotone"
          dataKey="penalty"
          name="Penalty"
          stackId="rev"
          stroke={tokens.status.error}
          strokeWidth={1.6}
          fill="url(#revPenaltyFill)"
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Effective tax rate (burden / gross income) per income band over time —
 *  makes the regressive/progressive verdict visible: a downward-sloping
 *  low→high spread is regressive. */
export function EffectiveRateChart({ steps }: { steps: SimulationStep[] }) {
  const data = steps
    .filter((s) => s.effective_rate_by_type != null)
    .map((s) => ({
      step: s.step,
      ...Object.fromEntries(
        BAND_SERIES.map(({ key }) => [key, (s.effective_rate_by_type?.[key] ?? 0) * 100])
      ),
    }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="step" tick={AXIS_TICK} stroke={GRID} />
        <YAxis tick={AXIS_TICK} stroke={GRID} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}%`]} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "monospace" }} />
        {BAND_SERIES.map(({ key, label }) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={label}
            stroke={tokens.agent[key]}
            strokeWidth={1.8}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function formatRupees(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)}Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)}L`;
  if (value >= 1e3) return `₹${(value / 1e3).toFixed(0)}k`;
  return `₹${Math.round(value)}`;
}
