"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUp, ChevronRight, Search } from "lucide-react";
import { API_BASE as API } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { EmptyState, ErrorState, Skeleton, inputClass } from "@/components/ui/kit";
import { cn } from "@/lib/utils";

interface Statute { key: string; title: string; sections: number; chapters: number }
interface OutlineSection { path: string; number: string; heading: string }
interface OutlineGroup { path: string; label: string; heading: string; sections: OutlineSection[] }
interface Outline { title: string; groups: OutlineGroup[]; schedules: { path: string; label: string; heading: string }[] }
interface NodeView {
  path: string; kind: string; label: string; heading: string; page: number | null; text: string;
  parent: string | null; children: { path: string; kind: string; label: string; preview: string }[];
}

const get = (p: string) => fetch(`${API}${p}`).then((r) => {
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
});

/** Read and write ?s=<statute>&p=<path> so every provision has a link. */
function useSelection() {
  const [sel, setSel] = useState<{ s: string | null; p: string | null }>({ s: null, p: null });
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setSel({ s: q.get("s"), p: q.get("p") });
  }, []);
  const update = useCallback((s: string | null, p: string | null) => {
    setSel({ s, p });
    const q = new URLSearchParams();
    if (s) q.set("s", s);
    if (p) q.set("p", p);
    window.history.replaceState(null, "", `${window.location.pathname}${q.toString() ? `?${q}` : ""}`);
  }, []);
  return [sel, update] as const;
}

/** "BASIS OF CHARGE" → "Basis of charge". */
const sentence = (h: string) => (h === h.toUpperCase() ? h.charAt(0) + h.slice(1).toLowerCase() : h);

export default function StatutesPage() {
  const [statutes, setStatutes] = useState<Statute[] | null>(null);
  const [outline, setOutline] = useState<Outline | null>(null);
  const [node, setNode] = useState<NodeView | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sel, select] = useSelection();

  useEffect(() => {
    get("/api/corpus/statutes").then((d) => setStatutes(d.statutes)).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!statutes || sel.s) return;
    const first = statutes.find((s) => s.key.startsWith("ITA2025/amended")) ?? statutes[0];
    if (first) select(first.key, null);
  }, [statutes, sel.s, select]);

  useEffect(() => {
    if (!sel.s) return;
    setOutline(null);
    get(`/api/corpus/${sel.s}/outline`).then(setOutline).catch((e) => setError(String(e)));
  }, [sel.s]);

  useEffect(() => {
    if (!sel.s || !sel.p) { setNode(null); return; }
    get(`/api/corpus/${sel.s}/node?path=${encodeURIComponent(sel.p)}`).then(setNode)
      .catch(() => setNode(null));
  }, [sel.s, sel.p]);

  const groups = useMemo(() => {
    if (!outline) return [];
    const f = filter.trim().toLowerCase();
    if (!f) return outline.groups;
    return outline.groups
      .map((g) => ({ ...g, sections: g.sections.filter((s) => s.number.toLowerCase() === f.replace(/^s\.?/, "")
        || s.heading.toLowerCase().includes(f)) }))
      .filter((g) => g.sections.length > 0);
  }, [outline, filter]);

  const current = statutes?.find((x) => x.key === sel.s);

  return (
    <PageContainer>
      <PageHeader
        kicker="Statutes"
        title="The parsed corpus"
        lede="Every Act in the corpus as the parser reads it: chapters, sections, sub-sections and provisos, with the exact text each one covers. Every provision has its own link."
        actions={
          statutes ? (
            <label className="flex flex-col gap-1.5 text-[13px] text-text-muted">
              Statute
              <select
                value={sel.s ?? ""}
                onChange={(e) => {
                  setFilter("");
                  select(e.target.value, null);
                }}
                className={cn(inputClass, "max-w-[min(32rem,90vw)] pr-8")}
              >
                {statutes.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.title} · {s.key.split("/")[1].replace(/_/g, " ")} · {s.sections} sections
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />

      {error && <ErrorState offline={/fetch/i.test(error)} message={error} onRetry={() => window.location.reload()} />}

      {!error && (
        <div className="grid gap-6 md:grid-cols-[19rem_minmax(0,1fr)]">
          <aside className="flex max-h-[78vh] flex-col overflow-hidden rounded-[6px] border border-border bg-bg-surface md:sticky md:top-20">
            <div className="border-b border-border p-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-dim" aria-hidden />
                <input
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder="Section number or heading"
                  aria-label="Filter sections"
                  className={cn(inputClass, "py-2 pl-9 text-[14px]")}
                />
              </div>
              {current && (
                <p className="mt-2 px-1 font-mono text-micro text-text-dim">
                  {current.chapters} chapters · {current.sections} sections
                </p>
              )}
            </div>
            <nav aria-label="Statute outline" className="scroll-thin flex-1 overflow-y-auto p-2 text-[13.5px]">
              {!outline && (
                <div className="space-y-2 p-2">
                  {Array.from({ length: 8 }).map((_, k) => (
                    <Skeleton key={k} className="h-5" />
                  ))}
                </div>
              )}
              {outline && groups.length === 0 && (
                <p className="p-3 text-[13px] text-text-muted">No section matches “{filter}”.</p>
              )}
              {groups.map((g) => (
                <details key={g.path || "loose"} open={!!filter || groups.length === 1} className="group mb-0.5">
                  <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-[4px] px-2 py-1.5 hover:bg-bg-elevated">
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-dim transition-transform group-open:rotate-90" />
                    <span className="shrink-0 text-text-primary">{g.label}</span>
                    {g.heading && (
                      <span className="truncate text-[12.5px] text-text-muted" title={g.heading}>
                        {sentence(g.heading)}
                      </span>
                    )}
                    <span className="ml-auto font-mono text-micro text-text-dim">{g.sections.length}</span>
                  </summary>
                  <ul className="ml-4 border-l border-border pl-1.5">
                    {g.sections.map((x) => (
                      <li key={x.path}>
                        <button
                          type="button"
                          onClick={() => select(sel.s, x.path)}
                          aria-current={sel.p === x.path ? "page" : undefined}
                          className={cn(
                            "flex w-full gap-2 rounded-[4px] px-2 py-1 text-left hover:bg-bg-elevated",
                            sel.p === x.path ? "bg-signal/10 text-text-primary" : "text-text-secondary"
                          )}
                        >
                          <span className={cn("w-12 shrink-0 font-mono text-[12.5px]", sel.p === x.path && "text-signal")}>
                            s.{x.number}
                          </span>
                          <span className="truncate" title={x.heading}>
                            {x.heading || "—"}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
              {outline && outline.schedules.length > 0 && !filter && (
                <div className="mt-2 border-t border-border pt-2">
                  {outline.schedules.map((x) => (
                    <button
                      type="button"
                      key={x.path}
                      onClick={() => select(sel.s, x.path)}
                      className="w-full rounded-[4px] px-2 py-1.5 text-left text-text-secondary hover:bg-bg-elevated"
                    >
                      {x.label}
                    </button>
                  ))}
                </div>
              )}
            </nav>
          </aside>

          <section aria-live="polite" className="min-w-0">
            {!node && (
              <div className="rounded-[6px] border border-border bg-bg-surface">
                <EmptyState title="Choose a provision">
                  Pick a section from the outline, or filter by its number (87A, for example) or a word in its heading.
                </EmptyState>
              </div>
            )}
            {node && (
              <article className="surface-paper rounded-[6px] px-6 py-8 shadow-lift sm:px-12 sm:py-12">
                <div className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-micro text-ink/55">
                  {node.parent && (
                    <button
                      type="button"
                      onClick={() => select(sel.s, node.parent)}
                      className="inline-flex items-center gap-1 underline-offset-2 hover:text-ink hover:underline"
                    >
                      <ArrowUp className="h-3 w-3" /> {node.parent}
                    </button>
                  )}
                  <span>{node.path}</span>
                  {node.page && <span>page {node.page}</span>}
                </div>
                <h2 className="font-serif text-[clamp(1.8rem,3.2vw,2.6rem)] leading-[1.08] text-ink">
                  {node.label}
                  {node.heading && <span className="text-ink/60"> · {node.heading}</span>}
                </h2>
                <p className="statute-text mt-6 max-w-[70ch] whitespace-pre-wrap font-serif text-[18px] leading-[1.7] text-ink">
                  {node.text}
                </p>
                {node.children.length > 0 && (
                  <div className="mt-10 border-t border-ink/15 pt-6">
                    <h3 className="mb-3 font-mono text-micro uppercase tracking-[0.16em] text-ink/55">Contains</h3>
                    <ul className="space-y-0.5">
                      {node.children.map((c) => (
                        <li key={c.path}>
                          <button
                            type="button"
                            onClick={() => select(sel.s, c.path)}
                            className="flex w-full gap-4 rounded-[4px] px-2 py-1.5 text-left text-[14px] hover:bg-ink/[0.05]"
                          >
                            <span className="w-24 shrink-0 font-mono text-[12.5px] text-signal-ink">{c.label}</span>
                            <span className="statute-text truncate text-ink/75">{c.preview}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            )}
          </section>
        </div>
      )}
    </PageContainer>
  );
}
