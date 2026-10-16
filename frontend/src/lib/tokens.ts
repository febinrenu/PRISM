/**
 * The app's view of the design tokens (source of truth: src/design/tokens.ts).
 *
 * Roles that change with the light/dark theme (surfaces, text, borders,
 * accents, status, entity and risk text tints, graph node colours) are CSS
 * variable references here, so SVG, charts and inline styles follow the
 * theme without re-rendering. `alpha()` understands them. Code that needs a
 * literal colour (canvas, WebGL, image export) uses `useTokens()` from
 * @/design/theme or `cssHex()` instead. The landing story imports
 * @/design/tokens directly and keeps raw hex.
 */
import { alpha as alphaHex, tokens as base } from "@/design/tokens";

const v = (name: string) => `var(--${name})`;

export const tokens = {
  ...base,
  bg: { deep: v("bg-deep"), base: v("bg-base"), surface: v("bg-surface"), elevated: v("bg-elevated"), overlay: v("bg-overlay") },
  text: { primary: v("text-primary"), secondary: v("text-secondary"), muted: v("text-muted"), dim: v("text-dim"), inverse: v("text-inverse") },
  border: { DEFAULT: v("border"), light: v("border-light"), glow: v("border-glow") },
  accent: { primary: v("accent-primary"), secondary: v("accent-secondary"), bright: v("accent-bright") },
  status: {
    success: v("status-success"),
    error: v("status-error"),
    warning: v("status-warning"),
    info: v("status-info"),
    critical: v("status-critical"),
  },
  entity: Object.fromEntries(
    Object.entries(base.entity).map(([k, e]) => [k, { base: e.base, text: v(`entity-${k.toLowerCase()}-text`) }])
  ) as unknown as typeof base.entity,
  risk: Object.fromEntries(
    Object.entries(base.risk).map(([k, e]) => [k, { base: e.base, text: v(`risk-${k.toLowerCase()}-text`) }])
  ) as unknown as typeof base.risk,
  node: { ...base.node, document: v("node-document"), chapter: v("node-chapter"), section: v("node-section") },
} as unknown as typeof base;

/** Colour + alpha: hex (#RGB/#RRGGBB) or a theme variable reference. */
export function alpha(color: string, a: number): string {
  const m = /^var\(--([\w-]+)\)$/.exec(color);
  if (m) {
    // borders are already rgba; tint them by stacking opacity instead
    if (m[1].startsWith("border")) return `color-mix(in srgb, ${color} ${Math.round(a * 100)}%, transparent)`;
    return `rgb(var(--${m[1]}-rgb) / ${a})`;
  }
  return alphaHex(color, a);
}

export function entityStyle(label: string): { base: string; text: string } {
  return (tokens.entity as Record<string, { base: string; text: string }>)[label] ?? { base: base.ink[600], text: tokens.text.secondary };
}

export function riskStyle(tier: string): { base: string; text: string } {
  return (tokens.risk as Record<string, { base: string; text: string }>)[tier] ?? tokens.risk.LOW;
}

/** The current value of a theme variable as a literal colour (for canvas and image export). */
export function cssHex(name: string): string {
  if (typeof document === "undefined") return "";
  return getComputedStyle(document.body).getPropertyValue(`--${name}`).trim();
}

export { cssVariables } from "@/design/tokens";
export type { EntityLabel, RiskTier, AgentType } from "@/design/tokens";
