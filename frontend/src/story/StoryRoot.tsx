"use client";

import "lenis/dist/lenis.css";
import "./story.css";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ReactLenis, type LenisRef } from "lenis/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";
import { Wordmark } from "@/components/brand/PrismMark";
import SiteFooter from "@/components/shell/SiteFooter";
import { cn } from "@/lib/utils";
import { fetchStory } from "./data";
import { ACTS, getActive, setActive, state, subscribe, type Tier } from "./engine/store";
import { detectTier } from "./engine/tier";
import { ActCurve, ActFaults, ActLimits, ActProvenance, ActReading, ActSociety, ActText, ActVerdict, Finale, Prologue } from "./acts";
import CurtainLink from "./CurtainLink";

gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);

const loadCanvas = () => import("./StoryCanvas");
const StoryCanvas = dynamic(loadCanvas, { ssr: false });

const NUMERALS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", ""];
const TITLES = ["", "The text", "Reading", "The curve", "Population", "Verdict", "Faults", "Provenance", "Limits", ""];

export default function StoryRoot() {
  const root = useRef<HTMLDivElement>(null);
  const lenisRef = useRef<LenisRef>(null);
  const [tier, setTier] = useState<Tier | null>(null);
  const [load, setLoad] = useState({ done: 0, total: 1, hidden: false });

  useEffect(() => {
    const t = detectTier();
    state.tier = t;
    setTier(t);
  }, []);

  // Real loading progress: fonts, the scene module and the two data files.
  useEffect(() => {
    if (tier === null) return;
    const tasks: Promise<unknown>[] = [document.fonts?.ready ?? Promise.resolve()];
    if (tier > 0) tasks.push(loadCanvas(), fetchStory("population"), fetchStory("constellation"));
    setLoad({ done: 0, total: tasks.length, hidden: false });
    let live = true;
    tasks.forEach((p) =>
      p.catch(() => null).finally(() => live && setLoad((l) => ({ ...l, done: l.done + 1 })))
    );
    return () => {
      live = false;
    };
  }, [tier]);
  useEffect(() => {
    if (load.done >= load.total && !load.hidden) {
      const id = setTimeout(() => setLoad((l) => ({ ...l, hidden: true })), 700);
      return () => clearTimeout(id);
    }
  }, [load]);

  // One clock: Lenis and R3F both run off the GSAP ticker.
  useEffect(() => {
    const update = (time: number) => {
      lenisRef.current?.lenis?.raf(time * 1000);
      state.velocity *= 0.9;
    };
    gsap.ticker.add(update);
    gsap.ticker.lagSmoothing(0);
    return () => gsap.ticker.remove(update);
  }, []);

  // Scroll → per-act progress, active act, step reveals.
  useEffect(() => {
    if (tier === null || !root.current) return;
    const acts = Array.from(root.current.querySelectorAll<HTMLElement>("[data-act]"));
    const steps = acts.map((a) => Array.from(a.querySelectorAll<HTMLElement>("[data-at]")));
    let tops: number[] = [];
    let heights: number[] = [];
    let last = window.scrollY;
    const measure = () => {
      tops = acts.map((a) => a.getBoundingClientRect().top + window.scrollY);
      heights = acts.map((a) => a.offsetHeight);
    };
    const onScroll = () => {
      const y = window.scrollY;
      const vh = window.innerHeight;
      state.velocity = state.velocity * 0.7 + (y - last) * 0.3;
      last = y;
      let active = 0;
      acts.forEach((a, i) => {
        const local = (y - tops[i]) / Math.max(1, heights[i] - vh);
        state.local[Number(a.dataset.act)] = local;
        if (tops[i] <= y + vh * 0.5) active = Number(a.dataset.act);
        for (const s of steps[i]) {
          const on = tier === 0 || local >= Number(s.dataset.at);
          if (on !== s.hasAttribute("data-on")) s.toggleAttribute("data-on", on);
        }
      });
      setActive(active);
    };
    measure();
    onScroll();
    const ro = new ResizeObserver(() => {
      measure();
      onScroll();
    });
    ro.observe(document.body);
    window.addEventListener("scroll", onScroll, { passive: true });
    const onPointer = (e: PointerEvent) => {
      state.pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      state.pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });
    return () => {
      ro.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pointermove", onPointer);
    };
  }, [tier]);

  // Title reveal: characters rise out of the baseline.
  useGSAP(
    () => {
      if (!tier) return;
      const split = SplitText.create(".story-title", { type: "lines,words", mask: "lines", linesClass: "pb-[0.08em]" });
      const tl = gsap.timeline({ delay: 0.15 });
      tl.from(split.words, { yPercent: 115, duration: 1.25, ease: "expo.out", stagger: 0.06 }).from(
        ".story-lede",
        { opacity: 0, y: 16, duration: 0.9, ease: "expo.out", stagger: 0.1 },
        "-=0.8"
      );
      return () => split.revert();
    },
    { scope: root, dependencies: [tier] }
  );

  const onDecline = useCallback(() => {
    setTier((t) => {
      const next = (t !== null && t > 1 ? t - 1 : t) as Tier;
      state.tier = next;
      return next;
    });
  }, []);

  const content = (
    <div ref={root} data-tier={tier ?? 2} className="relative">
      <div className="static-field" aria-hidden />
      {tier !== null && tier > 0 && (
        <div className="story-canvas fixed inset-0 z-0" aria-hidden>
          <StoryCanvas key={tier} onDecline={onDecline} />
        </div>
      )}
      <StoryHeader />
      <main id="main" className="relative z-10">
        <Prologue />
        <ActText />
        <ActReading />
        <ActCurve />
        <ActSociety />
        <ActVerdict />
        <ActFaults />
        <ActProvenance />
        <ActLimits />
        <Finale />
      </main>
      <div className="relative z-10 bg-ink">
        <SiteFooter />
      </div>
      <Loader done={load.done} total={load.total} hidden={load.hidden} />
      <div id="story-curtain" className="fixed inset-0 z-curtain hidden bg-ink" aria-hidden>
        <div className="h-1.5 w-full bg-signal" />
      </div>
    </div>
  );

  if (tier === 0) return content;
  return (
    <ReactLenis root ref={lenisRef} options={{ autoRaf: false, lerp: 0.085, anchors: true, wheelMultiplier: 0.95 }}>
      {content}
    </ReactLenis>
  );
}

function StoryHeader() {
  const active = useSyncExternalStore(subscribe, getActive, () => 0);
  const onPaper = ACTS[active] === "limits";
  return (
    <header
      data-paper={onPaper || undefined}
      className={cn(
        "fixed inset-x-0 top-0 z-nav transition-colors duration-500",
        onPaper && "[&_*]:!border-ink/25 [&_a]:!text-ink [&_span]:!text-ink/70"
      )}
    >
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-ink/85 to-transparent transition-opacity duration-500",
          onPaper && "opacity-0"
        )}
      />
      <div className="relative flex h-16 items-center justify-between gap-6 px-5 sm:px-10 lg:px-16">
        <Link href="/" className="text-text-primary" aria-label="PRISM">
          <Wordmark onPaper={onPaper} />
        </Link>
        <nav aria-label="Chapters" className="hidden items-center gap-1 lg:flex">
          {ACTS.map((id, i) =>
            NUMERALS[i] ? (
              <a
                key={id}
                href={`#${id}`}
                aria-current={active === i ? "step" : undefined}
                className={cn(
                  "group relative flex items-center gap-2 rounded-[3px] px-2 py-1 font-mono text-micro uppercase tracking-[0.14em] transition-colors",
                  active === i ? "text-text-primary" : "text-text-dim hover:text-text-secondary"
                )}
              >
                <span className={active === i ? "text-signal" : ""}>{NUMERALS[i]}</span>
                <span
                  className={cn(
                    "overflow-hidden whitespace-nowrap transition-[max-width,opacity] duration-500 ease-out-expo",
                    active === i ? "max-w-[10rem] opacity-100" : "max-w-0 opacity-0"
                  )}
                >
                  {TITLES[i]}
                </span>
              </a>
            ) : null
          )}
        </nav>
        <div className="flex items-center gap-2">
          <CurtainLink
            href="/statutes"
            className="hidden h-9 items-center rounded-[4px] px-3 text-[13.5px] text-text-secondary transition-colors hover:text-text-primary sm:inline-flex"
          >
            Statutes
          </CurtainLink>
          <CurtainLink
            href="/research"
            className="inline-flex h-9 items-center rounded-[4px] border border-border-light bg-ink/40 px-3.5 text-[13.5px] text-text-primary backdrop-blur-md transition-colors hover:border-glow"
          >
            Open the app
          </CurtainLink>
        </div>
      </div>
    </header>
  );
}

function Loader({ done, total, hidden }: { done: number; total: number; hidden: boolean }) {
  const pct = Math.round((done / Math.max(1, total)) * 100);
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none fixed bottom-5 right-5 z-overlay flex items-center gap-3 rounded-[4px] border border-border bg-ink/80 px-3 py-2 font-mono text-micro text-text-muted backdrop-blur-md transition-opacity duration-700",
        hidden && "opacity-0"
      )}
    >
      <span className="relative h-px w-16 bg-border-light">
        <span className="absolute inset-y-0 left-0 bg-signal transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </span>
      <span className="tabular">{pct < 100 ? `Loading the instrument ${pct}%` : "Ready"}</span>
    </div>
  );
}
