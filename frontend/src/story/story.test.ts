import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import core from "@/content/story.core.json";
import { reformLabel } from "@/lib/labels";

const numbers = (core as { numbers: Record<string, { value: string; source: { file: string; key: string } }> }).numbers;

describe("story snapshot", () => {
  it("has every paper number the story cites", () => {
    const src = ["acts.tsx", "ui.tsx"].map((f) => readFileSync(new URL(`./${f}`, import.meta.url), "utf8")).join("\n");
    const keys = Array.from(src.matchAll(/<Num k="([^"]+)"/g)).map((m) => m[1]);
    expect(keys.length).toBeGreaterThan(10);
    for (const k of keys) expect(numbers[k], k).toBeDefined();
  });

  it("sources every number to the paper's generated file", () => {
    for (const [k, v] of Object.entries(numbers)) {
      expect(v.source).toEqual({ file: "paper/tables/numbers.tex", key: k });
    }
  });

  it("keeps the focus case's quoted span inside the provision text", () => {
    const f = (core as any).focus;
    for (const e of f.effects) if (e.span) expect(f.text.slice(e.span[0], e.span[1])).toBe(e.quote);
  });
});

describe("labels", () => {
  it("names reforms readably", () => {
    expect(reformLabel("FA2024N2_budget")).toBe("FA 2024 (No. 2) · budget");
    expect(reformLabel("FA2025_rebate_12L")).toBe("FA 2025 · rebate ₹12L");
    expect(reformLabel("ITA2025_new_act")).toBe("ITA 2025 · new act");
  });
});
