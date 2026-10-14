"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import * as THREE from "three";
import { cn } from "@/lib/utils";
import { loop } from "../engine/loop";
import { state } from "../engine/store";
import type { Anchor, Pick } from "../gl/forms";

/** How present form `f` is at director form value `x`: 1 while held, 0 one form away. */
const presence = (f: number, x: number) => Math.max(0, 1 - Math.abs(x - f) * 2.4);

/**
 * Labels pinned to points in the scene (statute names on the skyline, axis
 * ticks, entity types, reader names) and a card for whatever the pointer
 * rests on. Positions are projected after each frame renders, so they never
 * lag the scene.
 */
export default function Overlay({ anchors, picks }: { anchors: Anchor[]; picks: Pick[] }) {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  const card = useRef<HTMLDivElement>(null);
  const hovered = useRef<Pick | null>(null);
  const router = useRouter();

  useEffect(() => {
    const v = new THREE.Vector3();
    const shown = new Map<number, number>();
    const project = (x: number, y: number, z: number, cam: THREE.Camera, w: number, h: number) => {
      v.set(x, y, z).project(cam);
      return {
        sx: (v.x * 0.5 + 0.5) * w,
        sy: (-v.y * 0.5 + 0.5) * h,
        front: v.z < 1,
      };
    };
    loop.overlay = () => {
      const cam = loop.camera;
      if (!cam) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const form = state.director.form;
      anchors.forEach((a, i) => {
        const el = refs.current[i];
        if (!el) return;
        const p = presence(a.form, form);
        if (p <= 0.001) {
          if (shown.get(i)) {
            el.style.opacity = "0";
            el.style.visibility = "hidden";
            shown.set(i, 0);
          }
          return;
        }
        const { sx, sy, front } = project(a.x, a.y, a.z, cam, w, h);
        el.style.visibility = front ? "visible" : "hidden";
        el.style.opacity = String(p * p);
        el.style.transform = `translate3d(${sx.toFixed(1)}px, ${sy.toFixed(1)}px, 0)`;
        shown.set(i, 1);
      });
      // hover: the nearest pick of the form on screen, within reach of the pointer
      let best: Pick | null = null;
      let bestD = 40 * 40;
      if (state.pointer.px >= 0) {
        for (const pk of picks) {
          if (presence(pk.form, form) < 0.75) continue;
          const { sx, sy, front } = project(pk.x, pk.y, pk.z, cam, w, h);
          if (!front) continue;
          const d = (sx - state.pointer.px) ** 2 + (sy - state.pointer.py) ** 2;
          if (d < bestD) {
            bestD = d;
            best = pk;
          }
        }
      }
      const c = card.current;
      if (!c) return;
      if (best !== hovered.current) {
        hovered.current = best;
        if (best) {
          c.querySelector("[data-t]")!.textContent = best.title;
          c.querySelector("[data-l]")!.innerHTML = "";
          for (const line of best.lines) {
            const li = document.createElement("li");
            li.textContent = line;
            c.querySelector("[data-l]")!.appendChild(li);
          }
          c.querySelector("[data-h]")!.textContent = best.href ? "Click to open" : "";
          c.dataset.tone = best.tone ?? "";
        }
        c.style.opacity = best ? "1" : "0";
        document.documentElement.toggleAttribute("data-pick", !!best?.href);
      }
      if (best) {
        const x = Math.min(w - 300, state.pointer.px + 18);
        const y = Math.min(h - 140, state.pointer.py + 18);
        c.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      }
    };
    const onClick = (e: MouseEvent) => {
      const pk = hovered.current;
      if (!pk?.href) return;
      if ((e.target as HTMLElement).closest("a,button,input,[role=button]")) return;
      router.push(pk.href);
    };
    window.addEventListener("click", onClick);
    return () => {
      loop.overlay = null;
      window.removeEventListener("click", onClick);
      document.documentElement.removeAttribute("data-pick");
    };
  }, [anchors, picks, router]);

  return (
    <>
      <div aria-hidden className="pointer-events-none fixed inset-0 z-[5] overflow-hidden">
        {anchors.map((a, i) => (
          <div
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            className={cn(
              "absolute left-0 top-0 opacity-0 will-change-transform",
              a.kind === "axis" && "max-sm:hidden",
            )}
            style={{ visibility: "hidden" }}
          >
            <div
              className={cn(
                "-translate-x-1/2 -translate-y-full whitespace-nowrap pb-1 text-center",
                a.kind === "title" && "font-serif text-[20px] italic text-text-primary",
                a.kind === "label" && "font-mono text-[12px] uppercase tracking-[0.14em] text-text-primary",
                a.kind === "axis" && "font-mono text-[12px] text-text-muted",
                a.tone === "signal" && "text-signal",
                a.tone === "dim" && "text-text-dim",
              )}
            >
              {a.label}
              {a.sub ? (
                <div className="mt-0.5 font-sans text-[12px] normal-case tracking-normal text-text-muted">{a.sub}</div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      <div aria-hidden className="pointer-events-none fixed inset-0 z-overlay overflow-hidden">
        <div
          ref={card}
          className="story-card absolute left-0 top-0 w-[280px] rounded-[6px] border border-border-light bg-ink/90 p-3.5 opacity-0 shadow-lift backdrop-blur-md transition-opacity duration-200"
        >
          <div data-t="" className="text-[14px] text-text-primary" />
          <ul data-l="" className="mt-1.5 space-y-0.5 text-[13px] leading-snug text-text-secondary" />
          <div data-h="" className="mt-2 font-mono text-[12px] text-text-dim" />
        </div>
      </div>
    </>
  );
}
