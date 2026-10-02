"use client";
import { useState, useRef } from "react";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { api } from "@/lib/api";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha, riskStyle } from "@/lib/tokens";
import {
  Search, Sparkles, AlertTriangle, ChevronRight,
  Loader2, BookOpen, FileText, Zap
} from "lucide-react";
import type { SearchResult, SearchHit, RiskTier } from "@/types";

function riskCfg(tier: RiskTier): { text: string; border: string; bg: string } {
  const { base, text } = riskStyle(tier);
  return { text, border: alpha(base, 0.35), bg: alpha(base, 0.1) };
}

const RISK_COLORS: Record<RiskTier, { text: string; border: string; bg: string }> = {
  CRITICAL: riskCfg("CRITICAL"),
  HIGH:     riskCfg("HIGH"),
  MEDIUM:   riskCfg("MEDIUM"),
  LOW:      riskCfg("LOW"),
};

const SUGGESTED = [
  "What are the penalties for non-compliance?",
  "Who is exempt from tax obligations?",
  "What are the filing deadlines?",
  "What powers does the Assessing Officer have?",
  "What deductions are available to senior citizens?",
];

function HitCard({ hit, index }: { hit: SearchHit; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const risk = RISK_COLORS[hit.risk_tier];
  const scoreColor = hit.score > 0.7 ? tokens.status.success : hit.score > 0.5 ? tokens.status.warning : tokens.text.secondary;

  return (
    <div
      className="rounded-xl overflow-hidden border border-border bg-bg-surface/70"
      style={{
        animation: `fadeSlideIn 0.2s ease-out ${index * 0.06}s both`,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-deep/50">
        <div className="flex items-center gap-2">
          <FileText className="w-3 h-3 text-text-muted" />
          <span className="text-[10px] font-mono text-text-secondary">
            {hit.section !== "—" ? `§ ${hit.section}` : `Page ${hit.page}`}
          </span>
          <span className="text-text-dim">·</span>
          <span className="text-[10px] font-mono text-text-muted">p.{hit.page}</span>
        </div>
        <div className="flex items-center gap-2">
          {/* Similarity score */}
          <div className="flex items-center gap-1">
            <div className="w-12 h-1.5 rounded-full bg-bg-deep">
              <div
                className="h-full rounded-full"
                style={{ width: `${hit.score * 100}%`, background: scoreColor }}
              />
            </div>
            <span className="text-[9px] font-mono" style={{ color: scoreColor }}>
              {Math.round(hit.score * 100)}%
            </span>
          </div>
          {/* Risk badge */}
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded-full uppercase"
            style={{ background: risk.bg, color: risk.text, border: `1px solid ${risk.border}` }}
          >
            {hit.risk_tier === "CRITICAL" && "⚠ "}
            {hit.risk_tier}
          </span>
          {hit.causal_count > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-accent-primary/10 border border-accent-primary/25 text-accent-bright">
              <Zap className="w-2.5 h-2.5 inline mr-0.5" />
              {hit.causal_count}
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4">
        <p className="text-xs leading-relaxed mb-3 text-text-secondary">
          {expanded ? hit.text : hit.text_preview}
          {!expanded && hit.text.length > hit.text_preview.length && (
            <button
              onClick={() => setExpanded(true)}
              className="ml-1 font-semibold transition-opacity opacity-70 hover:opacity-100 text-accent-primary"
            >
              more
            </button>
          )}
        </p>
        {/* Entity pills */}
        {hit.entities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {hit.entities.slice(0, 5).map((e, i) => {
              const c = ENTITY_COLORS[e.label as keyof typeof ENTITY_COLORS];
              return (
                <span
                  key={i}
                  className="text-[9px] font-mono px-1.5 py-0.5 rounded-full"
                  style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
                >
                  {e.label}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchTab() {
  const { docId, stage } = useDocumentStore();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const isReady = stage === "complete";

  const runSearch = async (q: string) => {
    if (!docId || !q.trim()) return;
    setQuery(q);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.search(docId, q.trim(), 10);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

  if (!isReady) {
    return (
      <div className="p-6 flex flex-col items-center justify-center gap-4 py-16">
        <Search className="w-8 h-8 opacity-20 text-accent-primary" />
        <p className="font-mono text-sm text-text-muted">
          Available after analysis completes
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* ── Search bar ── */}
      <form onSubmit={handleSubmit}>
        <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-bg-surface/80 border border-border">
          <Search className="w-4 h-4 flex-shrink-0 text-text-muted" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything about this document…"
            className="flex-1 bg-transparent outline-none text-sm font-mono placeholder:opacity-40 text-text-primary"
          />
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin flex-shrink-0 text-accent-primary" />
          ) : (
            <button
              type="submit"
              disabled={!query.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-40 bg-accent-primary/15 border border-accent-primary/35 text-accent-primary"
            >
              <Sparkles className="w-3 h-3" />
              Search
            </button>
          )}
        </div>
      </form>

      {/* ── Suggested queries ── */}
      {!result && !loading && (
        <div className="space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-widest text-text-dim">
            Try asking:
          </p>
          <div className="flex flex-col gap-1.5">
            {SUGGESTED.map((s) => (
              <button
                key={s}
                onClick={() => runSearch(s)}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-left text-xs transition-all group border border-border bg-bg-surface/50"
              >
                <ChevronRight className="w-3 h-3 flex-shrink-0 transition-transform group-hover:translate-x-0.5 text-text-muted" />
                <span className="text-text-secondary">{s}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl text-xs bg-status-error/10 border border-status-error/25">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-status-error" />
          <span className="text-status-error">{error}</span>
        </div>
      )}

      {/* ── Results ── */}
      {result && (
        <div className="space-y-4">
          {/* Answer synthesis */}
          <div className="p-4 rounded-2xl bg-accent-primary/5 border border-accent-primary/20">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-3.5 h-3.5 text-accent-primary" />
              <span className="text-[10px] font-mono uppercase tracking-wider text-accent-primary">
                Synthesized Answer
              </span>
              <span className="ml-auto text-[10px] font-mono text-text-muted">
                {result.total_searched} clauses searched
              </span>
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-line text-text-secondary">
              {result.answer}
            </p>
          </div>

          {/* Hits */}
          {result.hits.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <BookOpen className="w-3.5 h-3.5 text-text-muted" />
                <p className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
                  {result.hits.length} relevant clause{result.hits.length !== 1 ? "s" : ""}
                </p>
              </div>
              {result.hits.map((hit, i) => (
                <HitCard key={hit.clause_id} hit={hit} index={i} />
              ))}
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
