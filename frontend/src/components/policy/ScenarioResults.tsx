"use client";

import { useMemo } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { alpha, tokens } from "@/lib/tokens";
import { ASSUMPTION_LABELS, count, crore, inr, pct, signedIndex, signedPct } from "@/components/policy/format";
import type { PolicyScenarioResult } from "@/types";

const AXIS_TICK = { fill: tokens.text.dim, fontSize: 12, fontFamily: "monospace" };
const TOOLTIP_STYLE = {
  background: tokens.bg.overlay,
  border: `1px solid ${tokens.border.light}`,
  borderRadius: 4,
  fontSize: 12,
  fontFamily: "monospace",
  color: tokens.text.secondary,
};
const GRID = alpha(tokens.accent.primary, 0.07);

function Card({ title, subtitle, children, className }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("glass-card p-4", className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3">
        <p className="text-[14px] text-text-primary">{title}</p>
        {subtitle && <p className="font-mono text-micro text-text-dim">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "good" | "bad" | "neutral" }) {
  return (
    <div className="glass-card p-4">
      <p className="font-mono text-micro uppercase tracking-wider text-text-dim">{label}</p>
      <p
        className={cn(
          "mt-1.5 font-serif text-[1.7rem] leading-tight",
          tone === "good" ? "text-status-success" : tone === "bad" ? "text-status-warning" : "text-text-primary"
        )}
      >
        {value}
      </p>
      {sub && <div className="mt-1.5 text-[12.5px] leading-snug text-text-muted">{sub}</div>}
    </div>
  );
}

export default function ScenarioResults({
  result,
  busy,
  uncertaintyPending,
}: {
  result: PolicyScenarioResult;
  busy: boolean;
  uncertaintyPending: boolean;
}) {
  const { delta, baseline, scenario, impact, attribution, uncertainty, behaviour } = result;
  const edited = result.changes_applied.length > 0;

  const decileData = useMemo(
    () =>
      baseline.deciles.map((d, i) => ({
        decile: `D${d.decile}`,
        baseline: d.effective_rate * 100,
        scenario: scenario.deciles[i].effective_rate * 100,
      })),
    [baseline, scenario]
  );

  const bandData = useMemo(
    () =>
      impact.bands.map((b) => ({
        label: b.label,
        less: b.share_pay_less * 100,
        same: (1 - b.share_pay_less - b.share_pay_more) * 100,
        more: b.share_pay_more * 100,
        change: b.mean_change_inr,
      })),
    [impact.bands]
  );

  const leverData = useMemo(
    () => (attribution?.levers ?? []).map((l) => ({ label: l.label, value: l.revenue_crore })),
    [attribution]
  );

  const sign = delta.revenue_crore;
  const revenueTone = !edited ? "neutral" : sign > 0 ? "good" : "bad";
  const progressive = delta.kakwani;

  return (
    <div className={cn("space-y-4 transition-opacity", busy && "opacity-70")} aria-busy={busy}>
      {result.warnings.map((w) => (
        <div key={w} role="note" className="flex items-start gap-2 rounded-[4px] border border-status-warning/35 bg-status-warning/[0.06] px-3 py-2 text-[13px] text-text-secondary">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-warning" aria-hidden /> {w}
        </div>
      ))}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Revenue effect, per year"
          value={edited ? crore(delta.revenue_crore, true) : "No change"}
          tone={revenueTone}
          sub={
            <>
              {edited && <span>{signedPct(delta.revenue_pct)} of {crore(baseline.revenue_crore)}. </span>}
              {uncertainty ? (
                <span>
                  Across the assumptions the data cannot fix: {crore(uncertainty.revenue_delta_crore.p5, true)} to{" "}
                  {crore(uncertainty.revenue_delta_crore.p95, true)}
                  {uncertainty.sign_stable ? " (the direction never changes)." : " (the direction depends on them)."}
                </span>
              ) : uncertaintyPending ? (
                <span className="inline-flex items-center gap-1.5">
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> Estimating the range…
                </span>
              ) : null}
            </>
          }
        />
        <Stat
          label="Who is affected"
          value={edited ? `${pct(impact.overall.share_pay_less)} pay less` : "—"}
          sub={
            edited ? (
              <>
                {pct(impact.overall.share_pay_more)} pay more; {pct(impact.overall.share_unchanged)} are unaffected (of{" "}
                {count(result.population.returns)} returns).
              </>
            ) : (
              <>Change the law to see who gains and who loses.</>
            )
          }
        />
        <Stat
          label="Taxpayers paying tax"
          value={count(scenario.taxpayers_with_tax)}
          sub={
            <>
              {edited && Math.abs(delta.taxpayers_with_tax) >= 1 ? (
                <>
                  {delta.taxpayers_with_tax > 0 ? "+" : "−"}
                  {count(Math.abs(delta.taxpayers_with_tax))} against the baseline.{" "}
                </>
              ) : null}
              {pct(scenario.new_regime_share, 0)} file under the new regime.
            </>
          }
        />
        <Stat
          label="Progressivity (Kakwani)"
          value={signedIndex(progressive)}
          sub={
            Math.abs(progressive) < 0.0005
              ? "No change to how the burden is spread over income."
              : progressive > 0
                ? "More progressive than the baseline: the tax shifts toward higher incomes."
                : "Less progressive than the baseline: the tax shifts toward lower incomes."
          }
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Who pays more and who pays less" subtitle="share of returns, by gross total income">
          <ResponsiveContainer width="100%" height={Math.max(230, bandData.length * 30 + 50)}>
            <BarChart data={bandData} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }} stackOffset="expand">
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" tick={AXIS_TICK} stroke={GRID} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
              <YAxis type="category" dataKey="label" width={112} tick={AXIS_TICK} stroke={GRID} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v, name) => [`${Number(v).toFixed(1)}%`, name]}
                labelFormatter={(l) => {
                  const b = bandData.find((x) => x.label === l);
                  return b ? `${l}: ${b.change === 0 ? "no change" : `${b.change > 0 ? "+" : "−"}${inr(Math.abs(b.change))}`} per return on average` : String(l);
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: "monospace", color: tokens.text.secondary }} />
              <Bar dataKey="less" name="Pay less" stackId="a" fill={tokens.status.success} isAnimationActive={false} />
              <Bar dataKey="same" name="No change" stackId="a" fill={alpha(tokens.text.dim, 0.28)} isAnimationActive={false} />
              <Bar dataKey="more" name="Pay more" stackId="a" fill={tokens.status.warning} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-[12px] leading-relaxed text-text-muted">
            Bands follow the law’s own limits. A change to one band moves only the incomes above it, and the rebate can
            shield everyone below its limit; taxpayers whose deductions make the unchanged old regime cheaper do not move.
          </p>
        </Card>

        <Card title="Effective tax rate by income decile" subtitle="tax ÷ gross total income, %">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={decileData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="decile" tick={AXIS_TICK} stroke={GRID} />
              <YAxis tick={AXIS_TICK} stroke={GRID} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, name) => [`${Number(v).toFixed(2)}%`, name]} />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: "monospace" }} />
              <Line type="monotone" dataKey="baseline" name="Baseline law" stroke={tokens.text.dim} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="scenario" name="Your scenario" stroke={tokens.accent.primary} strokeWidth={2.4} dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="mt-2 text-[12px] leading-relaxed text-text-muted">
            Deciles of all {count(result.population.returns)} returns, lowest income first. The lowest deciles pay nothing
            under either law.
          </p>
        </Card>

        {attribution && attribution.levers.length > 0 && (
          <Card
            title="What drove the revenue change"
            subtitle={attribution.exact ? "exact split over each change (Shapley)" : "split over each change (sampled Shapley)"}
          >
            <ul className="space-y-3">
              {leverData.map((d) => {
                const max = Math.max(...leverData.map((x) => Math.abs(x.value)), 1);
                return (
                  <li key={d.label}>
                    <div className="flex items-baseline justify-between gap-3 text-[12.5px]">
                      <span className="text-text-secondary">{d.label}</span>
                      <span className="shrink-0 font-mono text-text-primary">{crore(d.value, true)}</span>
                    </div>
                    <div className="mt-1 h-2.5 rounded-full bg-bg-elevated" aria-hidden>
                      <div
                        className="h-2.5 rounded-full"
                        style={{
                          width: `${(Math.abs(d.value) / max) * 100}%`,
                          background: d.value >= 0 ? tokens.accent.primary : tokens.status.warning,
                        }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 text-[12px] leading-relaxed text-text-muted">
              Each change is credited with its average effect over every order the changes could be made in, so the parts
              add up to the whole ({crore(attribution.total_crore, true)}).
              {!attribution.matches_total && " (They differ from the total by more than rounding: treat the split with care.)"}
            </p>
          </Card>
        )}

        {uncertainty && (
          <Card title="Which assumption matters" subtitle={`${uncertainty.n} draws over the plausible ranges`}>
            <Tornado result={result} />
          </Card>
        )}
      </div>

      {behaviour && (
        <Card title="With a behavioural response" subtitle={`compliance model · ${behaviour.agents.toLocaleString()} agents · ${behaviour.seeds} seeds`}>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="font-mono text-micro uppercase tracking-wider text-text-dim">Static effect</p>
              <p className="mt-1 font-serif text-xl text-text-primary">{crore(delta.revenue_crore, true)}</p>
              <p className="text-[12px] text-text-muted">taxpayers keep reporting what they reported</p>
            </div>
            <div>
              <p className="font-mono text-micro uppercase tracking-wider text-text-dim">With evasion responding</p>
              <p className="mt-1 font-serif text-xl text-text-primary">{crore(behaviour.delta_revenue_crore.mean, true)}</p>
              <p className="text-[12px] text-text-muted">
                {crore(behaviour.delta_revenue_crore.min, true)} to {crore(behaviour.delta_revenue_crore.max, true)} across seeds
              </p>
            </div>
            <div>
              <p className="font-mono text-micro uppercase tracking-wider text-text-dim">Change in the tax gap</p>
              <p className="mt-1 font-serif text-xl text-text-primary">{signedPct(behaviour.delta_tax_gap)} points</p>
              <p className="text-[12px] text-text-muted">of tax owed that goes unpaid</p>
            </div>
          </div>
          <p className="mt-3 text-[12px] leading-relaxed text-text-muted">
            Audit rate {pct(behaviour.params.audit_rate, 1)}, penalty {behaviour.params.penalty_rate}× the evaded tax, mean tax
            morale {behaviour.params.morale}. {behaviour.note}
          </p>
        </Card>
      )}

      <Card title="By income band" subtitle="the same numbers as the charts, as a table">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-[13px]">
            <thead>
              <tr className="text-left font-mono text-micro uppercase tracking-wider text-text-dim">
                <th className="pb-2 pr-3 font-normal">Gross total income</th>
                <th className="pb-2 pr-3 text-right font-normal">Returns</th>
                <th className="pb-2 pr-3 text-right font-normal">Pay less</th>
                <th className="pb-2 pr-3 text-right font-normal">Pay more</th>
                <th className="pb-2 pr-3 text-right font-normal">Average change</th>
                <th className="pb-2 pr-3 text-right font-normal">Rate before</th>
                <th className="pb-2 text-right font-normal">Rate after</th>
              </tr>
            </thead>
            <tbody>
              {impact.bands.map((b) => (
                <tr key={b.label} className="border-t border-border">
                  <td className="py-1.5 pr-3 text-text-secondary">{b.label}</td>
                  <td className="py-1.5 pr-3 text-right font-mono text-text-muted">{count(b.returns)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{b.share_pay_less > 0 ? pct(b.share_pay_less, 0) : "—"}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">{b.share_pay_more > 0 ? pct(b.share_pay_more, 0) : "—"}</td>
                  <td className="py-1.5 pr-3 text-right font-mono">
                    {Math.abs(b.mean_change_inr) < 0.5 ? "—" : `${b.mean_change_inr > 0 ? "+" : "−"}${inr(Math.abs(b.mean_change_inr))}`}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono text-text-muted">{pct(b.base_rate, 1)}</td>
                  <td className="py-1.5 text-right font-mono">{pct(b.reform_rate, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Tornado({ result }: { result: PolicyScenarioResult }) {
  const u = result.uncertainty!;
  const point = result.delta.revenue_crore;
  const lo = Math.min(point, ...u.tornado.flatMap((t) => [t.at_low_crore, t.at_high_crore]));
  const hi = Math.max(point, ...u.tornado.flatMap((t) => [t.at_low_crore, t.at_high_crore]));
  const span = hi - lo || 1;
  const at = (v: number) => `${((v - lo) / span) * 100}%`;
  return (
    <div>
      <ul className="space-y-3">
        {u.tornado.map((t) => {
          const meta = ASSUMPTION_LABELS[t.input];
          const a = Math.min(t.at_low_crore, t.at_high_crore);
          const b = Math.max(t.at_low_crore, t.at_high_crore);
          const negligible = t.swing_crore < Math.max(1, Math.abs(point) * 0.005);
          return (
            <li key={t.input}>
              <div className="flex items-baseline justify-between gap-3 text-[12.5px]">
                <span className="text-text-secondary" title={meta?.hint}>{meta?.label ?? t.input}</span>
                <span className="font-mono text-[11.5px] text-text-dim">
                  {meta ? meta.format(t.low_value) : t.low_value} to {meta ? meta.format(t.high_value) : t.high_value}
                </span>
              </div>
              <div className="relative mt-1 h-3 rounded-full bg-bg-elevated" aria-hidden>
                <div
                  className="absolute top-0 h-3 rounded-full"
                  style={{ left: at(a), width: `max(3px, ${((b - a) / span) * 100}%)`, background: alpha(tokens.accent.primary, negligible ? 0.35 : 0.75) }}
                />
                <div className="absolute -top-0.5 h-4 w-px bg-text-primary" style={{ left: at(point) }} />
              </div>
              <p className="mt-0.5 text-[11.5px] text-text-dim">
                {negligible ? "No material effect on the result." : `Moves the result by ${crore(t.swing_crore)}.`}
              </p>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[12px] leading-relaxed text-text-muted">
        One assumption at a time across its range, the rest held where you set them; the tick is your estimate,{" "}
        {crore(point, true)}. Drawing all five together gives {crore(u.revenue_delta_crore.min, true)} to{" "}
        {crore(u.revenue_delta_crore.max, true)}; 90% of draws fall between {crore(u.revenue_delta_crore.p5, true)} and{" "}
        {crore(u.revenue_delta_crore.p95, true)}.
      </p>
    </div>
  );
}
