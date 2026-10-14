import { describe, expect, it } from "vitest";
import { ACTS, FORMS, HOLDS, STORY_LEN, TRACKS, actProgress, at, direct, newDirector, sample } from "./config";

describe("the story's score", () => {
  it("holds every form once, in order, along the scroll", () => {
    expect(HOLDS.map(([f]) => f)).toEqual([...FORMS]);
    for (let i = 0; i < HOLDS.length; i++) {
      expect(HOLDS[i][1]).toBeLessThanOrEqual(HOLDS[i][2]);
      if (i > 0) expect(HOLDS[i][1]).toBeGreaterThan(HOLDS[i - 1][2]);
    }
  });

  it("keeps every track's keys in scroll order", () => {
    for (const [name, keys] of Object.entries(TRACKS)) {
      for (let i = 1; i < keys.length; i++) expect(keys[i][0], name).toBeGreaterThanOrEqual(keys[i - 1][0]);
    }
  });

  it("is a pure function of the scroll position", () => {
    const a = direct(1234.5, newDirector());
    const b = direct(1234.5, newDirector());
    expect(a).toEqual(b);
    for (let y = 0; y < STORY_LEN; y += 37) {
      const d = direct(y, newDirector());
      for (const v of Object.values(d)) expect(Number.isFinite(v)).toBe(true);
      expect(d.form).toBeGreaterThanOrEqual(0);
      expect(d.form).toBeLessThanOrEqual(FORMS.length - 1);
    }
  });

  it("maps act progress both ways", () => {
    for (const a of ACTS) expect(actProgress(a.id, at(a.id, 0.4))).toBeCloseTo(0.4);
    expect(sample([[0, 1], [10, 3, "linear"]], 5)).toBeCloseTo(2);
  });
});
