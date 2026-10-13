/**
 * Mutable per-frame story state shared by the DOM (scroll) and the WebGL
 * scenes. Written by the scroll handler, read inside useFrame: no React
 * renders per frame. `subscribe` notifies only when the active act changes.
 */

export const ACTS = [
  "prologue",
  "text",
  "reading",
  "curve",
  "society",
  "verdict",
  "faults",
  "provenance",
  "limits",
  "finale",
] as const;
export type ActId = (typeof ACTS)[number];

export type Tier = 0 | 1 | 2 | 3;

export interface CameraPose {
  position: [number, number, number];
  target: [number, number, number];
  fov: number;
}

export const state = {
  /** Scroll progress through each act's sticky phase, unclamped (0..1 inside). */
  local: new Float32Array(ACTS.length).fill(-1),
  active: 0,
  /** Scroll velocity in px/frame, smoothed. */
  velocity: 0,
  pointer: { x: 0, y: 0 },
  tier: 2 as Tier,
  camera: { position: [0, 0, 10], target: [0, 0, 0], fov: 35 } as CameraPose,
  /** Seconds since the story mounted; advanced by the GSAP ticker. */
  time: 0,
};

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribe(l: Listener) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function setActive(i: number) {
  if (i === state.active) return;
  state.active = i;
  listeners.forEach((l) => l());
}

export const getActive = () => state.active;

export function actIndex(id: ActId) {
  return ACTS.indexOf(id);
}

/* ── small maths used by every scene ─────────────────────────────────── */

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const smooth = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeOut = (t: number) => 1 - Math.pow(1 - clamp(t), 3);

/**
 * How present an act's scene is: fades in while its section approaches
 * (local -0.35 → 0) and out as it leaves (1 → 1.35).
 */
export function presence(act: number) {
  const l = state.local[act];
  return smooth(-0.35, 0.02, l) * (1 - smooth(0.98, 1.35, l));
}

/** Clamped progress within an act. */
export const progress = (act: number) => clamp(state.local[act]);
