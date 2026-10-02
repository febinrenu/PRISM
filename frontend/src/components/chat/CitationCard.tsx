"use client";

import { useState } from "react";
import { FileText, ChevronDown, ExternalLink } from "lucide-react";
import Link from "next/link";
import { tokens, alpha } from "@/lib/tokens";
import type { RAGCitation } from "@/types";

/** A source card shown beneath a RAG answer. Click to expand the full clause
 *  text; deep-links into the Explainability Studio for that clause. */
export default function CitationCard({ citation }: { citation: RAGCitation }) {
  const [open, setOpen] = useState(false);
  const sim = Math.round((citation.similarity ?? 0) * 100);

  return (
    <div className="rounded-md border border-border bg-bg-surface overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-start gap-3 p-3 text-left transition-colors hover:bg-bg-elevated"
      >
        <div
          className="shrink-0 w-6 h-6 rounded-sm flex items-center justify-center font-mono text-[11px] font-bold"
          style={{
            color: tokens.accent.primary,
            background: alpha(tokens.accent.primary, 0.12),
            border: `1px solid ${alpha(tokens.accent.primary, 0.3)}`,
          }}
        >
          {citation.index}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <FileText className="w-3 h-3 text-text-muted shrink-0" />
            <span className="font-mono text-[11px] text-text-primary truncate">
              {citation.doc_name}
            </span>
            <span className="font-mono text-[10px] text-text-muted">p.{citation.page}</span>
            <span
              className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
              style={{
                color: tokens.status.success,
                background: alpha(tokens.status.success, 0.12),
              }}
            >
              {sim}% match
            </span>
          </div>
          {citation.section && (
            <p className="mt-1 font-mono text-[10px] text-text-muted truncate">{citation.section}</p>
          )}
          {!open && (
            <p className="mt-1.5 text-[12px] leading-snug text-text-secondary line-clamp-2">
              {citation.text_preview}
            </p>
          )}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-text-muted shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-border">
          <p className="text-[13px] leading-relaxed text-text-secondary whitespace-pre-wrap">
            {citation.text}
          </p>
          {citation.entity_types.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {citation.entity_types.map((t) => (
                <span
                  key={t}
                  className="font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm text-text-muted border border-border"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          <Link
            href={`/explain/${citation.doc_id}/${citation.clause_id}`}
            className="mt-2.5 inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-accent-primary hover:text-accent-bright transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            Open in Explainability Studio
          </Link>
        </div>
      )}
    </div>
  );
}
