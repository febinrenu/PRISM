import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { band, rupees, ScheduleCard, type Schedule } from "./RatesTab";

const row = (lower: number | null, upper: number | null, rate: number | null, text = "") => ({ label: "", text, lower, upper, rate });

describe("rate schedules", () => {
  it("writes bands as the law reads them", () => {
    expect(band(row(0, 400000, 0))).toBe("up to ₹4 lakh");
    expect(band(row(400000, 800000, 0.05))).toBe("₹4 lakh – ₹8 lakh");
    expect(band(row(2400000, null, 0.3))).toBe("above ₹24 lakh");
    expect(rupees(20000000)).toBe("₹2 crore");
    expect(rupees(12500)).toBe("₹12,500");
  });

  it("shows a complete schedule and a schedule that needs review", () => {
    const ok: Schedule = {
      page: 25, kind: "boxed", heading: "(iii) for any previous year …", assessment_year: "2026-27",
      rows: [row(0, 400000, 0, "1. Upto Rs. 4,00,000 | Nil"), row(400000, null, 0.05, "2. Above Rs. 4,00,000 | 5 per cent.")],
      check: { ok: true, reason: null },
    };
    const html = renderToStaticMarkup(createElement(ScheduleCard, { s: ok }));
    expect(html).toContain("p.25 · AY 2026-27");
    expect(html).toContain("complete schedule");
    expect(html).toContain("1. Upto Rs. 4,00,000 | Nil");
    expect(html).toContain("5%");
    const bad = renderToStaticMarkup(createElement(ScheduleCard, { s: { ...ok, check: { ok: false, reason: "no open top band" } } }));
    expect(bad).toContain("needs review: no open top band");
  });
});
