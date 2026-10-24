"use client";

import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Deletes a document after an inline confirmation: its analysis, model
 * readings, explanations, sandbox runs and the uploaded PDF. The server
 * decides who may (the owner, an admin, anyone for an anonymous upload).
 */
export default function DeleteDocumentButton({
  docId,
  name,
  onDeleted,
  compact = false,
}: {
  docId: string;
  name?: string;
  onDeleted: () => void;
  compact?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteDocument(docId);
      toast(`${name || "The document"} was deleted`);
      onDeleted();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The document could not be deleted.");
      setBusy(false);
      setConfirming(false);
    }
  };

  if (confirming)
    return (
      <span className="flex items-center gap-1.5" role="group" aria-label="Confirm deletion">
        {!compact && (
          <span className="hidden text-[12px] text-text-muted sm:inline">Delete its analysis and the PDF?</span>
        )}
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] bg-status-critical px-3 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-60"
        >
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
          Delete
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          disabled={busy}
          className="inline-flex h-8 items-center rounded-[4px] px-2 text-[13px] text-text-muted hover:text-text-primary"
        >
          Cancel
        </button>
      </span>
    );

  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setConfirming(true);
      }}
      title="Delete this document"
      aria-label={`Delete ${name || "this document"}`}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-[4px] text-[13px] text-text-muted hover:text-status-critical",
        compact ? "w-8 justify-center" : "border border-border-light px-3 hover:border-status-critical/60"
      )}
    >
      <Trash2 className="h-3.5 w-3.5" aria-hidden />
      {!compact && "Delete"}
    </button>
  );
}
