"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { PDF_URL } from "@/lib/api";
import { tokens, alpha } from "@/lib/tokens";
import type { Clause } from "@/types";
import type { DiffKind } from "./ClauseDiffList";

// Self-hosted PDF.js worker served from public/ (copied by postinstall) —
// no CDN dependency; bundling via import.meta.url breaks Next 14's Terser.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

const KIND_FILL: Record<DiffKind, string> = {
  added: tokens.diff.added,
  removed: tokens.diff.removed,
  modified: tokens.diff.modified,
};

/** Lean side-by-side PDF pane for the diff arena. Page is controlled by the
 *  parent so clicking a diff row can jump both panes at once. Clause bboxes
 *  are tinted by their diff status; matched clauses get a whisper-faint wash. */
export default function DiffPDFPane({
  docId,
  label,
  filename,
  clauses,
  statusByClauseId,
  selectedClauseId,
  page,
  onPageChange,
  onSelectClause,
}: {
  docId: string;
  label: "A" | "B";
  filename: string;
  clauses: Clause[];
  statusByClauseId: Map<string, DiffKind>;
  selectedClauseId: string | null;
  page: number;
  onPageChange: (page: number) => void;
  onSelectClause?: (clauseId: string) => void;
}) {
  const [numPages, setNumPages] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setPageWidth(Math.max(0, el.clientWidth - 24));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setIsLoaded(true);
  }, []);

  const safePage = numPages > 0 ? Math.min(Math.max(1, page), numPages) : page;
  const pageAnnotations = clauses.filter((c) => c.page === safePage && c.bbox);
  const paneAccent = label === "A" ? tokens.diff.removed : tokens.diff.added;

  return (
    <div className="glass-card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b border-border">
        <span
          className="w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 border"
          style={{
            color: paneAccent,
            borderColor: alpha(paneAccent, 0.35),
            background: alpha(paneAccent, 0.1),
          }}
        >
          {label}
        </span>
        <span className="text-xs font-display font-medium text-text-primary truncate">
          {filename}
        </span>
        {isLoaded && (
          <span className="ml-auto text-[10px] font-mono text-text-muted flex-shrink-0">
            {numPages}p
          </span>
        )}
      </div>

      {/* PDF */}
      <div ref={containerRef} className="flex-1 overflow-auto bg-bg-base/50 relative">
        {!isLoaded && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-text-muted">
              <div className="w-7 h-7 border-2 border-accent-primary/30 border-t-accent-primary rounded-full animate-spin mx-auto mb-2" />
              <p className="text-[10px] font-mono">Loading PDF…</p>
            </div>
          </div>
        )}

        <Document
          file={PDF_URL(docId)}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(err) => console.warn("PDF load error:", err.message)}
          loading=""
          error={
            <div className="flex flex-col items-center justify-center h-full p-6 text-center text-text-muted gap-2">
              <FileText className="w-8 h-8 opacity-30" />
              <p className="text-xs font-medium text-text-secondary">PDF preview unavailable</p>
              <p className="text-[10px] font-mono text-text-dim">
                Clause changes remain browsable in the center column.
              </p>
            </div>
          }
          className="flex flex-col items-center py-3"
        >
          <div className="relative">
            {pageWidth > 0 && (
              <Page
                pageNumber={safePage}
                width={pageWidth}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            )}

            {/* Normalized-bbox overlay tinted by diff status */}
            {isLoaded && pageAnnotations.length > 0 && (
              <svg
                className="absolute inset-0"
                style={{ width: "100%", height: "100%" }}
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
              >
                {pageAnnotations.map((clause) => {
                  if (!clause.bbox) return null;
                  const [x0, y0, x1, y1] = clause.bbox;
                  const status = statusByClauseId.get(clause.clause_id);
                  const isSelected = clause.clause_id === selectedClauseId;
                  const base = status ? KIND_FILL[status] : null;
                  const fill = base
                    ? alpha(base, isSelected ? 0.42 : 0.18)
                    : alpha(tokens.accent.primary, 0.05);
                  return (
                    <rect
                      key={clause.clause_id}
                      x={x0}
                      y={y0}
                      width={Math.max(x1 - x0, 0.001)}
                      height={Math.max(y1 - y0, 0.001)}
                      fill={fill}
                      stroke={isSelected && base ? base : "transparent"}
                      strokeWidth="0.0025"
                      rx="0.003"
                      style={{
                        cursor: status && onSelectClause ? "pointer" : "default",
                        pointerEvents: "all",
                      }}
                      onClick={() => status && onSelectClause?.(clause.clause_id)}
                    >
                      <title>
                        {status ? status.toUpperCase() : "matched"} ·{" "}
                        {clause.section_hierarchy.length > 0
                          ? `§${clause.section_hierarchy.join(".")}`
                          : clause.clause_id.slice(-5)}
                      </title>
                    </rect>
                  );
                })}
              </svg>
            )}
          </div>
        </Document>
      </div>

      {/* Page navigation */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 border-t border-border">
        <button
          onClick={() => onPageChange(Math.max(1, safePage - 1))}
          disabled={!isLoaded || safePage <= 1}
          className="flex items-center gap-1 px-2 py-1 rounded-lg border border-border text-[10px] font-mono text-text-muted hover:text-text-primary hover:border-accent-primary/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-3 h-3" /> Prev
        </button>
        <span className="text-[10px] font-mono text-text-muted">
          {safePage} / {numPages || "—"}
        </span>
        <button
          onClick={() => onPageChange(Math.min(numPages || safePage, safePage + 1))}
          disabled={!isLoaded || safePage >= numPages}
          className="flex items-center gap-1 px-2 py-1 rounded-lg border border-border text-[10px] font-mono text-text-muted hover:text-text-primary hover:border-accent-primary/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
