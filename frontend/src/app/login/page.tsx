"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import PrismMark from "@/components/brand/PrismMark";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary flex flex-col">
      <div className="animated-grid" />
      <div className="noise-overlay" />
      <nav className="relative z-20 px-6 py-4">
        <Link href="/" className="inline-flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <PrismMark size={28} />
        </Link>
      </nav>

      <div className="relative z-10 flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <h1 className="font-display text-3xl uppercase tracking-wider text-text-primary">
              {mode === "login" ? "Sign in" : "Create account"}
            </h1>
            <p className="mt-2 text-sm text-text-secondary">
              {mode === "login" ? "Access your PRISM workspace." : "Start analysing statutes with PRISM."}
            </p>
          </div>

          <form onSubmit={submit} className="glass-card p-6 flex flex-col gap-4">
            {mode === "register" && (
              <div>
                <label className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1.5 w-full rounded-md border border-border bg-bg-surface px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:border-light"
                  placeholder="Jane Researcher"
                />
              </div>
            )}
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full rounded-md border border-border bg-bg-surface px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:border-light"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full rounded-md border border-border bg-bg-surface px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:border-light"
                placeholder="At least 8 characters"
              />
            </div>

            {error && (
              <p className="flex items-center gap-2 text-[12px] text-status-error">
                <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-md bg-accent-primary text-text-inverse font-mono text-xs uppercase tracking-widest py-3 disabled:opacity-60"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}
              {mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="mt-4 text-center text-[12px] text-text-muted">
            {mode === "login" ? "No account yet? " : "Already have an account? "}
            <button
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="text-accent-primary hover:text-accent-bright transition-colors"
            >
              {mode === "login" ? "Create one" : "Sign in"}
            </button>
          </p>
          <p className="mt-6 text-center font-mono text-[9px] text-text-dim leading-relaxed">
            Credentials auth runs against the local PRISM API. GitHub / Google OAuth
            can be layered on in production via NextAuth + the /auth/oauth-upsert endpoint.
          </p>
        </div>
      </div>
    </main>
  );
}
