"use client";

import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";
import { ACTS } from "../engine/config";
import { getActive, subscribe } from "../engine/store";

/** Which side each act's copy sits on (matches ActSection's `side`). */
const SIDE: Record<string, "left" | "right" | "center"> = { verdict: "right", limits: "center", end: "center" };

/**
 * One fixed scrim behind the copy, between the scene and its labels, so the
 * words never fight the particles and the labels are never dimmed by it.
 */
export default function Scrim() {
  const active = useSyncExternalStore(subscribe, getActive, () => 0);
  const side = SIDE[ACTS[active]?.id] ?? "left";
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[4]">
      {(["left", "right", "center"] as const).map((s) => (
        <div
          key={s}
          className={cn("story-scrim absolute inset-0", `story-scrim-${s}`, side === s ? "opacity-100" : "opacity-0", ACTS[active]?.id === "hero" && "opacity-60")}
          style={side === s ? undefined : { opacity: 0 }}
        />
      ))}
    </div>
  );
}
