"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Table2 } from "lucide-react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { API_BASE } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ScheduleRow {
  label: string;
  text: string;
  lower: number | null;
  upper: number | null;
  rate: number | null;
}
export interface Schedule {
  page: number;
  kind: "boxed" | "two_column";
  heading: string;
  assessment_year: string | null;
  rows: ScheduleRow[];
  check: { ok: boolean; reason: string | null };
}

export const rupees = (v: number | null) => {
  if (v === null) return "—";
  if (v >= 1e7) return `₹${+(v / 1e7).toFixed(2)} crore`;
  if (v >= 1e5) return `₹${+(v / 1e5).toFixed(2)} lakh`;
  return `₹${v.toLocaleString("en-IN")}`;
};

export function band(r: ScheduleRow): string {
  if (r.lower === null) return "—";
  if (r.upper === null) return `above ${rupees(r.lower)}`;
  if (r.lower === 0) return `up to ${rupees(r.upper)}`;
  return `${rupees(r.lower)} – ${rupees(r.upper)}`;
}

/** One schedule: where it is, whom it covers, its bands, and whether it is
 *  complete. Each band is read from the words of its own row, shown beside it. */
export function ScheduleCard({ s, onPage }: { s: Schedule; onPage?: (page: number) => void }) {
  return (
    <section className="rounded-[6px] border border-border bg-bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => onPage?.(s.page)}
            className="font-mono text-[12px] text-text-muted hover:text-text-primary"
            title="Show this page in the document"
          >
            p.{s.page}
            {s.assessment_year && ` · AY ${s.assessment_year}`}
          </button>
          <p className="mt-0.5 text-[13px] leading-snug text-text-secondary">{s.heading || "Rate table"}</p>
        </div>
        {s.check.ok ? (
          <span className="inline-flex items-center gap-1 text-[12px] text-status-success">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> complete schedule
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[12px] text-status-warning">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> needs review: {s.check.reason}
          </span>
        )}
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <caption className="sr-only">Bands of the rate table on page {s.page}</caption>
          <thead>
            <tr className="text-left text-[12px] text-text-muted">
              <th className="px-4 py-2 font-normal">Income</th>
              <th className="px-2 py-2 text-right font-normal">Rate</th>
              <th className="px-4 py-2 font-normal">As printed</th>
            </tr>
          </thead>
          <tbody>
            {s.rows.map((r, i) => (
              <tr key={i} className="border-t border-border align-top">
                <td className="whitespace-nowrap px-4 py-1.5 font-mono text-text-primary">{band(r)}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-right font-mono text-text-primary">
                  {r.rate === null ? "—" : `${+(r.rate * 100).toFixed(2)}%`}
                </td>
                <td className={cn("min-w-[16rem] px-4 py-1.5 text-[12px] leading-snug", r.rate === null ? "text-status-warning" : "text-text-muted")}>
                  {r.text}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function RatesTab() {
  const { docId, setPdfPage } = useDocumentStore();
  const [data, setData] = useState<{ schedules: Schedule[]; review: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) return;
    setData(null);
    setError(null);
    fetch(`${API_BASE}/api/schedules/${docId}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(String(e.message ?? e)));
  }, [docId]);

  return (
    <div className="space-y-4 p-4">
      <div>
        <p className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-text-muted">
          <Table2 className="h-3.5 w-3.5" aria-hidden /> Rate schedules
        </p>
        <p className="mt-1 max-w-prose text-[13px] text-text-muted">
          Every rate table in the document, read row by row into bands and checked: it starts at zero, its bands meet
          without gaps or overlaps, its top band is open, and its rates do not fall.
        </p>
      </div>
      {error && <p className="text-[13px] text-status-error">Could not read the schedules ({error}).</p>}
      {!data && !error && <div className="shimmer h-40 rounded-[6px]" aria-busy="true" />}
      {data && data.schedules.length === 0 && (
        <p className="text-[13px] text-text-muted">No rate tables were found in this document.</p>
      )}
      {data && data.schedules.length > 0 && (
        <>
          <p className="text-[13px] text-text-secondary">
            {data.schedules.length} schedule{data.schedules.length === 1 ? "" : "s"}
            {data.review > 0 ? `, ${data.review} needing review` : ", all complete"}.
          </p>
          {data.schedules.map((s, i) => (
            <ScheduleCard key={i} s={s} onPage={setPdfPage} />
          ))}
        </>
      )}
    </div>
  );
}
