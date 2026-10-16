"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api";
import { systemName } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface DecileRow {
  decile: number;
  income_upper: number;
  before: number;
  expert: number;
  system?: number;
}
interface DecileData {
  ay: string;
  set: string | null;
  system: string | null;
  deciles: DecileRow[];
}

const pct = (v: number) => `${(v * 100).toFixed(v < 0.1 ? 2 : 1)}%`;
const lakh = (v: number) => `₹${(v / 100000).toFixed(v < 1000000 ? 1 : 0)}L`;

/**
 * Who pays: the effective income-tax rate in each tenth of the taxpayer
 * population under last year's law, the expert coding of this reform, and one
 * reader's version of it. Same engine, same population.
 */
export default function DecileView({ set, readers }: { set: string; readers: string[] }) {
  const [reader, setReader] = useState(readers[0] ?? "");
  const [data, setData] = useState<DecileData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!readers.includes(reader)) setReader(readers[0] ?? "");
  }, [readers, reader]);
  useEffect(() => {
    if (!reader) return;
    let live = true;
    setData(null);
    setError(null);
    fetch(`${API_BASE}/api/research/population/${set}/${reader}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => live && setData(d))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [set, reader]);

  const max = useMemo(
    () => (data ? Math.max(0.0001, ...data.deciles.flatMap((d) => [d.before, d.expert, d.system ?? 0])) : 1),
    [data]
  );
  const differs = data?.deciles.some((d) => d.system !== undefined && Math.abs(d.system - d.expert) > 0.0005);

  if (readers.length === 0) return null;
  return (
    <div className="glass-card mt-6 p-5">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="kicker mb-1">Who pays</div>
          <h3 className="text-[15px] font-medium text-text-primary">Effective tax rate by tenth of taxpayers{data ? `, AY ${data.ay}` : ""}</h3>
          <p className="mt-1 max-w-2xl text-[13px] text-text-muted">
            The same population and engine under last year&apos;s law, the expert coding of this reform, and one
            reader&apos;s version. Only readings that assembled into a schedule are listed.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Reader
          <select
            value={reader}
            onChange={(e) => setReader(e.target.value)}
            className="h-9 rounded-[4px] border border-border-light bg-bg-surface px-2.5 text-[13px] text-text-primary"
          >
            {readers.map((r) => (
              <option key={r} value={r}>
                {systemName(r)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="text-[13px] text-text-muted">No decile view for this reading ({error}).</p>}
      {!data && !error && <div className="shimmer h-48 rounded-[4px]" aria-busy="true" />}
      {data && (
        <>
          <div className="flex h-52 items-end gap-2 border-b border-border sm:gap-3" role="img" aria-label="Effective tax rate by decile">
            {data.deciles.map((d) => (
              <div key={d.decile} className="group relative flex h-full flex-1 items-end justify-center gap-[2px]">
                {(
                  [
                    ["before", d.before, "bg-ink-500"],
                    ["expert", d.expert, "bg-paper"],
                    ["system", d.system, d.system !== undefined && Math.abs(d.system - d.expert) > 0.0005 ? "bg-signal" : "bg-entity-right"],
                  ] as const
                ).map(([k, v, cls]) =>
                  v === undefined ? null : (
                    <div
                      key={k}
                      className={cn("w-full max-w-[14px] rounded-t-[3px] transition-[height] duration-500", cls)}
                      style={{ height: `${Math.max(1.5, (v / max) * 100)}%` }}
                    />
                  )
                )}
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-44 -translate-x-1/2 rounded-[4px] border border-border-light bg-bg-overlay p-2.5 text-[12px] opacity-0 shadow-lift transition-opacity group-hover:opacity-100">
                  <div className="mb-1 text-text-primary">
                    Decile {d.decile} · up to {lakh(d.income_upper)}
                  </div>
                  <div className="flex justify-between text-text-muted">
                    <span>last year</span>
                    <span className="font-mono">{pct(d.before)}</span>
                  </div>
                  <div className="flex justify-between text-text-secondary">
                    <span>the law</span>
                    <span className="font-mono">{pct(d.expert)}</span>
                  </div>
                  {d.system !== undefined && (
                    <div className="flex justify-between text-text-secondary">
                      <span>{systemName(reader)}</span>
                      <span className="font-mono">{pct(d.system)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-2 sm:gap-3">
            {data.deciles.map((d) => (
              <div key={d.decile} className="flex-1 text-center font-mono text-[12px] text-text-dim">
                {d.decile}
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-text-muted">
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-[2px] bg-ink-500" aria-hidden /> last year&apos;s law
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-[2px] bg-paper" aria-hidden /> the law (expert coding)
            </span>
            <span className="flex items-center gap-2">
              <span className={cn("h-2.5 w-2.5 rounded-[2px]", differs ? "bg-signal" : "bg-entity-right")} aria-hidden /> {systemName(reader)}
              {differs ? " (differs)" : " (matches)"}
            </span>
          </div>
          <table className="sr-only">
            <caption>Effective tax rate by decile</caption>
            <thead>
              <tr>
                <th>Decile</th>
                <th>Last year</th>
                <th>The law</th>
                <th>{systemName(reader)}</th>
              </tr>
            </thead>
            <tbody>
              {data.deciles.map((d) => (
                <tr key={d.decile}>
                  <td>{d.decile}</td>
                  <td>{pct(d.before)}</td>
                  <td>{pct(d.expert)}</td>
                  <td>{d.system !== undefined ? pct(d.system) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
