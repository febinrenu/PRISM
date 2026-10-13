"use client";

import Link from "next/link";
import useSWR from "swr";
import { ArrowUpRight, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { EmptyState, ErrorState, Skeleton, StatusTag } from "@/components/ui/kit";
import type { DocumentMeta } from "@/types";

/** The documents you can open: shared ones plus your own uploads. */
export default function DocumentCorpus({ limit = 8 }: { limit?: number }) {
  const { data, error, isLoading, mutate } = useSWR("documents", () => api.listDocuments());

  if (isLoading)
    return (
      <div className="space-y-2" aria-label="Loading documents">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-[68px]" />
        ))}
      </div>
    );
  if (error) return <ErrorState offline onRetry={() => mutate()} />;
  const docs: DocumentMeta[] = (data?.documents ?? []).slice().reverse().slice(0, limit);
  if (docs.length === 0)
    return <EmptyState title="Nothing analysed yet">Upload a statute above, or open the demo.</EmptyState>;

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-[8px] border border-border bg-bg-surface">
      {docs.map((d) => {
        const openable = d.status === "complete" || d.status === "processing";
        const body = (
          <>
            <FileText className="h-5 w-5 shrink-0 text-text-muted" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[15px] text-text-primary">{d.filename}</span>
              <span className="mt-0.5 block font-mono text-micro text-text-dim">
                {d.pages > 0 ? `${d.pages} pages` : "pages unknown"} · {(d.file_size_kb / 1024).toFixed(1)} MB
                {d.owner_id ? " · yours" : " · shared"}
              </span>
            </span>
            <StatusTag status={d.status} />
            {openable && <ArrowUpRight className="h-4 w-4 text-text-dim transition-colors group-hover:text-signal" aria-hidden />}
          </>
        );
        return (
          <li key={d.doc_id}>
            {openable ? (
              <Link href={`/analyze/${d.doc_id}`} className="group flex items-center gap-4 px-5 py-4 transition-colors hover:bg-bg-elevated">
                {body}
              </Link>
            ) : (
              <div className="flex items-center gap-4 px-5 py-4 opacity-70">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
