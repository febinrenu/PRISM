"use client";

import "lenis/dist/lenis.css";
import "./story.css";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { ReactLenis, type LenisRef } from "lenis/react";
import { gsap } from "gsap";
import SiteFooter from "@/components/shell/SiteFooter";
import { fetchStory, type Constellation, type PipelineGraph, type Population } from "./data";
import { STORY_LEN, direct } from "./engine/config";
import { loop } from "./engine/loop";
import { setActive, state, type Tier } from "./engine/store";
import { PARTICLES, detectTier } from "./engine/tier";
import { buildAtlas, type Atlas } from "./gl/atlas";
import { buildForms, charset, type FormData } from "./gl/forms";
import { StaticFigures, StoryActs } from "./dom/Acts";
import { activeAct, createController } from "./dom/controller";
import Cursor from "./dom/Cursor";
import Header, { progressBars } from "./dom/Header";
import Overlay from "./dom/Overlay";
import Preloader from "./dom/Preloader";
import { createSound, type Sound } from "./sound/engine";

const loadCanvas = () => import("./gl/StoryCanvas");
const StoryCanvas = dynamic(loadCanvas, { ssr: false });

interface Built {
  data: FormData;
  atlas: Atlas;
}

export default function StoryRoot() {
  const root = useRef<HTMLDivElement>(null);
  const lenis = useRef<LenisRef>(null);
  const [tier, setTier] = useState<Tier | null>(null);
  const [built, setBuilt] = useState<Built | null>(null);
  const readyRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [progress, setProgress] = useState({ v: 0, label: "Loading type" });
  const [sound, setSound] = useState(false);
  const soundRef = useRef<Sound | null>(null);

  // Tier, viewport unit, freeze flag.
  useEffect(() => {
    const { tier: t } = detectTier();
    state.tier = t;
    state.count = PARTICLES[t];
    const q = new URLSearchParams(window.location.search);
    state.freeze = q.get("freeze") === "1";
    if (q.get("debug") === "1") (window as unknown as { __prism: unknown }).__prism = { state, loop };
    let width = window.innerWidth;
    const setVh = () => {
      state.vh = window.innerHeight;
      document.documentElement.style.setProperty("--vhpx", `${window.innerHeight / 100}px`);
    };
    setVh();
    const onResize = () => {
      // ignore the mobile URL bar: only a width change re-measures the story
      if (window.innerWidth !== width) {
        width = window.innerWidth;
        setVh();
      }
    };
    window.addEventListener("resize", onResize);
    setTier(t);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Build everything the scene needs, with real progress.
  useEffect(() => {
    if (!tier) return;
    let live = true;
    // if the scene is not on screen within a minute, read the static story instead
    const fail = window.setTimeout(() => live && !readyRef.current && setTier(0), 60000);
    (async () => {
      try {
        setProgress({ v: 0.05, label: "Loading type" });
        await document.fonts?.ready;
        setProgress({ v: 0.12, label: "Loading the corpus" });
        const [population, constellation, graph] = await Promise.all([
          fetchStory<Population>("population"),
          fetchStory<Constellation>("constellation"),
          fetchStory<PipelineGraph>("pipeline"),
          loadCanvas(),
        ]);
        if (!live) return;
        setProgress({ v: 0.28, label: "Setting the glyphs" });
        const atlas = await buildAtlas(charset());
        setProgress({ v: 0.34, label: "Composing the forms" });
        const data = await buildForms({ population, constellation, graph, glyph: atlas.glyph }, undefined, (f) =>
          live && setProgress({ v: 0.34 + f * 0.46, label: "Composing the forms" })
        );
        if (!live) return;
        setProgress({ v: 0.84, label: "Compiling the light" });
        setBuilt({ data, atlas });
      } catch (e) {
        console.error(e);
        if (live) setTier(0);
      }
    })();
    return () => {
      live = false;
      window.clearTimeout(fail);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tier]);

  const onReady = useCallback(() => {
    readyRef.current = true;
    setProgress({ v: 1, label: "Ready" });
    setReady(true);
  }, []);
  const onGone = useCallback(() => setRevealed(true), []);

  // Hold the scroll until the curtain lifts.
  useEffect(() => {
    const l = lenis.current?.lenis;
    if (!l) return;
    if (revealed) l.start();
    else l.stop();
  }, [revealed, built]);

  // Split and arm the beats behind the curtain, so the reveal itself never stalls.
  const ctlRef = useRef<ReturnType<typeof createController> | null>(null);
  useEffect(() => {
    if (!tier || !built || !root.current) return;
    const ctl = createController(root.current, (k) => soundRef.current?.chime(k));
    ctlRef.current = ctl;
    return () => {
      ctl.destroy();
      ctlRef.current = null;
    };
  }, [tier, built]);

  // The single ticker: scroll → director → DOM → frame → overlay → sound.
  useEffect(() => {
    if (!tier || !revealed || !root.current) return;
    const ctl = ctlRef.current;
    if (!ctl) return;
    let last = performance.now();
    let lastY = -1;
    const tick = (time: number) => {
      const now = performance.now();
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const l = lenis.current?.lenis;
      l?.raf(now);
      const scroll = l ? l.animatedScroll : window.scrollY;
      const y = scroll / (state.vh / 100);
      if (lastY >= 0 && dt > 0) {
        const v = (y - lastY) / 100 / dt;
        state.velocity += (v - state.velocity) * Math.min(1, dt * 8);
      }
      lastY = y;
      state.y = y;
      if (!state.freeze) state.time += dt;
      direct(y, state.director);
      ctl.update(y, dt, state.velocity);
      const act = activeAct(y);
      setActive(act);
      const p = Math.min(1, Math.max(0, y / (STORY_LEN - 100)));
      progressBars.forEach((el) => (el.isConnected ? (el.style.transform = `scaleX(${p})`) : progressBars.delete(el)));
      loop.render?.(now / 1000);
      loop.overlay?.();
      soundRef.current?.update(act, state.director.exposure, state.velocity);
    };
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    const onPointer = (e: PointerEvent) => {
      state.pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      state.pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
      state.pointer.px = e.clientX;
      state.pointer.py = e.clientY;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });
    return () => {
      gsap.ticker.remove(tick);
      window.removeEventListener("pointermove", onPointer);
    };
  }, [tier, revealed]);

  const toggleSound = useCallback(() => {
    if (!soundRef.current) soundRef.current = createSound();
    setSound((s) => {
      soundRef.current?.setOn(!s);
      return !s;
    });
  }, []);
  useEffect(() => () => soundRef.current?.dispose(), []);

  if (tier === 0) {
    return (
      <div ref={root} data-tier="0" className="story-root relative">
        <Header sound={false} onSound={() => undefined} showSound={false} />
        <main id="main" className="relative">
          <StoryActs />
          <StaticFigures />
        </main>
        <SiteFooter />
        <div id="story-curtain" className="fixed inset-0 z-curtain hidden bg-ink" aria-hidden />
      </div>
    );
  }

  return (
    <ReactLenis root ref={lenis} options={{ autoRaf: false, lerp: 0.075, anchors: { offset: 0, duration: 2.2 }, wheelMultiplier: 0.9, syncTouch: false }}>
      <div ref={root} data-tier={tier ?? "pending"} className="story-root relative">
        <div className="fixed inset-0 z-0" aria-hidden>
          {built && tier && <StoryCanvas data={built.data} atlas={built.atlas} tier={tier} onReady={onReady} />}
        </div>
        {built && <Overlay anchors={built.data.anchors} picks={built.data.picks} />}
        <Header sound={sound} onSound={toggleSound} showSound />
        <main id="main" className="relative z-10">
          <StoryActs />
          <section aria-label="The figures, as tables" className="sr-only">
            <StaticFigures />
          </section>
        </main>
        <div className="relative z-10 bg-ink">
          <SiteFooter />
        </div>
        <Cursor />
        {!revealed && <Preloader progress={progress.v} label={progress.label} ready={ready} onGone={onGone} />}
        <div id="story-curtain" className="fixed inset-0 z-curtain hidden bg-ink" aria-hidden>
          <div className="story-progress h-1.5 w-full" />
        </div>
      </div>
    </ReactLenis>
  );
}
