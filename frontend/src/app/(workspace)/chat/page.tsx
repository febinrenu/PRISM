"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Send, Square, Sparkles, Database, Loader2, RefreshCw, Cpu, Cloud, ShieldCheck, BookOpen, FileText,
} from "lucide-react";
import PrismMark from "@/components/brand/PrismMark";
import { cn } from "@/lib/utils";
import AssistantMessage from "@/components/chat/AssistantMessage";
import { useRAGChat } from "@/hooks/useRAGChat";
import { api, Phase2UnavailableError } from "@/lib/api";
import type { CorpusDoc, CorpusStats, LLMBackendInfo } from "@/types";

// Each shows a different thing the answer can do: an exact section, a comparison
// across Acts, a rate, a condition, a limit.
const SUGGESTIONS = [
  "What is the rebate under section 156?",
  "Compare the rebate in section 87A of the old Income-tax Act with the new Act",
  "What is the penalty for failing to deduct tax at source?",
  "When can input tax credit be claimed under section 16 of the CGST Act?",
];

function DocButton({ d, selected, on, onToggle }: { d: CorpusDoc; selected: boolean; on: boolean; onToggle: () => void }) {
  const statute = d.kind === "statute";
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={cn(
        "rounded-[4px] border p-3 text-left transition-colors",
        selected ? "border-signal/45 bg-signal/[0.06]" : "border-border hover:border-border-light",
        !on && "opacity-50"
      )}
    >
      <div className="flex items-start gap-1.5">
        {statute ? (
          <BookOpen className="mt-0.5 h-3 w-3 shrink-0 text-text-muted" aria-hidden />
        ) : (
          <FileText className="mt-0.5 h-3 w-3 shrink-0 text-text-muted" aria-hidden />
        )}
        <span className="font-mono text-micro leading-snug text-text-primary">{d.doc_name}</span>
      </div>
      <div className="mt-1 font-mono text-micro uppercase tracking-wider text-text-muted">
        {statute ? `${d.clauses.toLocaleString()} passages` : `${d.clauses} clauses · ${d.causal} with cause → effect`}
      </div>
    </button>
  );
}

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

  // statutes are indexed in the background on a first run: follow the progress
  const indexing = corpus?.indexing ?? 0;
  useEffect(() => {
    if (!indexing) return;
    const t = setInterval(loadCorpus, 5000);
    return () => clearInterval(t);
  }, [indexing]);

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

  const ask = (q: string) => {
    if (!q.trim() || busy) return;
    send(q, Array.from(selected), strict);
  };

  const submit = () => {
    if (!input.trim() || busy) return;
    ask(input);
    setInput("");
  };

  const empty = !!corpus && corpus.total_clauses === 0 && !indexing;
  const statutes = corpus?.documents.filter((d) => d.kind === "statute") ?? [];
  const documents = corpus?.documents.filter((d) => d.kind !== "statute") ?? [];
  const fallback = backend?.fallback;

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border px-4 py-3 sm:px-6">
        <div>
          <h1 className="font-serif text-[22px] leading-none text-text-primary">Ask the corpus</h1>
          <p className="mt-1 text-[12.5px] text-text-muted">
            Answers from the statutes and analysed documents, each statement cited and checked ·{" "}
            {strict ? "corpus only" : "corpus and general knowledge"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {backend && (
            <span
              className="hidden items-center gap-1.5 rounded-[4px] border border-border px-2.5 py-1.5 font-mono text-[12px] text-text-secondary sm:inline-flex"
              title={fallback ? `If it fails, ${fallback.model} answers instead` : undefined}
            >
              {backend.cloud ? <Cloud className="h-3.5 w-3.5" /> : <Cpu className="h-3.5 w-3.5" />}
              {backend.model}
              {fallback && <span className="text-text-dim">· backup {fallback.model}</span>}
            </span>
          )}
          {messages.length > 0 && (
            <button
              type="button"
              onClick={reset}
              className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary"
            >
              <RefreshCw className="h-3.5 w-3.5" /> New chat
            </button>
          )}
        </div>
      </div>

      <div className="flex min-h-0 w-full flex-1">
        {/* Corpus sidebar */}
        <aside className="hidden md:flex flex-col w-72 shrink-0 border-r border-border p-5 gap-4 overflow-y-auto">
          <div className="flex items-center gap-2 font-mono text-micro uppercase tracking-widest text-text-muted">
            <Database className="w-3.5 h-3.5" />
            Corpus
            {corpus && (
              <span className="ml-auto normal-case tracking-normal text-text-secondary">
                {corpus.total_clauses.toLocaleString()} passages
              </span>
            )}
          </div>

          {offline && (
            <div className="rounded-md border border-border p-3 text-[12px] text-text-muted">
              The analysis server is not answering. Start it with start.bat and refresh.
            </div>
          )}

          {indexing > 0 && !offline && (
            <div role="status" className="flex items-start gap-2 rounded-md border border-border p-3 text-[12px] text-text-muted">
              <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
              Indexing the statutes ({indexing} left). You can ask now; more of the law becomes searchable as it finishes.
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
                className="inline-flex w-full items-center justify-center gap-2 rounded-[4px] bg-signal px-3 py-2 text-[13px] font-medium text-ink disabled:opacity-60"
              >
                {ingesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Database className="w-3 h-3" />}
                Index all documents
              </button>
            </div>
          )}

          {documents.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-micro uppercase tracking-widest text-text-dim">Analysed documents</p>
              {documents.map((d) => (
                <DocButton
                  key={d.doc_id}
                  d={d}
                  selected={selected.has(d.doc_id)}
                  on={selected.size === 0 || selected.has(d.doc_id)}
                  onToggle={() => toggleDoc(d.doc_id)}
                />
              ))}
            </div>
          )}

          {statutes.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-micro uppercase tracking-widest text-text-dim">Statutes</p>
              {statutes.map((d) => (
                <DocButton
                  key={d.doc_id}
                  d={d}
                  selected={selected.has(d.doc_id)}
                  on={selected.size === 0 || selected.has(d.doc_id)}
                  onToggle={() => toggleDoc(d.doc_id)}
                />
              ))}
            </div>
          )}

          {documents.length > 0 && (
            <button
              onClick={ingestAll}
              disabled={ingesting}
              className="mt-auto inline-flex items-center justify-center gap-2 font-mono text-micro uppercase tracking-widest px-3 py-2 rounded-sm border border-border text-text-muted hover:text-text-primary transition-colors disabled:opacity-60"
            >
              {ingesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Re-index documents
            </button>
          )}

          <p className="font-mono text-micro leading-relaxed text-text-dim">
            {selected.size === 0
              ? "Searching everything. Select some to filter retrieval."
              : `Filtering to ${selected.size} source${selected.size > 1 ? "s" : ""}.`}
          </p>
        </aside>

        {/* Chat area */}
        <section className="flex flex-col flex-1 min-h-0">
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-8 py-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto">
                <PrismMark size={56} />
                <h2 className="mt-6 font-serif text-title text-text-primary">What does the law say about…</h2>
                <p className="mt-3 text-sm text-text-secondary leading-relaxed">
                  Name a section and it is fetched exactly; ask a question and the best passages are retrieved. Every
                  statement cites its source, and every amount, rate and quotation is checked against it. When the
                  corpus has no answer, it says so.
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
                      <div className="max-w-[85%] rounded-[8px] rounded-tr-[2px] bg-contrast px-4 py-2.5 text-[15px] leading-relaxed text-on-contrast">
                        {m.content}
                      </div>
                    ) : (
                      <AssistantMessage message={m} onFollowUp={i === messages.length - 1 && !busy ? ask : undefined} />
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
                  type="button"
                  aria-pressed={strict}
                  onClick={() => setStrict((s) => !s)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-[4px] border px-2 py-1 text-[12.5px] transition-colors",
                    strict ? "border-status-success/40 text-status-success" : "border-border text-text-muted"
                  )}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {strict ? "Corpus only" : "Extended"}
                </button>
                <span className="font-mono text-micro text-text-dim">
                  {strict ? "Answers only from corpus sources, checked" : "Corpus + general legal knowledge (not checked)"}
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
                  maxLength={2000}
                  placeholder={empty ? "Index a document first…" : messages.length ? "Ask a follow-up…" : "Ask a question, or name a section…"}
                  disabled={empty || offline}
                  aria-label="Your question"
                  className="max-h-32 flex-1 resize-none rounded-[4px] border border-border-light bg-bg-surface px-4 py-3 text-[15px] text-text-primary placeholder:text-text-dim hover:border-glow focus:border-signal focus:outline-none disabled:opacity-50"
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
                    disabled={!input.trim() || empty || offline}
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[4px] bg-signal text-ink transition-opacity disabled:opacity-40"
                    aria-label="Send"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>
              <p className="mt-2 flex items-center gap-1.5 font-mono text-micro text-text-dim">
                <Sparkles className="w-3 h-3" />
                Amounts, rates and quotations are matched to the cited text. Read the cited provision before relying on
                an answer: whether a paraphrase is faithful is not something a check can settle.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
