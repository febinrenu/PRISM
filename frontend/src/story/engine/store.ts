/**
 * Per-frame story state shared by the scroll loop, the DOM layer and the
 * WebGL scene. Written once per tick, read inside useFrame: nothing here
 * causes a React render except the chapter change (`subscribe`).
 */
import { ACTS, newDirector, type Director } from "./config";

export type Tier = 0 | 1 | 2 | 3;

export const state = {
  /** Smoothed scroll position in viewport heights. */
  y: 0,
  /** Viewport height in px, fixed except when the width changes. */
  vh: 800,
  /** Scroll velocity in vh per second, smoothed (one source). */
  velocity: 0,
  pointer: { x: 0, y: 0, px: -1, py: -1 },
  tier: 2 as Tier,
  /** Seconds of story time; advanced with a clamped step. */
  time: 0,
  director: newDirector(),
  /** Particles drawn this tier. */
  count: 0,
  /** ?freeze=1: time stands still (reproducible screenshots). */
  freeze: false,
  /** Distance from the camera to what it looks at (particle depth of field). */
  focusDist: 10,
  /** The current act (index into ACTS). */
  active: 0,
};

export type { Director };

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribe(l: Listener) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

export function setActive(i: number) {
  if (i === state.active) return;
  state.active = i;
  listeners.forEach((l) => l());
}

export const getActive = () => state.active;
export const actCount = ACTS.length;
