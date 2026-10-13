"use client";

import Link from "next/link";
import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";

type View = "analyze" | "provenance" | "simulate" | "explain" | "compare";

/**
 * The second bar on every workspace route: which document you are in, and
 * the views of it you can switch between.
 */
export default function DocContextBar({
  docId,
  filename,
  view,
  status,
  children,
}: {
  docId: string;
  filename?: string | null;
  view: View;
  status?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const tabs: { id: View; label: string; href: string }[] = [
    { id: "analyze", label: "Workspace", href: `/analyze/${docId}` },
    { id: "provenance", label: "Provenance", href: `/provenance/${docId}` },
    { id: "simulate", label: "Policy sandbox", href: `/simulate/${docId}` },
    { id: "compare", label: "Compare", href: `/compare?a=${docId}` },
  ];
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-bg-base px-4 py-2 sm:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <FileText className="h-4 w-4 shrink-0 text-text-dim" aria-hidden />
        <span className="max-w-[16rem] truncate text-[14px] text-text-primary" title={filename ?? docId}>
          {filename ?? docId}
        </span>
        {status}
      </div>
      <nav aria-label="Document views" className="-mb-2 flex items-end gap-0.5 overflow-x-auto">
        {tabs.map((t) => {
          const active = t.id === view || (view === "explain" && t.id === "analyze");
          return (
            <Link
              key={t.id}
              href={t.href}
              aria-current={t.id === view ? "page" : undefined}
              className={cn(
                "relative shrink-0 px-3 pb-2.5 pt-1 text-[13.5px] transition-colors",
                active ? "text-text-primary" : "text-text-muted hover:text-text-primary"
              )}
            >
              {t.label}
              {active && <span aria-hidden className="absolute inset-x-3 bottom-0 h-[2px] bg-signal" />}
            </Link>
          );
        })}
      </nav>
      {children ? <div className="ml-auto flex items-center gap-2">{children}</div> : null}
    </div>
  );
}
