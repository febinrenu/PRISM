"use client";

import { useState } from "react";
import { BookOpen, ChevronDown, ExternalLink, FileText, Target } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { tokens, alpha } from "@/lib/tokens";
import type { RAGCitation } from "@/types";

/** A source card shown beneath a RAG answer. Click to expand the passage. A
 *  statute passage links to the exact provision in the statute reader; a clause
 *  of an analysed document links to the Explainability Studio. `open` and
 *  `onToggle` let the answer's [Source N] chips open the card they point at. */
export default function CitationCard({
  citation,
  cited,
  open: openProp,
  onToggle,
}: {
  citation: RAGCitation;
  /** True when the answer cites this passage; false when it was only retrieved. */
  cited?: boolean;
  open?: boolean;
  onToggle?: () => void;
}) {
  const [openState, setOpenState] = useState(false);
  const open = openProp ?? openState;
  const toggle = onToggle ?? (() => setOpenState((o) => !o));
  const isStatute = citation.kind === "statute";
  const exact = citation.match === "section";
  const sim = citation.similarity == null ? null : Math.round(citation.similarity * 100);
  const place = isStatute && citation.section ? `section ${citation.section}` : citation.section;

  return (
    <div
      id={`source-${citation.index}`}
      className={cn(
        "overflow-hidden rounded-md border bg-bg-surface transition-colors",
        cited === false ? "border-border/60 opacity-80" : "border-border"
      )}
    >
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-bg-elevated"
      >
        <div
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm font-mono text-micro font-bold"
          style={{
            color: tokens.accent.primary,
            background: alpha(tokens.accent.primary, cited === false ? 0.06 : 0.14),
            border: `1px solid ${alpha(tokens.accent.primary, 0.3)}`,
          }}
        >
          {citation.index}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {isStatute ? (
              <BookOpen className="h-3 w-3 shrink-0 text-text-muted" aria-hidden />
            ) : (
              <FileText className="h-3 w-3 shrink-0 text-text-muted" aria-hidden />
            )}
            <span className="truncate font-mono text-micro text-text-primary">{citation.doc_name}</span>
            {place && <span className="font-mono text-micro text-text-secondary">{place}</span>}
            {citation.page ? <span className="font-mono text-micro text-text-muted">p.{citation.page}</span> : null}
            {exact ? (
              <span
                className="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-micro"
                style={{ color: tokens.status.success, background: alpha(tokens.status.success, 0.12) }}
                title="Fetched by the section number in the question, not by similarity"
              >
                <Target className="h-2.5 w-2.5" aria-hidden /> exact section
              </span>
            ) : sim != null ? (
              <span
                className="rounded-sm px-1.5 py-0.5 font-mono text-micro"
                style={{ color: tokens.status.info, background: alpha(tokens.status.info, 0.12) }}
              >
                {sim}% similar
              </span>
            ) : null}
            {cited === false && (
              <span className="font-mono text-micro uppercase tracking-wider text-text-dim">not cited</span>
            )}
          </div>
          {citation.heading && (
            <p className="mt-1 truncate font-mono text-micro text-text-muted">{citation.heading}</p>
          )}
          {!open && (
            <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-text-secondary">{citation.text_preview}</p>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {open && (
        <div className="border-t border-border px-3 pb-3 pt-1">
          <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-text-secondary">{citation.text}</p>
          {citation.cut && (
            <p className="mt-2 font-mono text-micro text-text-dim">
              Long provision: the model saw the part most relevant to the question; the reader has all of it.
            </p>
          )}
          {citation.entity_types.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {citation.entity_types.map((t) => (
                <span
                  key={t}
                  className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-micro uppercase tracking-wider text-text-muted"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {isStatute && citation.statute_key && citation.node_path ? (
            <Link
              href={`/statutes?s=${encodeURIComponent(citation.statute_key)}&p=${encodeURIComponent(citation.node_path)}`}
              className="mt-2.5 inline-flex items-center gap-1.5 font-mono text-micro uppercase tracking-widest text-accent-primary transition-colors hover:text-accent-bright"
            >
              <ExternalLink className="h-3 w-3" aria-hidden />
              Open in the statute reader
            </Link>
          ) : !isStatute ? (
            <Link
              href={`/explain/${citation.doc_id}/${citation.clause_id}`}
              className="mt-2.5 inline-flex items-center gap-1.5 font-mono text-micro uppercase tracking-widest text-accent-primary transition-colors hover:text-accent-bright"
            >
              <ExternalLink className="h-3 w-3" aria-hidden />
              Open in Explainability Studio
            </Link>
          ) : null}
        </div>
      )}
    </div>
  );
}
