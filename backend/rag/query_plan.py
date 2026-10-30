"""
Reading a question before searching with it.

A question to Ask often names what it wants outright: "section 87A of the Income-tax
Act, 1961", "compare the rebate in the old and the new Act". Embedding such a
question and hoping the right section is near it wastes the information. This module
pulls out what the words say (section references, which Acts, whether two are being
compared) and spots a follow-up ("and for senior citizens?") that cannot be searched
as it stands. It is plain Python, so it is fast and testable without a model.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SectionRef:
    number: str                 # "156", "87A"
    subs: tuple[str, ...] = ()  # ("2", "a") for 156(2)(a)

    def __str__(self) -> str:
        return self.number + "".join(f"({s})" for s in self.subs)


@dataclass
class Plan:
    question: str                                  # as asked
    standalone: str                                # follow-up resolved; equals question otherwise
    refs: list[SectionRef] = field(default_factory=list)
    acts: list[tuple[str, Optional[str]]] = field(default_factory=list)   # (statute id, version or None)
    intent: str = "ask"                            # ask | lookup | compare
    rewritten: bool = False

    def as_event(self) -> dict:
        return {
            "stage": "plan", "question": self.question,
            "standalone": self.standalone if self.rewritten else None,
            "intent": self.intent, "sections": [str(r) for r in self.refs],
            "acts": [f"{a}/{v}" if v else a for a, v in self.acts],
        }


# ── section references ────────────────────────────────────────────────────────

#   a section number is digits and up to four letters (87A, 115BAC, 80JJAA), not an
#   amount or a period that follows it ("and 5 lakh", "3 years")
_NUM = (r"\d{1,3}[A-Za-z]{0,4}(?!\d)"
        r"(?!\s*(?:lakhs?|crores?|%|per\s*cent|percent|years?|days?|months?|rupees|rs\b|thousand))")
_SUBS = r"(?:\s*\(\s*[0-9A-Za-z]{1,4}\s*\))*"
_SECTION = re.compile(
    rf"(?<![\w])(?:sections?|secs?\.?|ss?\.|u/s)\s*({_NUM}{_SUBS}"
    rf"(?:\s*(?:,|and|&|or)\s*{_NUM}{_SUBS})*)",
    re.IGNORECASE,
)
_ONE = re.compile(rf"({_NUM})((?:\s*\(\s*[0-9A-Za-z]{{1,4}}\s*\))*)")
_SUB = re.compile(r"\(\s*([0-9A-Za-z]{1,4})\s*\)")


def find_sections(text: str) -> list[SectionRef]:
    """Section numbers named in `text`, in order, without repeats.

    "section 156", "s. 87A(2)(a)", "sections 80C and 80D" → 156, 87A(2)(a), 80C, 80D."""
    out: list[SectionRef] = []
    for m in _SECTION.finditer(text):
        for one in _ONE.finditer(m.group(1)):
            number = one.group(1).upper()
            ref = SectionRef(number, tuple(s.lower() if s.isalpha() else s for s in _SUB.findall(one.group(2))))
            if ref not in out:
                out.append(ref)
    return out


# ── which Act ─────────────────────────────────────────────────────────────────

_ITA = r"income[\s-]*tax"
_ACTS: list[tuple[str, re.Pattern]] = [
    ("ITA1961", re.compile(rf"{_ITA}\s+act,?\s*(?:of\s*)?1961|\bita[\s-]*1961|\b1961\b|\bold\s+(?:{_ITA}\s+)?(?:act|law|code)", re.I)),
    ("ITA2025", re.compile(rf"{_ITA}\s+(?:act|bill),?\s*(?:of\s*)?2025|\bita[\s-]*2025|\bnew\s+(?:{_ITA}\s+)?(?:act|law|code)"
                           rf"|\b{_ITA}\s+bill", re.I)),
    ("CGST2017", re.compile(r"\bcgst\b|central\s+goods\s+and\s+services\s+tax|\bgst\s+act\b|goods\s+and\s+services\s+tax", re.I)),
    ("COW2019", re.compile(r"code\s+on\s+wages|wages\s+code", re.I)),
    ("DPDP2023", re.compile(r"\bdpdp\b|digital\s+personal\s+data\s+protection", re.I)),
]
_FINANCE = re.compile(r"finance\s*(\(\s*no\.?\s*2\s*\)\s*)?act,?\s*(?:of\s*)?(20\d\d)", re.I)
_FINANCE_IDS = {("2019", True): "FA2019N2", ("2024", True): "FA2024N2", ("2020", False): "FA2020",
                ("2023", False): "FA2023", ("2025", False): "FA2025", ("2026", False): "FA2026"}
_AMENDED = re.compile(r"as\s+amended|amended\s+(?:version|act)|finance\s+act,?\s*2026|latest\s+version", re.I)
_ENACTED = re.compile(r"as\s+enacted|original(?:ly)?|enacted\s+version", re.I)


def find_acts(text: str) -> list[tuple[str, Optional[str]]]:
    """Which statutes the question names: (id, version); version is None unless the
    question says "as amended" / "as enacted" of the Income-tax Act, 2025."""
    out: list[tuple[str, Optional[str]]] = []

    def add(item):
        if item not in out:
            out.append(item)

    for m in _FINANCE.finditer(text):
        no2 = bool(m.group(1))
        key = _FINANCE_IDS.get((m.group(2), no2)) or _FINANCE_IDS.get((m.group(2), not no2))
        if key:
            add((key, None))
    for sid, pat in _ACTS:
        if pat.search(text):
            add((sid, None))
    # a bare "2025" names the new Income-tax Act only when income tax is in play
    if re.search(r"\b2025\b", text) and re.search(_ITA, text, re.I) and not any(a == "ITA2025" for a, _ in out):
        if not any(a == "FA2025" for a, _ in out):
            add(("ITA2025", None))
    if re.search(r"\bold\s+and\s+new\b|\bnew\s+and\s+old\b|\bold\s+(?:vs\.?|versus|or)\s+new\b", text, re.I):
        add(("ITA1961", None))
        add(("ITA2025", None))
    out = [(a, ("amended_fa2026" if _AMENDED.search(text) and not _ENACTED.search(text)
                else "enacted" if _ENACTED.search(text) else None) if a == "ITA2025" else v) for a, v in out]
    return out


_COMPARE = re.compile(
    r"\bcompar(?:e|es|ed|ing|ison)\b|\bdiffer(?:ence|ences|s|ent|ently)?\b|\bversus\b|\bvs\.?\b|\bwhat\s+changed\b"
    r"|\bhow\s+(?:has|have|did|does)\b.*\b(?:change|changed|differ)\b|\bchanged?\s+(?:from|between|since)\b"
    r"|\bold\s+(?:act|law)\b.*\bnew\b|\bnew\b.*\bold\s+(?:act|law)\b", re.I)


def detect_intent(text: str, refs: list[SectionRef], acts: list) -> str:
    if _COMPARE.search(text) and (len(acts) >= 2 or re.search(r"\bold\b.*\bnew\b|\bnew\b.*\bold\b", text, re.I)):
        return "compare"
    return "lookup" if refs else "ask"


# ── follow-ups ────────────────────────────────────────────────────────────────

_FOLLOW_UP = re.compile(
    r"^(?:and|but|also|then|so|what\s+about|how\s+about|what\s+if|why|how\s+much|how\s+many|"
    r"does\s+(?:it|that|this|the\s+same)|is\s+(?:it|that|this)|do\s+(?:they|those|these)|"
    r"in\s+that\s+case|for\s+(?:a|an|the|senior|resident|non|every|any|such)|what\s+is\s+its)\b", re.I)
_PRONOUN = re.compile(r"\b(?:it|its|that|this|those|these|they|them|there|such|same|above|former|latter)\b", re.I)


def needs_context(question: str, history: list[dict]) -> bool:
    """True when `question` probably leans on the earlier conversation."""
    if not history:
        return False
    if find_sections(question) or find_acts(question):
        return False          # it names what it is about
    words = question.split()
    if len(words) <= 6 or _FOLLOW_UP.match(question.strip()):
        return True
    return bool(_PRONOUN.search(question)) and len(words) <= 14


def last_user_question(history: list[dict]) -> Optional[str]:
    for turn in reversed(history):
        if turn.get("role") == "user" and (turn.get("content") or "").strip():
            return turn["content"].strip()
    return None


def heuristic_standalone(question: str, history: list[dict]) -> str:
    """A follow-up joined to the question it follows: crude, but it keeps the
    section, Act and subject words in the search when no model is available."""
    prev = last_user_question(history)
    return question if not prev else f"{question.strip().rstrip('?')} (about: {prev.rstrip('?')})"


def make_plan(question: str, history: Optional[list[dict]] = None, standalone: Optional[str] = None) -> Plan:
    """The plan for a question. `standalone` is the model's rewrite of a follow-up
    when there is one; without it a follow-up falls back to the heuristic join."""
    history = history or []
    q = question.strip()
    rewritten = False
    text = q
    if needs_context(q, history):
        text = (standalone or heuristic_standalone(q, history)).strip()
        rewritten = text != q
    refs = find_sections(text)
    acts = find_acts(text)
    return Plan(question=q, standalone=text, refs=refs, acts=acts,
                intent=detect_intent(text, refs, acts), rewritten=rewritten)
