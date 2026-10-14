"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { Wordmark } from "@/components/brand/PrismMark";
import { cn } from "@/lib/utils";
import CurtainLink from "../CurtainLink";
import { ACTS } from "../engine/config";
import { getActive, subscribe } from "../engine/store";

export const progressBars = new Set<HTMLElement>();

export default function Header({ sound, onSound, showSound }: { sound: boolean; onSound: () => void; showSound: boolean }) {
  const active = useSyncExternalStore(subscribe, getActive, () => 0);
  return (
    <header className="fixed inset-x-0 top-0 z-nav">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-ink/80 to-transparent" />
      <div className="absolute inset-x-0 top-0 h-[2px] bg-border">
        <div
          ref={(el) => void (el && progressBars.add(el))}
          className="story-progress h-full w-full origin-left scale-x-0 will-change-transform"
        />
      </div>
      <div className="relative flex h-16 items-center justify-between gap-6 px-5 sm:px-10 lg:px-16">
        <Link href="/" className="text-text-primary" aria-label="PRISM, back to the top" data-magnetic="">
          <Wordmark />
        </Link>
        <nav aria-label="Chapters" className="hidden items-center gap-0.5 lg:flex">
          {ACTS.map((a, i) =>
            a.numeral ? (
              <a
                key={a.id}
                href={`#${a.id}`}
                aria-current={active === i ? "step" : undefined}
                className={cn(
                  "relative flex items-center gap-2 rounded-[3px] px-2.5 py-1.5 font-mono text-micro uppercase tracking-[0.14em] transition-colors duration-300",
                  active === i ? "text-text-primary" : "text-text-dim hover:text-text-secondary"
                )}
              >
                <span>{a.numeral}</span>
                <span
                  className={cn(
                    "overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-500 ease-out-expo",
                    active === i ? "max-w-[9rem] opacity-100" : "max-w-0 opacity-0"
                  )}
                >
                  {a.title}
                </span>
              </a>
            ) : null
          )}
        </nav>
        <div className="flex items-center gap-2">
          {showSound && (
            <button
              type="button"
              onClick={onSound}
              aria-pressed={sound}
              data-magnetic=""
              className="inline-flex h-9 items-center gap-2 rounded-[4px] px-3 font-mono text-micro uppercase tracking-[0.14em] text-text-secondary transition-colors hover:text-text-primary"
            >
              {sound ? <Volume2 className="h-4 w-4" aria-hidden /> : <VolumeX className="h-4 w-4" aria-hidden />}
              <span className="hidden sm:inline">Sound</span>
              <span className="sr-only">{sound ? "on" : "off"}</span>
            </button>
          )}
          <CurtainLink
            href="/analyze/demo_income_tax_2025"
            data-magnetic=""
            className="inline-flex h-9 items-center rounded-[4px] border border-border-light bg-ink/40 px-3.5 text-[13.5px] text-text-primary backdrop-blur-md transition-colors hover:border-glow"
          >
            Open the demo
          </CurtainLink>
        </div>
      </div>
    </header>
  );
}
