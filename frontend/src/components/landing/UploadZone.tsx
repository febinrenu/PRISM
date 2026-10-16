"use client";

import { useCallback, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, FileUp, Loader2, ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { cn } from "@/lib/utils";

const MAX_MB = 50;

/** Drop or choose a PDF, or open the demo statute. Keyboard operable. */
export default function UploadZone() {
  const router = useRouter();
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<"upload" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { setDocId, reset } = useDocumentStore();

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) return setError("That file is not a PDF.");
      if (file.size > MAX_MB * 1024 * 1024) return setError(`That PDF is larger than ${MAX_MB} MB.`);
      setError(null);
      setBusy("upload");
      reset();
      try {
        const r = await api.uploadPdf(file);
        setDocId(r.doc_id, r.filename, r.pages);
        router.push(`/analyze/${r.doc_id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "The upload failed. Is the analysis server running?");
        setBusy(null);
      }
    },
    [router, setDocId, reset]
  );

  const openDemo = useCallback(async () => {
    setError(null);
    setBusy("demo");
    reset();
    try {
      const r = await api.triggerDemo();
      setDocId(r.doc_id, r.filename, r.pages);
      router.push(`/analyze/${r.doc_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The demo could not be opened.");
      setBusy(null);
    }
  }, [router, setDocId, reset]);

  return (
    <div className="space-y-4">
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        className={cn(
          "group relative flex cursor-pointer flex-col items-start gap-6 overflow-hidden rounded-[8px] border border-dashed p-8 transition-colors duration-300 sm:flex-row sm:items-center sm:p-10",
          "focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-signal",
          dragging ? "border-signal bg-signal/[0.06]" : "border-border-light bg-bg-surface hover:border-glow"
        )}
      >
        <div className="ruled opacity-60" aria-hidden />
        <span
          className={cn(
            "relative flex h-16 w-16 shrink-0 items-center justify-center rounded-[6px] border transition-colors",
            dragging ? "border-signal text-signal" : "border-border-light text-text-secondary group-hover:text-text-primary"
          )}
        >
          {busy === "upload" ? <Loader2 className="h-7 w-7 animate-spin" /> : <FileUp className="h-7 w-7" />}
        </span>
        <span className="relative flex-1">
          <span className="block font-serif text-[28px] leading-tight text-text-primary">
            {dragging ? "Drop it here" : busy === "upload" ? "Uploading…" : "Drop a statute PDF, or choose one"}
          </span>
          <span className="mt-2 block max-w-lg text-[14px] leading-relaxed text-text-muted">
            Acts, Bills and Finance Acts work best: the parser reads chapters, sections, provisos and schedules. Up to{" "}
            {MAX_MB} MB.
          </span>
        </span>
        <span className="relative inline-flex h-10 items-center rounded-[4px] bg-contrast px-4 text-[14px] font-medium text-on-contrast">
          Choose file
        </span>
        <input
          id={inputId}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          disabled={busy !== null}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
      </label>

      <button
        type="button"
        onClick={openDemo}
        disabled={busy !== null}
        className="flex w-full items-center gap-4 rounded-[8px] border border-border bg-bg-surface px-5 py-4 text-left transition-colors hover:border-border-light disabled:opacity-50"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[4px] border border-signal/40 text-signal">
          {busy === "demo" ? <Loader2 className="h-5 w-5 animate-spin" /> : <ScrollText className="h-5 w-5" />}
        </span>
        <span className="flex-1">
          <span className="block text-[15px] text-text-primary">Open the demo: the Income-tax Bill, 2025</span>
          <span className="block text-[13px] text-text-muted">Already analysed, so it opens straight away.</span>
        </span>
      </button>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-[6px] border border-status-critical/40 bg-status-critical/10 p-4 text-[14px] text-status-error"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
