"use client";
import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, Loader2, Sparkles, AlertCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { tokens, alpha } from "@/lib/tokens";

export default function UploadZone() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { setDocId, reset } = useDocumentStore();

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file.");
      return;
    }
    setError(null);
    setIsUploading(true);
    reset();
    try {
      const result = await api.uploadPdf(file);
      setDocId(result.doc_id, result.filename, result.pages);
      router.push(`/analyze/${result.doc_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed. Is the backend running?");
    } finally {
      setIsUploading(false);
    }
  }, [router, setDocId, reset]);

  const handleDemo = useCallback(async () => {
    setError(null);
    setIsLoadingDemo(true);
    reset();
    try {
      const result = await api.triggerDemo();
      setDocId(result.doc_id, result.filename, result.pages);
      router.push(`/analyze/${result.doc_id}`);
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message
          : "Demo PDF not found. Place income_tax_2025.pdf in backend/data/demo/"
      );
    } finally {
      setIsLoadingDemo(false);
    }
  }, [router, setDocId, reset]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div className="w-full max-w-3xl space-y-4">
      {/* Drop zone */}
      <motion.div
        className="relative rounded-2xl cursor-pointer overflow-hidden transition-all duration-300"
        style={{
          border: isDragging
            ? `1px solid ${alpha(tokens.accent.primary, 0.8)}`
            : `1px solid ${tokens.border.light}`,
          background: isDragging
            ? `linear-gradient(160deg, ${alpha(tokens.accent.primary, 0.16)}, ${alpha(tokens.bg.elevated, 0.95)})`
            : `linear-gradient(160deg, ${alpha(tokens.bg.elevated, 0.86)}, ${alpha(tokens.bg.surface, 0.9)})`,
          boxShadow: isDragging
            ? `0 26px 50px ${alpha(tokens.accent.primary, 0.18)}`
            : "0 16px 32px rgba(0,0,0,0.25)",
        }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => !isUploading && inputRef.current?.click()}
        whileTap={{ scale: 0.995 }}
      >
        {/* Corner accents */}
        <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 rounded-tl-2xl border-accent-primary/50" />
        <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 rounded-tr-2xl border-accent-primary/50" />
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 rounded-bl-2xl border-accent-primary/50" />
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 rounded-br-2xl border-accent-primary/50" />

        <div className="relative p-12 flex flex-col md:flex-row items-center gap-8">
          {/* Icon */}
          <motion.div
            className="relative flex-shrink-0"
            animate={isDragging ? { y: [-4, 4, -4] } : {}}
            transition={{ duration: 1, repeat: Infinity }}
          >
            <div className="w-20 h-20 rounded-2xl flex items-center justify-center bg-accent-primary/10 border border-accent-primary/35">
              {isUploading ? (
                <Loader2 className="w-9 h-9 animate-spin text-accent-primary" />
              ) : (
                <Upload className="w-9 h-9 text-accent-primary" />
              )}
            </div>
            {!isUploading && (
              <motion.div
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full border-2 flex items-center justify-center bg-status-success border-bg-base"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-text-primary" />
              </motion.div>
            )}
          </motion.div>

          {/* Text */}
          <div className="flex-1 text-center md:text-left">
            <h3 className="font-display font-bold text-2xl mb-2 text-text-primary">
              {isDragging ? "Release to analyze" : isUploading ? "Uploading…" : "Upload Legal Document"}
            </h3>
            <p className="text-sm leading-relaxed mb-4 text-text-secondary">
              Drop any legal PDF — Acts, Bills, Policies, Regulations, Contracts.
              The pipeline runs entirely locally and privately.
            </p>
            <div className="flex flex-wrap gap-2 justify-center md:justify-start">
              {["PDF only", "Max 50MB", "Local & Private"].map((tag) => (
                <span key={tag} className="text-[10px] font-mono px-2 py-1 rounded-lg uppercase tracking-wider text-text-muted border border-border bg-bg-deep/35">
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* CTA */}
          <div className="flex-shrink-0 flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-text-inverse pointer-events-none"
            style={{ background: `linear-gradient(135deg, ${tokens.accent.primary}, ${tokens.accent.bright})` }}>
            <FileText className="w-4 h-4" />
            <span>Browse</span>
            <ArrowRight className="w-4 h-4" />
          </div>
        </div>

        <input ref={inputRef} type="file" accept=".pdf" className="hidden"
          onChange={(e) => { const file = e.target.files?.[0]; if (file) handleFile(file); }} />
      </motion.div>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-border" />
        <span className="font-mono text-xs uppercase tracking-widest text-text-muted">or try the demo</span>
        <div className="flex-1 h-px bg-border" />
      </div>

      {/* Demo button */}
      <motion.button
        onClick={handleDemo}
        disabled={isLoadingDemo || isUploading}
        className="w-full py-4 px-6 rounded-xl transition-all duration-300 flex items-center justify-center gap-3 font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          border: `1px solid ${alpha(tokens.accent.primary, 0.38)}`,
          background: alpha(tokens.accent.primary, 0.08),
        }}
        whileHover={{ background: alpha(tokens.accent.primary, 0.16) }}
        whileTap={{ scale: 0.99 }}
      >
        {isLoadingDemo ? (
          <Loader2 className="w-4 h-4 animate-spin text-accent-primary" />
        ) : (
          <Sparkles className="w-4 h-4 text-accent-primary" />
        )}
        <span className="text-text-primary">
          {isLoadingDemo ? "Loading demo…" : "Try Demo — Income Tax Bill 2025"}
        </span>
        {!isLoadingDemo && (
          <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded text-text-muted border border-border bg-bg-deep/30">
            ~200 clauses
          </span>
        )}
      </motion.button>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: "auto" }}
            exit={{ opacity: 0, y: -8, height: 0 }}
            className="flex items-start gap-2.5 p-4 rounded-xl text-sm bg-status-error/10 border border-status-error/20"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-status-error" />
            <span className="text-status-error">{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
