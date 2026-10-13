import type { Tier } from "./store";

/**
 * Pick a rendering tier once, before the canvas mounts:
 *   0  no WebGL (or reduced motion): SVG and DOM figures only
 *   1  modest devices: fewer particles, no post-processing
 *   2  default: full scenes, light post-processing
 *   3  strong desktops: densest particles, full post-processing
 * `?tier=n` overrides for testing. drei's PerformanceMonitor can lower the
 * tier at runtime if frames drop.
 */
export function detectTier(): Tier {
  if (typeof window === "undefined") return 0;
  const forced = new URLSearchParams(window.location.search).get("tier");
  if (forced && /^[0-3]$/.test(forced)) return Number(forced) as Tier;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return 0;

  let gl: WebGL2RenderingContext | null = null;
  try {
    gl = document.createElement("canvas").getContext("webgl2");
  } catch {
    gl = null;
  }
  if (!gl) return 0;

  let renderer = "";
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  if (info) renderer = String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL));
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  if (/swiftshader|llvmpipe|software|basic render/i.test(renderer)) return 1;

  const nav = navigator as Navigator & { deviceMemory?: number };
  const memory = nav.deviceMemory ?? 8;
  const cores = nav.hardwareConcurrency ?? 8;
  const small = Math.min(window.innerWidth, window.innerHeight) < 600;
  if (small || memory <= 4 || cores <= 4) return 1;
  if (memory >= 8 && cores >= 8 && /nvidia|radeon|apple m|apple gpu|geforce|rtx|arc/i.test(renderer)) return 3;
  return 2;
}

/** Particle budgets per tier for the population and finale scenes. */
export const particleBudget = (tier: Tier) => [0, 8000, 24000, 60000][tier];
