"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Loader2, Copy, Check, RefreshCw, FileText, Activity, KeyRound,
  Cpu, Cloud, Database, Upload, MessageSquare, GitCompare,
} from "lucide-react";
import TopNav from "@/components/nav/TopNav";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DashboardData } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) api.dashboard().then(setData).catch(() => {});
  }, [user]);

  const copyKey = () => {
    if (!data) return;
    navigator.clipboard.writeText(data.api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const rotate = async () => {
    setRotating(true);
    try {
      const { api_key } = await api.rotateApiKey();
      setData((d) => (d ? { ...d, api_key } : d));
    } finally {
      setRotating(false);
    }
  };

  if (loading || !user) {
    return (
      <main className="min-h-screen bg-bg-base flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-accent-primary" />
      </main>
    );
  }

  const usagePct = data ? Math.min(100, Math.round((data.usage_total / Math.max(data.quota_per_hour, 1)) * 100)) : 0;

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <div className="animated-grid" />
      <div className="noise-overlay" />
      <TopNav />

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-display text-2xl uppercase tracking-wider">Welcome, {user.name || user.email}</h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted mt-1">
              Role: {user.role}
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary"
          >
            <Upload className="w-3 h-3" /> Upload document
          </Link>
        </div>

        {/* Quick actions */}
        <div className="grid sm:grid-cols-3 gap-4 mb-8">
          {[
            { href: "/chat", label: "RAG Chat", icon: MessageSquare },
            { href: "/corpus", label: "Corpus Explorer", icon: Database },
            { href: "/compare", label: "Compare Policies", icon: GitCompare },
          ].map((a) => {
            const Icon = a.icon;
            return (
              <Link key={a.href} href={a.href} className="glass-card p-5 glass-card-hover flex items-center gap-3">
                <Icon className="w-5 h-5 text-accent-primary" />
                <span className="font-display uppercase tracking-wider text-sm">{a.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* API key card */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <KeyRound className="w-4 h-4 text-accent-primary" />
              <h3 className="font-display uppercase tracking-wider text-sm">API Key</h3>
            </div>
            <div className="flex items-center gap-2 rounded-md border border-border bg-bg-surface p-2.5">
              <code className="flex-1 font-mono text-[11px] text-text-secondary truncate">
                {data?.api_key ?? "…"}
              </code>
              <button onClick={copyKey} className="text-text-muted hover:text-text-primary transition-colors">
                {copied ? <Check className="w-4 h-4 text-status-success" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <button
              onClick={rotate}
              disabled={rotating}
              className="mt-3 inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
            >
              {rotating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Rotate key
            </button>

            <div className="mt-5">
              <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-text-muted mb-1.5">
                <span>API usage</span>
                <span>{data?.usage_total ?? 0} / {data?.quota_per_hour ?? 100} per hr</span>
              </div>
              <div className="h-2 rounded-full bg-bg-surface overflow-hidden">
                <div className="h-full bg-accent-primary transition-all" style={{ width: `${usagePct}%` }} />
              </div>
            </div>
          </div>

          {/* My documents */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-4 h-4 text-accent-primary" />
              <h3 className="font-display uppercase tracking-wider text-sm">My Documents</h3>
            </div>
            {data && data.documents.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {data.documents.map((d) => (
                  <li key={d.doc_id}>
                    <Link
                      href={`/analyze/${d.doc_id}`}
                      className="flex items-center justify-between rounded-md border border-border p-2.5 hover:border-light transition-colors"
                    >
                      <span className="font-mono text-[11px] truncate">{d.doc_name}</span>
                      <span className="font-mono text-[9px] uppercase tracking-wider text-status-success">{d.status}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-text-muted">No documents yet. Upload one from the landing page.</p>
            )}
          </div>

          {/* My simulations */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-4 h-4 text-accent-primary" />
              <h3 className="font-display uppercase tracking-wider text-sm">My Simulations</h3>
            </div>
            {data && data.simulations.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {data.simulations.slice(0, 6).map((s, i) => {
                  let verdict = "";
                  try { verdict = JSON.parse(s.results).verdict ?? ""; } catch {}
                  return (
                    <li key={i} className="flex items-center justify-between rounded-md border border-border p-2.5">
                      <span className="font-mono text-[11px] truncate">{s.doc_id.slice(0, 20)}</span>
                      <span className="font-mono text-[9px] uppercase tracking-wider text-text-muted">{verdict}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-[13px] text-text-muted">No saved simulations yet.</p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
