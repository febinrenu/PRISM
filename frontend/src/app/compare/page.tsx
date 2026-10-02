"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import PrismMark from "@/components/brand/PrismMark";
import DocPicker from "@/components/compare/DocPicker";
import DiffSummaryPanel from "@/components/compare/DiffSummaryPanel";
import ClauseDiffList, { type DiffKind, type DiffRow } from "@/components/compare/ClauseDiffList";
import DiffPDFPane from "@/components/compare/DiffPDFPane";
import ComparativeSimPanel from "@/components/compare/ComparativeSimPanel";
import { tokens, alpha } from "@/lib/tokens";
import type { Clause, CompareResult } from "@/types";

interface ArenaData {
  result: CompareResult;
  clausesA: Clause[];
  clausesB: Clause[];
}

function LoadingSkeleton() {
  return (
    <div className="max-w-[1600px] mx-auto px-6 py-8 space-y-4">
      <div className="shimmer rounded-2xl h-24" />
      <div className="shimmer rounded-2xl h-48" />
      <div className="flex gap-4">
        <div className="shimmer rounded-2xl flex-1 h-[560px]" />
        <div className="shimmer rounded-2xl w-[380px] h-[560px]" />
        <div className="shimmer rounded-2xl flex-1 h-[560px]" />
      </div>
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <div className="glass-card p-8 flex flex-col items-center gap-3 text-center">
        <AlertTriangle className="w-6 h-6 text-status-error" />
        <p className="text-sm text-status-error">{message}</p>
        <Link
          href="/compare"
          className="mt-2 text-xs font-mono text-accent-primary hover:text-accent-bright transition-colors"
        >
          ← Pick different documents
        </Link>
      </div>
    </div>
  );
}

function Arena({ docIdA, docIdB }: { docIdA: string; docIdB: string }) {
  const [data, setData] = useState<ArenaData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [pageA, setPageA] = useState(1);
  const [pageB, setPageB] = useState(1);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    setSelectedRowId(null);
    setPageA(1);
    setPageB(1);
    Promise.all([api.compare(docIdA, docIdB), api.getClauses(docIdA), api.getClauses(docIdB)])
      .then(([result, resA, resB]) => {
        if (cancelled) return;
        setData({ result, clausesA: resA.clauses, clausesB: resB.clauses });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Comparison failed");
      });
    return () => {
      cancelled = true;
    };
  }, [docIdA, docIdB]);

  const clauseMapA = useMemo(
    () => new Map((data?.clausesA ?? []).map((c) => [c.clause_id, c])),
    [data]
  );
  const clauseMapB = useMemo(
    () => new Map((data?.clausesB ?? []).map((c) => [c.clause_id, c])),
    [data]
  );

  // Flatten clause_diff into ordered rows (by page, then modified > added > removed).
  const rows = useMemo<DiffRow[]>(() => {
    const cd = data?.result.clause_diff;
    if (!cd) return [];
    const out: DiffRow[] = [];
    for (const m of cd.modified) {
      out.push({
        id: `mod:${m.clause_a_id}:${m.clause_b_id}`,
        kind: "modified",
        clauseA: clauseMapA.get(m.clause_a_id) ?? null,
        clauseB: clauseMapB.get(m.clause_b_id) ?? null,
        similarity: m.similarity,
      });
    }
    for (const id of cd.added) {
      out.push({ id: `add:${id}`, kind: "added", clauseA: null, clauseB: clauseMapB.get(id) ?? null });
    }
    for (const id of cd.removed) {
      out.push({ id: `rem:${id}`, kind: "removed", clauseA: clauseMapA.get(id) ?? null, clauseB: null });
    }
    return out.sort(
      (a, b) =>
        (a.clauseB?.page ?? a.clauseA?.page ?? 0) - (b.clauseB?.page ?? b.clauseA?.page ?? 0)
    );
  }, [data, clauseMapA, clauseMapB]);

  // Diff status per clause, per pane (clauses absent from the maps are "matched").
  const { statusA, statusB } = useMemo(() => {
    const a = new Map<string, DiffKind>();
    const b = new Map<string, DiffKind>();
    for (const row of rows) {
      if (row.clauseA) a.set(row.clauseA.clause_id, row.kind);
      if (row.clauseB) b.set(row.clauseB.clause_id, row.kind);
    }
    return { statusA: a, statusB: b };
  }, [rows]);

  const selectedRow = rows.find((r) => r.id === selectedRowId) ?? null;

  const handleSelectRow = useCallback((row: DiffRow) => {
    setSelectedRowId(row.id);
    if (row.clauseA) setPageA(row.clauseA.page);
    if (row.clauseB) setPageB(row.clauseB.page);
  }, []);

  const handleSelectClause = useCallback(
    (pane: "A" | "B") => (clauseId: string) => {
      const row = rows.find((r) =>
        pane === "A" ? r.clauseA?.clause_id === clauseId : r.clauseB?.clause_id === clauseId
      );
      if (row) handleSelectRow(row);
    },
    [rows, handleSelectRow]
  );

  if (error) return <ErrorPanel message={error} />;
  if (!data) return <LoadingSkeleton />;

  const { result } = data;

  return (
    <main className="max-w-[1600px] mx-auto px-6 py-8 space-y-6">
      {/* Summary header */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-2">
          <span className="h-px w-8 bg-accent-primary/60" />
          <span className="kicker">Comparative intelligence</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="font-display text-2xl md:text-3xl text-text-primary truncate max-w-md">
            {result.doc_a.filename}
          </h1>
          <ArrowRight className="w-5 h-5 flex-shrink-0 text-accent-primary" />
          <h1 className="font-display text-2xl md:text-3xl text-text-primary truncate max-w-md">
            {result.doc_b.filename}
          </h1>
        </div>
        <p className="text-xs font-mono text-text-muted mt-2">
          {result.doc_a.clauses} vs {result.doc_b.clauses} clauses · {result.doc_a.entities} vs{" "}
          {result.doc_b.entities} entities · {result.doc_a.domain}
        </p>
      </motion.div>

      <DiffSummaryPanel result={result} />

      {!result.clause_diff && (
        <div className="glass-card p-4 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" style={{ color: tokens.status.warning }} />
          <p className="text-xs text-text-muted leading-relaxed">
            Clause-level diff is unavailable for this pair (embeddings missing or the documents are
            too dissimilar to align), so the panes below show every clause as unchanged. The entity
            and risk deltas above are still valid.
          </p>
        </div>
      )}

      {/* 3-zone diff arena */}
      <div className="flex gap-4 h-[72vh] min-h-[540px]">
        <div className="flex-1 min-w-0">
          <DiffPDFPane
            docId={docIdA}
            label="A"
            filename={result.doc_a.filename}
            clauses={data.clausesA}
            statusByClauseId={statusA}
            selectedClauseId={selectedRow?.clauseA?.clause_id ?? null}
            page={pageA}
            onPageChange={setPageA}
            onSelectClause={handleSelectClause("A")}
          />
        </div>
        <div className="w-[380px] flex-shrink-0">
          <ClauseDiffList rows={rows} selectedRowId={selectedRowId} onSelect={handleSelectRow} />
        </div>
        <div className="flex-1 min-w-0">
          <DiffPDFPane
            docId={docIdB}
            label="B"
            filename={result.doc_b.filename}
            clauses={data.clausesB}
            statusByClauseId={statusB}
            selectedClauseId={selectedRow?.clauseB?.clause_id ?? null}
            page={pageB}
            onPageChange={setPageB}
            onSelectClause={handleSelectClause("B")}
          />
        </div>
      </div>

      <ComparativeSimPanel
        docIdA={docIdA}
        docIdB={docIdB}
        nameA={result.doc_a.filename}
        nameB={result.doc_b.filename}
      />
    </main>
  );
}

function CompareArenaPage() {
  const searchParams = useSearchParams();
  const a = searchParams.get("a");
  const b = searchParams.get("b");
  const ready = Boolean(a && b && a !== b);

  return (
    <div className="min-h-screen app-shell bg-bg-base">
      <div className="gradient-orb-1" style={{ opacity: 0.3 }} />
      <div className="gradient-orb-3" style={{ opacity: 0.25 }} />
      <div className="noise-overlay" />

      <nav className="content-layer sticky top-0 z-20 flex items-center justify-between px-6 py-3 bg-bg-deep/90 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs font-mono text-text-muted hover:text-text-primary transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />{" "}
            Home
          </Link>
          <div className="w-px h-4 bg-border" />
          <PrismMark size={24} />
          <span className="font-display font-bold text-sm text-text-primary">
            Policy Diff Arena
          </span>
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
            style={{
              color: tokens.diff.added,
              borderColor: alpha(tokens.diff.added, 0.35),
              background: alpha(tokens.diff.added, 0.1),
            }}
          >
            Module D · Diff engine
          </span>
        </div>
        {ready && (
          <Link
            href="/compare"
            className="text-[10px] font-mono text-text-dim hover:text-text-primary transition-colors"
          >
            Change documents
          </Link>
        )}
      </nav>

      <div className="content-layer">
        {ready ? <Arena docIdA={a as string} docIdB={b as string} /> : <DocPicker initialA={a} initialB={b} />}
      </div>
    </div>
  );
}

/** /compare?a=<docId>&b=<docId> — useSearchParams requires a Suspense
 *  boundary for static prerendering of this route. */
export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <CompareArenaPage />
    </Suspense>
  );
}
