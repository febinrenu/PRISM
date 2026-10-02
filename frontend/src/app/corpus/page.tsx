"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Loader2, Database, Plus, Trash2, FileText, Zap, MessageSquare, Cpu, Cloud, RefreshCw,
} from "lucide-react";
import TopNav from "@/components/nav/TopNav";
import { api, Phase2UnavailableError } from "@/lib/api";
import type { CorpusStats, LLMBackendInfo, DocumentMeta } from "@/types";

export default function CorpusPage() {
  const [corpus, setCorpus] = useState<CorpusStats | null>(null);
  const [backend, setBackend] = useState<LLMBackendInfo | null>(null);
  const [allDocs, setAllDocs] = useState<DocumentMeta[]>([]);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    try {
      const [c, b, docs] = await Promise.all([api.getCorpus(), api.getBackend(), api.listDocuments()]);
      setCorpus(c);
      setBackend(b);
      setAllDocs(docs.documents);
      setOffline(false);
    } catch (e) {
      if (e instanceof Phase2UnavailableError) setOffline(true);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const indexed = new Set(corpus?.documents.map((d) => d.doc_id) ?? []);
  const notIndexed = allDocs.filter((d) => d.status === "complete" && !indexed.has(d.doc_id));

  const ingest = async (docId: string) => {
    setBusy(docId);
    try {
      await api.ingestDoc(docId);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const remove = async (docId: string) => {
    setBusy(docId);
    try {
      await api.removeFromCorpus(docId);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const ingestAll = async () => {
    setBusy("all");
    try {
      const res = await api.ingestAll();
      setCorpus(res.corpus);
      await load();
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <div className="animated-grid" />
      <div className="noise-overlay" />
      <TopNav />

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <h1 className="font-display text-2xl uppercase tracking-wider flex items-center gap-2">
              <Database className="w-5 h-5 text-accent-primary" /> Corpus Explorer
            </h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted mt-1">
              {corpus
                ? `${corpus.documents.length} documents · ${corpus.total_clauses.toLocaleString()} clauses indexed · ChromaDB`
                : "Loading…"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {backend && (
              <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-2.5 py-1.5 rounded-sm border border-border text-text-secondary">
                {backend.cloud ? <Cloud className="w-3 h-3" /> : <Cpu className="w-3 h-3" />}
                {backend.model}
              </span>
            )}
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary"
            >
              <MessageSquare className="w-3 h-3" /> Ask the corpus
            </Link>
          </div>
        </div>

        {offline && (
          <div className="glass-card p-5 text-text-muted text-sm">Backend unreachable. Start the API and refresh.</div>
        )}

        {/* Indexed documents */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {corpus?.documents.map((d) => (
            <div key={d.doc_id} className="glass-card p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-accent-primary shrink-0" />
                    <h3 className="font-mono text-[12px] text-text-primary truncate">{d.doc_name}</h3>
                  </div>
                </div>
                <button
                  onClick={() => remove(d.doc_id)}
                  disabled={busy === d.doc_id}
                  className="text-text-dim hover:text-status-error transition-colors"
                  title="Remove from corpus"
                >
                  {busy === d.doc_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                </button>
              </div>
              <div className="mt-4 flex items-center gap-4">
                <div>
                  <div className="font-display text-2xl text-text-primary">{d.clauses.toLocaleString()}</div>
                  <div className="font-mono text-[9px] uppercase tracking-widest text-text-muted">Clauses</div>
                </div>
                <div>
                  <div className="font-display text-2xl text-accent-primary flex items-center gap-1">
                    <Zap className="w-4 h-4" /> {d.causal}
                  </div>
                  <div className="font-mono text-[9px] uppercase tracking-widest text-text-muted">Causal</div>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Link
                  href={`/analyze/${d.doc_id}`}
                  className="flex-1 text-center font-mono text-[9px] uppercase tracking-widest py-2 rounded-sm border border-border text-text-secondary hover:border-light transition-colors"
                >
                  Analyse
                </Link>
                <Link
                  href={`/simulate/${d.doc_id}`}
                  className="flex-1 text-center font-mono text-[9px] uppercase tracking-widest py-2 rounded-sm border border-border text-text-secondary hover:border-light transition-colors"
                >
                  Simulate
                </Link>
              </div>
            </div>
          ))}
        </div>

        {/* Add documents to corpus */}
        {(notIndexed.length > 0 || (corpus && corpus.documents.length === 0)) && !offline && (
          <div className="mt-8 glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display uppercase tracking-wider text-sm flex items-center gap-2">
                <Plus className="w-4 h-4 text-accent-primary" /> Add to corpus
              </h3>
              <button
                onClick={ingestAll}
                disabled={busy === "all"}
                className="inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary disabled:opacity-60"
              >
                {busy === "all" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                Index all analysed docs
              </button>
            </div>
            {notIndexed.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {notIndexed.map((d) => (
                  <li key={d.doc_id} className="flex items-center justify-between rounded-md border border-border p-3">
                    <span className="font-mono text-[11px] truncate">{d.filename}</span>
                    <button
                      onClick={() => ingest(d.doc_id)}
                      disabled={busy === d.doc_id}
                      className="inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest px-2.5 py-1.5 rounded-sm border border-border text-text-secondary hover:border-light transition-colors"
                    >
                      {busy === d.doc_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                      Index
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-text-muted">
                All analysed documents are indexed. Upload and analyse more from the landing page.
              </p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
