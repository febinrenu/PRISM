"use client";

import { ScanText } from "lucide-react";
import type { ReadingSummary } from "@/types";

/** "p. 3, 5–9, 12" from page numbers. */
export function pageRanges(pages: number[]): string {
  const sorted = Array.from(new Set(pages)).sort((a, b) => a - b);
  const out: string[] = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    out.push(j > i ? `${sorted[i]}–${sorted[j]}` : `${sorted[i]}`);
    i = j + 1;
  }
  return `p. ${out.join(", ")}`;
}

/**
 * Says how the document's text was obtained when any page did not come
 * straight from the PDF's text layer: OCR'd pages are worth checking against
 * the page image; unreadable pages contributed nothing.
 */
export default function ReadingNotice({ reading }: { reading?: ReadingSummary | null }) {
  if (!reading || (!reading.ocr && !reading.unreadable && !reading.decoded)) return null;
  const parts: string[] = [];
  if (reading.ocr)
    parts.push(
      `${reading.ocr} page${reading.ocr === 1 ? " was" : "s were"} read by OCR (${pageRanges(reading.ocr_pages)}` +
        (reading.ocr_confidence !== null ? `, mean confidence ${Math.round(reading.ocr_confidence * 100)}%` : "") +
        "): check quotes from them against the page"
    );
  if (reading.unreadable)
    parts.push(
      `${reading.unreadable} page${reading.unreadable === 1 ? " has" : "s have"} no usable text (${pageRanges(reading.unreadable_pages)})` +
        (reading.ocr_available === false ? " and OCR is not installed on the server" : "")
    );
  if (reading.decoded)
    parts.push(`${reading.decoded} page${reading.decoded === 1 ? "" : "s"} decoded exactly from font glyph names`);
  const warn = reading.ocr > 0 || reading.unreadable > 0;
  return (
    <div
      role="status"
      className={
        "flex shrink-0 items-start gap-2.5 border-b border-border px-4 py-2 text-[13px] sm:px-6 " +
        (warn ? "bg-status-warning/[0.07] text-status-warning" : "bg-bg-surface text-text-muted")
      }
    >
      <ScanText className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <p className="min-w-0">{parts.join(" · ")}.</p>
    </div>
  );
}
