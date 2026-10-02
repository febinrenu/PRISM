"use client";
import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, FileText } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { PDF_URL } from "@/lib/api";
import { alpha, entityStyle } from "@/lib/tokens";

// Self-hosted PDF.js worker — copied from pdfjs-dist to public/ by the
// postinstall script (no CDN dependency, works fully offline). Bundling it
// via new URL(import.meta.url) breaks Next 14's Terser pass, hence public/.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

export default function PDFViewerPanel({ docId }: { docId: string }) {
  const { currentPdfPage, setPdfPage, clauses, selectedClauseId } =
    useDocumentStore();
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.0);
  const [isLoaded, setIsLoaded] = useState(false);

  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setIsLoaded(true);
    },
    []
  );

  // Get selected clause to highlight
  const selectedClause = clauses.find((c) => c.clause_id === selectedClauseId);
  const pageAnnotations = clauses.filter((c) => c.page === currentPdfPage && c.bbox);

  const pdfUrl = PDF_URL(docId);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-text-muted" />
          <span className="text-xs font-display font-medium text-text-primary">
            Document Viewer
          </span>
          {isLoaded && (
            <span className="text-[10px] text-text-muted font-mono bg-bg-elevated px-1.5 py-0.5 rounded border border-border">
              {numPages}p
            </span>
          )}
        </div>
        {/* Zoom */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setScale((s) => Math.max(0.5, s - 0.1))}
            className="p-1 rounded hover:bg-bg-elevated border border-transparent hover:border-border transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5 text-text-muted" />
          </button>
          <span className="text-[10px] font-mono text-text-muted w-10 text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={() => setScale((s) => Math.min(2.5, s + 0.1))}
            className="p-1 rounded hover:bg-bg-elevated border border-transparent hover:border-border transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5 text-text-muted" />
          </button>
        </div>
      </div>

      {/* PDF Viewer */}
      <div className="flex-1 overflow-auto bg-bg-base/50 relative">
        {!isLoaded && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-text-muted text-sm">
              <div className="w-8 h-8 border-2 border-accent-primary/30 border-t-accent-primary rounded-full animate-spin mx-auto mb-2" />
              <p className="text-xs">Loading PDF…</p>
            </div>
          </div>
        )}

        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(err) => {
            console.warn("PDF load error:", err.message);
          }}
          loading=""
          error={
            <div className="flex flex-col items-center justify-center h-full p-8 text-center text-text-muted text-sm gap-3">
              <FileText className="w-10 h-10 opacity-30" />
              <div>
                <p className="font-medium text-text-secondary">PDF Preview Unavailable</p>
                <p className="text-xs mt-1 text-text-muted">
                  The clause intelligence panel on the right contains all extracted data.
                </p>
                <p className="text-xs mt-2 text-text-dim font-mono">
                  (PDF serving requires /api/pdf/&#123;docId&#125; endpoint)
                </p>
              </div>
            </div>
          }
          className="flex flex-col items-center py-4 gap-2"
        >
          <div className="relative">
            <Page
              pageNumber={currentPdfPage}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={false}
            />

            {/* SVG annotation overlay — every clause tinted by its dominant
                entity type; click a region to select that clause in the feed */}
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
                  const isSelected = clause.clause_id === selectedClauseId;
                  const entity = entityStyle(clause.entities[0]?.label ?? "");
                  return (
                    <rect
                      key={clause.clause_id}
                      x={x0}
                      y={y0}
                      width={Math.max(x1 - x0, 0.001)}
                      height={Math.max(y1 - y0, 0.001)}
                      fill={alpha(entity.base, isSelected ? 0.45 : 0.16)}
                      stroke={isSelected ? entity.text : "transparent"}
                      strokeWidth="0.0025"
                      rx="0.003"
                      style={{ cursor: "pointer", pointerEvents: "all" }}
                      onClick={() =>
                        useDocumentStore.getState().setSelectedClauseId(
                          isSelected ? null : clause.clause_id
                        )
                      }
                    >
                      <title>
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
      {isLoaded && numPages > 1 && (
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-2.5 border-t border-border">
          <button
            onClick={() => setPdfPage(Math.max(1, currentPdfPage - 1))}
            disabled={currentPdfPage <= 1}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-xs text-text-muted hover:text-text-primary hover:border-accent-primary/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Prev
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-text-muted">
              Page
            </span>
            <input
              type="number"
              min={1}
              max={numPages}
              value={currentPdfPage}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                if (v >= 1 && v <= numPages) setPdfPage(v);
              }}
              className="w-12 text-center bg-bg-elevated border border-border rounded px-1.5 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary/50"
            />
            <span className="text-xs font-mono text-text-muted">/ {numPages}</span>
          </div>
          <button
            onClick={() => setPdfPage(Math.min(numPages, currentPdfPage + 1))}
            disabled={currentPdfPage >= numPages}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-border text-xs text-text-muted hover:text-text-primary hover:border-accent-primary/40 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Hint when PDF not visible */}
      {isLoaded && selectedClause && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex-shrink-0 px-4 py-2 border-t border-border bg-accent-primary/5 text-[10px] text-accent-primary font-mono"
        >
          → Viewing clause on page {selectedClause.page}
        </motion.div>
      )}
    </div>
  );
}
