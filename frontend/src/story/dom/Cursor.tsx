"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";

/**
 * A ring and a dot that follow the pointer. Links and buttons marked
 * `data-magnetic` lean toward it. Fine pointers only; never under reduced
 * motion (the story is static then anyway).
 */
export default function Cursor() {
  const ring = useRef<HTMLDivElement>(null);
  const dot = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const r = ring.current!;
    const d = dot.current!;
    document.documentElement.classList.add("story-cursor");
    const rx = gsap.quickTo(r, "x", { duration: 0.45, ease: "expo.out" });
    const ry = gsap.quickTo(r, "y", { duration: 0.45, ease: "expo.out" });
    const dx = gsap.quickTo(d, "x", { duration: 0.08, ease: "power3.out" });
    const dy = gsap.quickTo(d, "y", { duration: 0.08, ease: "power3.out" });
    let mag: HTMLElement | null = null;
    const move = (e: PointerEvent) => {
      rx(e.clientX);
      ry(e.clientY);
      dx(e.clientX);
      dy(e.clientY);
      gsap.to([r, d], { opacity: 1, duration: 0.3, overwrite: "auto" });
      const t = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-magnetic],a,button") ?? null;
      if (t !== mag) {
        if (mag) gsap.to(mag, { x: 0, y: 0, duration: 0.6, ease: "elastic.out(1,0.4)" });
        mag = t;
        r.toggleAttribute("data-on", !!t);
      }
      if (mag && mag.hasAttribute("data-magnetic")) {
        const b = mag.getBoundingClientRect();
        gsap.to(mag, { x: (e.clientX - (b.left + b.width / 2)) * 0.22, y: (e.clientY - (b.top + b.height / 2)) * 0.3, duration: 0.4, ease: "power3.out" });
      }
    };
    const leave = () => gsap.to([r, d], { opacity: 0, duration: 0.3 });
    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      document.documentElement.classList.remove("story-cursor");
    };
  }, []);
  return (
    <>
      <div ref={ring} aria-hidden className="story-ring pointer-events-none fixed left-0 top-0 z-toast opacity-0" />
      <div ref={dot} aria-hidden className="story-dot pointer-events-none fixed left-0 top-0 z-toast opacity-0" />
    </>
  );
}
