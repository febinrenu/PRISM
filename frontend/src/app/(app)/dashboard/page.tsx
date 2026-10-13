"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Check, Copy, FileText, KeyRound, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { EmptyState, ErrorState, Panel, PageSkeleton, SandboxTag, StatusTag } from "@/components/ui/kit";
import { buttonVariants } from "@/components/ui/button";
import DocumentCorpus from "@/components/landing/DocumentCorpus";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const { data, error, mutate } = useSWR(user ? ["dashboard", user.id] : null, () => api.dashboard());
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);

  if (loading) return <PageSkeleton />;
  if (!user)
    return (
      <PageContainer>
        <PageHeader kicker="Dashboard" title="Your documents and API key" />
        <div className="grid gap-10 lg:grid-cols-2 [&>*]:min-w-0">
          <Panel>
            <EmptyState
              title="Sign in to see your dashboard"
              action={
                <Link href="/login?next=/dashboard" className={buttonVariants({ variant: "primary" })}>
                  Sign in
                </Link>
              }
            >
              Signed in, your uploads are private to you and you get an API key for the public /v1 endpoints.
            </EmptyState>
          </Panel>
          <section aria-labelledby="shared-h">
            <h2 id="shared-h" className="mb-4 font-serif text-title">
              Shared documents
            </h2>
            <DocumentCorpus />
          </section>
        </div>
      </PageContainer>
    );

  const copyKey = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(data.api_key);
    setCopied(true);
    toast("API key copied");
    setTimeout(() => setCopied(false), 1500);
  };
  const rotate = async () => {
    setRotating(true);
    try {
      const { api_key } = await api.rotateApiKey();
      mutate(data ? { ...data, api_key } : data, { revalidate: false });
      toast("A new API key was issued. The old one no longer works.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "The key could not be rotated.");
    } finally {
      setRotating(false);
    }
  };
  const usagePct = data ? Math.min(100, Math.round((data.usage_total / Math.max(data.quota_per_hour, 1)) * 100)) : 0;

  return (
    <PageContainer>
      <PageHeader
        kicker={`Dashboard · ${user.role}`}
        title={`Welcome back, ${user.name || user.email.split("@")[0]}.`}
        lede="Your uploads, your API key and your sandbox runs."
        actions={
          <Link href="/start" className={buttonVariants({ variant: "primary" })}>
            Analyse a PDF
          </Link>
        }
      />
      {error ? (
        <ErrorState message={String(error.message ?? error)} onRetry={() => mutate()} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
          <Panel kicker="Access" title="API key" className="lg:col-span-1">
            <div className="flex items-center gap-2 rounded-[4px] border border-border bg-bg-base p-2.5">
              <KeyRound className="h-4 w-4 shrink-0 text-text-dim" aria-hidden />
              <code className="flex-1 truncate font-mono text-[13px] text-text-secondary">{data?.api_key ?? "…"}</code>
              <button type="button" onClick={copyKey} aria-label="Copy API key" className="text-text-muted hover:text-text-primary">
                {copied ? <Check className="h-4 w-4 text-status-success" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
            <button
              type="button"
              onClick={rotate}
              disabled={rotating}
              className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-text-muted hover:text-text-primary disabled:opacity-50"
            >
              {rotating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Rotate key
            </button>
            <div className="mt-6">
              <div className="mb-1.5 flex items-center justify-between text-[13px] text-text-muted">
                <span>Calls this hour</span>
                <span className="font-mono">
                  {data?.usage_total ?? 0} / {data?.quota_per_hour ?? "–"}
                </span>
              </div>
              <div
                className="h-1.5 overflow-hidden rounded-full bg-ink-700"
                role="progressbar"
                aria-valuenow={usagePct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="API usage this hour"
              >
                <div className="h-full bg-signal transition-[width]" style={{ width: `${usagePct}%` }} />
              </div>
            </div>
            <Link href="/api-docs" className="mt-6 inline-block text-[13px] text-text-secondary underline underline-offset-4">
              How to call the API
            </Link>
          </Panel>

          <Panel kicker="Yours" title="Uploaded documents" flush className="lg:col-span-1">
            {!data ? (
              <div className="p-5 text-[13px] text-text-muted">Loading…</div>
            ) : data.documents.length === 0 ? (
              <EmptyState title="No uploads yet" icon={<FileText className="h-5 w-5" />}>
                Upload a statute and it will be listed here, visible only to you.
              </EmptyState>
            ) : (
              <ul className="divide-y divide-border">
                {data.documents.map((d) => (
                  <li key={d.doc_id}>
                    <Link href={`/analyze/${d.doc_id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-bg-elevated">
                      <span className="min-w-0 flex-1 truncate text-[14px]">{d.doc_name}</span>
                      <StatusTag status={d.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel kicker="Sandbox" title="Saved policy runs" actions={<SandboxTag />} flush className="lg:col-span-1">
            {!data ? (
              <div className="p-5 text-[13px] text-text-muted">Loading…</div>
            ) : data.simulations.length === 0 ? (
              <EmptyState title="No sandbox runs">Runs of the illustrative policy simulator you save appear here.</EmptyState>
            ) : (
              <ul className="divide-y divide-border">
                {data.simulations.slice(0, 8).map((s, i) => {
                  let verdict = "";
                  try {
                    verdict = JSON.parse(s.results).verdict ?? "";
                  } catch {
                    verdict = "";
                  }
                  return (
                    <li key={i}>
                      <Link href={`/simulate/${s.doc_id}`} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-bg-elevated">
                        <span className="truncate font-mono text-[13px] text-text-secondary">{s.doc_id}</span>
                        <span className="text-[12px] text-text-muted">{verdict}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </div>
      )}
      <section aria-labelledby="shared-h" className="mt-14">
        <h2 id="shared-h" className="mb-4 font-serif text-title">
          All documents you can open
        </h2>
        <DocumentCorpus limit={20} />
      </section>
    </PageContainer>
  );
}
