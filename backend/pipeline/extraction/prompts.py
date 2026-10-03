"""Versioned extraction prompts. Changing the text means bumping the version,
which also changes every cache key that depends on it."""

EXTRACTION_PROMPT_VERSION = 2

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

Include only the effect kinds that this provision actually states, with only the numbers it states.
Most provisions have no effects; use "effects": [] for them. If the provision states no rule at all
(a heading, a commencement clause), return {{"rules": []}}.

{context_block}PROVISION TEXT:
{text}
"""


def render(text: str, context: str = "") -> str:
    context_block = f"CONTEXT (the enclosing section, for reference only — do not extract from it):\n{context}\n\n" if context else ""
    return EXTRACTION_PROMPT_V1.format(text=text, context_block=context_block)
