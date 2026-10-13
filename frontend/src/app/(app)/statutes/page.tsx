"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, Loader2, Search, ScrollText } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  return (
    <div className="relative app-shell bg-bg-base text-text-primary">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl uppercase tracking-wider">Statutes</h1>
            <p className="text-sm text-text-muted mt-1">The parsed corpus: every provision with its structure and exact text.</p>
          </div>
          {statutes && (
            <label className="text-xs text-text-muted flex items-center gap-2">
              Statute
              <select
                value={sel.s ?? ""}
                onChange={(e) => { setFilter(""); select(e.target.value, null); }}
                className="bg-bg-surface border border-border rounded-md px-2 py-1.5 text-sm text-text-primary"
              >
                {statutes.map((s) => (
                  <option key={s.key} value={s.key}>{s.title} ({s.key.split("/")[1]}, {s.sections} sections)</option>
                ))}
              </select>
            </label>
          )}
        </header>

        {error && <p role="alert" className="text-status-error text-sm mb-3">Could not load the corpus ({error}).</p>}

        <div className="grid md:grid-cols-[20rem_1fr] gap-4">
          <aside className="bg-bg-surface border border-border rounded-sm flex flex-col max-h-[75vh]">
            <div className="p-3 border-b border-border">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                <input
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder="Section number or heading"
                  aria-label="Filter sections"
                  className="w-full pl-8 pr-2 py-1.5 rounded-md text-sm bg-bg-base border border-border focus:border-accent-primary/50 outline-none"
                />
              </div>
            </div>
            <nav aria-label="Statute outline" className="overflow-y-auto p-2 text-[13px]">
              {!outline && <Loader2 className="w-4 h-4 animate-spin text-accent-primary m-3" />}
              {groups.map((g) => (
                <details key={g.path || "loose"} open={!!filter || groups.length === 1} className="group mb-1">
                  <summary className="flex items-center gap-1 px-2 py-1 rounded cursor-pointer list-none hover:bg-bg-elevated">
                    <ChevronRight className="w-3 h-3 text-text-muted transition-transform group-open:rotate-90" />
                    <span className="font-medium shrink-0">{g.label}</span>
                    {g.heading && <span className="truncate text-text-muted text-[12px]" title={g.heading}>{g.heading}</span>}
                    <span className="ml-auto text-micro text-text-muted tabular-nums">{g.sections.length}</span>
                  </summary>
                  <ul className="pl-5">
                    {g.sections.map((s) => (
                      <li key={s.path}>
                        <button
                          onClick={() => select(sel.s, s.path)}
                          aria-current={sel.p === s.path ? "true" : undefined}
                          className={`w-full text-left px-2 py-0.5 rounded flex gap-2 hover:bg-bg-elevated ${
                            sel.p === s.path ? "bg-accent-primary/10 text-accent-bright" : "text-text-secondary"}`}
                        >
                          <span className="font-mono w-12 shrink-0">s.{s.number}</span>
                          <span className="truncate" title={s.heading}>{s.heading || "—"}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
              {outline && outline.schedules.length > 0 && !filter && (
                <div className="mt-2 pt-2 border-t border-border">
                  {outline.schedules.map((s) => (
                    <button key={s.path} onClick={() => select(sel.s, s.path)}
                      className="w-full text-left px-2 py-1 rounded hover:bg-bg-elevated text-text-secondary">
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
            </nav>
          </aside>

          <section className="bg-bg-surface border border-border rounded-sm p-5 min-h-[40vh]" aria-live="polite">
            {!node && (
              <div className="h-full flex flex-col items-center justify-center text-text-muted text-sm gap-2 py-16">
                <ScrollText className="w-6 h-6" />
                Choose a section from the outline.
              </div>
            )}
            {node && (
              <article className="space-y-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted font-mono">
                  {node.parent && (
                    <button onClick={() => select(sel.s, node.parent)} className="hover:text-text-primary underline-offset-2 hover:underline">
                      ↑ {node.parent}
                    </button>
                  )}
                  <span>{node.path}</span>
                  {node.page && <span>· p.{node.page}</span>}
                </div>
                <h2 className="font-display text-lg">
                  {node.label}{node.heading && <span className="text-text-secondary font-normal"> — {node.heading}</span>}
                </h2>
                <p className="statute-text text-sm leading-relaxed whitespace-pre-wrap text-text-primary">{node.text}</p>
                {node.children.length > 0 && (
                  <div>
                    <h3 className="text-xs uppercase tracking-wider text-text-muted mb-2">Contains</h3>
                    <ul className="space-y-1">
                      {node.children.map((c) => (
                        <li key={c.path}>
                          <button onClick={() => select(sel.s, c.path)}
                            className="w-full text-left text-[13px] px-2 py-1 rounded border border-transparent hover:border-border hover:bg-bg-elevated flex gap-3">
                            <span className="font-mono text-text-muted w-20 shrink-0">{c.label}</span>
                            <span className="statute-text text-text-secondary truncate">{c.preview}</span>
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
      </div>
    </div>
  );
}
