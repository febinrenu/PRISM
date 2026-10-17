import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StructuredSection, type SystemRow } from "./StructuredView";

const sets = ["FA2020_new_regime", "FA2025_old_schedule"];
const reform = (set: string, first: boolean, done: boolean, flip: number) => ({
  set, first_complete: first, first_flip_rate: first ? 0 : 1, complete: done, flip_rate: flip, repairs: first ? 0 : 1, review: [],
});
const rows: SystemRow[] = [{
  system: "gpt-oss-120b",
  headline: { assembled: 1, no_flip: 1, reforms: 2 },
  variants: [{
    variant: "tables+schema",
    first_pass: { assembled: 1, no_flip: 1, reforms: 2 },
    repaired: { assembled: 2, no_flip: 1, reforms: 2 },
    repairs_asked: 1, assembled_by_repair: 1, repaired_but_flipped: 1,
    reforms: [reform("FA2020_new_regime", true, true, 0), reform("FA2025_old_schedule", false, true, 0.29)],
  }],
}];
const headline = [
  { set: "FA2020_new_regime", system: "gpt-oss-120b", complete: true, flip_rate: 0 },
  { set: "FA2025_old_schedule", system: "gpt-oss-120b", complete: false, flip_rate: 1 },
];

describe("structured reading", () => {
  const html = renderToStaticMarkup(createElement(StructuredSection, { rows, note: "Designed on these reforms; a held-out check is pending.", headline, sets }));

  it("draws one strip per condition, each tile in its state", () => {
    expect(html).toContain("headline: 1 of 2 reforms keep every conclusion");
    expect(html).toContain("tables+schema first pass: 1 of 2 reforms keep every conclusion");
    expect(html).toContain("tables+schema after repair: 1 of 2 reforms keep every conclusion");
    // after repair, the second reform assembled but flipped: a critical tile
    expect((html.match(/bg-status-critical/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it("says when a repair assembled a wrong reading, and carries the caveat", () => {
    expect(html).toContain("1 repair asked, 1 assembled by it, 1 of those flipped a conclusion");
    expect(html).toContain("held-out check is pending");
  });
});

describe("held-out check", () => {
  it("shows each reader's held-out result and drops the same-reforms tag", () => {
    const heldout = [
      { system: "gpt-oss-20b", condition: "headline", reforms: 5, first_pass: { assembled: 4, no_flip: 4 }, final: { assembled: 4, no_flip: 4 }, repairs: 0, numbers: { fields: 129, in_quote: 106, in_provision: 22, missing: 1 } },
      { system: "gpt-oss-20b", condition: "tables+schema", reforms: 5, first_pass: { assembled: 5, no_flip: 5 }, final: { assembled: 5, no_flip: 5 }, repairs: 0, numbers: { fields: 128, in_quote: 123, in_provision: 5, missing: 0 } },
    ];
    const html = renderToStaticMarkup(createElement(StructuredSection, { rows, note: "fixed before any run", headline, sets, heldout }));
    expect(html).toContain("Five reforms not opened while this was built");
    expect(html).toContain("canonical text");
    expect(html).toContain("96.1%");
    expect(html).not.toContain("same reforms");
  });
});
