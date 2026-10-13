/**
 * Small layout and state primitives shared by every app route: Panel, Tag,
 * StatusTag, SandboxTag, Callout, Skeleton, EmptyState, ErrorState, Kbd.
 */
import * as React from "react";
import Link from "next/link";
import { AlertTriangle, FlaskConical, Info, RotateCcw, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Panel ─────────────────────────────────────────────────────────────── */

type PanelProps = React.HTMLAttributes<HTMLElement> & {
  as?: "section" | "div" | "article" | "aside";
  title?: React.ReactNode;
  kicker?: React.ReactNode;
  actions?: React.ReactNode;
  /** Remove body padding (tables, charts that bleed). */
  flush?: boolean;
};

export function Panel({ as = "section", title, kicker, actions, flush, className, children, ...props }: PanelProps) {
  const Tag = as as React.ElementType;
  return (
    <Tag className={cn("glass-card", className)} {...props}>
      {(title || kicker || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-3.5">
          <div className="min-w-0">
            {kicker ? <div className="kicker mb-1">{kicker}</div> : null}
            {title ? <h2 className="text-[15px] font-medium text-text-primary">{title}</h2> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      )}
      <div className={cn(!flush && "p-5")}>{children}</div>
    </Tag>
  );
}

/* ── Tags ──────────────────────────────────────────────────────────────── */

type TagTone = "neutral" | "signal" | "ok" | "warn" | "critical" | "info";

const toneClass: Record<TagTone, string> = {
  neutral: "border-border-light text-text-secondary bg-bg-elevated",
  signal: "border-signal/40 text-signal-soft bg-signal/10",
  ok: "border-status-success/40 text-status-success bg-status-success/10",
  warn: "border-status-warning/40 text-status-warning bg-status-warning/10",
  critical: "border-status-critical/45 text-status-error bg-status-critical/10",
  info: "border-status-info/40 text-status-info bg-status-info/10",
};

export function Tag({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: TagTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[3px] border px-1.5 py-0.5 font-mono text-micro uppercase tracking-[0.08em]",
        toneClass[tone],
        className
      )}
      {...props}
    />
  );
}

/** State tag: always icon + label, never colour alone. */
export function StatusTag({ status }: { status: "complete" | "processing" | "pending" | "error" | string }) {
  const map: Record<string, { tone: TagTone; label: string; dot: string }> = {
    complete: { tone: "ok", label: "Ready", dot: "●" },
    processing: { tone: "warn", label: "Processing", dot: "◐" },
    pending: { tone: "neutral", label: "Queued", dot: "○" },
    error: { tone: "critical", label: "Failed", dot: "✕" },
  };
  const s = map[status] ?? { tone: "neutral" as TagTone, label: status, dot: "○" };
  return (
    <Tag tone={s.tone}>
      <span aria-hidden>{s.dot}</span>
      {s.label}
    </Tag>
  );
}

/** Marks anything driven by illustrative (not statute-derived) assumptions. */
export function SandboxTag({ className }: { className?: string }) {
  return (
    <Tag tone="warn" className={className} title="Illustrative model: parameters are partly assumed, not validated">
      <FlaskConical className="h-3 w-3" aria-hidden />
      Sandbox
    </Tag>
  );
}

/* ── Callout ───────────────────────────────────────────────────────────── */

export function Callout({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: "info" | "warn" | "signal";
  title?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const Icon = tone === "info" ? Info : AlertTriangle;
  const ring =
    tone === "warn"
      ? "border-status-warning/30 bg-status-warning/[0.06]"
      : tone === "signal"
        ? "border-signal/30 bg-signal/[0.06]"
        : "border-border-light bg-bg-elevated/60";
  const ic = tone === "warn" ? "text-status-warning" : tone === "signal" ? "text-signal" : "text-text-muted";
  return (
    <div role="note" className={cn("flex gap-3 rounded-[4px] border px-4 py-3 text-[13px] leading-relaxed", ring, className)}>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", ic)} aria-hidden />
      <div className="min-w-0 text-text-secondary">
        {title ? <div className="mb-0.5 font-medium text-text-primary">{title}</div> : null}
        {children}
      </div>
    </div>
  );
}

/* ── Skeleton & states ─────────────────────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("shimmer h-4 w-full", className)} />;
}

export function PageSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6" role="status" aria-label="Loading">
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-8 h-10 w-2/3 max-w-xl" />
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </div>
      <Skeleton className="mt-4 h-72" />
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
  icon,
  className,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-14 text-center", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border-light text-text-muted">
        {icon ?? <span className="font-serif text-xl leading-none">§</span>}
      </div>
      <h3 className="font-serif text-2xl text-text-primary">{title}</h3>
      {children ? <p className="max-w-md text-[14px] leading-relaxed text-text-muted">{children}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "This view could not load",
  message,
  onRetry,
  offline,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  offline?: boolean;
}) {
  return (
    <EmptyState
      title={offline ? "The analysis server is not reachable" : title}
      icon={offline ? <WifiOff className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5 text-status-error" />}
      action={
        onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-[4px] border border-border-light px-3 py-1.5 text-[13px] text-text-primary hover:border-glow"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Try again
          </button>
        ) : (
          <Link href="/" className="text-[13px] text-text-secondary underline underline-offset-4 hover:text-text-primary">
            Back to the start
          </Link>
        )
      }
    >
      {offline
        ? "Start the backend (uvicorn on port 8000) and try again. Nothing on this page is cached."
        : message}
    </EmptyState>
  );
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-[3px] border border-border-light bg-bg-elevated px-1 font-mono text-micro text-text-muted",
        className
      )}
    >
      {children}
    </kbd>
  );
}
