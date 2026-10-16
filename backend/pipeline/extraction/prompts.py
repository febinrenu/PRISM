"""Versioned extraction prompts. Changing the text means bumping the version,
which also changes every cache key that depends on it."""

EXTRACTION_PROMPT_VERSION = 3

EXTRACTION_PROMPT_V1 = """You are reading one provision of an Indian statute. Extract every legal rule it states.

A rule is one deontic statement: an obligation ("shall"), a prohibition ("shall not", "no person shall"),
a permission ("may"), a power given to an authority, a deeming fiction ("shall be deemed"), or a
definition ("means", "includes"). A provision can contain several rules; a proviso or exception that
qualifies a rule is listed in that rule's "exceptions".

QUOTING RULE: every field named "quote" or holding text must be copied EXACTLY, character for
character, from the provision text below. Do not paraphrase. Use null when the provision has no such
part. Never invent text.

For numbers: amounts in rupees as plain numbers (700000 for "seven hundred thousand rupees" or
"Rs. 7,00,000"); rates as fractions (0.05 for "5 per cent."). For each effect, "quote" is the exact
words the numbers come from. In penalty/fee/interest effects: "amount" is a fixed sum, "per_day" is
the rupees charged for each day (100 for "one hundred rupees for every day"), "max_amount" is a cap,
"rate" is a fraction of an amount, "rate_per_month" a fraction charged per month. In slab_row
effects, fill "regime" and "age_band" from the provision or its context when they are stated.

Return ONLY this JSON:
{{
  "rules": [
    {{
      "modality": "obligation | prohibition | permission | power | deeming | definition",
      "subject": "exact words naming who the rule binds, or null",
      "agent_class": "individual | company | firm | huf | any_person | employer | registered_person | data_fiduciary | authority | other",
      "conditions": [{{"quote": "exact words of a condition", "negated": false}}],
      "action": "exact words of what must / may / must not be done, or null",
      "consequence": "exact words of what follows (penalty, liability, effect), or null",
      "exceptions": ["exact words of each proviso or exception that qualifies this rule"],
      "cross_refs": ["exact words of each reference to another provision, e.g. sub-section (1) of section 87A"],
      "effects": [
        {{"kind": "slab_row", "lower": 0, "upper": 300000, "rate": 0.0, "regime": "old | new | both",
          "age_band": "below_60 | 60_to_80 | 80_plus | all", "applies_to_ay": "2026-27 or null", "quote": "..."}},
        {{"kind": "rebate", "max_income": 0, "max_rebate": 0, "marginal_relief": false, "regime": "...", "quote": "..."}},
        {{"kind": "standard_deduction", "amount": 0, "regime": "...", "quote": "..."}},
        {{"kind": "surcharge_band", "threshold": 0, "rate": 0.0, "regime": "...", "quote": "..."}},
        {{"kind": "surcharge_cap", "max_rate": 0.0, "regime": "...", "quote": "..."}},
        {{"kind": "cess", "rate": 0.0, "quote": "..."}},
        {{"kind": "penalty | fee | interest", "amount": null, "per_day": null, "rate": null,
          "rate_per_month": null, "max_amount": null, "trigger": "short description", "quote": "..."}},
        {{"kind": "tds | advance_tax | due_date", "rate": null, "days": null, "description": "...", "quote": "..."}}
      ]
    }}
  ]
}}

EFFECTS: whenever the provision states — or changes — a tax rate, an income slab, a rebate, a
deduction amount, a surcharge, a cess, a fee, an interest charge or a penalty, you MUST include the
matching effect with its numbers. Leave "effects": [] only for provisions that state none of these.
- A rebate of income-tax (section 87A, or section 156 of the Income-tax Act, 2025) is a "deduction
  from the amount of income-tax" of up to some amount where total income does not exceed a limit:
  kind "rebate", max_income = the limit, max_rebate = the amount, marginal_relief = true when the
  provision caps the tax at the amount by which total income exceeds the limit.
- A standard deduction is the fixed amount deducted from salary income (section 16(ia)).

AMENDMENTS: if the provision amends another Act (inserts, substitutes or omits words or provisions),
extract the rule as the amended provision reads AFTER the amendment, and give that rule's effects.
Example: substituting "twelve hundred thousand rupees" for "seven hundred thousand rupees" and
"sixty thousand rupees" for "twenty-five thousand rupees" in the s.87A rebate gives
{{"kind": "rebate", "max_income": 1200000, "max_rebate": 60000, ...}}. Set "applies_to_ay" to the
assessment year from which the amended provision applies when the provision says so.

If the provision states no rule at all (a heading, a commencement clause), return {{"rules": []}}.

{context_block}PROVISION TEXT:
{text}
"""


def render(text: str, context: str = "") -> str:
    context_block = f"CONTEXT (the enclosing section, for reference only — do not extract from it):\n{context}\n\n" if context else ""
    return EXTRACTION_PROMPT_V1.format(text=text, context_block=context_block)


# ── v4: the structured condition ────────────────────────────────────────────
# The same instructions as v1–v3, plus two things a reader of the printed
# page has and the linearised text lacks: the provision's rate tables rebuilt
# row by row (pipeline.statute.tables), and how a rate-table row maps onto a
# slab_row. Its worked example uses invented numbers, so nothing in it
# matches a value of any Act or of the expert coding.

STRUCTURED_PROMPT_VERSION = 4

_RATE_TABLE_GUIDE = """RATE TABLES: give one slab_row effect for every row of a rate table, including the last row.
"lower" is the income the band starts above ("From Rs. 3,50,001" or "exceeds Rs. 3,50,000" gives
350000; the first band starts at 0). "upper" is the income the band ends at, and null for the last
band ("Above ...", or "exceeds ..." with no upper limit). "rate" is the band's marginal rate as a
fraction: in "Rs. 7,000 plus 15 per cent. of the amount by which the total income exceeds
Rs. 3,50,000" the rate is 0.15; "Nil" is 0.0. (These numbers are an illustration, not from any Act.)

"""

_TABLES_BLOCK = """
TABLES IN THIS PROVISION, rebuilt row by row from the printed page. The provision text above can show
a table's lines out of order; read each row's band and rate here. For an effect read from a table
row, set its "quote" to that row exactly as written below.
{tables}
"""


def render_structured(text: str, context: str = "", tables: str = "") -> str:
    """The v4 prompt. Without tables it differs from v1 only by the rate
    table guide."""
    context_block = f"CONTEXT (the enclosing section, for reference only — do not extract from it):\n{context}\n\n" if context else ""
    head, sep, tail = EXTRACTION_PROMPT_V1.partition("If the provision states no rule at all")
    template = head + _RATE_TABLE_GUIDE + sep + tail
    prompt = template.format(text=text, context_block=context_block)
    if tables:
        prompt += _TABLES_BLOCK.format(tables=tables)
    return prompt


REPAIR_PROMPT_VERSION = 5

_REPAIR = """{prompt}
YOUR EARLIER ANSWER for this provision was:
{answer}

When the rules extracted from this provision were assembled into the parameter "{target}", a
structural check failed: {reason}.
{explain}
Read the provision again and return the complete corrected JSON, in the same format. Change only
what the failed check concerns; keep everything else as it was.
"""

# What each assembler check means, in general terms (no values).
CHECKS = {
    "no slab rows": "No slab_row effects were found. Every row of the provision's rate table is one slab_row.",
    "no open top band": "A complete rate schedule ends with a band that has no upper limit (upper: null).",
    "schedule does not start at zero": "A complete rate schedule's first band starts at 0.",
    "gap or overlap between bands": "Each band must start where the previous band ends.",
    "is empty": "A band's upper limit must be above its lower limit.",
    "rates decrease with income": "A band's rate is the marginal rate; check each row's rate.",
    "outside 0-1": "Rates are fractions between 0 and 1 (0.05 for 5 per cent.).",
    "no rebate effect": "A rebate of income-tax is a rebate effect with max_income and max_rebate.",
    "no standard deduction effect": "A standard deduction is a standard_deduction effect with its amount.",
    "conflicting effects": "Effects of this kind disagree; give each one the regime it is stated for, or keep only the one the provision states.",
}


def render_repair(prompt: str, answer: str, target: str, reason: str) -> str:
    explain = next((v for k, v in CHECKS.items() if k in reason), "")
    return _REPAIR.format(prompt=prompt.rstrip(), answer=answer.strip()[:6000], target=target,
                          reason=reason, explain=explain + "\n" if explain else "")
