"use client";

import { marquees } from "./controller";

/** Section headings of the Act drifting past; scroll speed pushes them along. */
export function Marquee({ items }: { items: string[] }) {
  const row = items.join("  ·  ");
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-[1.5vh] z-0 overflow-hidden opacity-[0.28] max-lg:hidden">
      <div ref={(el) => void (el && marquees.add(el))} className="flex w-max whitespace-nowrap font-serif text-[clamp(1.4rem,2.4vw,2.2rem)] italic text-text-dim will-change-transform">
        <span className="pr-12">{row}</span>
        <span className="pr-12">{row}</span>
      </div>
    </div>
  );
}
