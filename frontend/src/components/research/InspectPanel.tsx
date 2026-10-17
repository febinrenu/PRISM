"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, X } from "lucide-react";
import { API_BASE } from "@/lib/api";

const API = API_BASE;

interface NumberCheck {
  status: "verified" | "provision" | "unsupported" | "unchecked";
  fields: { field: string; value: number; found: "quote" | "provision" | "missing" }[];
}
interface Effect {
  kind: string; modality: string; quote: string | null; span: [number, number] | null;
  numbers?: NumberCheck;
  [field: string]: unknown;
}
interface UnitView { path: string; text: string; status: string; rules: number; hallucinated_fields: number; effects: Effect[] }
interface TargetView { target: string; provision: string; review: string | null; expert: unknown; system: unknown; units: UnitView[] }
interface Inspect { set: string; system: string; ay: string; statute: string; complete: boolean | null; targets: TargetView[] }

const lakh = (v: unknown) => {
  if (typeof v !== "number") return "—";
  return v >= 1e5 ? `₹${(v / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 2 })} lakh` : `₹${v.toLocaleString("en-IN")}`;
};
const pct = (v: unknown) => (typeof v === "number" ? `${+(v * 100).toFixed(2)}%` : "—");

/** A parameter value (slab table, rebate, deduction, rate) in plain words. */
function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) {
    return v.map((s: { lower: number; upper: number | null; rate: number }) =>
      `${lakh(s.lower)}–${s.upper === null ? "∞" : lakh(s.upper)}: ${pct(s.rate)}`).join(" · ");
  }
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("max_rebate" in o) {
      return `${lakh(o.max_rebate)} up to income ${lakh(o.max_income)}${o.marginal_relief ? ", with marginal relief" : ", no marginal relief"}`;
    }
    return JSON.stringify(o);
  }
  if (typeof v === "number") return v < 1 ? pct(v) : lakh(v);
  return String(v);
}

const SHOWN = ["lower", "upper", "rate", "max_income", "max_rebate", "marginal_relief", "amount", "threshold",
  "max_rate", "regime", "age_band", "applies_to_ay"];

function effectFields(e: Effect): string {
  return SHOWN.filter((k) => e[k] !== undefined && e[k] !== null && !(k === "regime" && e[k] === "both")
    && !(k === "age_band" && e[k] === "all"))
    .map((k) => {
      const v = e[k];
      const shown = ["lower", "upper", "max_income", "max_rebate", "amount", "threshold"].includes(k) ? lakh(v)
        : ["rate", "max_rate"].includes(k) ? pct(v) : String(v);
      return `${k.replace(/_/g, " ")} ${shown}`;
    }).join(", ");
}

const RATE_FIELDS = ["rate", "max_rate", "rate_per_month"];

/** One line on whether an effect's numbers are in the words it cites. */
export function numbersNote(n?: NumberCheck): { tone: "ok" | "warn" | "bad"; text: string } | null {
  if (!n || n.status === "unchecked") return null;
  const show = (f: NumberCheck["fields"][number]) =>
    `${f.field.replace(/_/g, " ")} ${RATE_FIELDS.includes(f.field) ? pct(f.value) : lakh(f.value)}`;
  if (n.status === "verified") return { tone: "ok", text: "every number is in its quote" };
  const missing = n.fields.filter((f) => f.found === "missing");
  if (missing.length) return { tone: "bad", text: `not in the statute: ${missing.map(show).join(", ")}` };
  const elsewhere = n.fields.filter((f) => f.found === "provision");
  return { tone: "warn", text: `in the provision but not in its quote: ${elsewhere.map(show).join(", ")}` };
}

/** The provision text with every quoted span highlighted. */
function Highlighted({ text, spans }: { text: string; spans: [number, number][] }) {
  const merged: [number, number][] = [];
  for (const [a, b] of [...spans].sort((x, y) => x[0] - y[0])) {
    if (merged.length && a <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], b);
    else merged.push([a, b]);
  }
  const parts: { t: string; m: boolean }[] = [];
  let pos = 0;
  for (const [a, b] of merged) {
    if (a > pos) parts.push({ t: text.slice(pos, a), m: false });
    parts.push({ t: text.slice(a, b), m: true });
    pos = b;
  }
  if (pos < text.length) parts.push({ t: text.slice(pos), m: false });
  return (
    <p className="statute-text text-[13px] leading-relaxed whitespace-pre-wrap">
      {parts.map((p, i) => p.m
        ? <mark key={i} className="bg-accent-primary/20 text-text-primary rounded-sm px-0.5">{p.t}</mark>
        : <span key={i} className="text-text-secondary">{p.t}</span>)}
    </p>
  );
}

export default function InspectPanel({ set, system, onClose }: { set: string; system: string; onClose: () => void }) {
  const [data, setData] = useState<Inspect | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetch(`${API}/api/research/inspect/${set}/${encodeURIComponent(system)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [set, system]);

  return (
    <section className="bg-bg-surface border border-accent-primary/30 rounded-sm p-4 space-y-4" aria-label={`What ${system} read`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-sm">What {system} read: {set}</h3>
          <p className="text-xs text-text-muted mt-1">
            Each provision the reform depends on, with the spans the system quoted highlighted, the effects it extracted,
            and the parameter they assembled into next to the expert&apos;s. Read from cached outputs; no model is called.
          </p>
        </div>
        <button onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text-primary"><X className="w-4 h-4" /></button>
      </div>
      {error && <p className="text-status-error text-sm" role="alert">Could not load ({error}).</p>}
      {!data && !error && <Loader2 className="w-4 h-4 animate-spin text-accent-primary" />}
      {data?.targets.map((t) => (
        <div key={t.target} className="border border-border rounded-sm">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 border-b border-border bg-bg-base/40">
            <span className="font-mono text-xs">{t.target}</span>
            <Link href={`/statutes?s=${encodeURIComponent(data.statute)}&p=${encodeURIComponent(t.provision)}`}
              className="text-xs text-accent-bright inline-flex items-center gap-1 hover:underline">
              {t.provision} <ExternalLink className="w-3 h-3" />
            </Link>
            {t.review
              ? <span className="ml-auto inline-flex items-center gap-1 text-xs text-status-error"><AlertTriangle className="w-3.5 h-3.5" />{t.review}</span>
              : <span className="ml-auto inline-flex items-center gap-1 text-xs text-status-success"><CheckCircle2 className="w-3.5 h-3.5" />assembled</span>}
          </div>
          <dl className="grid sm:grid-cols-[6rem_1fr] gap-x-3 gap-y-1 px-3 py-2 text-xs">
            <dt className="text-text-muted">Expert</dt><dd className="tabular-nums">{formatValue(t.expert)}</dd>
            <dt className="text-text-muted">{system}</dt>
            <dd className="tabular-nums">{t.review ? "— (not assembled)" : formatValue(t.system)}</dd>
          </dl>
          {t.units.map((u) => (
            <div key={u.path} className="px-3 py-2 border-t border-border space-y-2">
              <p className="text-micro font-mono text-text-muted">
                {u.path} · {u.status} · {u.rules} rule{u.rules === 1 ? "" : "s"}
                {u.hallucinated_fields > 0 && ` · ${u.hallucinated_fields} quote(s) not found in the statute`}
              </p>
              <Highlighted text={u.text} spans={u.effects.flatMap((e) => (e.span ? [e.span] : []))} />
              {u.effects.length > 0 && (
                <ul className="text-xs space-y-0.5">
                  {u.effects.map((e, i) => (
                    <li key={i} className="flex flex-wrap gap-x-2 gap-y-0.5">
                      <span className="font-mono text-text-muted w-28 shrink-0">{e.kind}</span>
                      <span className="text-text-secondary">{effectFields(e) || "—"}</span>
                      {(() => {
                        const note = numbersNote(e.numbers);
                        if (!note) return null;
                        return (
                          <span
                            className={
                              note.tone === "ok" ? "text-status-success" : note.tone === "warn" ? "text-status-warning" : "text-status-critical"
                            }
                          >
                            · {note.text}
                          </span>
                        );
                      })()}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
