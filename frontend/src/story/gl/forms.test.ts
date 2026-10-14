import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { FORMS } from "../engine/config";
import { N_CORE, N_MAX, TEXT, buildForms, charset, particleClasses } from "./forms";

const json = (f: string) => JSON.parse(readFileSync(new URL(`../../../public/story/${f}.json`, import.meta.url), "utf8"));
const chars = charset();
const inputs = () => ({
  population: json("population"),
  constellation: json("constellation"),
  graph: json("pipeline"),
  glyph: (ch: string) => chars.indexOf(ch) + 1,
});

describe("particle forms", () => {
  it("are deterministic, complete and finite", async () => {
    const a = await buildForms(inputs());
    const b = await buildForms(inputs());
    expect(a.forms).toBe(FORMS.length);
    expect(a.pos.length).toBe(FORMS.length * N_MAX * 4);
    expect(Buffer.from(a.pos.buffer).equals(Buffer.from(b.pos.buffer))).toBe(true);
    expect(Buffer.from(a.meta.buffer).equals(Buffer.from(b.meta.buffer))).toBe(true);
    for (let i = 0; i < a.pos.length; i++) if (!Number.isFinite(a.pos[i])) throw new Error(`non-finite at ${i}`);
    // readable text lives in the prefix every tier draws
    for (let f = 0; f < a.forms; f++) {
      for (let p = N_CORE; p < N_MAX; p++) {
        const o = (f * N_MAX + p) * 4;
        if (a.meta[o + 3] & TEXT) throw new Error(`text glyph outside the core prefix in form ${FORMS[f]}`);
      }
    }
    expect(a.anchors.length).toBeGreaterThan(20);
    expect(a.picks.length).toBeGreaterThan(60);
  }, 60000);

  it("give every prefix the same class mix", () => {
    const c = particleClasses(N_MAX);
    const share = (n: number, k: number) => c.subarray(0, n).filter((x) => x === k).length / n;
    for (let k = 0; k < 6; k++) expect(Math.abs(share(N_CORE, k) - share(N_MAX, k))).toBeLessThan(0.02);
  });
});
