/**
 * DOM and SVG versions of every scene. They are the whole story on devices
 * without WebGL (tier 0) or with reduced motion, and the screen-reader
 * equivalent of the canvas everywhere else.
 */
import * as React from "react";
import { tokens } from "@/design/tokens";
import { cn } from "@/lib/utils";
import { ERROR_LABEL, SYSTEM_LABEL, inr, lakh, pct, reformLabel, story } from "./data";

/** The provision with what was read (blue) and what was missed (vermilion). */
export function ProvisionCard({ className }: { className?: string }) {
  const text = story.focus.text;
  const quoted = story.focus.effects.find((e) => e.span)?.span ?? null;
  const cb = text.indexOf("in clause (b)");
  const missed: [number, number] | null = cb >= 0 ? [cb, text.indexOf(";", cb) + 1 || text.length] : null;
  const cuts = Array.from(new Set([0, text.length, ...(quoted ?? []), ...(missed ?? [])])).sort((a, b) => a - b);
  const parts: { t: string; kind: "read" | "missed" | null }[] = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const [a, b] = [cuts[i], cuts[i + 1]];
    const kind = missed && a >= missed[0] && b <= missed[1] ? "missed" : quoted && a >= quoted[0] && b <= quoted[1] ? "read" : null;
    parts.push({ t: text.slice(a, b), kind });
  }
  return (
    <figure className={cn("surface-paper rounded-[6px] p-6 shadow-lift sm:p-8", className)}>
      <figcaption className="mb-4 font-mono text-micro uppercase tracking-[0.14em] text-ink/60">
        The Finance Act, 2025 · {story.focus.provision.replace("/", " ")}
      </figcaption>
      <p className="statute-text whitespace-pre-line font-serif text-[17px] leading-[1.65] text-ink">
        {parts.map((p, i) =>
          p.kind === "read" ? (
            <mark key={i} className="rounded-[2px] bg-[rgba(47,98,200,0.14)] px-0.5 text-ink">
              {p.t}
            </mark>
          ) : p.kind === "missed" ? (
            <mark key={i} className="rounded-[2px] bg-signal/20 px-0.5 text-signal-ink">
              {p.t}
            </mark>
          ) : (
            <React.Fragment key={i}>{p.t}</React.Fragment>
          )
        )}
      </p>
      <div className="mt-5 flex flex-wrap gap-4 text-[12px] text-ink/70">
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-5 rounded-[2px] bg-[rgba(47,98,200,0.25)]" aria-hidden /> words the model quoted
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-5 rounded-[2px] bg-signal/30" aria-hidden /> the clause it missed
        </span>
      </div>
    </figure>
  );
}

export function FieldList({ className }: { className?: string }) {
  const ex = story.focus.extracted;
  const law = story.focus.expert;
  const rows: [string, string, string, boolean][] = [
    ["Income limit", `₹${inr(ex.max_income)}`, `₹${inr(law.max_income)}`, ex.max_income === law.max_income],
    ["Maximum rebate", `₹${inr(ex.max_rebate)}`, `₹${inr(law.max_rebate)}`, ex.max_rebate === law.max_rebate],
    ["Marginal relief", String(ex.marginal_relief), String(law.marginal_relief), ex.marginal_relief === law.marginal_relief],
  ];
  return (
    <table className={cn("w-full border-collapse text-left text-[14px]", className)}>
      <caption className="sr-only">What the model read from section 20, against the expert coding</caption>
      <thead>
        <tr className="border-b border-border text-micro uppercase tracking-[0.12em] text-text-dim">
          <th className="py-2 font-normal">Field</th>
          <th className="py-2 font-normal">Model read</th>
          <th className="py-2 font-normal">The law</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([f, a, b, ok]) => (
          <tr key={f} className="border-b border-border">
            <th scope="row" className="py-2.5 font-normal text-text-secondary">
              {f}
            </th>
            <td className={cn("py-2.5 font-mono", ok ? "text-text-primary" : "text-signal")}>
              {a} <span aria-label={ok ? "correct" : "wrong"}>{ok ? "✓" : "✕"}</span>
            </td>
            <td className="py-2.5 font-mono text-text-secondary">{b}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Tax on a salary: last year's law, this year's law and the model's reading. */
export function CurveFigure({ className }: { className?: string }) {
  const { salary, series, largest_gap } = story.curve;
  const W = 640;
  const H = 360;
  const P = { l: 56, r: 16, t: 16, b: 36 };
  const smax = salary[salary.length - 1];
  const tmax = Math.max(...series.system, ...series.expert, ...series.before);
  const x = (s: number) => P.l + (s / smax) * (W - P.l - P.r);
  const y = (t: number) => H - P.b - (t / tmax) * (H - P.t - P.b);
  const path = (v: number[]) => v.map((t, i) => `${i ? "L" : "M"}${x(salary[i]).toFixed(1)},${y(t).toFixed(1)}`).join("");
  const gx = x(largest_gap.salary);
  return (
    <figure className={cn("w-full", className)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-labelledby="curve-title">
        <title id="curve-title">{`New-regime tax on a salary up to ₹${lakh(smax)}. At ₹${lakh(largest_gap.salary)} the law gives ₹${inr(largest_gap.expert)} and the model's reading ₹${inr(largest_gap.system)}.`}</title>
        {[5, 10, 15, 20, 25].map((l) => (
          <g key={l}>
            <line x1={x(l * 1e5)} x2={x(l * 1e5)} y1={P.t} y2={H - P.b} stroke={tokens.paper[100]} strokeOpacity={0.06} />
            <text x={x(l * 1e5)} y={H - 12} textAnchor="middle" fontSize="12" fill={tokens.paper[400]} fontFamily="var(--font-geist-mono)">
              ₹{l}L
            </text>
          </g>
        ))}
        <path d={path(series.before)} fill="none" stroke={tokens.paper[400]} strokeDasharray="4 4" strokeWidth={1.2} />
        <path d={path(series.expert)} fill="none" stroke={tokens.paper[100]} strokeWidth={2} />
        <path d={path(series.system)} fill="none" stroke={tokens.signal[500]} strokeWidth={2} />
        <line x1={gx} x2={gx} y1={y(largest_gap.expert)} y2={y(largest_gap.system)} stroke={tokens.signal[500]} strokeWidth={6} strokeOpacity={0.35} />
      </svg>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-text-muted">
        <span className="inline-flex items-center gap-2">
          <span className="h-px w-5 border-t border-dashed border-paper-400" aria-hidden /> law for the previous year
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-0.5 w-5 bg-paper" aria-hidden /> the law, AY {story.deciles.ay}
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-0.5 w-5 bg-signal" aria-hidden /> {SYSTEM_LABEL[story.focus.system]}&apos;s reading
        </span>
      </figcaption>
    </figure>
  );
}

/** Effective tax rate by decile, before and after the reform. */
export function DecileFigure({ className }: { className?: string }) {
  const ds = story.deciles.deciles;
  const max = Math.max(...ds.map((d) => Math.max(d.before, d.expert, d.system ?? 0)));
  return (
    <figure className={cn("w-full", className)}>
      <div className="flex h-44 items-end gap-1.5" aria-hidden>
        {ds.map((d) => (
          <div key={d.decile} className="flex h-full flex-1 flex-col justify-end gap-0.5">
            <div className="flex h-full items-end gap-[2px]">
              <div className="flex-1 rounded-t-[2px] bg-paper-400/40" style={{ height: `${(d.before / max) * 100}%` }} />
              <div className="flex-1 rounded-t-[2px] bg-paper" style={{ height: `${(d.expert / max) * 100}%` }} />
            </div>
            <div className="text-center font-mono text-micro text-text-dim">D{d.decile}</div>
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>Effective income-tax rate by income decile</caption>
        <thead>
          <tr>
            <th>Decile</th>
            <th>Previous year&apos;s law</th>
            <th>AY {story.deciles.ay} law</th>
            <th>{SYSTEM_LABEL[story.focus.system]}&apos;s reading</th>
          </tr>
        </thead>
        <tbody>
          {ds.map((d) => (
            <tr key={d.decile}>
              <td>{d.decile}</td>
              <td>{pct(d.before, 2)}</td>
              <td>{pct(d.expert, 2)}</td>
              <td>{d.system != null ? pct(d.system, 2) : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <figcaption className="mt-3 flex gap-5 text-[12px] text-text-muted">
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-[2px] bg-paper-400/40" aria-hidden /> previous year
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-[2px] bg-paper" aria-hidden /> AY {story.deciles.ay}
        </span>
      </figcaption>
    </figure>
  );
}

export function VerdictTable({ className }: { className?: string }) {
  const { reforms, systems, cells } = story.matrix;
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full min-w-[560px] border-collapse text-[13px]">
        <caption className="sr-only">
          For each reform and reader: whether the reading assembled into a complete law, and how many conclusions flipped
        </caption>
        <thead>
          <tr>
            <th className="py-2 pr-3 text-left font-normal text-text-dim">Reform</th>
            {systems.map((s) => (
              <th key={s.id} className="px-1 py-2 text-center text-[12px] font-normal text-text-muted">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reforms.map((r) => (
            <tr key={r.id} className="border-t border-border">
              <th scope="row" className="py-1.5 pr-3 text-left font-mono text-micro font-normal text-text-muted">
                {reformLabel(r.id)}
              </th>
              {systems.map((s) => {
                const c = cells.find((x) => x.set === r.id && x.system === s.id);
                const ok = c?.status === "assembled";
                return (
                  <td key={s.id} className="px-1 py-1.5 text-center">
                    <span
                      className={cn(
                        "inline-flex h-7 w-full items-center justify-center rounded-[3px] font-mono text-micro",
                        ok ? "bg-paper/85 text-ink" : "bg-ink-700 text-text-dim"
                      )}
                      title={ok ? `${c?.flips} flips` : (c?.reasons ?? []).join(", ")}
                    >
                      {ok ? `${c?.flips} flips` : "no conclusion"}
                    </span>
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

export function FaultBars({ className }: { className?: string }) {
  const kinds = story.injection.kinds;
  return (
    <ul className={cn("space-y-1.5", className)}>
      {kinds.map((k) => (
        <li key={k.error} className="grid grid-cols-[minmax(0,13rem)_1fr_3.5rem] items-center gap-3 text-[13px]">
          <span className="truncate text-text-secondary">{ERROR_LABEL[k.error] ?? k.error}</span>
          <span className="h-2 rounded-full bg-ink-700">
            <span
              className={cn("block h-2 rounded-full", k.max_flip_rate > 0 ? "bg-signal" : "bg-paper-400")}
              style={{ width: `${Math.max(1.5, k.max_flip_rate * 100)}%` }}
            />
          </span>
          <span className="text-right font-mono text-text-primary">{pct(k.max_flip_rate)}</span>
        </li>
      ))}
    </ul>
  );
}
