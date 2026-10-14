"use client";

/**
 * Building blocks of the story's DOM layer. An act is a tall section whose
 * stage sticks to the viewport; inside the stage, beats take turns as the
 * act's progress (q, 0 → 1 while the stage is pinned) passes their window.
 * The beat controller (controller.ts) animates them; with tier 0 every beat
 * simply shows, in order, as a readable page.
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import { ACTS, type ActId } from "../engine/config";

export function ActSection({
  id,
  label,
  side = "left",
  children,
  overlay,
}: {
  id: ActId;
  label: string;
  side?: "left" | "right" | "center";
  children: React.ReactNode;
  overlay?: React.ReactNode;
}) {
  const act = ACTS.find((a) => a.id === id)!;
  return (
    <section
      id={id}
      data-act={id}
      aria-label={label}
      className="story-act relative"
      style={{ ["--len" as string]: act.len }}
    >
      <div className="story-stage sticky top-0 w-full overflow-hidden">
        {overlay}
        <div
          className={cn(
            "story-copy relative mx-auto flex h-full w-full max-w-[1600px] px-5 sm:px-10 lg:px-16",
            side === "left" && "items-end pb-[9vh] lg:items-center lg:pb-0",
            side === "right" && "items-end justify-end pb-[9vh] lg:items-center lg:pb-0",
            side === "center" && "items-end justify-center pb-[9vh] text-center lg:items-center lg:pb-0"
          )}
        >
          <div className={cn("beats grid w-full min-w-0 grid-cols-[minmax(0,1fr)]", side === "center" ? "max-w-[64rem]" : "max-w-[34rem] xl:max-w-[38rem]")}>{children}</div>
        </div>
      </div>
    </section>
  );
}

/** One beat: shown while the act's progress is in [from, to). */
export function Beat({ from, to, className, children }: { from: number; to: number; className?: string; children: React.ReactNode }) {
  return (
    <div data-beat="" data-from={from} data-to={to} className={cn("beat min-w-0 [grid-area:1/1]", className)}>
      {children}
    </div>
  );
}

export function Kicker({ n, children, className }: { n?: string; children: React.ReactNode; className?: string }) {
  return (
    <div data-rise="" className={cn("story-anchor mb-5 flex items-center gap-3 font-mono text-micro uppercase tracking-[0.22em] text-text-muted", className)}>
      {n ? <span className="text-text-primary">{n}</span> : null}
      {n ? <span className="h-px w-8 bg-border-light" aria-hidden /> : null}
      <span>{children}</span>
    </div>
  );
}

export function Headline({ id, as = "h2", className, children }: { id?: string; as?: "h1" | "h2"; className?: string; children: React.ReactNode }) {
  const Tag = as;
  return (
    <Tag
      id={id}
      data-split=""
      className={cn(
        "font-serif text-text-primary",
        as === "h1"
          ? "text-[clamp(3rem,min(8.4vw,13.5vh),8.6rem)] leading-[0.9] tracking-[-0.03em]"
          : "text-[clamp(2.2rem,min(4.9vw,8.4vh),4.4rem)] leading-[0.98] tracking-[-0.022em]",
        className
      )}
    >
      {children}
    </Tag>
  );
}

export function Body({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p data-rise="" className={cn("mt-6 max-w-[36rem] text-[16px] leading-[1.68] text-text-secondary sm:text-[17px]", className)}>
      {children}
    </p>
  );
}

/** A big number with a label. The figure counts up when its beat enters. */
export function Stat({ value, label, tone, source }: { value: React.ReactNode; label: React.ReactNode; tone?: "signal"; source?: React.ReactNode }) {
  return (
    <div data-rise="" className="min-w-0">
      <div className={cn("font-serif text-[clamp(2rem,3.6vw,3.2rem)] leading-none tabular", tone === "signal" ? "text-signal" : "text-text-primary")}>
        {value}
        {source}
      </div>
      <div className="mt-2 text-[13px] leading-snug text-text-muted">{label}</div>
    </div>
  );
}

/** A counting figure: renders the final text (for readers and no-JS), animates from zero. */
export function Count({ children }: { children: string }) {
  return (
    <span data-count={children} className="tabular">
      {children}
    </span>
  );
}

export function Chip({ color, children, className }: { color: string; children: React.ReactNode; className?: string }) {
  return (
    <span data-rise="" className={cn("inline-flex items-center gap-2 rounded-[3px] border border-border bg-ink/60 px-2.5 py-1.5 text-[13px] text-text-secondary backdrop-blur-sm", className)}>
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
      {children}
    </span>
  );
}

/** Ordinal step labels ("01", "02") computed, never typed. */
export const step = (i: number) => String(i).padStart(2, "0");
