"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { useRouter } from "next/navigation";
import type { DocumentMeta } from "@/types";
import { FileText, GitBranch, CheckCircle2, Loader2, Clock, AlertCircle, Database } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { tokens } from "@/lib/tokens";

const STATUS_STYLES = {
  complete:   { color: tokens.status.success, Icon: CheckCircle2, label: "Complete" },
  processing: { color: tokens.status.warning, Icon: Loader2,      label: "Processing…" },
  pending:    { color: tokens.text.secondary, Icon: Clock,         label: "Pending" },
  error:      { color: tokens.status.error,   Icon: AlertCircle,   label: "Error" },
};

function DocCard({ doc, index }: { doc: DocumentMeta; index: number }) {
  const router = useRouter();
  const { setDocId } = useDocumentStore();
  const status = STATUS_STYLES[doc.status] || STATUS_STYLES.pending;
  const StatusIcon = status.Icon;

  const handleOpen = () => {
    setDocId(doc.doc_id, doc.filename, doc.pages);
    router.push(`/analyze/${doc.doc_id}`);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.07 }}
      onClick={doc.status === "complete" || doc.status === "processing" ? handleOpen : undefined}
      className="group flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-200 bg-bg-surface/70 border border-border"
      style={{
        cursor: doc.status === "complete" || doc.status === "processing" ? "pointer" : "default",
      }}
    >
      {/* Icon */}
      <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-accent-primary/10 border border-accent-primary/20">
        <FileText className="w-5 h-5 text-accent-primary" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm truncate text-text-primary">{doc.filename}</p>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-[10px] font-mono text-text-muted">
            {doc.pages > 0 ? `${doc.pages}p` : "—"}
          </span>
          <span className="text-[10px] font-mono text-text-muted">
            {doc.file_size_kb > 0 ? `${(doc.file_size_kb / 1024).toFixed(1)} MB` : "—"}
          </span>
          <span className="text-[9px] font-mono text-text-dim">
            {doc.doc_id.slice(0, 8)}
          </span>
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span
          className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded-lg"
          style={{
            color: status.color,
            background: `${status.color}18`,
            border: `1px solid ${status.color}40`,
          }}
        >
          <StatusIcon className={`w-3 h-3 ${doc.status === "processing" ? "animate-spin" : ""}`} />
          {status.label}
        </span>

        {doc.status === "complete" && (
          <div className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity bg-accent-primary/10 border border-accent-primary/25 text-accent-primary">
            <GitBranch className="w-3 h-3" />
            Open
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function DocumentCorpus() {
  const [docs, setDocs] = useState<DocumentMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listDocuments()
      .then((res) => setDocs(res.documents || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || docs.length === 0) return null;

  const completedDocs = docs.filter((d) => d.status === "complete");
  const recentDocs = docs.slice(-6).reverse(); // Show most recent 6

  return (
    <AnimatePresence>
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 px-6 py-16 max-w-7xl mx-auto border-t border-border"
      >
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-4 h-4 text-accent-primary" />
              <p className="font-mono text-xs uppercase tracking-widest text-accent-primary">
                Document Corpus
              </p>
            </div>
            <h2 className="font-display font-bold text-2xl text-text-primary">
              Recent Analyses
            </h2>
            <p className="text-sm mt-1 text-text-muted">
              {completedDocs.length} document{completedDocs.length !== 1 ? "s" : ""} analyzed in this session
            </p>
          </div>
          {completedDocs.length >= 2 && (
            <a
              href={`/compare?a=${completedDocs[completedDocs.length - 1].doc_id}`}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all bg-accent-primary/10 border border-accent-primary/25 text-accent-primary"
            >
              <GitBranch className="w-3.5 h-3.5" />
              Compare Documents
            </a>
          )}
        </div>

        <div className="space-y-2">
          {recentDocs.map((doc, i) => (
            <DocCard key={doc.doc_id} doc={doc} index={i} />
          ))}
        </div>
      </motion.section>
    </AnimatePresence>
  );
}
