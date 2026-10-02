/**
 * PRISM design tokens — the single source of truth for every color in the app.
 *
 * Rules:
 *  - DOM styling → Tailwind classes (the config reads these values as CSS vars)
 *  - SVG / D3 / React Flow / Recharts / canvas export → import `tokens` and use
 *    the hex values directly. CSS `var(...)` strings do NOT work as SVG
 *    presentation attributes or html-to-image backgrounds.
 */

export const tokens = {
  bg: {
    deep: "#040A08",
    base: "#06110D",
    surface: "#0A1612",
    elevated: "#12211B",
    overlay: "#172922",
  },
  border: {
    DEFAULT: "rgba(197, 168, 128, 0.15)",
    light: "rgba(197, 168, 128, 0.30)",
    glow: "rgba(197, 168, 128, 0.60)",
  },
  text: {
    primary: "#F4F1E9",
    secondary: "#C8C5B9",
    muted: "#8E8F87",
    dim: "#5B5C57",
    inverse: "#06110D",
  },
  accent: {
    primary: "#C5A880",
    secondary: "#A58A65",
    bright: "#E8D5B7",
  },
  // Entity colors: `base` for fills/pills, `text` for on-dark foregrounds
  entity: {
    OBLIGATION: { base: "#345C4B", text: "#8CBDA5" },
    PENALTY: { base: "#8B444A", text: "#D88D93" },
    RIGHT: { base: "#597387", text: "#9EB9CC" },
    THRESHOLD: { base: "#C5A880", text: "#E8D5B7" },
    ACTOR: { base: "#62506B", text: "#B8A5C1" },
    BENEFICIARY: { base: "#3F6860", text: "#93C0B7" },
  },
  risk: {
    CRITICAL: { base: "#8B444A", text: "#D88D93" },
    HIGH: { base: "#B07D4C", text: "#DDA96E" },
    MEDIUM: { base: "#597387", text: "#9EB9CC" },
    LOW: { base: "#345C4B", text: "#8CBDA5" },
  },
  status: {
    success: "#8CBDA5",
    error: "#D88D93",
    warning: "#DDA96E",
    info: "#9EB9CC",
  },
  chart: ["#C5A880", "#8CBDA5", "#9EB9CC", "#D88D93", "#B8A5C1", "#93C0B7"],
  // Simulation agent-type series colors
  agent: {
    low_income: "#D88D93",
    middle_income: "#DDA96E",
    high_income: "#C5A880",
    small_business: "#9EB9CC",
    large_corporate: "#8CBDA5",
  },
  diff: {
    added: "#9EB9CC",
    removed: "#D88D93",
    modified: "#DDA96E",
  },
  node: {
    document: "#C5A880",
    chapter: "#A58A65",
    section: "#8E8F87",
    clause: "#C8C5B9",
    entity: "#8CBDA5",
    causal: "#DDA96E",
  },
} as const;

export type EntityLabel = keyof typeof tokens.entity;
export type RiskTier = keyof typeof tokens.risk;
export type AgentType = keyof typeof tokens.agent;

/** Hex + alpha → rgba() string. Accepts #RGB / #RRGGBB. */
export function alpha(hex: string, a: number): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function entityStyle(label: string): { base: string; text: string } {
  return tokens.entity[label as EntityLabel] ?? { base: tokens.accent.secondary, text: tokens.accent.bright };
}

export function riskStyle(tier: string): { base: string; text: string } {
  return tokens.risk[tier as RiskTier] ?? tokens.risk.LOW;
}

function rgbTriple(hex: string): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `${r} ${g} ${b}`;
}

/** CSS custom properties injected into :root by the Tailwind plugin. */
export const cssVariables: Record<string, string> = {
  "--bg-deep": tokens.bg.deep,
  "--bg-base": tokens.bg.base,
  "--bg-surface": tokens.bg.surface,
  "--bg-elevated": tokens.bg.elevated,
  "--bg-overlay": tokens.bg.overlay,
  "--border": tokens.border.DEFAULT,
  "--border-light": tokens.border.light,
  "--border-glow": tokens.border.glow,
  "--text-primary": tokens.text.primary,
  "--text-secondary": tokens.text.secondary,
  "--text-muted": tokens.text.muted,
  "--text-dim": tokens.text.dim,
  "--accent-primary": tokens.accent.primary,
  "--accent-secondary": tokens.accent.secondary,
  "--accent-bright": tokens.accent.bright,
  "--status-success": tokens.status.success,
  "--status-error": tokens.status.error,
  "--status-warning": tokens.status.warning,
  "--status-info": tokens.status.info,
  "--text-inverse": tokens.text.inverse,
  "--entity-obligation": tokens.entity.OBLIGATION.base,
  "--entity-penalty": tokens.entity.PENALTY.base,
  "--entity-right": tokens.entity.RIGHT.base,
  "--entity-threshold": tokens.entity.THRESHOLD.base,
  "--entity-actor": tokens.entity.ACTOR.base,
  "--entity-beneficiary": tokens.entity.BENEFICIARY.base,
  // RGB triples — used by tailwind.config so opacity modifiers
  // (e.g. bg-accent-primary/20) work with token colors.
  "--bg-deep-rgb": rgbTriple(tokens.bg.deep),
  "--bg-base-rgb": rgbTriple(tokens.bg.base),
  "--bg-surface-rgb": rgbTriple(tokens.bg.surface),
  "--bg-elevated-rgb": rgbTriple(tokens.bg.elevated),
  "--bg-overlay-rgb": rgbTriple(tokens.bg.overlay),
  "--text-primary-rgb": rgbTriple(tokens.text.primary),
  "--text-secondary-rgb": rgbTriple(tokens.text.secondary),
  "--text-muted-rgb": rgbTriple(tokens.text.muted),
  "--text-dim-rgb": rgbTriple(tokens.text.dim),
  "--text-inverse-rgb": rgbTriple(tokens.text.inverse),
  "--accent-primary-rgb": rgbTriple(tokens.accent.primary),
  "--accent-secondary-rgb": rgbTriple(tokens.accent.secondary),
  "--accent-bright-rgb": rgbTriple(tokens.accent.bright),
  "--status-success-rgb": rgbTriple(tokens.status.success),
  "--status-error-rgb": rgbTriple(tokens.status.error),
  "--status-warning-rgb": rgbTriple(tokens.status.warning),
  "--status-info-rgb": rgbTriple(tokens.status.info),
  "--entity-obligation-rgb": rgbTriple(tokens.entity.OBLIGATION.base),
  "--entity-penalty-rgb": rgbTriple(tokens.entity.PENALTY.base),
  "--entity-right-rgb": rgbTriple(tokens.entity.RIGHT.base),
  "--entity-threshold-rgb": rgbTriple(tokens.entity.THRESHOLD.base),
  "--entity-actor-rgb": rgbTriple(tokens.entity.ACTOR.base),
  "--entity-beneficiary-rgb": rgbTriple(tokens.entity.BENEFICIARY.base),
};
