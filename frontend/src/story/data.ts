/**
 * The story's data: the snapshot written by `python -m cli story-export`.
 * Every number the story prints is read from here, never typed into copy
 * (scripts/check-story-literals.mjs enforces this).
 */
import core from "@/content/story.core.json";

export interface Source {
  file?: string;
  key?: string;
  inspect?: string;
  [k: string]: string | undefined;
}

export interface NumberEntry {
  value: string;
  source: Source;
}

export interface Cell {
  set: string;
  system: string;
  status: "assembled" | "no conclusion" | "missing";
  complete?: boolean;
  flips?: number;
  conclusions?: number;
  revenue_error_crore?: number;
  decile_rate_l1?: number;
  param_diff?: string[];
  reasons?: string[];
  source?: Source;
}

export interface Reform {
  id: string;
  ay: string;
  statute: string;
  description: string;
  targets: Record<string, string>;
}

export interface SystemInfo {
  id: string;
  label: string;
  kind: string;
  params_b: number;
}

export interface Effect {
  kind?: string;
  regime?: string;
  max_income?: number;
  max_rebate?: number;
  marginal_relief?: boolean;
  quote?: string;
  span?: [number, number] | null;
  modality?: string;
}

export interface StoryCore {
  version: number;
  numbers: Record<string, NumberEntry>;
  matrix: { reforms: Reform[]; systems: SystemInfo[]; cells: Cell[] };
  focus: {
    set: string;
    system: string;
    target: string;
    provision: string;
    path: string;
    text: string;
    effects: Effect[];
    expert: { marginal_relief: boolean; max_income: number; max_rebate: number };
    extracted: { marginal_relief: boolean; max_income: number; max_rebate: number };
    param_diff: string[];
    revenue_error_crore: number;
    taxpayers_with_different_tax: number;
    revenue_change_expert_crore: number;
    revenue_change_system_crore: number;
    flips: number;
    conclusions: number;
    source: Source;
  };
  curve: {
    salary: number[];
    series: { before: number[]; expert: number[]; system: number[] };
    largest_gap: { salary: number; expert: number; system: number; difference: number };
    source: Source;
  };
  deciles: {
    ay: string;
    system: string | null;
    deciles: { decile: number; income_upper: number; before: number; expert: number; system?: number }[];
  };
  injection: {
    kinds: { error: string; injections: number; flipping: number; max_flip_rate: number; max_revenue_error_crore: number }[];
    rows: { set: string; target: string; error: string; flip_rate: number; revenue_error_crore: number }[];
    source: Source;
  };
  behaviour: {
    expert_penalty: number;
    misread_penalty: number;
    sobol_total: Record<string, number>;
    systems: Record<string, { penalty_rate: number | null; matches_expert: boolean }>;
    source: Source;
  };
  corpus: {
    statutes: { key: string; title: string; sections: number; chapters: number }[];
    sections_total: number;
    characters_total: number;
    source: Source;
  };
  population: { ay: string; returns_total: number; points: number; source: Source };
}

export const story = core as unknown as StoryCore;

/** A number exactly as the paper prints it, with its source. */
export function n(key: string): NumberEntry {
  const e = story.numbers[key];
  if (!e) throw new Error(`story number ${key} is not in the snapshot`);
  return e;
}

/** Numeric value of a paper number ("4,077" → 4077). */
export function nv(key: string): number {
  return Number(n(key).value.replace(/,/g, ""));
}

/** Indian digit grouping: 1744789 → "17,44,789". */
export function inr(x: number, digits = 0): string {
  return x.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/** ₹ in lakh for salaries: 1280000 → "12.8 lakh". */
export function lakh(x: number): string {
  const v = x / 100000;
  return `${Number.isInteger(v) ? v : v.toFixed(v < 10 ? 2 : 1).replace(/0$/, "")} lakh`;
}

/** Millions with one decimal: 1744789 → "1.7 million". */
export function millions(x: number): string {
  return `${(x / 1e6).toFixed(1)} million`;
}

export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

export const SYSTEM_LABEL: Record<string, string> = Object.fromEntries(
  story.matrix.systems.map((s) => [s.id, s.label])
);

/** "FA2024N2_budget" → "FA 2024 (No. 2) · budget". */
export function reformLabel(id: string): string {
  const [act, ...rest] = id.split("_");
  const name = act
    .replace(/^FA(\d{4})N2$/, "FA $1 (No. 2)")
    .replace(/^FA(\d{4})$/, "FA $1")
    .replace(/^ITA(\d{4})$/, "ITA $1");
  const what = rest
    .join(" ")
    .replace(/(\d+)L/, "₹$1L")
    .replace("ITA2025", "under ITA 2025");
  return what ? `${name} · ${what}` : name;
}

export const ERROR_LABEL: Record<string, string> = {
  drop_rebate: "Rebate dropped",
  other_regime_rebate: "Rebate given to the wrong regime",
  lakh_crore_confusion: "Lakh read as crore",
  drop_middle_band: "Middle slab dropped",
  shift_bound_1_lakh: "Slab bound off by ₹1 lakh",
  drop_top_band: "Top slab dropped",
  rate_from_adjacent_row: "Rate read from the next row",
  drop_marginal_relief: "Marginal relief dropped",
  previous_year_rebate: "Last year's rebate",
  previous_year_table: "Last year's slab table",
  rebate_amount_misread: "Rebate amount misread",
  previous_year_standard_deduction: "Last year's standard deduction",
  off_by_one_rupee: "Bound off by one rupee",
};

/** Population and constellation files are fetched by the scenes. */
export interface Population {
  ay: string;
  columns: string[];
  rows: [number, number, number, number, number, number][];
  returns_total: number;
}

export interface Constellation {
  statute: string;
  title: string;
  nodes: { k: string; l: string; h: string; p: number }[];
  thread: number[];
}

const cache = new Map<string, Promise<unknown>>();
export function fetchStory<T>(file: "population" | "constellation"): Promise<T> {
  if (!cache.has(file)) {
    cache.set(
      file,
      fetch(`/story/${file}.json`).then((r) => {
        if (!r.ok) throw new Error(`${file}: ${r.status}`);
        return r.json();
      })
    );
  }
  return cache.get(file) as Promise<T>;
}
