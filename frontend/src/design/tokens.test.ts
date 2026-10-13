import { describe, expect, it } from "vitest";
import { cssVariables, tokens } from "./tokens";

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const [r, g, b] = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a: string, b: string) => {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

describe("tokens", () => {
  it("body text roles meet WCAG AA on the ink surfaces", () => {
    for (const bg of [tokens.bg.base, tokens.bg.surface, tokens.bg.elevated]) {
      expect(contrast(tokens.text.primary, bg)).toBeGreaterThanOrEqual(7);
      expect(contrast(tokens.text.secondary, bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tokens.text.muted, bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tokens.text.dim, bg)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("vermilion text on paper uses the ink variant", () => {
    expect(contrast(tokens.signal[500], tokens.paper[100])).toBeLessThan(3);
    expect(contrast(tokens.signal.ink, tokens.paper[100])).toBeGreaterThanOrEqual(4.5);
  });

  it("primary buttons (ink on vermilion) are readable", () => {
    expect(contrast(tokens.ink[900], tokens.signal[500])).toBeGreaterThanOrEqual(4.5);
  });

  it("every colour variable has an rgb triple for opacity modifiers", () => {
    for (const k of Object.keys(cssVariables)) {
      if (k.endsWith("-rgb") || k.startsWith("--border")) continue;
      expect(cssVariables[`${k}-rgb`]).toMatch(/^\d+ \d+ \d+$/);
    }
  });
});
