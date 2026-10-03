"""
Blind second coding of the income-tax parameters by a language model.

The model is given, for each assessment year, the statute excerpts a human
coder is pointed to in docs/expert_coding_form.md (rate schedules, s.115BAC,
s.87A, s.16(ia), surcharge and cess provisions) and the blank coding
template — never the gold parameters. It must say, per regime, whether each
value was read from the excerpts or supplied from general knowledge (some
Finance Acts are not in the corpus).

This is an automated cross-check of the expert coding, reported as such; it
is not a substitute for human inter-coder agreement.
"""
import json
import re
from pathlib import Path
from typing import Optional

import httpx

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_URL
from pipeline.statute.corpus import CORPUS_DIR

MAX_EXCERPT = 14_000


def _text(statute: str, version: str = "enacted") -> str:
    p = CORPUS_DIR / statute / version / "text.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _ast(statute: str, version: str = "enacted") -> dict:
    p = CORPUS_DIR / statute / version / "ast.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"nodes": []}


def schedule_part(statute: str, part: str, version: str = "enacted") -> str:
    """First Schedule, Part I or Part III, Paragraph A (individuals)."""
    text = _text(statute, version)
    m = re.search(r"THE FIRST SCHEDULE", text)
    if not m:
        return ""
    rest = text[m.start():]
    pm = re.search(rf"\nPART\s+{part}\b", rest)
    if not pm:
        return ""
    chunk = rest[pm.start():]
    end = re.search(r"\nParagraph\s+B\b", chunk)
    return chunk[: end.start() if end else MAX_EXCERPT][:MAX_EXCERPT]


def section(statute: str, number: str, version: str = "enacted", quoted: Optional[bool] = None) -> str:
    text = _text(statute, version)
    for n in _ast(statute, version)["nodes"]:
        if n["kind"] == "section" and n["number"] == number and (quoted is None or n["quoted"] == quoted):
            return text[n["start"]:n["end"]][:MAX_EXCERPT]
    return ""


def amending_section(statute: str, target: str) -> str:
    """The Finance Act section that amends `target` (e.g. '115BAC', '87A')."""
    text = _text(statute)
    for n in _ast(statute)["nodes"]:
        if n["kind"] != "section" or n["quoted"]:
            continue
        own = text[n["start"]:n["own_end"]]
        if re.search(rf"\bsection {re.escape(target)}\b", own[:220]):
            return text[n["start"]:n["end"]][:MAX_EXCERPT]
    return ""


def grep(statute: str, pattern: str, version: str = "enacted", width: int = 1200) -> str:
    text = _text(statute, version)
    out = []
    for m in re.finditer(pattern, text):
        out.append(text[max(0, m.start() - 200): m.start() + width])
        if len(out) >= 2:
            break
    return "\n…\n".join(out)


# Which excerpts a coder reads for each year (mirrors the coding form).
def sources_for(ay: str) -> list[tuple[str, str]]:
    S = []
    add = lambda label, txt: S.append((label, txt)) if txt else None  # noqa: E731
    if ay == "2020-21":
        add("Finance Act 2020, First Schedule Part I Para A", schedule_part("FA2020", "I"))
        add("Finance (No. 2) Act 2019, First Schedule Part III Para A", schedule_part("FA2019N2", "III"))
    elif ay == "2021-22":
        add("Finance Act 2020, First Schedule Part III Para A", schedule_part("FA2020", "III"))
        add("Finance Act 2020, s.53 inserting s.115BAC", section("FA2020", "115BAC", quoted=True))
    elif ay == "2022-23":
        add("Finance Act 2020, First Schedule Part III Para A (Finance Act 2022 is not available)", schedule_part("FA2020", "III"))
        add("Finance Act 2020, s.53 inserting s.115BAC", section("FA2020", "115BAC", quoted=True))
    elif ay == "2023-24":
        add("Finance Act 2023, First Schedule Part I Para A", schedule_part("FA2023", "I"))
        add("Finance Act 2020, s.53 inserting s.115BAC", section("FA2020", "115BAC", quoted=True))
    elif ay == "2024-25":
        add("Finance Act 2023, s.52 amending s.115BAC", amending_section("FA2023", "115BAC"))
        add("Finance Act 2023, s.44 amending s.87A", amending_section("FA2023", "87A"))
        add("Finance Act 2023, First Schedule Part III Para A", schedule_part("FA2023", "III"))
        add("Finance Act 2023, s.2 (surcharge and cess)", section("FA2023", "2", quoted=False))
    elif ay == "2025-26":
        add("Finance (No. 2) Act 2024, s.37 substituting s.115BAC(1A)", amending_section("FA2024N2", "115BAC"))
        add("Finance (No. 2) Act 2024, s.10 amending s.16", amending_section("FA2024N2", "16"))
        add("Finance Act 2025, First Schedule Part I Para A", schedule_part("FA2025", "I"))
        add("Finance Act 2023, s.44 amending s.87A", amending_section("FA2023", "87A"))
    elif ay == "2026-27":
        add("Finance Act 2025, s.25 amending s.115BAC", amending_section("FA2025", "115BAC"))
        add("Finance Act 2025, s.20 amending s.87A", amending_section("FA2025", "87A"))
        add("Finance Act 2026, First Schedule Part I Para A", schedule_part("FA2026", "I"))
        add("Finance (No. 2) Act 2024, s.10 amending s.16", amending_section("FA2024N2", "16"))
    elif ay == "2027-28":
        add("Income-tax Act 2025 (as amended), s.202", section("ITA2025", "202", "amended_fa2026", quoted=False))
        add("Income-tax Act 2025 (as amended), s.156", section("ITA2025", "156", "amended_fa2026", quoted=False))
        add("Income-tax Act 2025 (as amended), salary deductions (standard deduction)",
            grep("ITA2025", r"Standard deduction\.", "amended_fa2026", 600))
        add("Finance Act 2026, First Schedule Part III Para A", schedule_part("FA2026", "III"))
        add("Finance Act 2026, s.2", section("FA2026", "2", quoted=False))
    return S


_INSTRUCTIONS = """You are coding Indian personal income-tax parameters for ONE assessment year, for a
resident individual whose income is taxed at normal rates (ignore special-rate capital gains,
lotteries and agricultural-income aggregation).

Fill the JSON template below. Rules:
- Amounts in rupees as numbers (700000, not "7 lakh"); rates as fractions (0.05 for 5%).
- Slabs as {"lower","upper","rate"} starting at 0; the last slab has "upper": null.
- "rebate" is the section 87A (or Income-tax Act 2025 s.156) rebate: max_income is the total-income
  limit, max_rebate the maximum amount, marginal_relief true if tax payable is capped at the income
  above the limit. Use null for the whole rebate object if no rebate applies.
- "standard_deduction" is the deduction on salary income for that regime (0 if none).
- "surcharge" lists {"threshold","rate"} bands for total income exceeding each threshold.
- "allows_chapter_via_deductions": true if Chapter VI-A deductions (80C etc.) are allowed.
- "default_regime": "old" or "new" — the regime that applies unless the person opts otherwise.
- In each regime's "source" say which excerpt each value came from. In "note", list every value you
  could NOT read from the excerpts and supplied from general knowledge instead.
Return only the filled JSON object for this year.

Assessment year: {ay}

TEMPLATE:
{template}

STATUTE EXCERPTS:
{excerpts}
"""


def code_year(ay: str, template: dict, model: str = GEMINI_MODEL, timeout: float = 240.0) -> dict:
    excerpts = "\n\n".join(f"=== {label} ===\n{txt}" for label, txt in sources_for(ay))
    prompt = (_INSTRUCTIONS.replace("{ay}", ay)
              .replace("{template}", json.dumps(template, indent=1))
              .replace("{excerpts}", excerpts))
    r = httpx.post(
        f"{GEMINI_URL}/models/{model}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    raw = body["candidates"][0]["content"]["parts"][0]["text"]
    return {"coding": json.loads(raw), "model_version": body.get("modelVersion"),
            "sources": [label for label, _ in sources_for(ay)], "prompt_chars": len(prompt)}
