import { describe, expect, it } from "vitest";
import { count, crore, inr, pct, signedIndex, signedPct, slabTax } from "@/components/policy/format";

describe("policy number formatting", () => {
  it("writes rupees as the law does", () => {
    expect(inr(1200000)).toBe("₹12 lakh");
    expect(inr(24000000)).toBe("₹2.4 crore");
    expect(inr(75000)).toBe("₹75,000");
    expect(inr(-450000)).toBe("−₹4.5 lakh");
  });

  it("writes aggregates in crore and lakh crore, signed on request", () => {
    expect(crore(21113)).toBe("₹21,113 crore");
    expect(crore(-21113, true)).toBe("−₹21,113 crore");
    expect(crore(21113, true)).toBe("+₹21,113 crore");
    expect(crore(973000)).toBe("₹9.73 lakh crore");
  });

  it("writes shares and index differences without false precision", () => {
    expect(pct(0.0883)).toBe("8.8%");
    expect(signedPct(-0.0217)).toBe("−2.2%");
    expect(signedPct(0.05)).toBe("+5.0%");
    expect(signedIndex(0.014)).toBe("+0.014");
    expect(signedIndex(-0.0032)).toBe("−0.003");
    expect(signedIndex(0.0001)).toBe("0.000");
  });

  it("counts returns in lakh and crore", () => {
    expect(count(7.52e7)).toBe("7.52 crore");
    expect(count(8.5e5)).toBe("8.5 lakh");
    expect(count(950)).toBe("950");
  });

  it("computes slab tax as the calculator does", () => {
    const slabs = [
      { lower: 0, upper: 400000, rate: 0 },
      { lower: 400000, upper: 800000, rate: 0.05 },
      { lower: 800000, upper: 1200000, rate: 0.1 },
      { lower: 1200000, upper: null, rate: 0.15 },
    ];
    expect(slabTax(1200000, slabs)).toBe(60000); // 20,000 + 40,000: the figure the ₹60,000 rebate cancels
    expect(slabTax(300000, slabs)).toBe(0);
    expect(slabTax(1500000, slabs)).toBe(105000);
  });
});
