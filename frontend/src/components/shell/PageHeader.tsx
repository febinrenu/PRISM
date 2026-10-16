import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn("flex items-center gap-1 text-[13px] text-text-muted", className)}>
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1">
              {c.href && !last ? (
                <Link href={c.href} className="hover:text-text-primary">
                  {c.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={last ? "text-text-secondary" : ""}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight className="h-3.5 w-3.5 opacity-50" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Page title block: kicker, serif title, lede and actions. One per route.
 */
export function PageHeader({
  kicker,
  title,
  lede,
  actions,
  crumbs,
  className,
  children,
}: {
  kicker?: React.ReactNode;
  title: React.ReactNode;
  lede?: React.ReactNode;
  actions?: React.ReactNode;
  crumbs?: Crumb[];
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className={cn("relative pb-8 pt-10 sm:pt-14", className)}>
      {crumbs ? <Breadcrumbs items={crumbs} className="mb-5" /> : null}
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0 max-w-3xl">
          {kicker ? <div className="kicker mb-3">{kicker}</div> : null}
          <h1 className="font-serif text-headline text-text-primary">{title}</h1>
          {lede ? <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-text-secondary">{lede}</p> : null}
        </div>
        {actions ? <div className="flex min-w-0 flex-wrap items-center gap-2 lg:max-w-[50%] lg:shrink-0">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}

/** Standard content width for app pages. */
export function PageContainer({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8", className)} {...props} />;
}
