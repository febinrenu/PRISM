/**
 * The particle forms. Each form places every particle somewhere meaningful,
 * built only from the story snapshot and the three data files: the beam is
 * the demo Act's own clauses, the skyline is the corpus, the page and the
 * tagged clause are real text with real entity spans, the web is the
 * provenance graph, the dune is the taxpayer population, and so on.
 *
 * Output per form: position+size (float4), meta (palette, glyph, brightness,
 * flags as bytes) and aux (choreography delay). Particles keep one entity
 * class for the whole story; consecutive forms are matched in Morton order
 * so particles travel to nearby targets instead of crossing the scene.
 */
import { ENTITY_ORDER, ERROR_LABEL, SYSTEM_LABEL, inr, lakh, pnv, reformLabel, story } from "../data";
import type { Constellation, PipelineGraph, Population } from "../data";
import { FORMS } from "../engine/config";
import { clamp, gauss, layout, morton, rng } from "./util";

export const N_MAX = 65536;
/** Particles every tier draws; text that must be read lives in this prefix. */
export const N_CORE = 12288;

/* Palette slots (uniform array uPal in the particle shader). */
export const PAL = { paper: 6, signal: 7, grey: 8, gain: 9, ramp: 10 } as const;
/* Flags. */
export const FLOW = 1;
export const INTRINSIC = 2; // colour shows regardless of the prism gate
export const SINGLE = 4; // flow leaves the prism as one beam
export const TEXT = 8; // a glyph that should stay sharp

export interface Anchor {
  form: number;
  x: number;
  y: number;
  z: number;
  label: string;
  sub?: string;
  kind: "label" | "axis" | "title";
  tone?: "signal" | "dim";
}

export interface Pick {
  form: number;
  x: number;
  y: number;
  z: number;
  title: string;
  lines: string[];
  href?: string;
  tone?: "signal";
}

export interface FormData {
  n: number;
  forms: number;
  pos: Float32Array; // forms * n * 4
  meta: Uint8Array;
  aux: Uint8Array;
  classes: Uint8Array;
  anchors: Anchor[];
  picks: Pick[];
  /** Fan directions of the six beams (unit vectors) and their relative widths. */
  beams: { dir: [number, number, number]; width: number; label: string; count: string }[];
}

export interface Inputs {
  population: Population;
  constellation: Constellation;
  graph: PipelineGraph;
  glyph: (ch: string) => number;
}

/* ── a growable target set ─────────────────────────────────────────────── */

class Targets {
  n = 0;
  x: number[] = [];
  y: number[] = [];
  z: number[] = [];
  s: number[] = [];
  pal: number[] = [];
  g: number[] = [];
  b: number[] = [];
  f: number[] = [];
  d: number[] = []; // delay, -1 = random
  cls: number[] = []; // required class, -1 = any
  pri: number[] = []; // must be drawn on every tier
  add(x: number, y: number, z: number, s: number, pal: number, g = 0, b = 1, f = 0, d = -1, cls = -1, pri = 0) {
    this.x.push(x);
    this.y.push(y);
    this.z.push(z);
    this.s.push(s);
    this.pal.push(pal);
    this.g.push(g);
    this.b.push(b);
    this.f.push(f);
    this.d.push(d);
    this.cls.push(cls);
    this.pri.push(pri);
    this.n++;
  }
}

/* ── text helpers ──────────────────────────────────────────────────────── */

interface TextOpts {
  x: number;
  y: number;
  z: number;
  cols: number;
  size: number;
  adv?: number;
  lh?: number;
  pal?: (i: number) => number;
  bright?: (i: number) => number;
  lift?: (i: number) => number;
  flags?: (i: number) => number;
  delayFrom?: number;
  delaySpan?: number;
  center?: boolean;
}

/** Lay real text out as glyph particles; returns the laid-out characters' positions. */
function text(t: Targets, inp: Inputs, str: string, o: TextOpts) {
  const adv = o.adv ?? o.size * 0.6;
  const lh = o.lh ?? o.size * 1.35;
  const chars = layout(str, o.cols);
  const rows = chars.length ? chars[chars.length - 1].row + 1 : 0;
  const width = o.cols * adv;
  const x0 = o.center === false ? o.x : o.x - width / 2;
  const y0 = o.y + (rows * lh) / 2;
  const placed: { i: number; x: number; y: number; z: number }[] = [];
  chars.forEach((c, k) => {
    const x = x0 + c.col * adv + adv / 2;
    const y = y0 - c.row * lh - lh / 2;
    const z = o.z + (o.lift?.(c.i) ?? 0);
    const d = o.delayFrom !== undefined ? o.delayFrom + (k / Math.max(1, chars.length)) * (o.delaySpan ?? 0.6) : -1;
    t.add(x, y, z, o.size, o.pal?.(c.i) ?? PAL.paper, inp.glyph(c.ch), o.bright?.(c.i) ?? 1, TEXT | (o.flags?.(c.i) ?? 0), d, -1, 1);
    placed.push({ i: c.i, x, y, z });
  });
  return { placed, rows, width, height: rows * lh };
}

/** Particles spaced along a segment. */
function segment(
  t: Targets,
  a: [number, number, number],
  b: [number, number, number],
  count: number,
  size: number,
  pal: number,
  bright: number,
  r: () => number,
  jitter = 0,
  flags = 0,
  bend = 0
) {
  for (let k = 0; k < count; k++) {
    const u = (k + r()) / count;
    const lift = bend * Math.sin(Math.PI * u);
    t.add(
      a[0] + (b[0] - a[0]) * u + gauss(r) * jitter,
      a[1] + (b[1] - a[1]) * u + gauss(r) * jitter,
      a[2] + (b[2] - a[2]) * u + gauss(r) * jitter + lift,
      size,
      pal,
      0,
      bright,
      flags
    );
  }
}

/* ── the forms ─────────────────────────────────────────────────────────── */

type Gen = (ctx: Ctx) => Targets;
interface Ctx {
  n: number;
  inp: Inputs;
  classCount: number[];
  anchors: Anchor[];
  picks: Pick[];
  form: number;
  beams: FormData["beams"];
}

const streamText = story.pipeline.samples.map((s) => s.text.replace(/\s+/g, " ")).join(" ");

/** The beam: statute characters flowing into the prism and out as six hues. */
function flowGen(single: boolean): Gen {
  return (ctx) => {
    const t = new Targets();
    const r = rng(single ? 71 : 17);
    let k = 0;
    ctx.classCount.forEach((count, c) => {
      for (let i = 0; i < count; i++) {
        const ch = streamText[(k * 7919) % streamText.length];
        k++;
        const u = gauss(r) * 0.5;
        const v = gauss(r) * 0.5;
        const phase = r();
        const edge = Math.min(1, Math.hypot(u, v));
        const pal = single ? (edge > 0.75 && r() < 0.6 ? c : PAL.paper) : c;
        const flags = FLOW | (single ? SINGLE | (pal !== PAL.paper ? INTRINSIC : 0) : 0);
        const size = 0.05 + r() * 0.05;
        t.add(u, v, phase, size, pal, /\s/.test(ch) ? 0 : ctx.inp.glyph(ch), (0.75 + r() * 0.5) * (single ? 0.45 : 1), flags, -1, c);
      }
    });
    return t;
  };
}

/** The corpus as stacks of pages, one per statute, in order of enactment. */
const skyline: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(23);
  const year = (k: string) => Number((k.match(/(\d{4})/) ?? ["", "0"])[1]);
  const list = [...story.corpus.statutes].sort((a, b) => year(a.key) - year(b.key) || a.key.localeCompare(b.key));
  const maxS = Math.max(...list.map((s) => s.sections));
  const total = list.reduce((s, x) => s + x.sections, 0);
  const span = 11.5;
  list.forEach((s, i) => {
    const x = 1.2 - span / 2 + (i + 0.5) * (span / list.length);
    const z = -Math.abs(i - (list.length - 1) / 2) * 0.35;
    const h = 0.6 + (s.sections / maxS) * 5.6;
    const base = -2.6;
    const count = Math.round((ctx.n * 0.94 * s.sections) / total);
    const w = 0.95;
    const d = 0.7;
    for (let k = 0; k < count; k++) {
      const sheet = Math.floor(r() * (h / 0.045));
      const y = base + sheet * 0.045;
      // most particles on the visible faces, as lines of text
      const face = r();
      let px: number, pz: number;
      if (face < 0.55) {
        px = x + (r() - 0.5) * w;
        pz = z + d / 2;
      } else if (face < 0.8) {
        px = x + (r() < 0.5 ? -w / 2 : w / 2);
        pz = z + (r() - 0.5) * d;
      } else {
        px = x + (r() - 0.5) * w;
        pz = z + (r() - 0.5) * d;
      }
      const top = sheet * 0.045 > h - 0.1;
      const ch = streamText[(k * 131 + i * 17) % streamText.length];
      t.add(px, y + (r() - 0.5) * 0.012, pz, 0.026 + r() * 0.018, PAL.paper, /\s/.test(ch) ? 0 : ctx.inp.glyph(ch), top ? 1.3 : 0.45 + 0.35 * (sheet % 7 === 0 ? 1 : r()), 0, (i / list.length) * 0.6 + r() * 0.2);
    }
    const name = s.key.split("/")[0];
    ctx.anchors.push({ form: ctx.form, x, y: base + h + 0.25, z: z + d / 2, label: name, sub: `${inr(s.sections)} sections`, kind: "label" });
  });
  // dust
  while (t.n < ctx.n) t.add((r() - 0.5) * 18, -2.6 + r() * 9, -4 + r() * 6, 0.02, PAL.paper, 0, 0.12);
  return t;
};

const PAGE_TEXT = story.pipeline.samples[0];

/** One readable page, the rest of the Act behind it. */
const page: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(29);
  const { width, height } = text(t, ctx.inp, PAGE_TEXT.text, {
    x: 0,
    y: 0.2,
    z: 2,
    cols: 46,
    size: 0.125,
    adv: 0.064,
    lh: 0.17,
    bright: () => 1.15,
    delayFrom: 0,
    delaySpan: 0.85,
  });
  // the page's edge
  const w = width + 0.5;
  const h = height + 0.6;
  const corners: [number, number, number][] = [
    [-w / 2, 0.2 + h / 2, 2],
    [w / 2, 0.2 + h / 2, 2],
    [w / 2, 0.2 - h / 2, 2],
    [-w / 2, 0.2 - h / 2, 2],
  ];
  for (let i = 0; i < 4; i++) segment(t, corners[i], corners[(i + 1) % 4], 160, 0.022, PAL.paper, 0.22, r);
  ctx.anchors.push({ form: ctx.form, x: -w / 2, y: 0.2 + h / 2 + 0.2, z: 2, label: `page ${PAGE_TEXT.page}`, sub: "Income-tax Bill, 2025", kind: "axis" });
  // the ghost stack: the other pages of the Act, receding
  const pages = 90;
  while (t.n < ctx.n) {
    const p = 1 + Math.floor(Math.pow(r(), 0.7) * pages);
    const z = 2 - p * 0.16;
    const line = Math.floor(r() * 26);
    const y = 0.2 + h / 2 - 0.3 - line * ((h - 0.6) / 26);
    const x = -w / 2 + 0.25 + r() * (w - 0.5);
    const ch = streamText[(t.n * 37) % streamText.length];
    t.add(x + Math.sin(p * 1.7) * 0.3, y + Math.cos(p * 2.3) * 0.15, z, 0.05, PAL.paper, /\s/.test(ch) ? 0 : ctx.inp.glyph(ch), 0.12 * (1 - p / (pages + 10)), 0, 0.85 + r() * 0.15);
  }
  return t;
};

/** The Act's structure as a cone tree: document, chapters, sections, and the rebate thread's sub-sections. */
const tree: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(31);
  const nodes = ctx.inp.constellation.nodes;
  const depth: number[] = nodes.map(() => 0);
  const kids: number[][] = nodes.map(() => []);
  nodes.forEach((n, i) => {
    if (n.p >= 0) {
      depth[i] = depth[n.p] + 1;
      kids[n.p].push(i);
    }
  });
  const roots = nodes.map((n, i) => (n.p < 0 ? i : -1)).filter((i) => i >= 0);
  // leaf-count angular layout
  const leaves: number[] = nodes.map(() => 0);
  for (let i = nodes.length - 1; i >= 0; i--) leaves[i] = Math.max(1, kids[i].reduce((s, k) => s + leaves[k], 0));
  const ang: number[] = nodes.map(() => 0);
  const totalLeaves = roots.reduce((s, i) => s + leaves[i], 0);
  let acc = 0;
  const place = (i: number, a0: number, a1: number) => {
    ang[i] = (a0 + a1) / 2;
    let a = a0;
    for (const k of kids[i]) {
      const span = ((a1 - a0) * leaves[k]) / leaves[i];
      place(k, a, a + span);
      a += span;
    }
  };
  for (const i of roots) {
    const span = (Math.PI * 2 * leaves[i]) / totalLeaves;
    place(i, acc, acc + span);
    acc += span;
  }
  const thread = new Set<number>();
  for (const s of ctx.inp.constellation.thread) {
    const stack = [s];
    while (stack.length) {
      const k = stack.pop()!;
      thread.add(k);
      stack.push(...kids[k]);
    }
  }
  const radius = [2.3, 4.6, 5.6, 6.2, 6.6, 6.9];
  const ys = [1.6, -0.2, -1.3, -2.0, -2.5, -2.9];
  const P = nodes.map((n, i) => {
    const d = Math.min(depth[i], radius.length - 1);
    const rad = radius[d] * (thread.has(i) && d >= 2 ? 0.8 : 1);
    return [Math.cos(ang[i]) * rad, ys[d], Math.sin(ang[i]) * rad] as [number, number, number];
  });
  const root: [number, number, number] = [0, 3.4, 0];
  // edges first (budget), then node glyph clusters
  const edgeBudget = ctx.n * 0.5;
  const edges = nodes.map((n, i) => [n.p >= 0 ? P[n.p] : root, P[i], i] as const);
  const len = edges.map(([a, b]) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
  const totalLen = len.reduce((s, x) => s + x, 0);
  edges.forEach(([a, b, i], k) => {
    const hot = thread.has(i);
    segment(t, a, b, Math.max(2, Math.round((edgeBudget * len[k]) / totalLen)), hot ? 0.035 : 0.022, PAL.paper, hot ? 1.4 : 0.35, r, 0.004);
  });
  const nodeBudget = ctx.n - t.n - 600;
  const weight = nodes.map((n, i) => (n.k === "chapter" ? 6 : n.k === "section" ? 2 : 1) * (thread.has(i) ? 3 : 1));
  const totalW = weight.reduce((s, x) => s + x, 0);
  nodes.forEach((n, i) => {
    const count = Math.max(1, Math.round((nodeBudget * weight[i]) / totalW));
    const label = (n.h || n.l || "§").replace(/\s+/g, " ");
    const hot = thread.has(i);
    for (let k = 0; k < count; k++) {
      const ch = label[k % label.length];
      const rr = 0.05 + 0.1 * Math.sqrt(r()) * (n.k === "chapter" ? 2.2 : 1);
      const a = r() * Math.PI * 2;
      t.add(P[i][0] + Math.cos(a) * rr, P[i][1] + gauss(r) * 0.04, P[i][2] + Math.sin(a) * rr, n.k === "chapter" ? 0.07 : 0.05, PAL.paper, /\s/.test(ch) ? 0 : ctx.inp.glyph(ch), hot ? 1.6 : n.k === "chapter" ? 1.0 : 0.6, 0, clamp(depth[i] / 4) * 0.7 + r() * 0.2);
    }
  });
  for (let k = 0; k < 600; k++) {
    const a = r() * Math.PI * 2;
    const rr = 0.25 * Math.sqrt(r());
    t.add(root[0] + Math.cos(a) * rr, root[1] + gauss(r) * 0.06, root[2] + Math.sin(a) * rr, 0.06, PAL.paper, 0, 1.6, 0, 0);
  }
  ctx.anchors.push({ form: ctx.form, x: root[0], y: root[1] + 0.45, z: root[2], label: ctx.inp.constellation.title, kind: "title" });
  for (const s of ctx.inp.constellation.thread) {
    const n = nodes[s];
    ctx.anchors.push({ form: ctx.form, x: P[s][0], y: P[s][1] + 0.35, z: P[s][2], label: `s. ${n.l}`, sub: n.h, kind: "label" });
  }
  return t;
};

const TAG = story.pipeline.samples[0];

/** The same clause, tagged: each entity span lifts out in its type's colour. */
const entities: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(37);
  const label = new Int16Array(TAG.text.length).fill(-1);
  for (const [l, a, b] of TAG.entities) for (let i = a; i < b; i++) label[i] = ENTITY_ORDER.indexOf(l);
  text(t, ctx.inp, TAG.text, {
    x: 0,
    y: 0.25,
    z: 1,
    cols: 46,
    size: 0.125,
    adv: 0.064,
    lh: 0.17,
    pal: (i) => (label[i] >= 0 ? label[i] : PAL.paper),
    bright: (i) => (label[i] >= 0 ? 2.2 : 0.75),
    lift: (i) => (label[i] >= 0 ? 0.45 : 0),
  });
  // six clusters, one per entity type, sized by the square root of its count
  const counts = ENTITY_ORDER.map((l) => pnv(`entity@${l}`));
  const roots = counts.map(Math.sqrt);
  const sumR = roots.reduce((s, x) => s + x, 0);
  const budget = ctx.n - t.n;
  ENTITY_ORDER.forEach((l, c) => {
    const k = c / (ENTITY_ORDER.length - 1);
    const cx = -0.5 + k * 7.4;
    const cy = 2.9 + Math.sin(k * Math.PI) * 0.5;
    const cz = -5.5 - Math.sin(k * Math.PI) * 1.2;
    const rad = 0.3 + 0.75 * (roots[c] / Math.max(...roots));
    const count = Math.round((budget * roots[c]) / sumR);
    for (let k = 0; k < count && t.n < ctx.n; k++) {
      const u = gauss(r) * 0.45;
      const v = gauss(r) * 0.45;
      const w = gauss(r) * 0.45;
      t.add(cx + u * rad, cy + v * rad, cz + w * rad, 0.04, c, 0, 0.5 + r() * 0.5, 0, 0.2 + r() * 0.6, c);
    }
    ctx.anchors.push({ form: ctx.form, x: cx, y: cy + rad + 0.25, z: cz, label: l.toLowerCase(), sub: `${inr(counts[c])} tagged`, kind: "label" });
  });
  while (t.n < ctx.n) t.add((r() - 0.5) * 16, (r() - 0.5) * 8, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

const RISK_BRIGHT: Record<string, number> = { CRITICAL: 2.4, HIGH: 1.7, MEDIUM: 1.15, LOW: 0.75 };

/** Condition → consequence: arcs over the clause, and every pattern in the Act behind it. */
const threads: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(41);
  const cond = new Int8Array(TAG.text.length);
  for (const [c0, c1, a0, a1] of TAG.causal) {
    for (let i = c0; i < c1; i++) cond[i] = 1;
    for (let i = a0; i < a1; i++) cond[i] = 2;
  }
  const { placed } = text(t, ctx.inp, TAG.text, {
    x: 0,
    y: 0.2,
    z: 0.6,
    cols: 46,
    size: 0.125,
    adv: 0.064,
    lh: 0.17,
    bright: (i) => (cond[i] ? 1.5 : 0.4),
  });
  const at = new Map(placed.map((p) => [p.i, p]));
  const centroid = (a: number, b: number): [number, number, number] => {
    let x = 0,
      y = 0,
      n = 0;
    for (let i = a; i < b; i++) {
      const p = at.get(i);
      if (p) {
        x += p.x;
        y += p.y;
        n++;
      }
    }
    return [x / Math.max(1, n), y / Math.max(1, n), 0.65];
  };
  TAG.causal.forEach(([c0, c1, a0, a1, risk], k) => {
    const a = centroid(c0, c1);
    const b = centroid(a0, a1);
    segment(t, a, b, 900, 0.05, PAL.paper, RISK_BRIGHT[risk] ?? 1, r, 0.012, 0, 1.6 + k * 0.4);
    ctx.anchors.push({ form: ctx.form, x: (a[0] + b[0]) / 2, y: Math.max(a[1], b[1]) + 0.35, z: 0.65 + 1.6 + k * 0.4, label: `${risk.toLowerCase()} risk`, sub: "condition → consequence", kind: "label" });
  });
  // every pattern in the Act, as a field of arcs behind, by risk tier
  const tiers = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => ({ k, n: pnv(`risk@${k}`) }));
  const totalArcs = tiers.reduce((s, x) => s + x.n, 0);
  const perArc = Math.max(6, Math.floor((ctx.n - t.n) / totalArcs));
  for (const tier of tiers) {
    for (let a = 0; a < tier.n && t.n + perArc <= ctx.n; a++) {
      const th = r() * Math.PI * 2;
      const ph = Math.acos(2 * r() - 1);
      const R = 6 + r() * 4;
      const p: [number, number, number] = [Math.sin(ph) * Math.cos(th) * R + 2, Math.cos(ph) * R * 0.55, -Math.abs(Math.sin(ph) * Math.sin(th)) * R - 5];
      const q: [number, number, number] = [p[0] + gauss(r) * 0.9, p[1] + gauss(r) * 0.6, p[2] + gauss(r) * 0.4];
      segment(t, p, q, perArc, 0.026, PAL.paper, (RISK_BRIGHT[tier.k] ?? 1) * 0.2, r, 0.01, 0, 0.35);
    }
  }
  while (t.n < ctx.n) t.add((r() - 0.5) * 18, (r() - 0.5) * 9, -8 + r() * 4, 0.02, PAL.paper, 0, 0.1);
  return t;
};

/** The provenance web: document → chapter → clause → pattern, with entity hubs. */
const graph: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(43);
  const g = ctx.inp.graph;
  const type = (i: number) => g.types[g.nodes[i][0]];
  const pos: [number, number, number][] = [];
  const dirOf: [number, number, number][] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  const chapters = g.nodes.map((_, i) => i).filter((i) => type(i) === "chapter");
  const entityIdx = g.nodes.map((_, i) => i).filter((i) => type(i) === "entity");
  g.nodes.forEach((row, i) => {
    const ty = type(i);
    if (ty === "document") {
      pos[i] = [0, 0, 0];
      dirOf[i] = [0, 1, 0];
      return;
    }
    if (ty === "chapter") {
      const k = chapters.indexOf(i);
      const y = 1 - (2 * (k + 0.5)) / chapters.length;
      const rad = Math.sqrt(1 - y * y);
      const d: [number, number, number] = [Math.cos(golden * k) * rad, y * 0.75, Math.sin(golden * k) * rad];
      dirOf[i] = d;
      pos[i] = [d[0] * 1.7, d[1] * 1.7, d[2] * 1.7];
      return;
    }
    if (ty === "entity") {
      const k = entityIdx.indexOf(i);
      const a = (k / entityIdx.length) * Math.PI * 2;
      pos[i] = [Math.cos(a) * 6.4, -3.1 + Math.sin(a * 3) * 0.2, Math.sin(a) * 6.4 * 0.6 - 1];
      dirOf[i] = [Math.cos(a), 0, Math.sin(a)];
      return;
    }
    const p = row[1] >= 0 ? row[1] : 0;
    const pd = dirOf[p] ?? [0, 1, 0];
    const spread = ty === "clause" ? 0.42 : 0.18;
    const d = [pd[0] + gauss(r) * spread, pd[1] + gauss(r) * spread * 0.8, pd[2] + gauss(r) * spread];
    const l = Math.hypot(d[0], d[1], d[2]) || 1;
    const u: [number, number, number] = [d[0] / l, d[1] / l, d[2] / l];
    dirOf[i] = u;
    const R = ty === "clause" ? 3.3 + r() * 0.5 : 4.5 + r() * 0.4;
    pos[i] = [u[0] * R, u[1] * R * 0.85, u[2] * R];
  });
  const labelOfEntity = (i: number) => g.nodes[i][2] ?? 0;
  // tree edges
  const treeBudget = ctx.n * 0.34;
  const linkBudget = ctx.n * 0.22;
  const perTree = Math.max(3, Math.floor(treeBudget / g.nodes.length));
  g.nodes.forEach((row, i) => {
    if (row[1] < 0) return;
    const ty = type(i);
    segment(t, pos[row[1]], pos[i], perTree, 0.022, PAL.paper, ty === "causal" ? 0.8 : 0.4, r, 0.003);
  });
  const perLink = Math.max(3, Math.floor(linkBudget / Math.max(1, g.links.length)));
  for (const [a, b] of g.links) {
    segment(t, pos[a], pos[b], perLink, 0.018, labelOfEntity(b), 0.32, r, 0.004, 0, 0);
  }
  // nodes
  const nodeBudget = ctx.n - t.n - 400;
  const w = g.nodes.map((_, i) => ({ document: 40, chapter: 6, clause: 2, causal: 2, entity: 5 })[type(i)] ?? 1);
  const totalW = w.reduce((s, x) => s + x, 0);
  g.nodes.forEach((_, i) => {
    const ty = type(i);
    const count = Math.max(1, Math.round((nodeBudget * w[i]) / totalW));
    const rad = ty === "document" ? 0.35 : ty === "chapter" ? 0.12 : 0.05;
    const pal = ty === "entity" ? labelOfEntity(i) : PAL.paper;
    const bright = ty === "causal" ? 1.8 : ty === "document" ? 2 : ty === "entity" ? 1.4 : 1;
    for (let k = 0; k < count; k++) {
      t.add(pos[i][0] + gauss(r) * rad, pos[i][1] + gauss(r) * rad, pos[i][2] + gauss(r) * rad, ty === "clause" ? 0.05 : 0.06, pal, 0, bright, 0, clamp(Math.hypot(...pos[i]) / 6.5) * 0.8 + r() * 0.15);
    }
  });
  for (const h of g.hubs.slice(0, 120)) {
    ctx.picks.push({
      form: ctx.form,
      x: pos[h.i][0],
      y: pos[h.i][1],
      z: pos[h.i][2],
      title: `Clause · page ${h.page}`,
      lines: [h.preview + "…"],
      href: `/explain/${g.doc}/${h.clause_id}`,
    });
  }
  while (t.n < ctx.n) {
    const a = r() * Math.PI * 2;
    const R = 7 + r() * 5;
    t.add(Math.cos(a) * R, (r() - 0.5) * 7, Math.sin(a) * R, 0.02, PAL.paper, 0, 0.12);
  }
  return t;
};

/* income axis shared by the population, the curve and the torn curve */
const SAL_MAX = story.curve.salary[story.curve.salary.length - 1];

/**
 * The taxpayers as a parade: every return in order of income, left to right
 * (x = share of all returns), each column as tall as its income (log scale).
 * Teal: pays less under the new law than under the year before.
 */
const population: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(47);
  const rows = ctx.inp.population.rows;
  const total = rows.reduce((s, x) => s + x[1], 0);
  const lmin = Math.log(Math.max(10000, rows[0][0]));
  const lmax = Math.log(rows[rows.length - 1][0]);
  const H = (inc: number) => 0.15 + ((Math.log(Math.max(10000, inc)) - lmin) / (lmax - lmin)) * 5.6;
  const base = -2.4;
  const budget = ctx.n - 2600;
  let cum = 0;
  for (const row of rows) {
    const share = row[1] / total;
    const x0 = -6.5 + cum * 13;
    const x1 = -6.5 + (cum + share) * 13;
    cum += share;
    const count = Math.max(1, Math.round(budget * share));
    const h = H(row[0]);
    const pays_less = row[4] < row[3] - 0.5;
    const pal = pays_less ? PAL.gain : PAL.ramp + Math.round(((row[2] - 1) / 9) * 5);
    for (let k = 0; k < count && t.n < ctx.n - 2600; k++) {
      const top = r() < 0.18;
      const y = top ? base + h + gauss(r) * 0.015 : base + Math.pow(r(), 0.8) * h;
      t.add(x0 + r() * (x1 - x0), y, (r() - 0.5) * 2.4, top ? 0.04 : 0.032, pal, 0, top ? (pays_less ? 1.9 : 1.2) : pays_less ? 1.0 : 0.5, INTRINSIC, cum * 0.8 + r() * 0.15);
    }
  }
  // tenths of the population: thin lines at every decile boundary, labelled with its income
  story.deciles.deciles.slice(0, 9).forEach((d, i) => {
    const x = -6.5 + ((i + 1) / 10) * 13;
    const h = H(d.income_upper);
    segment(t, [x, base, 1.25], [x, base + h + 0.25, 1.25], 160, 0.018, PAL.paper, 0.4, r);
    if (i % 2 === 1 || i === 8) ctx.anchors.push({ form: ctx.form, x, y: base + h + 0.55, z: 1.25, label: `₹${lakh(d.income_upper)}`, kind: "axis" });
  });
  segment(t, [-6.5, base, 1.25], [6.5, base, 1.25], 500, 0.02, PAL.paper, 0.45, r);
  ctx.anchors.push({ form: ctx.form, x: -6.5, y: base - 0.35, z: 1.25, label: "poorest", kind: "axis", tone: "dim" });
  ctx.anchors.push({ form: ctx.form, x: 6.5, y: base - 0.35, z: 1.25, label: "richest", kind: "axis", tone: "dim" });
  while (t.n < ctx.n) t.add((r() - 0.5) * 16, -2.6 + r() * 7, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

function curvePoints(series: number[], yMax: number) {
  return story.curve.salary.map((s, i) => [-6 + (s / SAL_MAX) * 12, -2.3 + (series[i] / yMax) * 5] as [number, number]);
}

function ribbon(t: Targets, pts: [number, number][], count: number, pal: number, bright: number, r: () => number, depth: number, flags = 0, delayFrom = 0) {
  for (let k = 0; k < count; k++) {
    const u = r() * (pts.length - 1);
    const i = Math.floor(u);
    const f = u - i;
    const a = pts[i];
    const b = pts[Math.min(pts.length - 1, i + 1)];
    t.add(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f + gauss(r) * 0.012, (r() - 0.5) * depth, 0.04, pal, 0, bright, flags, delayFrom + (u / pts.length) * 0.6);
  }
}

function axes(t: Targets, ctx: Ctx, r: () => number) {
  segment(t, [-6, -2.3, 0], [6.2, -2.3, 0], 500, 0.02, PAL.paper, 0.5, r);
  segment(t, [-6, -2.3, 0], [-6, 2.9, 0], 260, 0.02, PAL.paper, 0.35, r);
  for (const s of [500000, 1000000, 1500000, 2000000, 2500000].filter((x) => x <= SAL_MAX)) {
    const x = -6 + (s / SAL_MAX) * 12;
    segment(t, [x, -2.36, 0], [x, -2.24, 0], 12, 0.02, PAL.paper, 0.6, r);
    ctx.anchors.push({ form: ctx.form, x, y: -2.6, z: 0, label: `₹${lakh(s)}`, kind: "axis" });
  }
}

const yMaxCurve = Math.max(...story.curve.series.before, ...story.curve.series.expert, ...story.curve.series.system);

/** Tax by salary under the law (bright), and the year before (dim). */
const curve: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(53);
  axes(t, ctx, r);
  const exp = curvePoints(story.curve.series.expert, yMaxCurve);
  const before = curvePoints(story.curve.series.before, yMaxCurve);
  ribbon(t, exp, Math.round(ctx.n * 0.38), PAL.paper, 1.35, r, 0.9, 0, 0.1);
  ribbon(t, before, Math.round(ctx.n * 0.16), PAL.grey, 0.55, r, 0.5, INTRINSIC, 0.2);
  // the area under the law's curve, faint
  while (t.n < ctx.n - 2000) {
    const u = r() * (exp.length - 1);
    const p = exp[Math.floor(u)];
    t.add(p[0], -2.3 + r() * (p[1] + 2.3), (r() - 0.5) * 0.9, 0.025, PAL.ramp + 2, 0, 0.18, INTRINSIC);
  }
  const last = exp[exp.length - 1];
  ctx.anchors.push({ form: ctx.form, x: last[0], y: last[1] + 0.35, z: 0, label: `AY ${story.deciles.ay}`, sub: "the law", kind: "label" });
  while (t.n < ctx.n) t.add((r() - 0.5) * 16, (r() - 0.5) * 8, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

/** A question, and the sections the retriever cites for it. */
const ask: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(59);
  const chat = story.chat;
  const q = text(t, ctx.inp, chat.query, { x: 1.6, y: 1.9, z: 1.2, cols: 34, size: 0.15, adv: 0.085, lh: 0.22, bright: () => 1.5, delayFrom: 0, delaySpan: 0.4 });
  const qx = 1.6;
  const qy = 1.9 - q.height / 2 - 0.15;
  chat.citations.forEach((c, k) => {
    const x = -1.4 + k * 1.55;
    const z = 0.2 - Math.abs(k - 2) * 0.45;
    const y = -0.75 - Math.abs(k - 2) * 0.1;
    const head = c.number ? `s.${c.number} ${c.heading}` : c.heading || c.statute.split("/")[0];
    text(t, ctx.inp, head.slice(0, 40), { x, y: y + 0.85, z, cols: 20, size: 0.085, adv: 0.052, lh: 0.12, bright: () => (c.relevant ? 1.6 : 0.8), delayFrom: 0.35 + k * 0.08, delaySpan: 0.1 });
    text(t, ctx.inp, c.snippet.slice(0, 150), { x, y: y - 0.25, z, cols: 22, size: 0.06, adv: 0.045, lh: 0.1, bright: () => (c.relevant ? 0.85 : 0.4), delayFrom: 0.4 + k * 0.08, delaySpan: 0.2 });
    segment(t, [qx, qy, 1.2], [x, y + 1.15, z], 260, 0.03, c.relevant ? PAL.gain : PAL.paper, c.relevant ? 1.3 : 0.4, r, 0.01, c.relevant ? INTRINSIC : 0, 0.3);
    ctx.anchors.push({ form: ctx.form, x, y: y - 1.35, z, label: `#${c.rank}`, sub: c.relevant ? "the right section" : "another section", kind: "axis", tone: c.relevant ? undefined : "dim" });
  });
  while (t.n < ctx.n) {
    const a = r() * Math.PI * 2;
    const R = 5 + r() * 6;
    t.add(Math.cos(a) * R, (r() - 0.5) * 8, -3 - r() * 5, 0.02, PAL.paper, 0, 0.12);
  }
  return t;
};

const FOCUS = story.focus;
const missedStart = FOCUS.text.indexOf("(ii) in clause (b)");
const missedEnd = missedStart >= 0 ? FOCUS.text.indexOf("\n", missedStart) : -1;

/** The amendment: what the model read (bright) and the clause it missed (vermilion). */
const focus: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(61);
  const span = FOCUS.effects.find((e) => e.span)?.span ?? null;
  const inQuote = (i: number) => !!span && i >= span[0] && i < span[1];
  const missed = (i: number) => missedStart >= 0 && i >= missedStart && i < missedEnd;
  text(t, ctx.inp, FOCUS.text, {
    x: 0,
    y: 0.2,
    z: 1.5,
    cols: 52,
    size: 0.11,
    adv: 0.058,
    lh: 0.16,
    pal: (i) => (missed(i) ? PAL.signal : PAL.paper),
    flags: (i) => (missed(i) ? INTRINSIC : 0),
    bright: (i) => (missed(i) ? 2.3 : inQuote(i) ? 1.5 : 0.55),
    lift: (i) => (missed(i) ? 0.25 : 0),
    delayFrom: 0,
    delaySpan: 0.7,
  });
  while (t.n < ctx.n) t.add((r() - 0.5) * 16, (r() - 0.5) * 8, -4 - r() * 5, 0.02, PAL.paper, 0, 0.12);
  return t;
};

/** The curve the misreading draws: it tears away from the law. */
const torn: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(67);
  axes(t, ctx, r);
  const exp = curvePoints(story.curve.series.expert, yMaxCurve);
  const sys = curvePoints(story.curve.series.system, yMaxCurve);
  ribbon(t, exp, Math.round(ctx.n * 0.3), PAL.paper, 1.25, r, 0.9);
  ribbon(t, sys, Math.round(ctx.n * 0.22), PAL.signal, 1.6, r, 0.7, INTRINSIC, 0.3);
  // fill the tear between the two curves
  const gapIdx: number[] = [];
  story.curve.series.system.forEach((v, i) => {
    if (Math.abs(v - story.curve.series.expert[i]) > 1) gapIdx.push(i);
  });
  while (t.n < ctx.n - 1500 && gapIdx.length) {
    const i = gapIdx[Math.floor(r() * gapIdx.length)];
    const y0 = exp[i][1];
    const y1 = sys[i][1];
    t.add(exp[i][0] + (r() - 0.5) * 0.03, y0 + (y1 - y0) * r(), (r() - 0.5) * 0.6, 0.03, PAL.signal, 0, 0.6, INTRINSIC, 0.5 + r() * 0.3);
  }
  const g = story.curve.largest_gap;
  const gx = -6 + (g.salary / SAL_MAX) * 12;
  const gi = story.curve.salary.indexOf(g.salary);
  ctx.anchors.push({ form: ctx.form, x: gx, y: (gi >= 0 ? sys[gi][1] : 0) + 0.45, z: 0, label: `₹${inr(g.system)} vs ₹${inr(g.expert)}`, sub: `at ₹${lakh(g.salary)}`, kind: "label", tone: "signal" });
  while (t.n < ctx.n) t.add((r() - 0.5) * 16, (r() - 0.5) * 8, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

/** Reforms × readers: a tile per run, lit if it assembled, vermilion if a conclusion flipped. */
const verdict: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(73);
  const { reforms, systems, cells } = story.matrix;
  const cols = systems.length;
  const rows = reforms.length;
  const tw = 0.86;
  const th = 0.36;
  const gx = 0.11;
  const gy = 0.1;
  const W = cols * tw + (cols - 1) * gx;
  const H = rows * th + (rows - 1) * gy;
  const per = Math.floor((ctx.n * 0.9) / (rows * cols));
  reforms.forEach((ref, i) => {
    systems.forEach((sys, j) => {
      const c = cells.find((x) => x.set === ref.id && x.system === sys.id);
      const status = c?.status ?? "missing";
      const flipped = status === "assembled" && (c?.flips ?? 0) > 0;
      const x0 = -W / 2 + j * (tw + gx);
      const y0 = H / 2 - i * (th + gy);
      const z = -Math.pow((x0 + tw / 2) / (W / 2), 2) * 0.8;
      const bright = flipped ? 2 : status === "assembled" ? 1.25 : status === "no conclusion" ? 0.38 : 0.12;
      const pal = flipped ? PAL.signal : status === "assembled" ? PAL.paper : PAL.grey;
      const delay = (i * cols + j) / (rows * cols);
      for (let k = 0; k < per; k++) {
        const u = r();
        const v = r();
        const edge = u < 0.04 || u > 0.96 || v < 0.06 || v > 0.94;
        t.add(x0 + u * tw, y0 - v * th, z + (r() - 0.5) * 0.04, edge ? 0.03 : 0.035, pal, 0, edge ? bright * 1.2 : bright * 0.7, INTRINSIC, delay * 0.8);
      }
      ctx.picks.push({
        form: ctx.form,
        x: x0 + tw / 2,
        y: y0 - th / 2,
        z,
        title: `${reformLabel(ref.id)} · ${SYSTEM_LABEL[sys.id]}`,
        lines:
          status === "assembled"
            ? [`${c?.flips ?? 0} of ${c?.conclusions ?? 0} conclusions flipped`, `revenue error ₹${inr(c?.revenue_error_crore ?? 0)} crore`]
            : status === "no conclusion"
              ? ["did not assemble into a schedule", ...(c?.reasons ?? []).slice(0, 2)]
              : ["not run"],
        href: `/research?set=${ref.id}&inspect=${sys.id}`,
        tone: flipped ? "signal" : undefined,
      });
      if (i === 0) ctx.anchors.push({ form: ctx.form, x: x0 + tw / 2, y: H / 2 + 0.3, z, label: SYSTEM_LABEL[sys.id], kind: "axis" });
    });
    ctx.anchors.push({ form: ctx.form, x: -W / 2 - 0.15, y: H / 2 - i * (th + gy) - th / 2, z: -0.8, label: reformLabel(ref.id), kind: "axis", tone: "dim" });
  });
  while (t.n < ctx.n) t.add((r() - 0.5) * 18, (r() - 0.5) * 9, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

/** Every injected error kind as a column; one spark per injection, vermilion when it flipped a conclusion. */
const faults: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(79);
  const kinds = story.injection.kinds;
  const span = 11;
  const maxRate = Math.max(...kinds.map((k) => k.max_flip_rate), 0.01);
  const colBudget = ctx.n * 0.6;
  const heights = kinds.map((k) => 0.15 + (k.max_flip_rate / maxRate) * 4.6);
  const sumH = heights.reduce((s, x) => s + x, 0);
  const X = (i: number) => 2.2 - span / 2 + (i + 0.5) * (span / kinds.length);
  kinds.forEach((k, i) => {
    const x = X(i);
    const h = heights[i];
    const count = Math.round((colBudget * h) / sumH);
    for (let q = 0; q < count; q++) {
      const y = -2.4 + r() * h;
      const face = r() < 0.7;
      t.add(x + (r() - 0.5) * 0.55, y, face ? 0.3 : (r() - 0.5) * 0.6, 0.035, k.flipping > 0 ? PAL.paper : PAL.grey, 0, k.flipping > 0 ? 0.9 : 0.4, 0, (i / kinds.length) * 0.6 + (y + 2.4) / 12);
    }
    if (i === 0) ctx.anchors.push({ form: ctx.form, x, y: -2.4 + h + 1.2, z: 0.3, label: ERROR_LABEL[k.error] ?? k.error.replace(/_/g, " "), sub: "the strongest error", kind: "label", tone: "signal" });
    ctx.picks.push({
      form: ctx.form,
      x,
      y: -2.4 + h / 2,
      z: 0.3,
      title: ERROR_LABEL[k.error] ?? k.error.replace(/_/g, " "),
      lines: [`${k.flipping} of ${k.injections} injections flipped a conclusion`, `up to ${Math.round(k.max_flip_rate * 100)}% of conclusions`, `revenue error up to ₹${inr(k.max_revenue_error_crore)} crore`],
      tone: k.flipping > 0 ? "signal" : undefined,
    });
  });
  // one spark per injection
  const rows = story.injection.rows;
  const per = Math.max(8, Math.floor((ctx.n * 0.3) / Math.max(1, rows.length)));
  rows.forEach((row, n) => {
    const i = kinds.findIndex((k) => k.error === row.error);
    const x = X(Math.max(0, i)) + gauss(r) * 0.12;
    const y = -2.4 + 0.15 + (row.flip_rate / maxRate) * 4.6 + 0.35 + r() * 0.4;
    const flipped = row.flip_rate > 0;
    for (let q = 0; q < per && t.n < ctx.n; q++) {
      t.add(x + gauss(r) * 0.05, y + gauss(r) * 0.05, 0.3 + gauss(r) * 0.05, 0.04, flipped ? PAL.signal : PAL.grey, 0, flipped ? 2 : 0.5, INTRINSIC, 0.5 + (n / rows.length) * 0.4);
    }
  });
  while (t.n < ctx.n) t.add((r() - 0.5) * 18, (r() - 0.5) * 9, -6 + r() * 3, 0.02, PAL.paper, 0, 0.1);
  return t;
};

/** Quiet: a slow, sparse field. */
const limits: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(83);
  while (t.n < ctx.n) {
    const th = r() * Math.PI * 2;
    const ph = Math.acos(2 * r() - 1);
    const R = 4 + Math.pow(r(), 0.5) * 6;
    t.add(Math.sin(ph) * Math.cos(th) * R * 1.4, Math.cos(ph) * R * 0.6, Math.sin(ph) * Math.sin(th) * R * 0.7 - 6, 0.035, PAL.paper, 0, 0.25 + r() * 0.25);
  }
  return t;
};

/** Everything returns into the prism. */
const gather: Gen = (ctx) => {
  const t = new Targets();
  const r = rng(89);
  const S = 1.6;
  while (t.n < ctx.n) {
    // uniform in an equilateral triangle × depth
    let u = r();
    let v = r();
    if (u + v > 1) {
      u = 1 - u;
      v = 1 - v;
    }
    const ax = 0,
      ay = 1.0;
    const bx = -0.866,
      by = -0.5;
    const cx = 0.866,
      cy = -0.5;
    const x = ax + (bx - ax) * u + (cx - ax) * v;
    const y = ay + (by - ay) * u + (cy - ay) * v;
    t.add(x * S * 0.8, y * S * 0.8, (r() - 0.5) * S * 0.9, 0.035, PAL.paper, 0, 0.55);
  }
  return t;
};

const GENS: Record<(typeof FORMS)[number], Gen> = {
  flow: flowGen(false),
  skyline,
  page,
  tree,
  entities,
  threads,
  graph,
  population,
  curve,
  ask,
  focus,
  torn,
  verdict,
  faults,
  limits,
  gather,
  exit: flowGen(true),
};

/* ── assignment ────────────────────────────────────────────────────────── */

function mortonKeys(xs: ArrayLike<number>, ys: ArrayLike<number>, zs: ArrayLike<number>, idx: number[]) {
  let x0 = Infinity,
    y0 = Infinity,
    z0 = Infinity,
    x1 = -Infinity,
    y1 = -Infinity,
    z1 = -Infinity;
  for (const i of idx) {
    x0 = Math.min(x0, xs[i]);
    x1 = Math.max(x1, xs[i]);
    y0 = Math.min(y0, ys[i]);
    y1 = Math.max(y1, ys[i]);
    z0 = Math.min(z0, zs[i]);
    z1 = Math.max(z1, zs[i]);
  }
  const sx = 1 / Math.max(1e-6, x1 - x0);
  const sy = 1 / Math.max(1e-6, y1 - y0);
  const sz = 1 / Math.max(1e-6, z1 - z0);
  const key = new Map<number, number>();
  for (const i of idx) key.set(i, morton((xs[i] - x0) * sx, (ys[i] - y0) * sy, (zs[i] - z0) * sz));
  return key;
}

function sortByKey(idx: number[], key: Map<number, number>) {
  return idx.sort((a, b) => key.get(a)! - key.get(b)! || a - b);
}

/** Pads or trims a target set to exactly n, never touching priority targets. */
function fit(t: Targets, n: number, seed: number): Targets {
  const r = rng(seed);
  while (t.n > n) {
    let k = Math.floor(r() * t.n);
    for (let tries = 0; t.pri[k] && tries < 50; tries++) k = Math.floor(r() * t.n);
    const last = t.n - 1;
    for (const arr of [t.x, t.y, t.z, t.s, t.pal, t.g, t.b, t.f, t.d, t.cls, t.pri]) {
      arr[k] = arr[last];
      arr.pop();
    }
    t.n--;
  }
  while (t.n < n) {
    const k = Math.floor(r() * t.n);
    t.add(t.x[k] + gauss(r) * 0.02, t.y[k] + gauss(r) * 0.02, t.z[k] + gauss(r) * 0.02, t.s[k], t.pal[k], t.g[k], t.b[k] * 0.4, t.f[k], t.d[k], t.cls[k], 0);
  }
  return t;
}

/** Class of every particle: entity types in proportion to the square root of their counts. */
export function particleClasses(n: number, seed = 5): Uint8Array {
  const w = ENTITY_ORDER.map((l) => Math.sqrt(pnv(`entity@${l}`)));
  const sum = w.reduce((s, x) => s + x, 0);
  const exact = w.map((x) => (n * x) / sum);
  const counts = exact.map(Math.floor);
  let rest = n - counts.reduce((s, x) => s + x, 0);
  exact
    .map((x, i) => [x - Math.floor(x), i] as const)
    .sort((a, b) => b[0] - a[0])
    .forEach(([, i]) => {
      if (rest-- > 0) counts[i]++;
    });
  const out = new Uint8Array(n);
  let k = 0;
  counts.forEach((c, i) => {
    for (let j = 0; j < c; j++) out[k++] = i;
  });
  // seeded shuffle: any prefix is a uniform sample
  const r = rng(seed);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    const tmp = out[i];
    out[i] = out[j];
    out[j] = tmp;
  }
  return out;
}

export async function buildForms(inp: Inputs, n = N_MAX, onProgress?: (f: number) => void): Promise<FormData> {
  const F = FORMS.length;
  const pos = new Float32Array(F * n * 4);
  const meta = new Uint8Array(F * n * 4);
  const aux = new Uint8Array(F * n * 4);
  const classes = particleClasses(n);
  const classCount = ENTITY_ORDER.map((_, c) => classes.reduce((s, x) => s + (x === c ? 1 : 0), 0));
  const anchors: Anchor[] = [];
  const picks: Pick[] = [];
  const counts = ENTITY_ORDER.map((l) => pnv(`entity@${l}`));
  const roots = counts.map(Math.sqrt);
  const maxRoot = Math.max(...roots);
  // spectrum order top → bottom (penalty bends least, actor most)
  const order = ["PENALTY", "THRESHOLD", "RIGHT", "BENEFICIARY", "OBLIGATION", "ACTOR"];
  const beams = ENTITY_ORDER.map((l, c) => {
    const k = order.indexOf(l);
    const a = 0.3 - k * 0.12;
    const zz = (k - 2.5) * 0.04;
    const len = Math.hypot(1, a, zz);
    return { dir: [1 / len, a / len, zz / len] as [number, number, number], width: 0.35 + 0.65 * (roots[c] / maxRoot), label: l, count: pn(l) };
  });
  const all = Array.from({ length: n }, (_, i) => i);
  const core = all.filter((i) => i < N_CORE);
  const extra = all.filter((i) => i >= N_CORE);
  const prev = { x: new Float32Array(n), y: new Float32Array(n), z: new Float32Array(n) };
  for (let f = 0; f < F; f++) {
    const ctx: Ctx = { n, inp, classCount, anchors, picks, form: f, beams };
    const t = fit(GENS[FORMS[f]](ctx), n, 1000 + f);
    const base = f * n * 4;
    const write = (p: number, k: number) => {
      const o = base + p * 4;
      pos[o] = t.x[k];
      pos[o + 1] = t.y[k];
      pos[o + 2] = t.z[k];
      pos[o + 3] = t.s[k];
      meta[o] = t.pal[k];
      meta[o + 1] = t.g[k];
      meta[o + 2] = Math.round(clamp(t.b[k] / 2.55) * 255);
      meta[o + 3] = t.f[k];
      aux[o] = t.d[k] < 0 ? 0 : Math.round(clamp(t.d[k]) * 254) + 1;
    };
    const tIdx = Array.from({ length: t.n }, (_, i) => i);
    const tKey = mortonKeys(t.x, t.y, t.z, tIdx);
    if (FORMS[f] === "flow" || FORMS[f] === "exit") {
      // class-bound: each class flows in its own beam
      for (let c = 0; c < ENTITY_ORDER.length; c++) {
        const P = sortByKey(all.filter((i) => classes[i] === c), f === 0 ? new Map(all.map((i) => [i, i])) : mortonKeys(prev.x, prev.y, prev.z, all.filter((i) => classes[i] === c)));
        const T = tIdx.filter((k) => t.cls[k] === c);
        // flow targets carry no meaningful position: keep a random order
        P.forEach((p, j) => write(p, T[j % T.length]));
      }
    } else {
      // priority targets go to particles every tier draws
      const pri = tIdx.filter((k) => t.pri[k]);
      const rest = tIdx.filter((k) => !t.pri[k]);
      const r = rng(2000 + f);
      for (let i = rest.length - 1; i > 0; i--) {
        const j = Math.floor(r() * (i + 1));
        const tmp = rest[i];
        rest[i] = rest[j];
        rest[j] = tmp;
      }
      const coreT = pri.concat(rest.slice(0, Math.max(0, core.length - pri.length)));
      const extraT = rest.slice(Math.max(0, core.length - pri.length));
      const prevKey = mortonKeys(prev.x, prev.y, prev.z, all);
      const Pc = sortByKey([...core], prevKey);
      const Pe = sortByKey([...extra], prevKey);
      const Tc = sortByKey(coreT, tKey);
      const Te = sortByKey(extraT, tKey);
      Pc.forEach((p, j) => write(p, Tc[j]));
      Pe.forEach((p, j) => write(p, Te[j]));
    }
    for (let p = 0; p < n; p++) {
      const o = base + p * 4;
      if (meta[o + 3] & FLOW) {
        // a flow particle's resting place for matching: along its beam
        const s = pos[o + 2];
        prev.x[p] = -8 + s * 16;
        prev.y[p] = pos[o + 1] * 0.3;
        prev.z[p] = pos[o] * 0.3;
      } else {
        prev.x[p] = pos[o];
        prev.y[p] = pos[o + 1];
        prev.z[p] = pos[o + 2];
      }
    }
    onProgress?.((f + 1) / F);
    await new Promise((res) => setTimeout(res, 0));
  }
  return { n, forms: F, pos, meta, aux, classes, anchors, picks, beams };
}

function pn(label: string) {
  return inr(pnv(`entity@${label}`));
}

/** Every character the forms draw, for the glyph atlas. */
export function charset(): string {
  const parts = [
    streamText,
    story.focus.text,
    story.chat.query,
    ...story.chat.citations.map((c) => c.heading + c.snippet + c.number),
    "§0123456789.,;:()-–—“”‘’\"'/₹",
  ];
  const set = new Set<string>();
  for (const p of parts) for (const ch of p) if (!/\s/.test(ch)) set.add(ch);
  return Array.from(set).slice(0, 255).join("");
}
