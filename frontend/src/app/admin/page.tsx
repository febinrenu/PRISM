"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2, Users, FileText, Activity, Radio, Database, Cpu, Cloud, RefreshCw, ShieldEllipsis,
} from "lucide-react";
import TopNav from "@/components/nav/TopNav";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminMetrics, AdminUser } from "@/types";

const BACKENDS = [
  { key: "ollama", label: "Ollama (base)" },
  { key: "ollama_finetuned", label: "PRISM-Legal (LoRA)" },
  { key: "groq", label: "Groq (cloud)" },
];

export default function AdminPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) router.push("/dashboard");
  }, [loading, user, router]);

  const load = async () => {
    try {
      const [m, u] = await Promise.all([api.adminMetrics(), api.adminUsers()]);
      setMetrics(m);
      setUsers(u.users);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load admin data.");
    }
  };

  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user]);

  const switchBackend = async (backend: string) => {
    setBusy("backend");
    try {
      await api.adminSwitchBackend(backend);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const reindex = async () => {
    setBusy("reindex");
    try {
      await api.adminReindexCorpus();
      await load();
    } finally {
      setBusy(null);
    }
  };

  if (loading || !user || user.role !== "admin") {
    return (
      <main className="min-h-screen bg-bg-base flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-accent-primary" />
      </main>
    );
  }

  const cards = metrics
    ? [
        { label: "Users", value: metrics.users, icon: Users },
        { label: "Documents", value: metrics.documents, icon: FileText },
        { label: "Simulations", value: metrics.simulations, icon: Activity },
        { label: "API Calls", value: metrics.api_calls_total, icon: Radio },
        { label: "Corpus Clauses", value: metrics.corpus.total_clauses, icon: Database },
      ]
    : [];

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <div className="animated-grid" />
      <div className="noise-overlay" />
      <TopNav />

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-8">
        <h1 className="font-display text-2xl uppercase tracking-wider flex items-center gap-2 mb-8">
          <ShieldEllipsis className="w-5 h-5 text-accent-primary" /> Admin Dashboard
        </h1>

        {error && <div className="glass-card p-4 text-status-error text-sm mb-6">{error}</div>}

        {/* Metrics grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          {cards.map((c) => {
            const Icon = c.icon;
            return (
              <div key={c.label} className="glass-card p-5">
                <Icon className="w-4 h-4 text-accent-primary mb-3" />
                <div className="font-display text-3xl text-text-primary">{c.value.toLocaleString()}</div>
                <div className="font-mono text-[9px] uppercase tracking-widest text-text-muted mt-1">{c.label}</div>
              </div>
            );
          })}
        </div>

        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* LLM backend switcher */}
          <div className="glass-card p-6">
            <h3 className="font-display uppercase tracking-wider text-sm mb-4">LLM Backend</h3>
            <div className="flex items-center gap-2 mb-4 font-mono text-[11px] text-text-secondary">
              {metrics?.llm_backend.cloud ? <Cloud className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
              Active: <span className="text-accent-primary">{metrics?.llm_backend.model}</span>
              {metrics?.llm_backend.kind === "groq" && !metrics.llm_backend.configured && (
                <span className="text-status-warning">(no GROQ_API_KEY set)</span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {BACKENDS.map((b) => (
                <button
                  key={b.key}
                  onClick={() => switchBackend(b.key)}
                  disabled={busy === "backend"}
                  className={`text-left rounded-md border p-3 font-mono text-[11px] transition-colors ${
                    metrics?.llm_backend.backend === b.key
                      ? "border-accent-primary/40 bg-accent-primary/10 text-text-primary"
                      : "border-border text-text-secondary hover:border-light"
                  }`}
                >
                  {b.label}
                </button>
              ))}
            </div>
            <p className="mt-3 font-mono text-[9px] text-text-dim">
              Runtime switch for this process. Persist by setting LLM_BACKEND in backend/.env.
            </p>
          </div>

          {/* Corpus manager */}
          <div className="glass-card p-6">
            <h3 className="font-display uppercase tracking-wider text-sm mb-4">Corpus Manager</h3>
            <div className="font-mono text-[11px] text-text-secondary mb-4">
              {metrics?.corpus.documents.length ?? 0} documents ·{" "}
              {metrics?.corpus.total_clauses.toLocaleString() ?? 0} clauses ·{" "}
              storage: {metrics?.storage.backend}
            </div>
            <button
              onClick={reindex}
              disabled={busy === "reindex"}
              className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary disabled:opacity-60"
            >
              {busy === "reindex" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Re-index all documents
            </button>
          </div>
        </div>

        {/* Users table */}
        <div className="glass-card p-6">
          <h3 className="font-display uppercase tracking-wider text-sm mb-4">Users</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="font-mono text-[9px] uppercase tracking-widest text-text-muted border-b border-border">
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Docs</th>
                  <th className="py-2 pr-4">API calls</th>
                  <th className="py-2">Joined</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-border/50 font-mono text-[11px] text-text-secondary">
                    <td className="py-2.5 pr-4 text-text-primary">{u.email}</td>
                    <td className="py-2.5 pr-4">{u.role}</td>
                    <td className="py-2.5 pr-4">{u.doc_count}</td>
                    <td className="py-2.5 pr-4">{u.api_calls}</td>
                    <td className="py-2.5 text-text-muted">{String(u.created_at).slice(0, 10)}</td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-text-muted text-[12px]">No users yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
