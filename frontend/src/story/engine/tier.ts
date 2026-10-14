import type { Tier } from "./store";

/**
 * Pick a rendering tier once, before anything mounts:
 *   0  no WebGL2, or reduced motion: the static story (DOM figures)
 *   1  software renderers and very small devices: fewer particles, light post
 *   2  integrated GPUs: full scene
 *   3  discrete GPUs and Apple silicon: densest particles, glass refraction
 * `?tier=n` overrides. The tier never changes after the scene mounts; the
 * frame governor only lowers the pixel ratio.
 */
export function detectTier(): { tier: Tier; renderer: string } {
  if (typeof window === "undefined") return { tier: 0, renderer: "" };
  const forced = new URLSearchParams(window.location.search).get("tier");
  let renderer = "";
  let gl: WebGL2RenderingContext | null = null;
  try {
    gl = document.createElement("canvas").getContext("webgl2");
  } catch {
    gl = null;
  }
  if (gl) {
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    if (info) renderer = String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
  if (forced && /^[0-3]$/.test(forced)) return { tier: Number(forced) as Tier, renderer };
  if (!gl) return { tier: 0, renderer };
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return { tier: 0, renderer };
  try {
    if (window.localStorage.getItem("prism-story-static") === "1") return { tier: 0, renderer };
  } catch {
    /* storage blocked */
  }
  if (/swiftshader|llvmpipe|software|basic render/i.test(renderer)) return { tier: 1, renderer };
  const nav = navigator as Navigator & { deviceMemory?: number };
  if ((nav.deviceMemory ?? 8) <= 2) return { tier: 1, renderer };
  const small = Math.min(window.innerWidth, window.innerHeight) < 600;
  if (small && (nav.hardwareConcurrency ?? 8) <= 4) return { tier: 1, renderer };
  if (/nvidia|geforce|rtx|radeon|arc\b|apple m|apple gpu|adreno.*7\d\d/i.test(renderer)) return { tier: 3, renderer };
  return { tier: 2, renderer };
}

export const PARTICLES: Record<Tier, number> = { 0: 0, 1: 12288, 2: 32768, 3: 65536 };
export const MAX_DPR: Record<Tier, number> = { 0: 1, 1: 1, 2: 1.5, 3: 2 };
