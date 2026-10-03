"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import TopNav from "@/components/nav/TopNav";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Run {
  set: string; system: string; ay: string; complete: boolean; samples: number;
  flip_rate: number | null; flipped: string[];
  revenue_change_expert_crore: number | null; revenue_change_system_crore: number | null;
  kakwani_expert: number | null; kakwani_system: number | null; decile_rate_l1: number | null;
  review: { target: string; reason: string }[]; param_diff: string[];
  hallucinated_fields: number; span_fields: number;
  attribution?: Attribution | null;
}
interface Player {
  target: string; provision: string; revenue_error_crore: number; decile_rate_l1: number; flips: number;
}
interface Attribution {
  players: Player[]; identical_targets: string[]; failed_targets: string[];
  total: { revenue_error_crore: number; decile_rate_l1: number; flips: number };
  minimal_restoring_set: string[] | null;
}
interface Design { ay: string; description: string; targets: Record<string, string>; statute: string }

const fmtCr = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `₹${Math.round(v).toLocaleString("en-IN")} cr`;

function AttributionPanel({ a }: { a: Attribution }) {
  if (a.players.length === 0) {
    return a.failed_targets.length === 0
      ? <p className="text-xs text-status-success">Every targeted parameter matches the expert reading.</p>
      : null;
  }
  const scale = Math.max(...a.players.map((p) => Math.abs(p.revenue_error_crore)), 1);
  return (
    <div className="space-y-1.5 text-xs">
      <p className="text-text-muted">Where the divergence comes from (Shapley share of revenue error)</p>
      {a.players.map((p) => (
        <div key={p.target} className="flex items-center gap-2" title={p.provision}>
          <span className="w-36 truncate font-mono">{p.target}</span>
          <div className="flex-1 h-2 bg-bg-overlay rounded-full overflow-hidden">
            <div className={`h-full ${p.revenue_error_crore < 0 ? "bg-status-error" : "bg-status-warning"}`}
              style={{ width: `${(Math.abs(p.revenue_error_crore) / scale) * 100}%` }} />
          </div>
          <span className="w-28 text-right tabular-nums">{fmtCr(p.revenue_error_crore)}</span>
          <span className="w-16 text-right tabular-nums text-text-muted">{p.flips.toFixed(1)} flips</span>
        </div>
      ))}
      {a.minimal_restoring_set && (
        <p className="text-text-secondary">
          Correcting <span className="font-mono">{a.minimal_restoring_set.join(", ")}</span> restores every conclusion.
        </p>
      )}
    </div>
  );
}

function Cell({ run }: { run?: Run }) {
  if (!run) return <span className="text-text-dim">·</span>;
  if (!run.complete) return <span className="inline-flex items-center gap-1 text-status-error"><XCircle className="w-3.5 h-3.5" />no result</span>;
  const f = run.flip_rate ?? 0;
  const tone = f === 0 ? "text-status-success" : f < 0.2 ? "text-status-warning" : "text-status-error";
  const Icon = f === 0 ? CheckCircle2 : AlertTriangle;
  return <span className={`inline-flex items-center gap-1 ${tone}`}><Icon className="w-3.5 h-3.5" />{(f * 100).toFixed(0)}% flips</span>;
}

export default function ResearchPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [design, setDesign] = useState<Record<string, Design>>({});
  const [backtest, setBacktest] = useState<any>(null);
  const [sens, setSens] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const get = (p: string) => fetch(`${API}${p}`).then((r) => (r.ok ? r.json() : null));
    Promise.all([get("/api/research/experiments"), get("/api/research/provision-sets"),
      get("/api/research/backtest"), get("/api/research/sensitivity"), get("/api/research/stats")])
      .then(([e, d, b, s, st]) => {
        setStats(st);
        setRuns(e?.runs ?? []);
        setDesign(d ?? {});
        setBacktest(b);
        setSens(s);
        if (d) setActive(Object.keys(d)[0]);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const systems = useMemo(() => Array.from(new Set((runs ?? []).map((r) => r.system))), [runs]);
  const sets = Object.keys(design);
  const runFor = (s: string, sys: string) => runs?.find((r) => r.set === s && r.system === sys);

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <TopNav />
      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        <header>
          <h1 className="font-display text-2xl uppercase tracking-wider">Expert vs extracted</h1>
          <p className="text-sm text-text-muted mt-2 max-w-3xl leading-relaxed">
            Each row is one year&apos;s change in personal income tax. Every system reads the same statute provisions; its rules are
            turned into tax parameters by one assembler and simulated on the same taxpayer population as the expert coding. A flip
            is a pre-registered policy conclusion (revenue direction, progressivity, which deciles gain) that differs from the
            expert&apos;s.
          </p>
        </header>

        {error && <p className="text-status-error text-sm" role="alert">{error}</p>}
        {!runs && !error && <Loader2 className="w-5 h-5 animate-spin text-accent-primary" />}

        {runs && (
          <section className="border border-border rounded-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-surface text-text-muted font-mono text-xs uppercase tracking-wider">
                <tr>
                  <th className="text-left px-3 py-2">Reform</th>
                  <th className="text-left px-3 py-2">AY</th>
                  {systems.map((s) => <th key={s} className="text-left px-3 py-2">{s}</th>)}
                </tr>
              </thead>
              <tbody>
                {sets.map((s) => (
                  <tr key={s} onClick={() => setActive(s)}
                    className={`border-t border-border cursor-pointer ${active === s ? "bg-bg-elevated" : "hover:bg-bg-surface"}`}>
                    <td className="px-3 py-2 font-mono text-xs">{s}</td>
                    <td className="px-3 py-2 text-text-muted">{design[s]?.ay}</td>
                    {systems.map((sys) => <td key={sys} className="px-3 py-2 text-xs"><Cell run={runFor(s, sys)} /></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {active && design[active] && (
          <section className="space-y-3">
            <h2 className="font-display text-lg uppercase tracking-wider">{active}</h2>
            <p className="text-sm text-text-secondary">{design[active].description}</p>
            <p className="text-xs text-text-muted font-mono">
              {Object.entries(design[active].targets).map(([t, p]) => `${t} ← ${p}`).join("   ·   ")}
            </p>
            <div className="grid md:grid-cols-2 gap-3">
              {systems.map((sys) => {
                const r = runFor(active, sys);
                if (!r) return null;
                const exp = r.revenue_change_expert_crore ?? 0;
                const got = r.revenue_change_system_crore;
                const scale = Math.max(Math.abs(exp), Math.abs(got ?? 0), 1);
                return (
                  <div key={sys} className="bg-bg-surface border border-border rounded-sm p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm">{sys}</span>
                      <Cell run={r} />
                    </div>
                    <div className="space-y-1.5 text-xs">
                      <p className="text-text-muted">Revenue change vs previous year&apos;s law</p>
                      {[["Expert", exp], [sys, got]].map(([label, v]) => (
                        <div key={String(label)} className="flex items-center gap-2">
                          <span className="w-28 truncate text-text-secondary">{label}</span>
                          <div className="flex-1 h-2 bg-bg-overlay rounded-full overflow-hidden">
                            {v !== null && (
                              <div className="h-full bg-accent-primary" style={{ width: `${(Math.abs(Number(v)) / scale) * 100}%` }} />
                            )}
                          </div>
                          <span className="w-32 text-right tabular-nums">{fmtCr(v as number | null)}</span>
                        </div>
                      ))}
                    </div>
                    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                      <dt className="text-text-muted">Effective-rate distance (deciles)</dt>
                      <dd className="tabular-nums text-right">{r.decile_rate_l1 === null ? "—" : r.decile_rate_l1.toFixed(4)}</dd>
                      <dt className="text-text-muted">Kakwani (expert / system)</dt>
                      <dd className="tabular-nums text-right">{r.kakwani_expert?.toFixed(3)} / {r.kakwani_system?.toFixed(3) ?? "—"}</dd>
                      <dt className="text-text-muted">Quotes not found in statute</dt>
                      <dd className="tabular-nums text-right">{r.hallucinated_fields}/{r.span_fields}</dd>
                      <dt className="text-text-muted">Self-consistency samples</dt>
                      <dd className="tabular-nums text-right">{r.samples}</dd>
                    </dl>
                    {r.attribution && <AttributionPanel a={r.attribution} />}
                    {r.review.length > 0 && (
                      <ul className="text-xs text-status-error space-y-0.5">
                        {r.review.map((v, i) => <li key={i}>{v.target}: {v.reason}</li>)}
                      </ul>
                    )}
                    {r.param_diff.length > 0 && (
                      <p className="text-xs text-status-warning">Differs from expert: {r.param_diff.slice(0, 6).join(", ")}</p>
                    )}
                    {r.flipped.length > 0 && r.complete && (
                      <p className="text-xs text-text-muted">Flipped: {r.flipped.join(", ")}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {stats && (
          <section className="grid md:grid-cols-2 gap-3">
            <div className="bg-bg-surface border border-border rounded-sm p-4 text-sm">
              <h3 className="font-display uppercase tracking-wider text-sm mb-1">Do flips survive population uncertainty?</h3>
              <p className="text-xs text-text-muted mb-3">
                {stats.draws} re-draws of the population assumptions. Persistence: share of draws where the flip remains;
                noise floor: how often the expert&apos;s own conclusions move.
              </p>
              <table className="w-full text-xs">
                <thead className="text-text-muted"><tr>
                  <th className="text-left font-normal">Reform / system</th><th className="text-right font-normal">Flips</th>
                  <th className="text-right font-normal">Min persistence</th><th className="text-right font-normal">Noise floor</th>
                </tr></thead>
                <tbody>
                  {stats.robustness.filter((r: any) => r.complete).map((r: any) => {
                    const p = Object.values(r.persistence as Record<string, number>);
                    return (
                      <tr key={r.set + r.system} className="border-t border-border">
                        <td className="py-1 font-mono">{r.set} · {r.system}</td>
                        <td className="text-right tabular-nums">{(r.flip_rate_calibrated * 100).toFixed(0)}%</td>
                        <td className="text-right tabular-nums">{p.length ? Math.min(...p).toFixed(2) : "—"}</td>
                        <td className="text-right tabular-nums">{r.noise_floor_mean.toFixed(3)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="bg-bg-surface border border-border rounded-sm p-4 text-sm">
              <h3 className="font-display uppercase tracking-wider text-sm mb-1">Systems compared</h3>
              <p className="text-xs text-text-muted mb-3">Agreement with the expert on paired conclusions; exact McNemar, Holm-corrected.</p>
              {Object.entries(stats.systems.agreement_rate as Record<string, number>).map(([s, v]) => (
                <p key={s} className="flex justify-between text-xs"><span className="font-mono">{s}</span>
                  <span className="tabular-nums">{(v * 100).toFixed(1)}% of {stats.systems.conclusions[s]}</span></p>
              ))}
              <div className="mt-3 space-y-0.5">
                {Object.entries(stats.systems.tests as Record<string, any>).map(([k, t]) => (
                  <p key={k} className="flex justify-between text-xs text-text-secondary"><span>{k}</span>
                    <span className="tabular-nums">p = {t.p_holm < 0.001 ? "<0.001" : t.p_holm.toFixed(3)}</span></p>
                ))}
              </div>
            </div>
          </section>
        )}

        {backtest && (
          <section className="grid md:grid-cols-3 gap-3">
            <div className="bg-bg-surface border border-border rounded-sm p-4 text-sm space-y-1">
              <h3 className="font-display uppercase tracking-wider text-sm mb-2">In-sample</h3>
              {backtest.in_sample.map((r: any) => (
                <p key={r.ay} className="flex justify-between text-xs"><span>AY {r.ay}</span>
                  <span className="tabular-nums">simulated / reported {r.ratio.toFixed(3)}</span></p>
              ))}
            </div>
            <div className="bg-bg-surface border border-border rounded-sm p-4 text-sm space-y-1">
              <h3 className="font-display uppercase tracking-wider text-sm mb-2">Forecast (held out)</h3>
              <p className="text-xs text-text-muted">Ageing chosen on selection years: {backtest.forecast.chosen_method}</p>
              {backtest.forecast.test.map((t: any) => (
                <p key={t.base_ay + t.target_ay} className="flex justify-between text-xs">
                  <span>{t.base_ay} → {t.target_ay}</span>
                  <span className="tabular-nums">error {(t.ape_model * 100).toFixed(1)}% vs naive {(t.ape_naive * 100).toFixed(1)}%</span>
                </p>
              ))}
            </div>
            <div className="bg-bg-surface border border-border rounded-sm p-4 text-sm space-y-1">
              <h3 className="font-display uppercase tracking-wider text-sm mb-2">Reform cost</h3>
              {backtest.reform_cost.map((r: any) => (
                <p key={r.reform} className="flex justify-between text-xs"><span>{r.reform}</span>
                  <span className="tabular-nums">{fmtCr(r.simulated_cost_crore)} vs announced {fmtCr(r.announced_cost_crore)}</span></p>
              ))}
            </div>
          </section>
        )}

        {sens && (
          <section className="bg-bg-surface border border-border rounded-sm p-4">
            <h3 className="font-display uppercase tracking-wider text-sm mb-3">What drives the simulated outcomes (Sobol total-order index)</h3>
            <div className="grid md:grid-cols-2 gap-4">
              {Object.entries(sens.sobol as Record<string, Record<string, { ST: number }>>).map(([out, idx]) => (
                <div key={out}>
                  <p className="text-xs text-text-muted mb-1 font-mono">{out}</p>
                  {Object.entries(idx).sort((a, b) => b[1].ST - a[1].ST).map(([name, v]) => (
                    <div key={name} className="flex items-center gap-2 text-xs">
                      <span className="w-28 truncate">{name}</span>
                      <div className="flex-1 h-1.5 bg-bg-overlay rounded-full overflow-hidden">
                        <div className="h-full bg-accent-primary" style={{ width: `${Math.max(0, Math.min(1, v.ST)) * 100}%` }} />
                      </div>
                      <span className="w-12 text-right tabular-nums">{v.ST.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
