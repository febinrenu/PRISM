"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Wordmark } from "@/components/brand/PrismMark";
import { Button } from "@/components/ui/button";
import { Field, inputClass } from "@/components/ui/kit";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
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
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
      setBusy(false);
    }
  };

  return (
    <div className="w-full max-w-sm">
      <h1 className="font-serif text-headline text-text-primary">{mode === "login" ? "Sign in" : "Create an account"}</h1>
      <p className="mt-3 text-[15px] text-text-secondary">
        {mode === "login" ? "Your uploads and API key are waiting." : "Uploads you make signed in are private to you."}
      </p>
      <form onSubmit={submit} className="mt-8 flex flex-col gap-5" noValidate={false}>
        {mode === "register" && (
          <Field id="name" label="Name">
            <input id="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </Field>
        )}
        <Field id="email" label="Email">
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field id="password" label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>
        {error && (
          <p role="alert" className="flex items-center gap-2 text-[13px] text-status-error">
            <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={busy} className="mt-1">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-[14px] text-text-muted">
        {mode === "login" ? "No account yet? " : "Already have one? "}
        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="text-text-primary underline decoration-border-light underline-offset-4 hover:decoration-signal"
        >
          {mode === "login" ? "Create one" : "Sign in"}
        </button>
      </p>
      <p className="mt-10 text-[13px] text-text-dim">
        You can use everything except your private uploads and API key without signing in.{" "}
        <Link href="/research" className="underline underline-offset-4 hover:text-text-secondary">
          Browse the results
        </Link>
        .
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <aside className="surface-paper relative hidden flex-col justify-between overflow-hidden p-12 lg:flex">
        <Link href="/" className="text-ink" aria-label="PRISM, back to the story">
          <Wordmark onPaper />
        </Link>
        <blockquote className="max-w-md">
          <p className="font-serif text-[2.6rem] leading-[1.05] text-ink">
            “for the words <span className="text-ink/45">seven hundred thousand rupees</span>, the words{" "}
            <span className="bg-signal/20 px-1 text-signal-ink">twelve hundred thousand rupees</span> shall be substituted”
          </p>
          <footer className="mt-6 font-mono text-micro uppercase tracking-[0.16em] text-ink/60">
            The Finance Act, 2025 · section 20
          </footer>
        </blockquote>
        <div className="h-px w-full bg-ink/15" aria-hidden />
      </aside>
      <div className="flex flex-col px-6 py-6 sm:px-10">
        <Link href="/" className="text-text-primary lg:hidden" aria-label="PRISM, back to the story">
          <Wordmark />
        </Link>
        <div className="flex flex-1 items-center justify-center py-12">
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
