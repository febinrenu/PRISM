/** Human labels for research identifiers, shared by the app and the story. */

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

export const SYSTEM_NAMES: Record<string, string> = {
  "gpt-oss-120b": "gpt-oss-120b",
  "qwen3.8-27b": "Qwen 3.8 27B",
  "gpt-oss-20b": "gpt-oss-20b",
  "phi3.5": "Phi-3.5 mini",
  "gemma2-2b": "Gemma 2 2B",
  rules: "Rule-based",
};
export const systemName = (id: string) => SYSTEM_NAMES[id] ?? id;

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
export const errorLabel = (e: string) => ERROR_LABEL[e] ?? e.replace(/_/g, " ");
