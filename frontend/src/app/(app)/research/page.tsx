"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Search } from "lucide-react";
import InspectPanel from "@/components/research/InspectPanel";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { Callout, ErrorState, PageSkeleton, Panel, Tag } from "@/components/ui/kit";
import { API_BASE as API } from "@/lib/api";
import { errorLabel, reformLabel, systemName } from "@/lib/labels";
import { cn } from "@/lib/utils";

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
interface InjRow {
  set: string; target: string; error: string; flip_rate: number; revenue_error_crore: number;
  flipped: string[]; min_persistence: number | null;
}
interface Design { ay: string; description: string; targets: Record<string, string>; statute: string }
interface StoryNumbers {
  numbers: Record<string, { value: string }>;
  behaviour?: { expert_penalty: number; misread_penalty: number };
}

const fmtCr = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `₹${Math.round(v).toLocaleString("en-IN")} cr`;

const SECTIONS = [
  ["matrix", "Reforms × readers"],
  ["reform", "One reform"],
  ["injection", "Injected errors"],
  ["robustness", "Robustness"],
  ["validation", "Validation"],
  ["sensitivity", "Sensitivity"],
  ["beyond", "Beyond the headline"],
] as const;

/* ── Matrix cell: the verdict tile ──────────────────────────────────────── */

function Verdict({ run }: { run?: Run }) {
  if (!run) return <span className="block h-9 rounded-[3px] bg-ink-800" aria-label="not run" />;
  if (!run.complete)
    return (
      <span
        className="flex h-9 items-center justify-center rounded-[3px] bg-[repeating-linear-gradient(135deg,rgb(var(--ink-700-rgb))_0_6px,rgb(var(--ink-800-rgb))_6px_12px)] text-[12px] text-text-dim"
        title={run.review.map((r) => `${r.target}: ${r.reason}`).join("\n")}
      >
        no conclusion
      </span>
    );
  const f = run.flip_rate ?? 0;
  const err = Math.abs((run.revenue_change_system_crore ?? 0) - (run.revenue_change_expert_crore ?? 0));
  return (
    <span
      className={cn(
        "flex h-9 items-center justify-center gap-1.5 rounded-[3px] font-mono text-[12px]",
        f > 0 ? "bg-status-critical/85 text-ink" : "bg-paper/90 text-ink",
        f === 0 && err > 1 && "ring-1 ring-inset ring-signal"
      )}
      title={err > 1 ? `revenue error ${fmtCr(err)}` : "identical to the expert reading"}
    >
      {(f * 100).toFixed(0)}% flips
      {err > 1 && (
        <>
          <span className="h-1.5 w-1.5 rounded-full bg-signal" aria-hidden />
          <span className="sr-only">revenue differs</span>
        </>
      )}
    </span>
  );
}

function AttributionBars({ a, complete }: { a: Attribution; complete: boolean }) {
  if (a.players.length === 0)
    return a.failed_targets.length === 0 ? (
      <p className="text-[13px] text-status-success">Every targeted parameter matches the expert reading.</p>
    ) : null;
  const scale = Math.max(...a.players.map((p) => Math.abs(p.revenue_error_crore)), 1);
  return (
    <div className="space-y-2 text-[13px]">
      <p className="text-text-muted">Where the divergence comes from (Shapley share of revenue error)</p>
      {!complete && <p className="text-status-warning">Partly assembled: shown for the provisions that were read.</p>}
      {a.players.map((p) => (
        <div key={p.target} className="grid grid-cols-[minmax(0,9rem)_1fr_7rem] items-center gap-3" title={p.provision}>
          <span className="truncate font-mono text-[12.5px] text-text-secondary">{p.target}</span>
          <span className="h-1.5 overflow-hidden rounded-full bg-ink-700">
            <span className="block h-full bg-signal" style={{ width: `${(Math.abs(p.revenue_error_crore) / scale) * 100}%` }} />
          </span>
          <span className="text-right font-mono text-[12.5px]">{fmtCr(p.revenue_error_crore)}</span>
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

function InjectionMap({ rows }: { rows: InjRow[] }) {
  const reforms = Array.from(new Set(rows.map((r) => r.set)));
  const errors = Array.from(new Set(rows.map((r) => r.error))).sort(
    (a, b) =>
      Math.max(...rows.filter((r) => r.error === b).map((r) => r.flip_rate)) -
      Math.max(...rows.filter((r) => r.error === a).map((r) => r.flip_rate))
  );
  const cell = (e: string, s: string) =>
    rows.filter((r) => r.error === e && r.set === s).sort((a, b) => b.flip_rate - a.flip_rate)[0];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-separate border-spacing-[3px] text-[12.5px]">
        <caption className="sr-only">Share of conclusions flipped by each injected error, per reform</caption>
        <thead>
          <tr>
            <th className="pr-3 text-left font-normal text-text-dim">Error</th>
            {reforms.map((s) => (
              <th key={s} className="px-1 align-bottom font-normal text-text-muted">
                <span className="block max-w-[6.5rem] text-[12px] leading-tight">{reformLabel(s)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {errors.map((e) => (
            <tr key={e}>
              <th scope="row" className="whitespace-nowrap pr-3 text-left font-normal text-text-secondary">
                {errorLabel(e)}
              </th>
              {reforms.map((s) => {
                const c = cell(e, s);
                if (!c) return <td key={s} className="text-center text-text-dim">·</td>;
                const a = Math.min(1, c.flip_rate / 0.65);
                return (
                  <td key={s}>
                    <div
                      title={`${fmtCr(c.revenue_error_crore)} revenue error${c.flipped.length ? " · " + c.flipped.join(", ") : ""}`}
                      className={cn(
                        "flex h-7 min-w-[3.5rem] items-center justify-center rounded-[3px] font-mono",
                        c.flip_rate === 0 ? "bg-ink-800 text-text-dim" : a > 0.45 ? "text-ink" : "text-text-primary"
                      )}
                      style={c.flip_rate > 0 ? { background: `rgb(var(--signal-rgb) / ${0.18 + 0.82 * a})` } : undefined}
                    >
                      {(c.flip_rate * 100).toFixed(0)}%
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Bar({ value, max, tone = "paper" }: { value: number; max: number; tone?: "paper" | "signal" }) {
  return (
    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
      <span
        className={cn("block h-full", tone === "signal" ? "bg-signal" : "bg-paper")}
        style={{ width: `${Math.max(0, Math.min(1, value / Math.max(max, 1e-9))) * 100}%` }}
      />
    </span>
  );
}

export default function ResearchPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [design, setDesign] = useState<Record<string, Design>>({});
  const [backtest, setBacktest] = useState<any>(null);
  const [sens, setSens] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [inj, setInj] = useState<InjRow[] | null>(null);
  const [story, setStory] = useState<StoryNumbers | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [inspected, setInspected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const get = (p: string) => fetch(`${API}${p}`).then((r) => (r.ok ? r.json() : null));
    Promise.all([
      get("/api/research/experiments"),
      get("/api/research/provision-sets"),
      get("/api/research/backtest"),
      get("/api/research/sensitivity"),
      get("/api/research/stats"),
      get("/api/research/error-injection"),
      get("/api/research/story"),
    ])
      .then(([e, d, b, s, st, ij, sy]) => {
        setStats(st);
        setInj(ij?.rows ?? null);
        setRuns(e?.runs ?? []);
        setDesign(d ?? {});
        setBacktest(b);
        setSens(s);
        setStory(sy);
        // ?set=<provision set>&inspect=<system> opens a specific case directly
        const q = new URLSearchParams(window.location.search);
        const wanted = q.get("set");
        if (d) setActive(wanted && wanted in d ? wanted : Object.keys(d)[0]);
        if (q.get("inspect")) setInspected(q.get("inspect"));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const systems = useMemo(() => Array.from(new Set((runs ?? []).map((r) => r.system))), [runs]);
  const sets = Object.keys(design);
  const runFor = (s: string, sys: string) => runs?.find((r) => r.set === s && r.system === sys);
  const assembled = (runs ?? []).filter((r) => r.complete);
  const flips = assembled.reduce((n, r) => n + r.flipped.length, 0);
  const num = (k: string) => story?.numbers[k]?.value ?? "—";

  const choose = (s: string) => {
    setActive(s);
    setInspected(null);
    const q = new URLSearchParams(window.location.search);
    q.set("set", s);
    q.delete("inspect");
    window.history.replaceState(null, "", `?${q}`);
  };

  if (error) return <div className="mx-auto max-w-3xl px-4 py-20"><ErrorState offline message={error} onRetry={() => window.location.reload()} /></div>;
  if (!runs) return <PageSkeleton />;

  return (
    <PageContainer>
      <PageHeader
        kicker="Research"
        title="Do machine-read rules reach the law's conclusions?"
        lede="Each reform is one year's change in personal income tax. Every reader extracts rules from the same provisions; one assembler turns them into tax parameters, and the same population is simulated under the expert coding and under each reading. A flip is a pre-registered conclusion (revenue direction, progressivity, which deciles gain) that differs from the expert's."
        actions={
          <Link href="/" className="inline-flex items-center gap-1.5 text-[14px] text-text-secondary underline-offset-4 hover:text-text-primary hover:underline">
            The story version <ArrowUpRight className="h-4 w-4" />
          </Link>
        }
      >
        <dl className="mt-10 grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-border bg-border sm:grid-cols-4">
          {[
            ["Reforms", sets.length],
            ["Readers", systems.length],
            ["Readings that assembled", `${assembled.length} of ${runs.length}`],
            ["Conclusions flipped", flips],
          ].map(([k, v]) => (
            <div key={String(k)} className="bg-bg-base px-5 py-4">
              <dt className="text-[12px] text-text-muted">{k}</dt>
              <dd className="mt-1 font-serif text-[2rem] leading-none text-text-primary">{v}</dd>
            </div>
          ))}
        </dl>
      </PageHeader>

      <nav
        aria-label="Sections"
        className="sticky top-14 z-sticky -mx-4 mb-8 flex gap-1 overflow-x-auto border-b border-border bg-bg-base/85 px-4 py-2 backdrop-blur-md sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
      >
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="shrink-0 rounded-[4px] px-3 py-1.5 text-[13px] text-text-muted hover:bg-bg-elevated hover:text-text-primary">
            {label}
          </a>
        ))}
      </nav>

      <section id="matrix" aria-labelledby="matrix-h" className="scroll-mt-32">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h2 id="matrix-h" className="font-serif text-title">Reforms × readers</h2>
          <p className="flex items-center gap-4 text-[12px] text-text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-3 w-5 rounded-[2px] bg-paper/90" />assembled</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-3 w-5 rounded-[2px] ring-1 ring-inset ring-signal bg-paper/90" />revenue differs</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-3 w-5 rounded-[2px] bg-ink-700" />no conclusion</span>
          </p>
        </div>
        <div className="overflow-x-auto rounded-[6px] border border-border">
          <table className="w-full min-w-[820px] text-[13px]">
            <caption className="sr-only">Share of pre-registered conclusions flipped, per reform and reader</caption>
            <thead className="bg-bg-surface">
              <tr>
                <th className="px-4 py-3 text-left font-normal text-text-muted">Reform</th>
                {systems.map((s) => (
                  <th key={s} className="px-2 py-3 text-center font-normal text-text-muted">{systemName(s)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sets.map((s) => (
                <tr key={s} className={cn("border-t border-border", active === s && "bg-bg-elevated")}>
                  <th scope="row" className="px-4 py-2 text-left font-normal">
                    <button
                      type="button"
                      onClick={() => choose(s)}
                      aria-pressed={active === s}
                      className="text-left hover:text-signal"
                    >
                      <span className="block text-[13.5px] text-text-primary">{reformLabel(s)}</span>
                      <span className="block font-mono text-[12px] text-text-dim">AY {design[s]?.ay}</span>
                    </button>
                  </th>
                  {systems.map((sys) => (
                    <td key={sys} className="px-2 py-2">
                      <Verdict run={runFor(s, sys)} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {active && design[active] && (
        <section id="reform" aria-labelledby="reform-h" className="mt-16 scroll-mt-32">
          <div className="kicker mb-2">One reform</div>
          <h2 id="reform-h" className="font-serif text-headline">{reformLabel(active)}</h2>
          <p className="mt-3 max-w-3xl text-[15px] text-text-secondary">{design[active].description}</p>
          <p className="mt-2 font-mono text-[12.5px] text-text-dim">
            {Object.entries(design[active].targets).map(([t, p]) => `${t} ← ${p}`).join("   ·   ")}
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {systems.map((sys) => {
              const r = runFor(active, sys);
              if (!r) return null;
              const exp = r.revenue_change_expert_crore ?? 0;
              const got = r.revenue_change_system_crore;
              const scale = Math.max(Math.abs(exp), Math.abs(got ?? 0), 1);
              const differs = got !== null && Math.abs(got - exp) > 1;
              return (
                <Panel
                  key={sys}
                  title={systemName(sys)}
                  actions={
                    <>
                      <Verdict run={r} />
                      <button
                        type="button"
                        onClick={() => setInspected(sys)}
                        className="inline-flex h-9 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary"
                      >
                        <Search className="h-3.5 w-3.5" /> Inspect
                      </button>
                    </>
                  }
                >
                  <div className="space-y-2 text-[13px]">
                    <p className="text-text-muted">Revenue change against the previous year&apos;s law</p>
                    {([["Expert", exp, "paper"], [systemName(sys), got, differs ? "signal" : "paper"]] as const).map(([label, v, tone]) => (
                      <div key={label} className="flex items-center gap-3">
                        <span className="w-28 truncate text-text-secondary">{label}</span>
                        {v !== null ? <Bar value={Math.abs(Number(v))} max={scale} tone={tone} /> : <span className="flex-1 text-text-dim">no reading</span>}
                        <span className={cn("w-32 text-right font-mono text-[12.5px]", tone === "signal" && "text-signal")}>
                          {fmtCr(v as number | null)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <dl className="mt-5 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-[13px]">
                    <dt className="text-text-muted">Effective-rate distance across deciles</dt>
                    <dd className="text-right font-mono">{r.decile_rate_l1 === null ? "—" : r.decile_rate_l1.toFixed(4)}</dd>
                    <dt className="text-text-muted">Kakwani, expert / reader</dt>
                    <dd className="text-right font-mono">{r.kakwani_expert?.toFixed(3)} / {r.kakwani_system?.toFixed(3) ?? "—"}</dd>
                    <dt className="text-text-muted">Quotes not found in the statute</dt>
                    <dd className="text-right font-mono">{r.hallucinated_fields}/{r.span_fields}</dd>
                    <dt className="text-text-muted">Self-consistency samples</dt>
                    <dd className="text-right font-mono">{r.samples}</dd>
                  </dl>
                  {r.attribution && <div className="mt-5"><AttributionBars a={r.attribution} complete={r.complete} /></div>}
                  {r.review.length > 0 && (
                    <ul className="mt-4 space-y-1 text-[13px] text-status-warning">
                      {r.review.map((v, i) => <li key={i}><span className="font-mono">{v.target}</span>: {v.reason}</li>)}
                    </ul>
                  )}
                  {r.param_diff.length > 0 && (
                    <p className="mt-3 text-[13px] text-signal-soft">Differs from the expert: <span className="font-mono">{r.param_diff.slice(0, 6).join(", ")}</span></p>
                  )}
                  {r.flipped.length > 0 && r.complete && <p className="mt-2 text-[13px] text-text-muted">Flipped: {r.flipped.join(", ")}</p>}
                </Panel>
              );
            })}
          </div>
          {inspected && (
            <div className="mt-6">
              <InspectPanel set={active} system={inspected} onClose={() => setInspected(null)} />
            </div>
          )}
        </section>
      )}

      {inj && inj.length > 0 && (
        <section id="injection" aria-labelledby="inj-h" className="mt-16 scroll-mt-32">
          <div className="kicker mb-2">Injected errors</div>
          <h2 id="inj-h" className="font-serif text-headline">Which mistakes change a conclusion?</h2>
          <p className="mb-6 mt-3 max-w-3xl text-[15px] text-text-secondary">
            Typed errors injected into the expert law, one provision at a time. Each cell is the share of pre-registered
            conclusions flipped by the worst injection of that kind in that reform; hover for the revenue error.
          </p>
          <Panel flush className="p-4"><InjectionMap rows={inj} /></Panel>
        </section>
      )}

      {stats && (
        <section id="robustness" aria-labelledby="rob-h" className="mt-16 grid scroll-mt-32 gap-4 lg:grid-cols-2">
          <h2 id="rob-h" className="sr-only">Robustness</h2>
          <Panel kicker="Robustness" title="Do flips survive population uncertainty?">
            <p className="mb-4 text-[13px] text-text-muted">
              {stats.draws} re-draws of the population assumptions. Persistence: share of draws where a flip remains. Noise
              floor: how often the expert&apos;s own conclusions move.
            </p>
            <div className="max-h-80 overflow-y-auto scroll-thin">
              <table className="w-full text-[13px]">
                <thead className="sticky top-0 bg-bg-surface text-text-muted">
                  <tr>
                    <th className="py-1 text-left font-normal">Reform · reader</th>
                    <th className="text-right font-normal">Flips</th>
                    <th className="text-right font-normal">Min persistence</th>
                    <th className="text-right font-normal">Noise floor</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.robustness.filter((r: any) => r.complete).map((r: any) => {
                    const p = Object.values(r.persistence as Record<string, number>);
                    return (
                      <tr key={r.set + r.system} className="border-t border-border">
                        <td className="py-1.5 pr-2 text-text-secondary">{reformLabel(r.set)} · {systemName(r.system)}</td>
                        <td className="text-right font-mono">{(r.flip_rate_calibrated * 100).toFixed(0)}%</td>
                        <td className="text-right font-mono">{p.length ? Math.min(...p).toFixed(2) : "—"}</td>
                        <td className="text-right font-mono">{r.noise_floor_mean.toFixed(3)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel kicker="Comparison" title="Readers against the expert">
            <p className="mb-4 text-[13px] text-text-muted">Agreement on paired conclusions; exact McNemar tests, Holm-corrected.</p>
            <div className="space-y-2">
              {Object.entries(stats.systems.agreement_rate as Record<string, number>).map(([s, v]) => (
                <div key={s} className="flex items-center gap-3 text-[13px]">
                  <span className="w-28 truncate text-text-secondary">{systemName(s)}</span>
                  <Bar value={v} max={1} />
                  <span className="w-28 text-right font-mono">{(v * 100).toFixed(1)}% of {stats.systems.conclusions[s]}</span>
                </div>
              ))}
            </div>
            <div className="mt-5 space-y-1 border-t border-border pt-4">
              {Object.entries(stats.systems.tests as Record<string, any>).map(([k, t]) => (
                <p key={k} className="flex justify-between gap-4 text-[13px] text-text-secondary">
                  <span>{k}</span>
                  <span className="font-mono">p = {t.p_holm < 0.001 ? "<0.001" : t.p_holm.toFixed(3)}</span>
                </p>
              ))}
            </div>
          </Panel>
        </section>
      )}

      {backtest && (
        <section id="validation" aria-labelledby="val-h" className="mt-16 scroll-mt-32">
          <div className="kicker mb-2">Validation</div>
          <h2 id="val-h" className="mb-6 font-serif text-headline">Does the population model match reality?</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <Panel title="In sample">
              {backtest.in_sample.map((r: any) => (
                <p key={r.ay} className="flex justify-between py-0.5 text-[13px]">
                  <span className="text-text-secondary">AY {r.ay}</span>
                  <span className="font-mono">simulated / reported {r.ratio.toFixed(3)}</span>
                </p>
              ))}
            </Panel>
            <Panel title="Forecast, held out">
              <p className="mb-2 text-[13px] text-text-muted">Ageing method chosen on selection years: {backtest.forecast.chosen_method.replace(/_/g, " ")}</p>
              {backtest.forecast.test.map((t: any) => (
                <p key={t.base_ay + t.target_ay} className="flex justify-between gap-3 py-0.5 text-[13px]">
                  <span className="text-text-secondary">{t.base_ay} → {t.target_ay}</span>
                  <span className={cn("font-mono", t.ape_model > t.ape_naive && "text-status-warning")}>
                    {(t.ape_model * 100).toFixed(1)}% vs naive {(t.ape_naive * 100).toFixed(1)}%
                  </span>
                </p>
              ))}
            </Panel>
            <Panel title="Reform cost">
              {backtest.reform_cost.map((r: any) => (
                <p key={r.reform} className="flex justify-between gap-3 py-0.5 text-[13px]">
                  <span className="text-text-secondary">{r.reform}</span>
                  <span className="font-mono">{fmtCr(r.simulated_cost_crore)} vs {fmtCr(r.announced_cost_crore)} announced</span>
                </p>
              ))}
            </Panel>
          </div>
        </section>
      )}

      {sens && (
        <section id="sensitivity" aria-labelledby="sens-h" className="mt-16 scroll-mt-32">
          <div className="kicker mb-2">Sensitivity</div>
          <h2 id="sens-h" className="mb-6 font-serif text-headline">What drives the simulated outcomes</h2>
          <Panel title="Sobol total-order index">
            <div className="grid gap-8 md:grid-cols-2">
              {Object.entries(sens.sobol as Record<string, Record<string, { ST: number }>>).map(([out, idx]) => (
                <div key={out}>
                  <p className="mb-2 font-mono text-[12.5px] text-text-muted">{out}</p>
                  {Object.entries(idx).sort((a, b) => b[1].ST - a[1].ST).map(([name, v]) => (
                    <div key={name} className="flex items-center gap-3 py-0.5 text-[13px]">
                      <span className="w-36 truncate text-text-secondary">{name.replace(/_/g, " ")}</span>
                      <Bar value={v.ST} max={1} />
                      <span className="w-12 text-right font-mono">{v.ST.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Panel>
        </section>
      )}

      {story && (
        <section id="beyond" aria-labelledby="beyond-h" className="mt-16 scroll-mt-32">
          <div className="kicker mb-2">Beyond the headline</div>
          <h2 id="beyond-h" className="mb-6 font-serif text-headline">Behaviour, explanations, retrieval</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <Panel title="Compliance behaviour" actions={<Tag>agent-based</Tag>}>
              <p className="text-[14px] leading-relaxed text-text-secondary">
                Tax gap with the statutory {Math.round((story.behaviour?.expert_penalty ?? 0) * 100)}% penalty: median <b className="font-mono font-normal text-text-primary">{num("bhgapmedian")}</b>{" "}
                ({num("bhgapfive")}–{num("bhgapninetyfive")}). Misreading it as {Math.round((story.behaviour?.misread_penalty ?? 0) * 100)}% raises the gap by{" "}
                <b className="font-mono font-normal text-signal">{num("bhdiffmean")}</b>. {num("bhcorrect")} readers found the
                penalty rate.
              </p>
            </Panel>
            <Panel title="Faithfulness of cited spans">
              <p className="text-[14px] leading-relaxed text-text-secondary">
                ERASER comprehensiveness of gpt-oss-120b&apos;s cited spans{" "}
                <b className="font-mono font-normal text-text-primary">{num("faithcomprehensiveness@gpt-oss-120b@dev")}</b>,
                random spans of the same length{" "}
                <b className="font-mono font-normal text-text-primary">{num("faithrandomcomprehensiveness@gpt-oss-120b@dev")}</b>.
                The citations are no better than chance.
              </p>
            </Panel>
            <Panel title="Retrieval for the Ask view">
              <p className="text-[14px] leading-relaxed text-text-secondary">
                Recall at five <b className="font-mono font-normal text-text-primary">{num("ragrfive@hybrid-minilm+rerank")}</b>{" "}
                over {num("ragqueries")} questions with BM25, MiniLM and a re-ranker; unanswerable questions separated with AUROC{" "}
                {num("ragauroc@hybrid-minilm+rerank")}.
              </p>
            </Panel>
          </div>
          <Callout className="mt-6" title="Where these numbers come from">
            Every figure on this page is read from the result files the paper is built from (<span className="font-mono">python -m cli reproduce</span>);
            none is computed in the browser except formatting.
          </Callout>
        </section>
      )}
    </PageContainer>
  );
}
