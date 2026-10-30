/** Number formatting for the policy sandbox: rupees as the law writes them (lakh, crore). */

const LAKH = 1e5;
const CRORE = 1e7;

const grouped = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹ amount: "₹12 lakh", "₹2.4 crore", "₹75,000". */
export function inr(x: number): string {
  const a = Math.abs(x);
  const sign = x < 0 ? "−" : "";
  if (a >= CRORE) return `${sign}₹${trim(a / CRORE)} crore`;
  if (a >= LAKH) return `${sign}₹${trim(a / LAKH)} lakh`;
  return `${sign}₹${grouped.format(a)}`;
}

function trim(v: number): string {
  return Number(v.toFixed(2)).toString();
}

/** An aggregate in ₹ crore: "₹21,113 crore", "₹8.35 lakh crore". Signed when `signed`. */
export function crore(x: number, signed = false): string {
  const a = Math.abs(x);
  const sign = x < 0 ? "−" : signed && x > 0 ? "+" : "";
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)} lakh crore`;
  return `${sign}₹${grouped.format(Math.round(a))} crore`;
}

/** A share as a percentage with sensible precision. */
export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

export function signedPct(x: number, digits = 1): string {
  const v = (x * 100).toFixed(digits);
  return x > 0 ? `+${v}%` : x < 0 ? `−${v.replace("-", "")}%` : `${v}%`;
}

/** A count of returns: "7.5 crore", "85 lakh". */
export function count(x: number): string {
  if (x >= CRORE) return `${trim(x / CRORE)} crore`;
  if (x >= LAKH) return `${trim(x / LAKH)} lakh`;
  return grouped.format(Math.round(x));
}

/** Index differences are small: three decimals, signed. */
export function signedIndex(x: number): string {
  const v = Math.abs(x).toFixed(3);
  return x > 0.0005 ? `+${v}` : x < -0.0005 ? `−${v}` : "0.000";
}

export const ASSUMPTION_LABELS: Record<string, { label: string; hint: string; format: (v: number) => string }> = {
  optimal_share: {
    label: "Taxpayers choosing the cheaper regime",
    hint: "Share who file under whichever regime costs them less",
    format: (v) => pct(v, 0),
  },
  via_scale: {
    label: "Chapter VI-A deductions",
    hint: "Old-regime deductions, relative to the rank-matched estimate",
    format: (v) => `${v.toFixed(2)}×`,
  },
  top_alpha: {
    label: "Tail of the top income band",
    hint: "Pareto shape of incomes above the last published band: lower means a heavier tail",
    format: (v) => v.toFixed(2),
  },
  senior_share: {
    label: "Taxpayers aged 60 to 80",
    hint: "The published statistics carry no age split",
    format: (v) => pct(v, 0),
  },
  growth: {
    label: "Nominal income growth",
    hint: "Beyond the published series, per year",
    format: (v) => pct(v, 1),
  },
};

/** Tax on `income` under a slab schedule (the calculator's own rule, for presets). */
export function slabTax(income: number, slabs: { lower: number; upper: number | null; rate: number }[]): number {
  let tax = 0;
  for (const s of slabs) {
    const top = s.upper ?? Infinity;
    tax += s.rate * Math.max(0, Math.min(income, top) - s.lower);
  }
  return tax;
}
