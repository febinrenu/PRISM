import * as THREE from "three";
import { tokens } from "@/design/tokens";

export const C = {
  ink: new THREE.Color(tokens.ink[900]),
  paper: new THREE.Color(tokens.paper[100]),
  paperDim: new THREE.Color(tokens.paper[300]),
  graphite: new THREE.Color(tokens.ink[600]),
  signal: new THREE.Color(tokens.signal[500]),
  /** HDR vermilion: the only colour bright enough to bloom. */
  signalHot: new THREE.Color(tokens.signal[500]).multiplyScalar(3.2),
  blue: new THREE.Color(tokens.hue.blue.base),
  teal: new THREE.Color(tokens.hue.teal.base),
};

/** Deterministic PRNG (mulberry32), so scenes look the same on every visit. */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The font stacks next/font registered, for drawing on canvas. */
export function fontStack(variable: "--font-serif" | "--font-geist-sans" | "--font-geist-mono") {
  if (typeof document === "undefined") return "serif";
  const v = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
  return v || (variable === "--font-serif" ? "Georgia, serif" : variable === "--font-geist-mono" ? "monospace" : "sans-serif");
}

/** Greedy word wrap for canvas text; returns lines with each word's x. */
export function wrap(ctx: CanvasRenderingContext2D, text: string, width: number) {
  const out: { words: { w: string; x: number; start: number; end: number }[] }[] = [];
  let line: { w: string; x: number; start: number; end: number }[] = [];
  let x = 0;
  const space = ctx.measureText(" ").width;
  const re = /\S+/g;
  let m: RegExpExecArray | null;
  const push = () => {
    out.push({ words: line });
    line = [];
    x = 0;
  };
  const paragraphs = text.split("\n");
  let offset = 0;
  for (const para of paragraphs) {
    re.lastIndex = 0;
    while ((m = re.exec(para))) {
      const w = m[0];
      const ww = ctx.measureText(w).width;
      if (x > 0 && x + ww > width) push();
      line.push({ w, x, start: offset + m.index, end: offset + m.index + w.length });
      x += ww + space;
    }
    push();
    offset += para.length + 1;
  }
  return out;
}

/** A sprite label drawn on canvas; height in world units. */
export function labelSprite(
  text: string,
  opts: { height?: number; color?: string; font?: "mono" | "sans" | "serif"; weight?: number; size?: number } = {}
) {
  const size = opts.size ?? 44;
  const fam =
    opts.font === "serif" ? fontStack("--font-serif") : opts.font === "sans" ? fontStack("--font-geist-sans") : fontStack("--font-geist-mono");
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d")!;
  ctx.font = `${opts.weight ?? 400} ${size}px ${fam}`;
  const w = Math.ceil(ctx.measureText(text).width) + 16;
  c.width = w;
  c.height = Math.ceil(size * 1.4);
  ctx.font = `${opts.weight ?? 400} ${size}px ${fam}`;
  ctx.fillStyle = opts.color ?? tokens.paper[100];
  ctx.textBaseline = "middle";
  ctx.fillText(text, 8, c.height / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false });
  const s = new THREE.Sprite(mat);
  const h = opts.height ?? 0.22;
  s.scale.set((h * c.width) / c.height, h, 1);
  return s;
}

export function disposeObject(o: THREE.Object3D) {
  o.traverse((x) => {
    const m = x as THREE.Mesh;
    m.geometry?.dispose?.();
    const mat = m.material as THREE.Material | THREE.Material[] | undefined;
    (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((mm) => {
      const map = (mm as THREE.MeshBasicMaterial).map;
      map?.dispose();
      mm.dispose();
    });
  });
}
