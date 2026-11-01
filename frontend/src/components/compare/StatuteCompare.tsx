"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowLeftRight, ChevronDown, ChevronUp, Download, ExternalLink, Search } from "lucide-react";
import { API_BASE as API } from "@/lib/api";
import { EmptyState, ErrorState, Skeleton, inputClass } from "@/components/ui/kit";
import { cn } from "@/lib/utils";

type Status = "unchanged" | "formatting" | "renumbered" | "modified" | "added" | "removed";
interface Sec { path: string; number: string; heading: string }
interface Figures { removed: string[]; added: string[] }
interface Row {
  id: string; status: Status; a: Sec | null; b: Sec | null;
  similarity: number | null; score: number | null; figures: Figures | null;
}
interface Compared {
  summary: Record<string, number>; rows: Row[];
  a: { key: string; title: string }; b: { key: string; title: string };
}
interface Side { path: string; number: string; heading: string; text: string; marked: number[][] }
interface Pair { a: Side; b: Side; similarity: number; figures: Figures | null }
interface Statute { key: string; title: string; sections: number }

type Filter = "changes" | "modified" | "figures" | "renumbered" | "added" | "removed" | "same" | "all";

const get = (p: string) => fetch(`${API}${p}`).then(async (r) => {
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? `${r.status}`);
  }
  return r.json();
});

const PRESETS: { a: string; b: string; label: string }[] = [
  { a: "ITA1961/consolidated", b: "ITA2025/enacted", label: "Income-tax Act 1961 → 2025" },
  { a: "ITA2025/enacted", b: "ITA2025/amended_fa2026", label: "Income-tax Act 2025: enacted → amended by FA 2026" },
  { a: "FA2024N2/enacted", b: "FA2025/enacted", label: "Finance Act 2024 (No. 2) → 2025" },
  { a: "FA2025/enacted", b: "FA2026/enacted", label: "Finance Act 2025 → 2026" },
];

const STATUS: Record<Status, { label: string; text: string }> = {
  modified: { label: "Modified", text: "text-status-warning" },
  renumbered: { label: "Renumbered", text: "text-status-info" },
  added: { label: "Added", text: "text-status-success" },
  removed: { label: "Removed", text: "text-status-error" },
  formatting: { label: "Formatting only", text: "text-text-dim" },
  unchanged: { label: "Unchanged", text: "text-text-dim" },
};

const FILTERS: { id: Filter; label: string; test: (r: Row) => boolean }[] = [
  { id: "changes", label: "All changes", test: (r) => !["unchanged", "formatting"].includes(r.status) },
  { id: "modified", label: "Modified", test: (r) => r.status === "modified" },
  { id: "figures", label: "Rates and amounts", test: (r) => !!r.figures },
  { id: "renumbered", label: "Renumbered", test: (r) => r.status === "renumbered" },
  { id: "added", label: "Added", test: (r) => r.status === "added" },
  { id: "removed", label: "Removed", test: (r) => r.status === "removed" },
  { id: "same", label: "Unchanged", test: (r) => ["unchanged", "formatting"].includes(r.status) },
  { id: "all", label: "Everything", test: () => true },
];

const sectionLabel = (r: Row) => {
  const a = r.a?.number, b = r.b?.number;
  if (a && b) return a === b ? `s.${a}` : `s.${a} → s.${b}`;
  return `s.${a ?? b}`;
};
const headingOf = (r: Row) => r.b?.heading || r.a?.heading || "";

function setUrl(sa: string, sb: string, row: string | null) {
  const q = new URLSearchParams({ mode: "statutes", sa, sb });
  if (row) q.set("row", row);
  window.history.replaceState(null, "", `${window.location.pathname}?${q}`);
}

/** The text with the ranges the other side lacks marked: struck out on A, inserted on B. */
function Marked({ text, ranges, side }: { text: string; ranges: number[][]; side: "a" | "b" }) {
  const parts = useMemo(() => {
    const out: { t: string; m: boolean }[] = [];
    let at = 0;
    for (const [s, e] of ranges) {
      if (s > at) out.push({ t: text.slice(at, s), m: false });
      out.push({ t: text.slice(s, e), m: true });
      at = e;
    }
    if (at < text.length) out.push({ t: text.slice(at), m: false });
    return out;
  }, [text, ranges]);
  return (
    <p className="statute-text whitespace-pre-wrap font-serif text-[16px] leading-[1.7] text-ink">
      {parts.map((p, i) =>
        !p.m ? (
          <span key={i}>{p.t}</span>
        ) : side === "a" ? (
          <del key={i} className="rounded-[2px] bg-[#b0213a]/15 text-[#8e1a2f] line-through decoration-[#8e1a2f]/70">{p.t}</del>
        ) : (
          <ins key={i} className="rounded-[2px] bg-[#1a6e47]/15 text-[#14573a] no-underline">{p.t}</ins>
        )
      )}
    </p>
  );
}

function FigureChips({ figures }: { figures: Figures | null }) {
  if (!figures) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Rates and amounts that changed">
      <span className="mr-1 font-mono text-micro uppercase tracking-[0.14em] text-text-dim">Figures</span>
      {figures.removed.map((f) => (
        <span key={`r${f}`} className="rounded-full border border-status-error/40 bg-status-error/10 px-2 py-0.5 font-mono text-[12px] text-status-error line-through">{f}</span>
      ))}
      {figures.added.map((f) => (
        <span key={`a${f}`} className="rounded-full border border-status-success/40 bg-status-success/10 px-2 py-0.5 font-mono text-[12px] text-status-success">{f}</span>
      ))}
    </div>
  );
}

export default function StatuteCompare({ initialA, initialB, initialRow }: { initialA: string | null; initialB: string | null; initialRow: string | null }) {
  const [statutes, setStatutes] = useState<Statute[] | null>(null);
  const [keyA, setKeyA] = useState<string | null>(initialA);
  const [keyB, setKeyB] = useState<string | null>(initialB);
  const [data, setData] = useState<Compared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("changes");
  const [query, setQuery] = useState("");
  const [rowId, setRowId] = useState<string | null>(initialRow);
  const [pair, setPair] = useState<Pair | null>(null);
  const [pairError, setPairError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    get("/api/corpus/statutes")
      .then((d) => setStatutes(d.statutes))
      .catch((e) => setError(String(e.message)));
  }, []);

  // a first visit opens the headline comparison
  useEffect(() => {
    if (!statutes || (keyA && keyB)) return;
    const keys = new Set(statutes.map((s) => s.key));
    const p = PRESETS.find((x) => keys.has(x.a) && keys.has(x.b));
    if (p) { setKeyA(p.a); setKeyB(p.b); }
  }, [statutes, keyA, keyB]);

  const load = useCallback(() => {
    if (!keyA || !keyB || keyA === keyB) return () => {};
    let stale = false;
    setLoading(true);
    setError(null);
    get(`/api/corpus/compare?a=${encodeURIComponent(keyA)}&b=${encodeURIComponent(keyB)}`)
      .then((d: Compared) => { if (!stale) setData(d); })
      .catch((e) => { if (!stale) { setData(null); setError(String(e.message)); } })
      .finally(() => { if (!stale) setLoading(false); });
    return () => { stale = true; };
  }, [keyA, keyB]);

  useEffect(() => load(), [load]);

  const rows = useMemo(() => {
    if (!data) return [];
    const f = FILTERS.find((x) => x.id === filter) ?? FILTERS[0];
    const q = query.trim().toLowerCase().replace(/^s\.?\s*/, "");
    return data.rows.filter((r) => {
      if (!f.test(r)) return false;
      if (!q) return true;
      return [r.a?.number, r.b?.number].some((n) => n && n.toLowerCase() === q) ||
        `${r.a?.heading ?? ""} ${r.b?.heading ?? ""}`.toLowerCase().includes(q);
    });
  }, [data, filter, query]);

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { changes: 0, modified: 0, figures: 0, renumbered: 0, added: 0, removed: 0, same: 0, all: 0 };
    for (const r of data?.rows ?? []) for (const f of FILTERS) if (f.test(r)) c[f.id]++;
    return c;
  }, [data]);

  const selected = useMemo(() => data?.rows.find((r) => r.id === rowId) ?? null, [data, rowId]);

  const virt = useVirtualizer({ count: rows.length, getScrollElement: () => listRef.current, estimateSize: () => 66, overscan: 8 });

  // the selected pair's two texts, with what changed marked
  useEffect(() => {
    setPair(null);
    setPairError(null);
    if (!selected || !data) return;
    let stale = false;
    const one = (key: string, path: string) =>
      get(`/api/corpus/${key}/node?path=${encodeURIComponent(path)}`);
    const req: Promise<Pair> = selected.a && selected.b
      ? get(`/api/corpus/compare/pair?a=${encodeURIComponent(data.a.key)}&pa=${encodeURIComponent(selected.a.path)}&b=${encodeURIComponent(data.b.key)}&pb=${encodeURIComponent(selected.b.path)}`)
      : Promise.all([selected.a ? one(data.a.key, selected.a.path) : null, selected.b ? one(data.b.key, selected.b.path) : null]).then(([na, nb]) => ({
          a: { path: selected.a?.path ?? "", number: selected.a?.number ?? "", heading: selected.a?.heading ?? "", text: na?.text ?? "", marked: [] },
          b: { path: selected.b?.path ?? "", number: selected.b?.number ?? "", heading: selected.b?.heading ?? "", text: nb?.text ?? "", marked: [] },
          similarity: 0, figures: null,
        }));
    req.then((p) => !stale && setPair(p)).catch((e) => !stale && setPairError(String(e.message)));
    return () => { stale = true; };
  }, [selected, data]);

  const choose = (id: string | null) => {
    setRowId(id);
    if (keyA && keyB) setUrl(keyA, keyB, id);
  };
  const changeStatutes = (a: string, b: string) => {
    setKeyA(a); setKeyB(b); setRowId(null); setFilter("changes"); setQuery("");
    setUrl(a, b, null);
  };
  const step = (d: 1 | -1) => {
    const i = rows.findIndex((r) => r.id === rowId);
    const next = rows[Math.min(rows.length - 1, Math.max(0, i + d))];
    if (next) {
      choose(next.id);
      virt.scrollToIndex(rows.indexOf(next), { align: "auto" });
    }
  };

  const exportCsv = () => {
    if (!data) return;
    const esc = (v: string | number | null | undefined) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [["status", "section_a", "section_b", "heading_a", "heading_b", "text_similarity", "figures_removed", "figures_added"].join(",")];
    for (const r of rows) {
      lines.push([r.status, r.a?.number, r.b?.number, r.a?.heading, r.b?.heading, r.similarity, r.figures?.removed.join("; "), r.figures?.added.join("; ")].map(esc).join(","));
    }
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `compare_${data.a.key.replace("/", "-")}_vs_${data.b.key.replace("/", "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const titleOf = (k: string | null) => statutes?.find((s) => s.key === k)?.title ?? k ?? "";
  const presets = PRESETS.filter((p) => statutes?.some((s) => s.key === p.a) && statutes?.some((s) => s.key === p.b));
  const idx = rows.findIndex((r) => r.id === rowId);

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
      {/* choose the two statutes */}
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-end">
        {(["a", "b"] as const).map((side, k) => {
          const value = side === "a" ? keyA : keyB;
          return (
            <label key={side} className={cn("flex min-w-0 flex-col gap-1.5 text-[13px] text-text-muted", k === 1 && "md:col-start-3")}>
              {side === "a" ? "From (baseline)" : "To (revision)"}
              <select
                value={value ?? ""}
                disabled={!statutes}
                onChange={(e) => (side === "a" ? changeStatutes(e.target.value, keyB ?? "") : changeStatutes(keyA ?? "", e.target.value))}
                className={cn(inputClass, "truncate pr-8")}
              >
                {!value && <option value="">Choose a statute</option>}
                {statutes?.map((s) => <option key={s.key} value={s.key}>{s.title} · {s.key.split("/")[1]}</option>)}
              </select>
            </label>
          );
        })}
        <button
          type="button"
          aria-label="Swap the two statutes"
          onClick={() => keyA && keyB && changeStatutes(keyB, keyA)}
          className="order-last inline-flex h-[46px] items-center justify-center gap-2 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary md:order-none md:col-start-2 md:row-start-1"
        >
          <ArrowLeftRight className="h-4 w-4" /> Swap
        </button>
      </div>

      {presets.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Suggested comparisons">
          <span className="font-mono text-micro uppercase tracking-[0.14em] text-text-dim">Try</span>
          {presets.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => changeStatutes(p.a, p.b)}
              className={cn(
                "rounded-full border px-3 py-1 text-[13px] transition-colors",
                keyA === p.a && keyB === p.b ? "border-signal text-text-primary" : "border-border-light text-text-secondary hover:border-glow hover:text-text-primary"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}

      {error && !loading && <div className="mt-8"><ErrorState title="The comparison could not be made" message={error} onRetry={() => load()} /></div>}

      {keyA && keyB && keyA === keyB && (
        <p className="mt-8 text-[14px] text-text-muted">Choose two different statutes.</p>
      )}

      {loading && (
        <div className="mt-8" role="status" aria-label="Matching sections">
          <p className="mb-4 font-mono text-micro uppercase tracking-[0.14em] text-text-dim">
            Matching {titleOf(keyA)} against {titleOf(keyB)}, section by section…
          </p>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
          <Skeleton className="mt-4 h-[420px]" />
        </div>
      )}

      {data && !loading && (
        <>
          {/* what changed, in numbers: each tile is also a filter */}
          <div role="group" aria-label="Kinds of change; choose one to filter the list" className="mt-8 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {([
              ["modified", "Modified", data.summary.modified, "text-status-warning"],
              ["figures", "Rates and amounts changed", data.summary.figures_changed, "text-status-warning"],
              ["renumbered", "Renumbered", data.summary.renumbered, "text-status-info"],
              ["added", `Only in ${data.b.key.split("/")[0]}`, data.summary.added, "text-status-success"],
              ["removed", `Only in ${data.a.key.split("/")[0]}`, data.summary.removed, "text-status-error"],
              ["same", "Unchanged", data.summary.unchanged + data.summary.formatting, "text-text-primary"],
            ] as [Filter, string, number, string][]).map(([id, label, n, tone]) => (
              <button
                key={id}
                type="button"
                onClick={() => setFilter(id)}
                aria-pressed={filter === id}
                className={cn(
                  "rounded-[6px] border bg-bg-surface px-4 py-3 text-left transition-colors hover:border-glow",
                  filter === id ? "border-signal" : "border-border"
                )}
              >
                <span className={cn("block font-serif text-[2rem] leading-none", tone)}>{n.toLocaleString("en-IN")}</span>
                <span className="mt-1.5 block text-[12.5px] leading-snug text-text-muted">{label}</span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-[13px] text-text-muted">
            {data.summary.matched.toLocaleString("en-IN")} of {data.summary.sections_a.toLocaleString("en-IN")} sections in the baseline found a counterpart among{" "}
            {data.summary.sections_b.toLocaleString("en-IN")}. Sections are matched by what they say, so a renumbered or rewritten provision still finds its
            match; &ldquo;unchanged&rdquo; includes sections that differ only in how the two sources print them.
          </p>

          <div className="mt-6 grid gap-6 lg:grid-cols-[23rem_minmax(0,1fr)]">
            {/* the list */}
            <aside className="flex h-[70vh] min-h-[420px] flex-col overflow-hidden rounded-[6px] border border-border bg-bg-surface lg:sticky lg:top-20 lg:h-[78vh]">
              <div className="space-y-2 border-b border-border p-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-dim" aria-hidden />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Section number or heading"
                    aria-label="Filter the changes"
                    className={cn(inputClass, "py-2 pl-9 text-[14px]")}
                  />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <label className="min-w-0 flex-1 text-[12px] text-text-muted">
                    <span className="sr-only">Show</span>
                    <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)} className={cn(inputClass, "py-1.5 text-[13px]")}>
                      {FILTERS.map((f) => <option key={f.id} value={f.id}>{f.label} ({counts[f.id].toLocaleString("en-IN")})</option>)}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={exportCsv}
                    title="Download the listed rows as CSV"
                    className="inline-flex h-9 items-center gap-1.5 rounded-[4px] border border-border-light px-2.5 text-[12.5px] text-text-secondary hover:border-glow hover:text-text-primary"
                  >
                    <Download className="h-3.5 w-3.5" /> CSV
                  </button>
                </div>
              </div>
              <div ref={listRef} tabIndex={0} role="region" aria-label="Sections that differ, scrollable" className="scroll-thin flex-1 overflow-y-auto">
                {rows.length === 0 ? (
                  <p className="p-4 text-[13px] text-text-muted">Nothing matches this filter.</p>
                ) : (
                  <ul role="list" className="relative" style={{ height: virt.getTotalSize() }}>
                    {virt.getVirtualItems().map((v) => {
                      const r = rows[v.index];
                      const meta = STATUS[r.status];
                      return (
                        <li key={r.id} className="absolute left-0 top-0 w-full" style={{ transform: `translateY(${v.start}px)`, height: v.size }}>
                          <button
                            type="button"
                            onClick={() => choose(r.id)}
                            aria-current={r.id === rowId ? "true" : undefined}
                            className={cn(
                              "flex h-full w-full flex-col justify-center gap-0.5 border-b border-border/60 px-3.5 text-left hover:bg-bg-elevated",
                              r.id === rowId && "bg-signal/10"
                            )}
                          >
                            <span className="flex items-center gap-2">
                              <span className={cn("font-mono text-[12.5px]", r.id === rowId ? "text-signal" : "text-text-primary")}>{sectionLabel(r)}</span>
                              <span className={cn("font-mono text-micro uppercase tracking-[0.12em]", meta.text)}>{meta.label}</span>
                              {r.similarity != null && r.status === "modified" && (
                                <span className="ml-auto font-mono text-micro text-text-dim">{Math.round(r.similarity * 100)}% alike</span>
                              )}
                              {r.figures && <span className="font-mono text-[12px] text-status-warning" title="A rate or an amount changed">₹ %</span>}
                            </span>
                            <span className="truncate text-[13px] text-text-secondary" title={headingOf(r)}>{headingOf(r) || "—"}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <div className="border-t border-border px-3 py-2 font-mono text-micro text-text-dim">
                {rows.length.toLocaleString("en-IN")} of {data.rows.length.toLocaleString("en-IN")} sections
              </div>
            </aside>

            {/* the selected pair */}
            <section aria-live="polite" className="min-w-0">
              {!selected && (
                <div className="rounded-[6px] border border-border bg-bg-surface">
                  <EmptyState title="Choose a section">
                    Pick a section from the list to read both versions side by side with the words that changed marked. The
                    list starts with every change; use the tiles above to look at one kind.
                  </EmptyState>
                </div>
              )}
              {selected && (
                <div>
                  <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
                    <h2 className="font-serif text-[clamp(1.5rem,2.6vw,2.1rem)] leading-tight text-text-primary">
                      {sectionLabel(selected)}
                      {headingOf(selected) && <span className="text-text-secondary"> · {headingOf(selected)}</span>}
                    </h2>
                    <span className={cn("font-mono text-micro uppercase tracking-[0.14em]", STATUS[selected.status].text)}>{STATUS[selected.status].label}</span>
                    <div className="ml-auto flex items-center gap-1.5">
                      <button type="button" aria-label="Previous section" disabled={idx <= 0} onClick={() => step(-1)} className="rounded-[4px] border border-border-light p-1.5 text-text-secondary hover:border-glow disabled:opacity-30"><ChevronUp className="h-4 w-4" /></button>
                      <button type="button" aria-label="Next section" disabled={idx < 0 || idx >= rows.length - 1} onClick={() => step(1)} className="rounded-[4px] border border-border-light p-1.5 text-text-secondary hover:border-glow disabled:opacity-30"><ChevronDown className="h-4 w-4" /></button>
                    </div>
                  </div>
                  <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-text-muted">
                    {selected.similarity != null && <span>Text {Math.round(selected.similarity * 100)}% alike</span>}
                    {selected.score != null && selected.status !== "unchanged" && selected.score < 0.6 && (
                      <span className="text-status-warning">Weak match ({Math.round(selected.score * 100)}%): check that these are the same provision</span>
                    )}
                    {selected.a && <Link href={`/statutes?s=${data.a.key}&p=${selected.a.path}`} className="inline-flex items-center gap-1 underline underline-offset-4 hover:text-text-primary">Baseline in Statutes <ExternalLink className="h-3 w-3" /></Link>}
                    {selected.b && <Link href={`/statutes?s=${data.b.key}&p=${selected.b.path}`} className="inline-flex items-center gap-1 underline underline-offset-4 hover:text-text-primary">Revision in Statutes <ExternalLink className="h-3 w-3" /></Link>}
                  </div>
                  <FigureChips figures={selected.figures} />
                  {pairError && <p role="alert" className="mt-4 rounded-[4px] border border-status-error/40 bg-status-error/[0.07] px-4 py-3 text-[13px] text-status-error">That section could not be loaded. {pairError}</p>}
                  {!pair && !pairError && <Skeleton className="mt-4 h-72" />}
                  {pair && (
                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      {(["a", "b"] as const).map((side) => {
                        const s = pair[side];
                        const key = side === "a" ? data.a : data.b;
                        return (
                          <article key={side} className="surface-paper min-w-0 rounded-[6px] px-5 py-6 shadow-lift sm:px-7">
                            <div className="mb-3 font-mono text-micro uppercase tracking-[0.14em] text-ink/55">
                              {side === "a" ? "Baseline" : "Revision"} · {key.title}{s.number ? ` · s.${s.number}` : ""}
                            </div>
                            {s.text ? <Marked text={s.text} ranges={s.marked} side={side} /> : (
                              <p className="font-serif text-[16px] italic text-ink/60">
                                {side === "a" ? "This section has no counterpart in the revision." : "This section has no counterpart in the baseline."}
                              </p>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
