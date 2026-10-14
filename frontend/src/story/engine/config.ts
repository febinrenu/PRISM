/**
 * The story's score: the acts (scroll lengths in viewport heights), the
 * particle forms in the order they appear, and the director's keyframe
 * tracks. The scene is a pure function of the scroll position, so scrolling
 * back retraces every frame exactly.
 */

export const ACTS = [
  { id: "hero", len: 240, numeral: "", title: "PRISM" },
  { id: "why", len: 320, numeral: "I", title: "Why" },
  { id: "read", len: 720, numeral: "II", title: "Reading" },
  { id: "run", len: 500, numeral: "III", title: "Running" },
  { id: "case", len: 320, numeral: "IV", title: "One clause" },
  { id: "verdict", len: 320, numeral: "V", title: "The verdict" },
  { id: "faults", len: 280, numeral: "VI", title: "Faults" },
  { id: "limits", len: 260, numeral: "VII", title: "Limits" },
  { id: "end", len: 260, numeral: "", title: "Begin" },
] as const;

export type ActId = (typeof ACTS)[number]["id"];

/** Particle forms, in story order: the director blends form k into k+1. */
export const FORMS = [
  "flow", // 0  the beam of statute text through the prism
  "skyline", // 1  the corpus as stacks of pages
  "page", // 2  one page, readable, in front of the Act
  "tree", // 3  chapter > section > sub-section
  "entities", // 4  a clause with its tagged entities lifted out
  "threads", // 5  condition → consequence
  "graph", // 6  the provenance web
  "population", // 7  taxpayers by income
  "curve", // 8  tax by salary
  "ask", // 9  a question and its cited sections
  "focus", // 10 the amendment, with the missed clause
  "torn", // 11 the curve the misreading draws
  "verdict", // 12 reforms × readers
  "faults", // 13 injected errors
  "limits", // 14 quiet
  "gather", // 15 everything returns into the prism
  "exit", // 16 one clean beam
] as const;
export type FormId = (typeof FORMS)[number];
export const F = Object.fromEntries(FORMS.map((f, i) => [f, i])) as Record<FormId, number>;

/** Where the light comes from: far behind and to the left, so the beam never crosses the copy. */
export const BEAM_SOURCE: [number, number, number] = [-8, 1.6, -30];

export const ACT_START: Record<ActId, number> = (() => {
  let y = 0;
  const out = {} as Record<ActId, number>;
  for (const a of ACTS) {
    out[a.id] = y;
    y += a.len;
  }
  return out;
})();

export const STORY_LEN = ACTS.reduce((s, a) => s + a.len, 0);
const LEN = Object.fromEntries(ACTS.map((a) => [a.id, a.len])) as Record<ActId, number>;

/**
 * A position in the story, in viewport heights from the top: `q` is the
 * act's progress through its sticky stage (0 when the stage pins, 1 when it
 * releases; up to about 1.4 while the next act scrolls in).
 */
export const at = (act: ActId, q: number) => ACT_START[act] + q * (LEN[act] - 100);

/** Progress of an act's sticky stage for a scroll position in vh. */
export const actProgress = (act: ActId, y: number) => (y - ACT_START[act]) / (LEN[act] - 100);

/* ── the director: every animated scene value, keyed along the scroll ───── */

export type Ease = "smooth" | "linear" | "in" | "out";
export type Key = [number, number, Ease?];

export interface Director {
  form: number;
  turb: number;
  chroma: number;
  gate: number;
  exposure: number;
  prism: number;
  prismX: number;
  prismY: number;
  prismZ: number;
  prismSpin: number;
  beam: number;
  flow: number;
  cam: number;
  focus: number;
  aperture: number;
  bloom: number;
  vignette: number;
  shiftX: number;
  wipe: number;
}

/** Each form is held over a stretch of scroll; transitions fill the gaps. */
export const HOLDS: [FormId, number, number][] = [
  ["flow", 0, at("hero", 0.95)],
  ["skyline", at("why", 0.12), at("why", 0.95)],
  ["page", at("read", 0.03), at("read", 0.16)],
  ["tree", at("read", 0.24), at("read", 0.36)],
  ["entities", at("read", 0.44), at("read", 0.56)],
  ["threads", at("read", 0.64), at("read", 0.76)],
  ["graph", at("read", 0.84), at("read", 1.02)],
  ["population", at("run", 0.06), at("run", 0.27)],
  ["curve", at("run", 0.38), at("run", 0.58)],
  ["ask", at("run", 0.7), at("run", 1.0)],
  ["focus", at("case", 0.05), at("case", 0.45)],
  ["torn", at("case", 0.6), at("case", 1.0)],
  ["verdict", at("verdict", 0.08), at("verdict", 1.0)],
  ["faults", at("faults", 0.1), at("faults", 1.0)],
  ["limits", at("limits", 0.12), at("limits", 0.95)],
  ["gather", at("end", -0.05), at("end", 0.2)],
  ["exit", at("end", 0.42), at("end", 1.4)],
];

/**
 * The tracks. Between keys values ease (smoothstep by default); before the
 * first and after the last they hold. Form transitions sit across act
 * boundaries so the particles travel while the copy changes.
 */
export const TRACKS: Record<keyof Director, Key[]> = {
  form: HOLDS.flatMap(([f, a, b]) => [[a, F[f], "linear"], [b, F[f], "linear"]] as Key[]),
  // transition turbulence comes from the form envelope; this scales it
  turb: [
    [0, 1],
    [at("verdict", 0), 1],
    [at("verdict", 0.1), 0.6],
    [at("limits", 0), 0.6],
    [at("limits", 0.2), 1.4],
    [at("end", 0.5), 1],
  ],
  // global colour: the spectrum outside the gate
  chroma: [
    [0, 0],
    [at("hero", 1.1), 0],
    [at("why", 0.08), 0],
    [at("run", 0), 0],
    [at("run", 0.06), 1],
    [at("limits", 0.1), 1],
    [at("limits", 0.4), 0.25],
    [at("end", 0.1), 0.25],
    [at("end", 0.3), 0],
  ],
  // strength of the prism gate (colour past the prism plane)
  gate: [
    [0, 1],
    [at("hero", 1), 1],
    [at("why", 0.08), 0],
    [at("read", 0.36), 0],
    [at("read", 0.4), 1],
    [at("read", 0.84), 1],
    [at("run", 0.05), 1],
    [at("end", 0.3), 1],
  ],
  exposure: [
    [0, 1],
    [at("why", 0.1), 0.9],
    [at("read", 0.03), 1.05],
    [at("read", 0.84), 0.9],
    [at("run", 0.06), 1],
    [at("limits", 0.1), 1],
    [at("limits", 0.35), 0.45],
    [at("end", 0), 0.45],
    [at("end", 0.25), 1],
  ],
  prism: [
    [0, 1],
    [at("hero", 1.05), 1],
    [at("why", 0.15), 0],
    [at("read", 0.37), 0],
    [at("read", 0.42), 1],
    [at("read", 0.55), 1],
    [at("read", 0.62), 0],
    [at("end", -0.15), 0],
    [at("end", 0.05), 1],
  ],
  prismX: [
    [0, 0],
    [at("hero", 1.05), 0],
    [at("why", 0.15), 0],
    [at("read", 0.37), 4.2],
    [at("read", 0.42), 3.6],
    [at("read", 0.54), -3.8, "linear"],
    [at("read", 0.62), -5],
    [at("end", -0.15), 0],
  ],
  prismY: [
    [0, 0],
    [at("hero", 1.05), 0.3],
    [at("why", 0.15), 4],
    [at("read", 0.37), 0.1],
    [at("read", 0.62), 0.1],
    [at("end", -0.15), 0],
  ],
  prismZ: [
    [0, 0],
    [at("read", 0.37), 1.2],
    [at("read", 0.62), 1.2],
    [at("end", -0.15), 0],
  ],
  prismSpin: [
    [0, 0],
    [at("hero", 1.2), 0.6],
    [at("why", 0.2), 1.2],
    [at("read", 0.42), 0],
    [at("read", 0.6), 0.5],
    [at("end", 0), 0],
    [at("end", 1.4), 0.4],
  ],
  beam: [
    [0, 1],
    [at("hero", 1.0), 1],
    [at("why", 0.1), 0],
    [at("end", 0.35), 0],
    [at("end", 0.55), 1],
  ],
  flow: [[0, 1]],
  // camera rail parameter: one keyframe per stop (see camera rail)
  // camera rail: two poses per held form (see gl/rail.ts), eased between
  cam: HOLDS.flatMap(([, a, b], k) => [[a, 2 * k], [b, 2 * k + 1, "linear"]] as Key[]),
  focus: [[0, 10]],
  aperture: [
    [0, 0],
    [at("read", 0), 0],
    [at("read", 0.05), 0.045],
    [at("read", 0.76), 0.045],
    [at("read", 0.84), 0.015],
    [at("run", 0.06), 0.02],
    [at("case", 0.05), 0.04],
    [at("case", 0.6), 0.015],
    [at("verdict", 0.1), 0.01],
    [at("end", 0), 0.03],
    [at("end", 0.4), 0],
  ],
  bloom: [
    [0, 1],
    [at("limits", 0.1), 1],
    [at("limits", 0.35), 0.45],
    [at("end", 0.1), 0.45],
    [at("end", 0.35), 0.6],
  ],
  vignette: [[0, 0.7]],
  // fraction of the viewport width the subject is pushed away from the copy
  shiftX: [
    [0, -0.14],
    [at("hero", 0.6), -0.14],
    [at("why", 0.15), -0.1],
    [at("why", 0.95), -0.1],
    [at("read", 0.05), -0.16],
    [at("read", 1.02), -0.16],
    [at("run", 0.06), -0.14],
    [at("run", 1.0), -0.14],
    [at("case", 0.06), -0.16],
    [at("case", 1.0), -0.16],
    [at("verdict", 0.1), 0.17],
    [at("verdict", 1.0), 0.17],
    [at("faults", 0.12), -0.12],
    [at("faults", 1.0), -0.12],
    [at("limits", 0.14), 0],
    [at("end", 1.4), 0],
  ],
  wipe: [[0, 0]],
};

const easeFn: Record<Ease, (t: number) => number> = {
  linear: (t) => t,
  smooth: (t) => t * t * (3 - 2 * t),
  in: (t) => t * t * t,
  out: (t) => 1 - Math.pow(1 - t, 3),
};

export function sample(keys: Key[], y: number): number {
  if (y <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [y1, v1, e] = keys[i];
    if (y <= y1) {
      const [y0, v0] = keys[i - 1];
      const t = y1 === y0 ? 1 : (y - y0) / (y1 - y0);
      return v0 + (v1 - v0) * easeFn[e ?? "smooth"](t);
    }
  }
  return keys[keys.length - 1][1];
}

/** Every director value at scroll position y (vh). Writes into `out`. */
export function direct(y: number, out: Director): Director {
  for (const k in TRACKS) (out as unknown as Record<string, number>)[k] = sample(TRACKS[k as keyof Director], y);
  return out;
}

export const newDirector = (): Director => direct(0, {} as Director);
