"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import PrismMark from "@/components/brand/PrismMark";

/**
 * The curtain over the scene while it is built: real progress (fonts, data,
 * glyphs, the forms, shader compilation). It lifts only when the first frame
 * is ready, so nothing pops in behind it.
 */
export default function Preloader({ progress, label, ready, onGone }: { progress: number; label: string; ready: boolean; onGone: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const num = useRef<HTMLSpanElement>(null);
  const shown = useRef({ v: 0 });
  useEffect(() => {
    gsap.to(shown.current, {
      v: progress * 100,
      duration: 0.6,
      ease: "power2.out",
      overwrite: true,
      onUpdate: () => {
        if (num.current) num.current.textContent = String(Math.round(shown.current.v)).padStart(3, "0");
      },
    });
  }, [progress]);
  useEffect(() => {
    if (!ready || !root.current) return;
    const el = root.current;
    const tl = gsap.timeline({ onComplete: onGone });
    tl.to(shown.current, {
      v: 100,
      duration: 0.35,
      onUpdate: () => {
        if (num.current) num.current.textContent = String(Math.round(shown.current.v)).padStart(3, "0");
      },
    })
      .to(el.querySelectorAll("[data-pl]"), { yPercent: -120, opacity: 0, duration: 0.7, ease: "expo.in", stagger: 0.05 })
      .to(el, { clipPath: "inset(0% 0% 100% 0%)", duration: 1.15, ease: "expo.inOut" }, "-=0.25")
      .set(el, { display: "none" });
    return () => {
      tl.kill();
    };
  }, [ready, onGone]);
  return (
    <div
      ref={root}
      role="status"
      aria-live="polite"
      className="story-preloader fixed inset-0 z-curtain flex flex-col justify-between bg-ink px-5 pb-8 pt-6 [clip-path:inset(0%_0%_0%_0%)] sm:px-10 lg:px-16"
    >
      <div className="flex items-center justify-between overflow-hidden">
        <div data-pl="" className="flex items-center gap-3 text-text-primary">
          <PrismMark size={28} title="" />
          <span className="font-sans text-[13px] font-semibold tracking-[0.22em]">PRISM</span>
        </div>
        <div data-pl="" className="font-mono text-micro uppercase tracking-[0.2em] text-text-dim">
          {label}
        </div>
      </div>
      <div className="overflow-hidden">
        <p data-pl="" className="max-w-[26ch] font-serif text-[clamp(1.6rem,3.2vw,2.6rem)] italic leading-[1.1] text-text-secondary">
          Reading the law, one clause at a time.
        </p>
      </div>
      <div className="flex items-end justify-between gap-6 overflow-hidden">
        <span data-pl="" ref={num} className="font-serif text-[clamp(5rem,16vw,14rem)] leading-[0.8] tracking-[-0.04em] text-text-primary tabular">
          000
        </span>
        <div data-pl="" className="mb-3 h-px w-[min(40vw,28rem)] bg-border">
          <div className="story-progress h-full origin-left transition-transform duration-500" style={{ transform: `scaleX(${progress})` }} />
        </div>
      </div>
    </div>
  );
}
