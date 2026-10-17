"use client";

import { useEffect, useState } from "react";
import { Callout, Panel, Tag } from "@/components/ui/kit";
import { API_BASE as API } from "@/lib/api";
import { reformLabel, systemName } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface Reform {
  set: string; first_complete: boolean; first_flip_rate: number; complete: boolean; flip_rate: number;
  repairs: number; review: { target: string; reason: string }[];
}
interface Counts { assembled: number; no_flip: number; reforms: number }
interface Variant {
  variant: string; first_pass: Counts; repaired: Counts | null; reforms: Reform[];
  repairs_asked?: number; assembled_by_repair?: number; repaired_but_flipped?: number;
}
export interface SystemRow { system: string; headline: Counts | null; variants: Variant[] }
export interface HeldoutRow {
  system: string;
  condition: string;
  reforms: number;
  first_pass: { assembled: number; no_flip: number };
  final: { assembled: number; no_flip: number };
  repairs: number;
  numbers: { fields: number; in_quote: number; in_provision: number; missing: number } | null;
}
export interface HeadlineRun { set: string; system: string; complete: boolean; flip_rate: number | null }

const VARIANT: Record<string, string> = {
  tables: "Rebuilt tables",
  "tables+json": "Rebuilt tables, JSON mode",
  "tables+schema": "Rebuilt tables, schema decoding",
};

type State = "kept" | "flipped" | "none";

function Strip({ cells, label }: { cells: { set: string; state: State; note?: string }[]; label: string }) {
  const kept = cells.filter((c) => c.state === "kept").length;
  return (
    <div className="flex items-center gap-3">
      <span className="flex gap-[3px]" role="img" aria-label={`${label}: ${kept} of ${cells.length} reforms keep every conclusion`}>
        {cells.map((c) => (
          <span
            key={c.set}
            title={`${reformLabel(c.set)}: ${c.state === "kept" ? "every conclusion kept" : c.state === "flipped" ? "a conclusion flipped" : "no conclusion"}${c.note ? ` (${c.note})` : ""}`}
            className={cn(
              "h-4 w-4 rounded-[2px]",
              c.state === "kept" && "bg-contrast/90",
              c.state === "flipped" && "bg-status-critical/85",
              c.state === "none" && "bg-[repeating-linear-gradient(135deg,rgb(var(--ink-700-rgb))_0_3px,rgb(var(--ink-800-rgb))_3px_6px)] ring-1 ring-inset ring-border"
            )}
          />
        ))}
      </span>
      <span className="font-mono text-[12.5px] tabular-nums text-text-secondary">
        {kept}/{cells.length}
      </span>
    </div>
  );
}

const state = (complete: boolean, flip: number | null): State => (!complete ? "none" : (flip ?? 0) > 0 ? "flipped" : "kept");

/**
 * The structured condition against the headline: for each reader, ten
 * reform tiles per condition (text only; rebuilt tables, first pass; after
 * one repair round).
 */
export default function StructuredView({ headline, sets }: { headline: HeadlineRun[]; sets: string[] }) {
  const [rows, setRows] = useState<SystemRow[] | null>(null);
  const [note, setNote] = useState("");
  const [heldout, setHeldout] = useState<HeldoutRow[] | null>(null);

  useEffect(() => {
    fetch(`${API}/api/research/structured`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setRows(d?.systems ?? []);
        setNote(d?.note ?? "");
        setHeldout(d?.heldout ?? null);
      })
      .catch(() => setRows([]));
  }, []);

  if (!rows || rows.length === 0) return null;
  return <StructuredSection rows={rows} note={note} headline={headline} sets={sets} heldout={heldout} />;
}

export function StructuredSection({
  rows,
  note,
  headline,
  sets,
  heldout = null,
}: {
  rows: SystemRow[];
  note: string;
  headline: HeadlineRun[];
  sets: string[];
  heldout?: HeldoutRow[] | null;
}) {
  return (
    <section id="structured" aria-labelledby="structured-h" className="mt-16 scroll-mt-32">
      <div className="kicker mb-2">Structured reading</div>
      <h2 id="structured-h" className="font-serif text-headline">Reading the table as printed</h2>
      <p className="mt-3 max-w-3xl text-[15px] text-text-secondary">
        Most readings above fail while being assembled, and two schedules reach every reader with their columns
        interleaved. Here each reader also gets the provision&apos;s rate tables rebuilt row by row from the PDF,
        decoding constrained to the answer&apos;s shape where the provider supports it, and one chance to correct a
        reading that fails a structural check. The check names the rule it broke, never a value.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-4 text-[12px] text-text-muted">
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-[2px] bg-contrast/90" />every conclusion kept</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-[2px] bg-status-critical/85" />a conclusion flipped</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-[2px] bg-ink-700 ring-1 ring-inset ring-border" />no conclusion</span>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {rows.map((row) => {
          const head = sets.map((s) => {
            const r = headline.find((h) => h.set === s && h.system === row.system);
            return { set: s, state: r ? state(r.complete, r.flip_rate) : ("none" as State) };
          });
          return (
            <Panel key={row.system} title={systemName(row.system)}>
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 text-[13px]">
                {row.headline && (
                  <>
                    <dt className="text-text-muted">Headline: canonical text only</dt>
                    <dd><Strip cells={head} label="headline" /></dd>
                  </>
                )}
                {row.variants.map((v) => {
                  const by = (s: string) => v.reforms.find((x) => x.set === s);
                  const first = sets.map((s) => {
                    const x = by(s);
                    return { set: s, state: x ? state(x.first_complete, x.first_flip_rate) : ("none" as State) };
                  });
                  const last = sets.map((s) => {
                    const x = by(s);
                    return {
                      set: s,
                      state: x ? state(x.complete, x.flip_rate) : ("none" as State),
                      note: x && x.repairs ? `${x.repairs} repair${x.repairs > 1 ? "s" : ""}` : undefined,
                    };
                  });
                  return (
                    <div key={v.variant} className="contents">
                      <dt className="text-text-muted">{VARIANT[v.variant] ?? v.variant}</dt>
                      <dd><Strip cells={first} label={`${v.variant} first pass`} /></dd>
                      {v.repaired && (
                        <>
                          <dt className="pl-4 text-text-muted">after one repair</dt>
                          <dd><Strip cells={last} label={`${v.variant} after repair`} /></dd>
                        </>
                      )}
                    </div>
                  );
                })}
              </dl>
              {row.variants.some((v) => v.repaired) && (
                <p className="mt-4 text-[12.5px] text-text-muted">
                  {row.variants
                    .filter((v) => v.repaired)
                    .map((v) => `${VARIANT[v.variant] ?? v.variant}: ${v.repairs_asked} repair${v.repairs_asked === 1 ? "" : "s"} asked, ${v.assembled_by_repair} assembled by it${v.repaired_but_flipped ? `, ${v.repaired_but_flipped} of those flipped a conclusion` : ""}`)
                    .join(" · ")}
                </p>
              )}
            </Panel>
          );
        })}
      </div>
      {note && (
        <Callout tone={heldout ? "info" : "warn"} className="mt-6" title="Read with care">
          {note} {!heldout && <Tag className="ml-1">same reforms</Tag>}
        </Callout>
      )}
      {heldout && heldout.length > 0 && (
        <Panel kicker="Held-out check, fixed before any run" title="Five reforms not opened while this was built" className="mt-4" flush>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-[13px]">
              <caption className="sr-only">Held-out reforms: conclusions kept and numbers found in their quotes</caption>
              <thead>
                <tr className="text-left text-[12px] text-text-muted">
                  <th className="px-4 py-2 font-normal">Reader</th>
                  <th className="px-2 py-2 font-normal">Condition</th>
                  <th className="px-2 py-2 text-right font-normal">No flip, first pass</th>
                  <th className="px-2 py-2 text-right font-normal">After one repair</th>
                  <th className="px-4 py-2 text-right font-normal">Numbers in their quote</th>
                </tr>
              </thead>
              <tbody>
                {heldout.map((h) => (
                  <tr key={`${h.system}-${h.condition}`} className="border-t border-border">
                    <td className="px-4 py-1.5 text-text-primary">{systemName(h.system)}</td>
                    <td className="px-2 py-1.5 text-text-muted">{h.condition === "headline" ? "canonical text" : VARIANT[h.condition] ?? h.condition}</td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums">{h.first_pass.no_flip}/{h.reforms}</td>
                    <td className="px-2 py-1.5 text-right font-mono tabular-nums">{h.final.no_flip}/{h.reforms}</td>
                    <td className="px-4 py-1.5 text-right font-mono tabular-nums">
                      {h.numbers && h.numbers.fields ? `${((100 * h.numbers.in_quote) / h.numbers.fields).toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </section>
  );
}
