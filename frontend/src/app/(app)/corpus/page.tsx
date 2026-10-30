"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Cloud, Cpu, FileText, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, Phase2UnavailableError } from "@/lib/api";
import type { CorpusStats, DocumentMeta, LLMBackendInfo } from "@/types";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { EmptyState, ErrorState, Panel, Skeleton } from "@/components/ui/kit";
import { buttonVariants } from "@/components/ui/button";

export default function CorpusPage() {
  const [corpus, setCorpus] = useState<CorpusStats | null>(null);
  const [backend, setBackend] = useState<LLMBackendInfo | null>(null);
  const [allDocs, setAllDocs] = useState<DocumentMeta[]>([]);
  const [offline, setOffline] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    try {
      const [c, b, docs] = await Promise.all([api.getCorpus(), api.getBackend(), api.listDocuments()]);
      setCorpus(c);
      setBackend(b);
      setAllDocs(docs.documents);
      setOffline(false);
      setLoadError(null);
    } catch (e) {
      if (e instanceof Phase2UnavailableError || e instanceof TypeError) setOffline(true);
      else setLoadError(e instanceof Error ? e.message : "The corpus could not be loaded.");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const indexed = new Set(corpus?.documents.map((d) => d.doc_id) ?? []);
  const notIndexed = allDocs.filter((d) => d.status === "complete" && !indexed.has(d.doc_id));

  const act = async (key: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(key);
    try {
      await fn();
      await load();
      toast(done);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "That did not work.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <PageContainer>
      <PageHeader
        kicker="Corpus"
        title="What the Ask view can search"
        lede="Analysed documents are indexed clause by clause for retrieval. Questions in the Ask view are answered only from what is indexed here."
        actions={
          <>
            {backend && (
              <span className="inline-flex h-10 items-center gap-1.5 rounded-[4px] border border-border px-3 font-mono text-[12.5px] text-text-secondary">
                {backend.cloud ? <Cloud className="h-3.5 w-3.5" /> : <Cpu className="h-3.5 w-3.5" />}
                {backend.model}
              </span>
            )}
            <Link href="/chat" className={buttonVariants({ variant: "primary" })}>
              Ask the corpus
            </Link>
          </>
        }
      >
        {corpus && (
          <p className="mt-6 font-mono text-[13px] text-text-muted">
            {corpus.documents.length} documents · {corpus.total_clauses.toLocaleString("en-IN")} clauses indexed
          </p>
        )}
      </PageHeader>

      {offline && <ErrorState offline onRetry={load} />}
      {!offline && loadError && <ErrorState title="The corpus could not be loaded" message={loadError} onRetry={load} />}

      {!offline && !loadError && !corpus && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      )}

      {corpus && corpus.documents.length === 0 && (
        <Panel>
          <EmptyState title="Nothing indexed yet">Index the analysed documents below to make them searchable.</EmptyState>
        </Panel>
      )}

      {corpus && corpus.documents.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {corpus.documents.map((d) => {
            // a statute is part of PRISM: read it in the statute reader, not removable
            const statute = d.kind === "statute";
            const key = statute ? d.doc_id.replace(/^statute:/, "").replace(":", "/") : "";
            return (
              <li key={d.doc_id} className="glass-card flex flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    {statute ? (
                      <BookOpen className="h-4 w-4 shrink-0 text-text-dim" aria-hidden />
                    ) : (
                      <FileText className="h-4 w-4 shrink-0 text-text-dim" aria-hidden />
                    )}
                    <h2 className="truncate text-[15px] text-text-primary">{d.doc_name}</h2>
                  </div>
                  {!statute && (
                    <button
                      type="button"
                      onClick={() => act(d.doc_id, () => api.removeFromCorpus(d.doc_id), "Removed from the corpus")}
                      disabled={busy === d.doc_id}
                      aria-label={`Remove ${d.doc_name} from the corpus`}
                      className="text-text-dim transition-colors hover:text-status-error"
                    >
                      {busy === d.doc_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    </button>
                  )}
                </div>
                <dl className="mt-5 flex gap-8">
                  <div>
                    <dd className="font-serif text-[2rem] leading-none text-text-primary">{d.clauses.toLocaleString("en-IN")}</dd>
                    <dt className="mt-1 text-[12px] text-text-muted">{statute ? "passages" : "clauses"}</dt>
                  </div>
                  {!statute && (
                    <div>
                      <dd className="font-serif text-[2rem] leading-none text-text-primary">{d.causal.toLocaleString("en-IN")}</dd>
                      <dt className="mt-1 text-[12px] text-text-muted">clauses with a condition → consequence</dt>
                    </div>
                  )}
                </dl>
                <div className="mt-auto flex gap-2 pt-5">
                  {statute ? (
                    <Link
                      href={`/statutes?s=${encodeURIComponent(key)}`}
                      className={buttonVariants({ variant: "outline", size: "sm", className: "flex-1" })}
                    >
                      Read the statute
                    </Link>
                  ) : (
                    <>
                      <Link href={`/analyze/${d.doc_id}`} className={buttonVariants({ variant: "outline", size: "sm", className: "flex-1" })}>
                        Workspace
                      </Link>
                      <Link href={`/provenance/${d.doc_id}`} className={buttonVariants({ variant: "ghost", size: "sm", className: "flex-1" })}>
                        Provenance
                      </Link>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {!offline && corpus && (notIndexed.length > 0 || corpus.documents.length === 0) && (
        <Panel
          className="mt-10"
          kicker="Not yet searchable"
          title="Add to the corpus"
          actions={
            <button
              type="button"
              onClick={() => act("all", () => api.ingestAll(), "Every analysed document is indexed")}
              disabled={busy === "all"}
              className={buttonVariants({ variant: "secondary", size: "sm" })}
            >
              {busy === "all" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Index all
            </button>
          }
          flush
        >
          {notIndexed.length > 0 ? (
            <ul className="divide-y divide-border">
              {notIndexed.map((d) => (
                <li key={d.doc_id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <span className="truncate text-[14px]">{d.filename}</span>
                  <button
                    type="button"
                    onClick={() => act(d.doc_id, () => api.ingestDoc(d.doc_id), `${d.filename} indexed`)}
                    disabled={busy === d.doc_id}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    {busy === d.doc_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Index
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-5 py-4 text-[14px] text-text-muted">
              Every analysed document is indexed. <Link href="/start" className="underline underline-offset-4">Analyse another</Link>.
            </p>
          )}
        </Panel>
      )}
    </PageContainer>
  );
}
