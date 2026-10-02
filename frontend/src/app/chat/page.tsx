"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft, Send, Square, Sparkles, Database, Loader2, RefreshCw,
  Cpu, Cloud, ShieldCheck, AlertTriangle, MessageSquare,
} from "lucide-react";
import PrismMark from "@/components/brand/PrismMark";
import CitationCard from "@/components/chat/CitationCard";
import { useRAGChat } from "@/hooks/useRAGChat";
import { api, Phase2UnavailableError } from "@/lib/api";
import { tokens, alpha } from "@/lib/tokens";
import type { CorpusStats, LLMBackendInfo } from "@/types";

const SUGGESTIONS = [
  "What are the penalties for late filing of income tax returns?",
  "Who is exempt from income tax under the rebate provisions?",
  "What thresholds trigger a tax audit obligation?",
  "What is the consequence of failing to deduct TDS?",
];

export default function ChatPage() {
  const { messages, busy, send, stop, reset } = useRAGChat();
  const [input, setInput] = useState("");
  const [strict, setStrict] = useState(true);
  const [corpus, setCorpus] = useState<CorpusStats | null>(null);
  const [backend, setBackend] = useState<LLMBackendInfo | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [offline, setOffline] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadCorpus = async () => {
    try {
      const [c, b] = await Promise.all([api.getCorpus(), api.getBackend()]);
      setCorpus(c);
      setBackend(b);
      setOffline(false);
    } catch (e) {
      if (e instanceof Phase2UnavailableError) setOffline(true);
    }
  };

  useEffect(() => {
    loadCorpus();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const ingestAll = async () => {
    setIngesting(true);
    try {
      const res = await api.ingestAll();
      setCorpus(res.corpus);
    } catch {
      /* surfaced via corpus state */
    } finally {
      setIngesting(false);
    }
  };

  const toggleDoc = (docId: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(docId) ? next.delete(docId) : next.add(docId);
      return next;
    });

  const submit = () => {
    if (!input.trim() || busy) return;
    send(input, Array.from(selected), strict);
    setInput("");
  };

  const empty = corpus && corpus.total_clauses === 0;

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary flex flex-col">
      <div className="animated-grid" />
      <div className="noise-overlay" />

      {/* Header */}
      <nav className="relative z-20 px-6 py-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <PrismMark size={28} />
          </Link>
          <div>
            <h1 className="font-display text-lg uppercase tracking-wider text-text-primary flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-accent-primary" /> RAG Legal Assistant
            </h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted">
              Grounded · Cited · {strict ? "Strict corpus" : "Extended knowledge"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {backend && (
            <span className="hidden sm:inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-2.5 py-1.5 rounded-sm border border-border text-text-secondary">
              {backend.cloud ? <Cloud className="w-3 h-3" /> : <Cpu className="w-3 h-3" />}
              {backend.model}
            </span>
          )}
          {messages.length > 0 && (
            <button
              onClick={reset}
              className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-2.5 py-1.5 rounded-sm border border-border text-text-muted hover:text-text-primary hover:border-light transition-colors"
            >
              <RefreshCw className="w-3 h-3" /> New chat
            </button>
          )}
        </div>
      </nav>

      <div className="relative z-10 flex flex-1 min-h-0 max-w-7xl w-full mx-auto">
        {/* Corpus sidebar */}
        <aside className="hidden md:flex flex-col w-72 shrink-0 border-r border-border p-5 gap-4 overflow-y-auto">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-text-muted">
            <Database className="w-3.5 h-3.5" />
            Corpus
            {corpus && (
              <span className="ml-auto text-accent-primary">
                {corpus.total_clauses.toLocaleString()} clauses
              </span>
            )}
          </div>

          {offline && (
            <div className="rounded-md border border-border p-3 text-[12px] text-text-muted">
              Backend unreachable. Start the API and refresh.
            </div>
          )}

          {empty && !offline && (
            <div className="rounded-md border border-border p-3 space-y-2">
              <p className="text-[12px] text-text-secondary">
                No documents indexed yet. Add every analysed document to the corpus.
              </p>
              <button
                onClick={ingestAll}
                disabled={ingesting}
                className="w-full inline-flex items-center justify-center gap-2 font-mono text-[10px] uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary disabled:opacity-60"
              >
                {ingesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Database className="w-3 h-3" />}
                Index all documents
              </button>
            </div>
          )}

          <div className="flex flex-col gap-2">
            {corpus?.documents.map((d) => {
              const on = selected.size === 0 || selected.has(d.doc_id);
              return (
                <button
                  key={d.doc_id}
                  onClick={() => toggleDoc(d.doc_id)}
                  className="text-left rounded-md border p-3 transition-colors"
                  style={{
                    borderColor: selected.has(d.doc_id) ? alpha(tokens.accent.primary, 0.4) : tokens.border.DEFAULT,
                    background: selected.has(d.doc_id) ? alpha(tokens.accent.primary, 0.08) : "transparent",
                    opacity: on ? 1 : 0.5,
                  }}
                >
                  <div className="font-mono text-[11px] text-text-primary truncate">{d.doc_name}</div>
                  <div className="mt-1 font-mono text-[9px] uppercase tracking-wider text-text-muted">
                    {d.clauses} clauses · {d.causal} causal
                  </div>
                </button>
              );
            })}
          </div>

          {corpus && corpus.documents.length > 0 && (
            <button
              onClick={ingestAll}
              disabled={ingesting}
              className="mt-auto inline-flex items-center justify-center gap-2 font-mono text-[9px] uppercase tracking-widest px-3 py-2 rounded-sm border border-border text-text-muted hover:text-text-primary transition-colors disabled:opacity-60"
            >
              {ingesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Re-index corpus
            </button>
          )}

          <p className="font-mono text-[9px] leading-relaxed text-text-dim">
            {selected.size === 0
              ? "Searching all documents. Select docs to filter retrieval."
              : `Filtering to ${selected.size} document${selected.size > 1 ? "s" : ""}.`}
          </p>
        </aside>

        {/* Chat area */}
        <section className="flex flex-col flex-1 min-h-0">
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-8 py-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto">
                <PrismMark size={56} />
                <h2 className="mt-6 font-display text-2xl uppercase tracking-wider text-text-primary">
                  Ask the corpus
                </h2>
                <p className="mt-3 text-sm text-text-secondary leading-relaxed">
                  Every answer is grounded in retrieved statute clauses and cited by source.
                  Nothing is invented — if it isn&apos;t in the corpus, PRISM says so.
                </p>
                <div className="mt-8 grid gap-2 w-full">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => setInput(s)}
                      className="text-left text-[13px] rounded-md border border-border p-3 text-text-secondary hover:border-light hover:text-text-primary transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto flex flex-col gap-6">
                {messages.map((m, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
                  >
                    {m.role === "user" ? (
                      <div className="max-w-[85%] rounded-lg rounded-tr-sm px-4 py-2.5 bg-accent-primary text-text-inverse text-[14px] leading-relaxed">
                        {m.content}
                      </div>
                    ) : (
                      <div className="max-w-[92%] w-full">
                        <div className="rounded-lg rounded-tl-sm border border-border bg-bg-surface p-4">
                          {m.content ? (
                            <p className="text-[14px] leading-relaxed text-text-primary whitespace-pre-wrap">
                              {m.content}
                              {m.streaming && <span className="ml-0.5 animate-pulse text-accent-primary">▊</span>}
                            </p>
                          ) : m.error ? (
                            <p className="flex items-center gap-2 text-[13px] text-status-error">
                              <AlertTriangle className="w-4 h-4" /> {m.error}
                            </p>
                          ) : (
                            <p className="flex items-center gap-2 text-[13px] text-text-muted">
                              <Loader2 className="w-4 h-4 animate-spin" /> Retrieving sources…
                            </p>
                          )}

                          {typeof m.retrievalConfidence === "number" && !m.error && (
                            <div className="mt-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest">
                              {m.grounded === false ? (
                                <span className="flex items-center gap-1.5 text-status-warning">
                                  <AlertTriangle className="w-3 h-3" /> Not in corpus
                                </span>
                              ) : (
                                <span className="flex items-center gap-1.5 text-status-success">
                                  <ShieldCheck className="w-3 h-3" />
                                  Grounded in {m.citations?.length ?? 0} sources
                                </span>
                              )}
                              <span className="text-text-dim">
                                · retrieval {Math.round((m.retrievalConfidence ?? 0) * 100)}%
                              </span>
                            </div>
                          )}
                        </div>

                        {m.citations && m.citations.length > 0 && (
                          <div className="mt-2.5 grid gap-2">
                            {m.citations.map((c) => (
                              <CitationCard key={c.index} citation={c} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          {/* Input bar */}
          <div className="border-t border-border p-4 bg-bg-base/80 backdrop-blur">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center gap-2 mb-2">
                <button
                  onClick={() => setStrict((s) => !s)}
                  className="inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded-sm border transition-colors"
                  style={{
                    borderColor: strict ? alpha(tokens.status.success, 0.4) : tokens.border.DEFAULT,
                    color: strict ? tokens.status.success : tokens.text.muted,
                  }}
                >
                  <ShieldCheck className="w-3 h-3" />
                  {strict ? "Strict RAG" : "Extended"}
                </button>
                <span className="font-mono text-[9px] text-text-dim">
                  {strict ? "Answers only from corpus sources" : "Corpus + general legal knowledge"}
                </span>
              </div>
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submit();
                    }
                  }}
                  rows={1}
                  placeholder={empty ? "Index a document first…" : "Ask a question about the loaded statutes…"}
                  disabled={!!empty || offline}
                  className="flex-1 resize-none rounded-md border border-border bg-bg-surface px-4 py-3 text-[14px] text-text-primary placeholder:text-text-dim focus:outline-none focus:border-light disabled:opacity-50 max-h-32"
                />
                {busy ? (
                  <button
                    onClick={stop}
                    className="shrink-0 h-11 w-11 flex items-center justify-center rounded-md border border-status-error/40 text-status-error hover:bg-status-error/10 transition-colors"
                    aria-label="Stop"
                  >
                    <Square className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={submit}
                    disabled={!input.trim() || !!empty || offline}
                    className="shrink-0 h-11 w-11 flex items-center justify-center rounded-md bg-accent-primary text-text-inverse disabled:opacity-40 transition-opacity"
                    aria-label="Send"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>
              <p className="mt-2 flex items-center gap-1.5 font-mono text-[9px] text-text-dim">
                <Sparkles className="w-3 h-3" />
                PRISM cites its sources. Verify against the linked clauses before relying on any answer.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
