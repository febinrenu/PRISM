/**
 * PRISM design tokens: the single source of truth for colour, type, space,
 * radius, depth and motion timing.
 *
 * Identity: ink, paper and one signal colour (vermilion). Vermilion marks
 * where a machine reading departs from the law, and primary actions. It is
 * not decoration.
 *
 * DOM styling → Tailwind classes (tailwind.config.ts reads these as CSS
 * variables). SVG / D3 / React Flow / Recharts / canvas / WebGL → import
 * `tokens` and use the hex values: `var(...)` does not work in SVG
 * presentation attributes, canvas or html-to-image backgrounds.
 *
 * The categorical palette (`chart`, entity hues) was checked with the dataviz
 * palette validator: lightness band, chroma floor, adjacent CVD separation
 * (worst ΔE 12.0) and 3:1 contrast against the ink surface. Entities always
 * carry a text label, so identity is never colour alone.
 */

export const ink = {
  950: "#08090A",
  900: "#0C0D0E",
  850: "#111214",
  800: "#17181B",
  750: "#1E1F23",
  700: "#2A2B30",
  600: "#3A3B41",
  500: "#5A5B62",
} as const;

export const paper = {
  50: "#F8F5EF",
  100: "#F1EDE4",
  200: "#E6E0D3",
  300: "#D5CDBC",
  400: "#B9B09C",
} as const;

export const signal = {
  200: "#FFC3AD",
  300: "#FF8A66",
  400: "#FF6A3D",
  500: "#FF4F1F",
  600: "#E23C0E",
  /** Vermilion for text on paper: #FF4F1F on paper is only 2.8:1. */
  ink: "#B8320F",
} as const;

/** Categorical hues on ink (validated) and their on-ink text tints. */
const hue = {
  blue: { base: "#4F7FE6", text: "#9DB8F5", paper: "#2F62C8" },
  teal: { base: "#1C9C82", text: "#72D1BC", paper: "#00876A" },
  violet: { base: "#8D6BE3", text: "#BFAAF3", paper: "#6E4CC9" },
  magenta: { base: "#D24F98", text: "#EE95C6", paper: "#B83A7E" },
  ochre: { base: "#B8852A", text: "#E3C07A", paper: "#94650F" },
  cyan: { base: "#2C98BF", text: "#80C9E3", paper: "#0479AD" },
} as const;

export const tokens = {
  ink,
  paper,
  signal,
  hue,
  bg: {
    deep: ink[950],
    base: ink[900],
    surface: ink[850],
    elevated: ink[800],
    overlay: ink[750],
  },
  border: {
    DEFAULT: "rgba(241, 237, 228, 0.10)",
    light: "rgba(241, 237, 228, 0.18)",
    glow: "rgba(241, 237, 228, 0.34)",
  },
  text: {
    primary: paper[100],
    secondary: "#C4BFB3",
    muted: "#9A958B",
    dim: "#8A857B",
    inverse: ink[900],
  },
  accent: {
    primary: signal[500],
    secondary: signal[600],
    bright: signal[300],
  },
  entity: {
    OBLIGATION: { base: hue.blue.base, text: hue.blue.text },
    PENALTY: { base: hue.magenta.base, text: hue.magenta.text },
    RIGHT: { base: hue.teal.base, text: hue.teal.text },
    THRESHOLD: { base: hue.ochre.base, text: hue.ochre.text },
    ACTOR: { base: hue.violet.base, text: hue.violet.text },
    BENEFICIARY: { base: hue.cyan.base, text: hue.cyan.text },
  },
  risk: {
    CRITICAL: { base: "#E03A5C", text: "#F2899E" },
    HIGH: { base: hue.ochre.base, text: hue.ochre.text },
    MEDIUM: { base: hue.blue.base, text: hue.blue.text },
    LOW: { base: hue.teal.base, text: hue.teal.text },
  },
  /** Reserved for state; never reused as a series colour. */
  status: {
    success: "#5CC394",
    error: "#F2899E",
    warning: "#E3B25F",
    info: "#9DB8F5",
    critical: "#E03A5C",
  },
  /** Fixed categorical order; never cycled (adjacent pairs validated). */
  chart: [hue.blue.base, hue.teal.base, hue.violet.base, hue.magenta.base, hue.ochre.base, hue.cyan.base],
  chartPaper: [hue.blue.paper, hue.teal.paper, hue.violet.paper, hue.magenta.paper, hue.ochre.paper, hue.cyan.paper],
  /** Diverging: blue ↔ neutral grey ↔ magenta. */
  diverging: { neg: "#3E6FD8", mid: "#8A8780", pos: "#C8448C" },
  /** Sequential magnitude (one hue, dark → light on ink). */
  sequential: ["#1F2C4A", "#29427A", "#3559A8", "#4F7FE6", "#7FA2EE", "#B1C7F6"],
  agent: {
    low_income: hue.magenta.base,
    middle_income: hue.ochre.base,
    high_income: hue.blue.base,
    small_business: hue.teal.base,
    large_corporate: hue.violet.base,
  },
  diff: {
    added: hue.teal.text,
    removed: "#F2899E",
    modified: hue.ochre.text,
  },
  node: {
    document: paper[100],
    chapter: "#C4BFB3",
    section: "#9A958B",
    clause: hue.blue.base,
    entity: hue.teal.base,
    causal: hue.ochre.base,
    effect: signal[500],
  },
  /** Type scale in px (minimum 12). */
  type: {
    micro: 12,
    small: 13,
    body: 15,
    lead: 18,
    title: 24,
    headline: 40,
    display: 88,
  },
  radius: { xs: 2, sm: 4, md: 8, lg: 14, xl: 22 },
  z: { base: 0, raised: 10, sticky: 30, nav: 40, overlay: 60, modal: 70, toast: 80, curtain: 90 },
} as const;

export type EntityLabel = keyof typeof tokens.entity;
export type RiskTier = keyof typeof tokens.risk;
export type AgentType = keyof typeof tokens.agent;

function rgbParts(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}

/** Hex + alpha → rgba() string. Accepts #RGB / #RRGGBB. */
export function alpha(hex: string, a: number): string {
  const [r, g, b] = rgbParts(hex);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function entityStyle(label: string): { base: string; text: string } {
  return tokens.entity[label as EntityLabel] ?? { base: tokens.ink[600], text: tokens.text.secondary };
}

export function riskStyle(tier: string): { base: string; text: string } {
  return tokens.risk[tier as RiskTier] ?? tokens.risk.LOW;
}

function rgbTriple(hex: string): string {
  return rgbParts(hex).join(" ");
}

const colourVars: Record<string, string> = {
  "bg-deep": tokens.bg.deep,
  "bg-base": tokens.bg.base,
  "bg-surface": tokens.bg.surface,
  "bg-elevated": tokens.bg.elevated,
  "bg-overlay": tokens.bg.overlay,
  "text-primary": tokens.text.primary,
  "text-secondary": tokens.text.secondary,
  "text-muted": tokens.text.muted,
  "text-dim": tokens.text.dim,
  "text-inverse": tokens.text.inverse,
  "accent-primary": tokens.accent.primary,
  "accent-secondary": tokens.accent.secondary,
  "accent-bright": tokens.accent.bright,
  "status-success": tokens.status.success,
  "status-error": tokens.status.error,
  "status-warning": tokens.status.warning,
  "status-info": tokens.status.info,
  "status-critical": tokens.status.critical,
  "entity-obligation": tokens.entity.OBLIGATION.base,
  "entity-penalty": tokens.entity.PENALTY.base,
  "entity-right": tokens.entity.RIGHT.base,
  "entity-threshold": tokens.entity.THRESHOLD.base,
  "entity-actor": tokens.entity.ACTOR.base,
  "entity-beneficiary": tokens.entity.BENEFICIARY.base,
  "signal": signal[500],
  "signal-soft": signal[300],
  "signal-deep": signal[600],
  "signal-ink": signal.ink,
  "paper": paper[100],
  // the inverted fill (selected pills, primary-contrast buttons, marks that
  // read as "the law"): paper on ink, ink on paper
  "contrast": paper[100],
  "on-contrast": ink[900],
  "paper-50": paper[50],
  "paper-200": paper[200],
  "paper-300": paper[300],
  "paper-400": paper[400],
  "ink": ink[900],
  "ink-950": ink[950],
  "ink-800": ink[800],
  "ink-700": ink[700],
  "ink-600": ink[600],
  "ink-500": ink[500],
  // text tints and graph node colours that change with the theme
  ...Object.fromEntries(Object.entries(tokens.entity).map(([k, v]) => [`entity-${k.toLowerCase()}-text`, v.text])),
  ...Object.fromEntries(Object.entries(tokens.risk).map(([k, v]) => [`risk-${k.toLowerCase()}-text`, v.text])),
  "node-document": tokens.node.document,
  "node-chapter": tokens.node.chapter,
  "node-section": tokens.node.section,
};

/**
 * The light theme: the same roles on paper. Each value was checked for WCAG AA
 * (4.5:1) against every light surface. Vermilion stays the button fill (ink on
 * it is 5.7:1); vermilion text uses signal-ink, which passes on paper.
 */
export const light = {
  bg: { deep: "#E8E3D7", base: "#F3EFE7", surface: "#FAF8F3", elevated: "#FFFFFF", overlay: "#FFFFFF" },
  text: { primary: "#121314", secondary: "#34353A", muted: "#55555A", dim: "#66645F", inverse: paper[100] },
  border: { DEFAULT: "rgba(18, 19, 20, 0.12)", light: "rgba(18, 19, 20, 0.2)", glow: "rgba(18, 19, 20, 0.36)" },
  accent: { primary: "#C2410C", secondary: "#A8360B", bright: "#B23A0B" },
  status: { success: "#1A6E47", error: "#B0213A", warning: "#7D550A", info: "#2A5BBF", critical: "#B81C3F" },
} as const;

export type ThemeName = "dark" | "light";

/** Theme-dependent token groups for code that draws with hex (SVG, canvas, charts). */
export function themedTokens(theme: ThemeName) {
  if (theme === "dark") return tokens;
  return {
    ...tokens,
    bg: light.bg,
    text: light.text,
    border: light.border,
    accent: light.accent,
    status: light.status,
    node: { ...tokens.node, document: light.text.primary, chapter: light.text.secondary, section: light.text.muted },
  } as unknown as typeof tokens;
}

const lightColourVars: Record<string, string> = {
  "bg-deep": light.bg.deep,
  "bg-base": light.bg.base,
  "bg-surface": light.bg.surface,
  "bg-elevated": light.bg.elevated,
  "bg-overlay": light.bg.overlay,
  "text-primary": light.text.primary,
  "text-secondary": light.text.secondary,
  "text-muted": light.text.muted,
  "text-dim": light.text.dim,
  "text-inverse": light.text.inverse,
  "accent-primary": light.accent.primary,
  "accent-secondary": light.accent.secondary,
  "accent-bright": light.accent.bright,
  "status-success": light.status.success,
  "status-error": light.status.error,
  "status-warning": light.status.warning,
  "status-info": light.status.info,
  "status-critical": light.status.critical,
  // vermilion as text on paper; the fill (bg-signal) keeps --signal
  "signal-soft": signal.ink,
  "entity-obligation-text": hue.blue.paper,
  "entity-penalty-text": hue.magenta.paper,
  "entity-right-text": hue.teal.paper,
  "entity-threshold-text": hue.ochre.paper,
  "entity-actor-text": hue.violet.paper,
  "entity-beneficiary-text": hue.cyan.paper,
  "risk-critical-text": "#B81C3F",
  "risk-high-text": hue.ochre.paper,
  "risk-medium-text": hue.blue.paper,
  "risk-low-text": hue.teal.paper,
  "contrast": "#121314",
  "on-contrast": paper[100],
  "node-document": "#121314",
  "node-chapter": "#34353A",
  "node-section": "#55555A",
  // mid inks serve as neutral tracks, tiles and hatching: lighten them on paper
  // (ink-900, used for text on paper and on vermilion, stays ink)
  "ink-800": "#E6E1D5",
  "ink-700": "#D8D2C5",
  "ink-600": "#BEB7A8",
  "ink-500": "#8F8A80",
};

/** CSS custom properties for the light theme (applied to the app's body, never the story). */
export const lightCssVariables: Record<string, string> = {
  ...Object.fromEntries(Object.entries(lightColourVars).map(([k, v]) => [`--${k}`, v])),
  ...Object.fromEntries(Object.entries(lightColourVars).map(([k, v]) => [`--${k}-rgb`, rgbTriple(v)])),
  "--border": light.border.DEFAULT,
  "--border-light": light.border.light,
  "--border-glow": light.border.glow,
};

/** CSS custom properties injected into :root by the Tailwind plugin. */
export const cssVariables: Record<string, string> = {
  ...Object.fromEntries(Object.entries(colourVars).map(([k, v]) => [`--${k}`, v])),
  // RGB triples so Tailwind opacity modifiers (bg-signal/20) work.
  ...Object.fromEntries(Object.entries(colourVars).map(([k, v]) => [`--${k}-rgb`, rgbTriple(v)])),
  "--border": tokens.border.DEFAULT,
  "--border-light": tokens.border.light,
  "--border-glow": tokens.border.glow,
};
