"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Download, Printer } from "lucide-react";
import { api } from "@/lib/api";
import DocContextBar from "@/components/shell/DocContextBar";
import { ErrorState, PageSkeleton, Panel, Tag } from "@/components/ui/kit";
import { entityStyle, riskStyle } from "@/lib/tokens";
import { cn } from "@/lib/utils";
import type { CausalPattern, ReportSummary, RiskTier } from "@/types";

const TIERS: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const ENTITY_ORDER = ["OBLIGATION", "PENALTY", "RIGHT", "THRESHOLD", "ACTOR", "BENEFICIARY"];
const PATTERN_LABEL: Record<string, string> = {
  IF_THEN: "if → then",
  CONDITION_ACTION: "condition → action",
  PENALTY_TRIGGER: "penalty trigger",
};
const tierTone = (t: string) => (t === "CRITICAL" ? "critical" : t === "HIGH" ? "warn" : t === "MEDIUM" ? "info" : "neutral");

/**
 * The analysis report, in the app: what the document obliges, where the
 * risky conditions are, and a checklist, each item linked to its clause.
 * The same report downloads as a standalone HTML file.
 */
export default function ReportPage({ params }: { params: { docId: string } }) {
  const { docId } = params;
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<RiskTier>("CRITICAL");

  useEffect(() => {
    let live = true;
    api
      .getReport(docId)
      .then((r) => {
        if (!live) return;
        setReport(r);
        const first = TIERS.find((t) => (r.causal_analysis.risk_matrix[t] ?? []).length > 0);
        if (first) setTier(first);
      })
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [docId]);

  const s = report?.executive_summary;
  const figures: [string, number][] = s
    ? [
        ["pages", s.total_pages],
        ["clauses", s.total_clauses],
        ["entities", s.total_entities],
        ["condition → consequence", s.causal_patterns],
        ["critical risks", s.critical_risks],
        ["high risks", s.high_risks],
      ]
    : [];
  const patterns: CausalPattern[] = report?.causal_analysis.risk_matrix[tier] ?? [];
  const entityTotal = report?.entity_counts ? Object.values(report.entity_counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="min-h-[calc(100dvh-3.5rem)]">
      <div className="print:hidden">
        <DocContextBar docId={docId} filename={report?.filename} view="report">
          <button
            type="button"
            onClick={() => window.print()}
            disabled={!report}
            className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary disabled:opacity-50"
          >
            <Printer className="h-3.5 w-3.5" /> Print
          </button>
          <button
            type="button"
            onClick={() => api.downloadReport(docId)}
            className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary"
          >
            <Download className="h-3.5 w-3.5" /> HTML
          </button>
        </DocContextBar>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {error && <ErrorState offline={/fetch/i.test(error)} message={error} onRetry={() => window.location.reload()} />}
        {!report && !error && <PageSkeleton rows={4} />}
        {report && s && (
          <>
            <header className="mb-10">
              <div className="kicker mb-3">Analysis report</div>
              <h1 className="max-w-4xl font-serif text-headline text-text-primary">{report.filename}</h1>
              <p className="mt-3 text-[14px] text-text-muted">
                Reads as {report.domain} · generated {new Date(report.generated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} ·
                every finding links to the clause it comes from
              </p>
            </header>

            <dl className="mb-10 grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
              {figures.map(([k, v]) => (
                <div key={k} className="bg-bg-surface px-4 py-4">
                  <dd className={cn("font-serif text-[2rem] leading-none tabular", k.includes("critical") && v > 0 ? "text-status-error" : "text-text-primary")}>
                    {v.toLocaleString("en-IN")}
                  </dd>
                  <dt className="mt-2 text-[12px] text-text-muted">{k}</dt>
                </div>
              ))}
            </dl>

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="min-w-0 space-y-6">
                <Panel kicker="Do this first" title="Compliance checklist" flush>
                  {report.compliance_checklist.length === 0 ? (
                    <p className="p-5 text-[14px] text-text-muted">No critical or high-risk items.</p>
                  ) : (
                    <ol className="divide-y divide-border">
                      {report.compliance_checklist.map((c, i) => (
                        <li key={i} className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 px-5 py-3.5">
                          <Tag tone={tierTone(c.priority)} className="mt-0.5 self-start">
                            {c.priority.toLowerCase()}
                          </Tag>
                          <p className="text-[14px] leading-snug text-text-primary">{c.item}</p>
                          <p className="col-start-2 text-[13px] leading-snug text-text-muted">→ {c.action}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </Panel>

                <Panel
                  kicker="Condition → consequence"
                  title="Risk matrix"
                  flush
                  actions={
                    <div role="tablist" aria-label="Risk tier" className="flex gap-1">
                      {TIERS.map((t) => (
                        <button
                          key={t}
                          type="button"
                          role="tab"
                          aria-selected={tier === t}
                          onClick={() => setTier(t)}
                          className={cn(
                            "rounded-[3px] px-2 py-1 font-mono text-micro uppercase tracking-[0.08em] transition-colors",
                            tier === t ? "bg-bg-overlay text-text-primary" : "text-text-muted hover:text-text-primary"
                          )}
                        >
                          {t.toLowerCase()} {(report.causal_analysis.risk_matrix[t] ?? []).length}
                        </button>
                      ))}
                    </div>
                  }
                >
                  {patterns.length === 0 ? (
                    <p className="p-5 text-[14px] text-text-muted">No {tier.toLowerCase()}-risk patterns.</p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {patterns.slice(0, 40).map((p, i) => {
                        const meta = p as CausalPattern & { section?: string; page?: number };
                        return (
                          <li key={`${p.source_clause_id}-${i}`}>
                            <Link
                              href={`/explain/${docId}/${p.source_clause_id}`}
                              className="group block px-5 py-3.5 transition-colors hover:bg-bg-elevated"
                            >
                              <div className="mb-1.5 flex items-center gap-2 font-mono text-micro text-text-dim">
                                <span className="h-1.5 w-1.5 rounded-full" style={{ background: riskStyle(p.risk_tier).base }} aria-hidden />
                                {PATTERN_LABEL[p.pattern_type] ?? p.pattern_type} · §{meta.section ?? "—"} · p.{meta.page ?? "—"}
                                <ArrowUpRight className="ml-auto h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                              </div>
                              <p className="text-[14px] leading-snug text-text-secondary">
                                <span className="text-text-muted">If </span>
                                {p.condition_span.slice(0, 180)}
                                <span className="text-text-muted"> → </span>
                                <span className="text-text-primary">{p.action_span.slice(0, 180)}</span>
                              </p>
                            </Link>
                          </li>
                        );
                      })}
                      {patterns.length > 40 && (
                        <li className="px-5 py-3 text-[13px] text-text-muted">
                          and {(patterns.length - 40).toLocaleString("en-IN")} more in the workspace&apos;s causal tab.
                        </li>
                      )}
                    </ul>
                  )}
                </Panel>
              </div>

              <aside className="min-w-0 space-y-6">
                {report.entity_counts && entityTotal > 0 && (
                  <Panel kicker="Who and what" title="Entities">
                    <ul className="space-y-2.5">
                      {ENTITY_ORDER.filter((l) => report.entity_counts![l]).map((l) => {
                        const n = report.entity_counts![l];
                        return (
                          <li key={l}>
                            <div className="mb-1 flex items-baseline justify-between text-[13px]">
                              <span className="capitalize text-text-secondary">{l.toLowerCase()}</span>
                              <span className="font-mono text-text-primary">{n.toLocaleString("en-IN")}</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
                              <div className="h-full rounded-full" style={{ width: `${(n / entityTotal) * 100}%`, background: entityStyle(l).base }} />
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </Panel>
                )}
                <Panel kicker="Pattern types" title="How the conditions are written">
                  <ul className="space-y-1.5 text-[13px]">
                    {Object.entries(report.causal_analysis.by_type).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span className="text-text-secondary">{PATTERN_LABEL[k] ?? k}</span>
                        <span className="font-mono text-text-primary">{Number(v).toLocaleString("en-IN")}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
                {report.graph_summary && (
                  <Panel kicker="Provenance" title="The graph behind it">
                    <p className="text-[13px] leading-relaxed text-text-secondary">
                      {report.graph_summary.nodes.toLocaleString("en-IN")} nodes and {report.graph_summary.edges.toLocaleString("en-IN")} edges tie every finding to
                      its clause, section and chapter.
                    </p>
                    <Link href={`/provenance/${docId}`} className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-text-primary underline underline-offset-4 print:hidden">
                      Open the graph <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </Panel>
                )}
              </aside>
            </div>

            {report.key_obligations && report.key_obligations.length > 0 && (
              <Panel kicker="What it requires" title="Key obligations" flush className="mt-6">
                <ul className="divide-y divide-border">
                  {report.key_obligations.map((o) => (
                    <li key={o.clause_id}>
                      <Link href={`/explain/${docId}/${o.clause_id}`} className="group block px-5 py-3.5 transition-colors hover:bg-bg-elevated">
                        <div className="mb-1.5 flex flex-wrap items-center gap-2 font-mono text-micro text-text-dim">
                          §{o.section} · p.{o.page}
                          {o.has_penalty && <Tag tone="critical">with penalty</Tag>}
                          <ArrowUpRight className="ml-auto h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                        </div>
                        <p className="text-[14px] leading-snug text-text-secondary">{o.text_preview}…</p>
                        <p className="mt-1.5 text-[12px] text-text-muted">obliges: {o.obligation_phrases.slice(0, 4).join(" · ")}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </>
        )}
      </div>
    </div>
  );
}
