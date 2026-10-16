"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FileText, Loader2, Swords } from "lucide-react";
import { api } from "@/lib/api";
import { tokens, alpha } from "@/lib/tokens";
import type { DocumentMeta } from "@/types";

function DocColumn({
  slot,
  accent,
  docs,
  selected,
  disabledId,
  onSelect,
}: {
  slot: "A" | "B";
  accent: string;
  docs: DocumentMeta[];
  selected: string;
  disabledId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold border"
          style={{
            color: accent,
            borderColor: alpha(accent, 0.35),
            background: alpha(accent, 0.1),
          }}
        >
          {slot}
        </span>
        <p className="text-micro font-mono uppercase tracking-widest text-text-muted">
          {slot === "A" ? "Document A · baseline" : "Document B · revision"}
        </p>
      </div>
      <div className="space-y-2">
        {docs.map((doc) => {
          const isSelected = doc.doc_id === selected;
          const isDisabled = doc.doc_id === disabledId;
          return (
            <button
              key={doc.doc_id}
              onClick={() => onSelect(doc.doc_id)}
              disabled={isDisabled}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left border transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              style={{
                background: isSelected ? alpha(accent, 0.12) : alpha(tokens.paper[100], 0.02),
                borderColor: isSelected ? alpha(accent, 0.55) : tokens.border.DEFAULT,
              }}
            >
              <FileText
                className="w-4 h-4 flex-shrink-0"
                style={{ color: isSelected ? accent : tokens.text.dim }}
              />
              <span className="min-w-0 flex-1">
                <span
                  className="block text-xs font-medium truncate"
                  style={{ color: isSelected ? tokens.text.primary : tokens.text.secondary }}
                >
                  {doc.filename}
                </span>
                <span className="block text-micro font-mono text-text-muted mt-0.5">
                  {doc.pages}p · {Math.round(doc.file_size_kb)} KB
                </span>
              </span>
              {isSelected && (
                <span
                  className="text-micro font-mono px-1.5 py-0.5 rounded-full flex-shrink-0 border"
                  style={{ color: accent, borderColor: alpha(accent, 0.4) }}
                >
                  selected
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Hero selection screen shown when ?a or ?b is missing — pick two analyzed
 *  documents and the arena opens. */
export default function DocPicker({
  initialA,
  initialB,
}: {
  initialA?: string | null;
  initialB?: string | null;
}) {
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentMeta[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [a, setA] = useState(initialA ?? "");
  const [b, setB] = useState(initialB ?? "");

  useEffect(() => {
    api
      .listDocuments()
      .then((r) => setDocs((r.documents || []).filter((d) => d.status === "complete")))
      .catch((e) => {
        // Distinguish a real backend failure from "no documents" — otherwise a
        // failed request looks identical to an empty corpus.
        setLoadError(e instanceof Error ? e.message : "Failed to load documents");
        setDocs([]);
      });
  }, []);

  useEffect(() => {
    if (a && b && a !== b) router.push(`/compare?a=${a}&b=${b}`);
  }, [a, b, router]);

  return (
    <div className="mx-auto max-w-7xl px-4 pb-10 sm:px-6 lg:px-8">

      {docs === null ? (
        <div className="flex items-center justify-center gap-2 py-16 text-text-muted">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-xs font-mono">Loading corpus…</span>
        </div>
      ) : loadError ? (
        <div className="glass-card p-10 text-center">
          <p className="text-xs font-mono text-status-error leading-relaxed">
            Couldn’t load your documents — {loadError}.
            <br />
            Is the analysis server running? Start it with start.bat and retry.
          </p>
        </div>
      ) : docs.length < 2 ? (
        <div className="glass-card p-10 text-center">
          <p className="text-xs font-mono text-text-muted leading-relaxed">
            Comparing needs two analysed documents.
            <br />
            <Link href="/start" className="text-text-primary underline underline-offset-4 hover:text-accent-primary">
              Upload and analyse a PDF
            </Link>{" "}
            first.
          </p>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card flex flex-col items-stretch gap-4 p-4 sm:flex-row sm:items-start sm:gap-6 sm:p-6"
        >
          <DocColumn
            slot="A"
            accent={tokens.diff.removed}
            docs={docs}
            selected={a}
            disabledId={b}
            onSelect={setA}
          />
          <div className="flex flex-shrink-0 items-center gap-2 self-center px-1 sm:flex-col">
            <Swords className="w-5 h-5 text-accent-primary" />
            <span className="text-micro font-mono uppercase tracking-widest text-text-dim">vs</span>
          </div>
          <DocColumn
            slot="B"
            accent={tokens.diff.added}
            docs={docs}
            selected={b}
            disabledId={a}
            onSelect={setB}
          />
        </motion.div>
      )}
    </div>
  );
}
