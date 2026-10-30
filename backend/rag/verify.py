"""
Checking an answer against the passages it cites.

The model is told to cite every claim as [Source N]. Whether a marker points at a
real source is a format check; whether the source says what the sentence says is the
one that matters. This module checks, sentence by sentence, what can be checked
exactly:

  * every rupee amount and rate the sentence states is in the cited passages
    (pipeline.extraction.numbers, the check behind the LLM tab's "needs review");
  * every quotation in the sentence occurs in them (pipeline.extraction.grounding);
  * the markers point at passages that exist, and a sentence that asserts something
    carries one.

What it cannot decide (whether a paraphrase is faithful) it does not claim to.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from pipeline.extraction.grounding import ground
from pipeline.extraction.numbers import unsupported_numbers
from pipeline.quantities import words_to_number

_CITE = re.compile(r"\[\s*Sources?\s+([\d,\s]+)\]", re.IGNORECASE)
_ABSTAIN = re.compile(r"not\s+found\s+in\s+the\s+loaded\s+corpus", re.IGNORECASE)
_QUOTE = re.compile(r"[\"“]([^\"”]{12,}?)[\"”]")
_ABBREV = {"no", "nos", "sec", "secs", "s", "ss", "sub", "cl", "art", "rs", "re", "viz", "etc", "e.g", "i.e", "vs", "dr", "sl"}
_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(₹\"“•\-*])|\n+")


@dataclass
class Claim:
    text: str
    sources: list[int] = field(default_factory=list)
    status: str = "supported"       # supported | unsupported | uncited
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"text": self.text, "sources": self.sources, "status": self.status, "issues": self.issues}


_ONES = "one|two|three|four|five|six|seven|eight|nine"
_TENS = "ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty"
_WHOLE = rf"(?:(?:twenty|thirty|forty|fifty)[- ](?:{_ONES})|{_TENS}|{_ONES}|\d+)"
_FRACTION = re.compile(
    rf"\b(?:(?P<whole>{_WHOLE})\s+and\s+)?(?P<frac>one[- ]third|two[- ]thirds|a\s+half|one[- ]half|half|"
    r"one[- ]fourth|a\s+quarter|one[- ]quarter|three[- ]fourths)\s+per\s*cent", re.IGNORECASE)
_FRACTIONS = {"one third": 1 / 3, "two thirds": 2 / 3, "a half": 0.5, "one half": 0.5, "half": 0.5,
              "one fourth": 0.25, "a quarter": 0.25, "one quarter": 0.25, "three fourths": 0.75}


def with_fraction_rates(text: str) -> str:
    """The text with a decimal beside each rate the law writes in words: "eight and
    one-third per cent" (8.33), "two and a half per cent" (2.5), "half per cent" (0.5).
    A faithful answer says 8.33%; that is not an invented figure."""
    extra = []
    for m in _FRACTION.finditer(text):
        frac = _FRACTIONS.get(re.sub(r"[-\s]+", " ", m.group("frac").lower()))
        if frac is None:
            continue
        whole = (m.group("whole") or "").lower()
        base = float(whole) if whole.isdigit() else (words_to_number(whole.replace("-", " ")) or 0.0) if whole else 0.0
        value = base + frac
        extra += [f"{value:.2f} per cent", f"{value:.2f}%", f"{value:.1f} per cent", f"{value:.1f}%"]
    return text + ("\n" + " ".join(extra) if extra else "")


def split_sentences(answer: str) -> list[str]:
    out, start = [], 0
    for m in _BREAK.finditer(answer):
        head = answer[start:m.start()]
        last = re.findall(r"([A-Za-z.]+)\.?$", head.rstrip())
        if answer[m.start()-1:m.start()] == "." and last and last[-1].lower().rstrip(".") in _ABBREV and "\n" not in m.group():
            continue                                    # "Sec. 5", "No. 2": not a sentence end
        if head.strip():
            out.append(head.strip())
        start = m.end()
    tail = answer[start:].strip()
    if tail:
        out.append(tail)
    return out


def _markers(sentence: str) -> list[int]:
    nums: list[int] = []
    for group in _CITE.findall(sentence):
        for part in re.split(r"[,\s]+", group.strip()):
            if part.isdigit() and int(part) not in nums:
                nums.append(int(part))
    return nums


def _asserts(sentence: str) -> bool:
    """Whether a sentence states something that needs a source: more than a lead-in
    or a closing line. Short lines and questions do not."""
    plain = _CITE.sub("", sentence).strip()
    return len(plain) >= 40 and not plain.endswith("?") and not plain.lower().startswith(("note", "in summary", "to summarise"))


# Spellings a small model uses for a citation marker: (Source 1), [source 2, 3], [Sources 1 and 2]
_LOOSE_MARK = re.compile(r"[\[(]\s*Sources?\s+(\d+(?:\s*(?:,|and|&)\s*\d+)*)\s*[\])]", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\[\s*Sources?\s+N\s*\]", re.IGNORECASE)


_SPACES = "    "            # no-break, thin and narrow no-break spaces
_DASHES = "‐‑‒–−"      # hyphens and dashes a model may use for "-"
_VULGAR = {"⅓": ".33", "⅔": ".67", "½": ".5", "¼": ".25", "¾": ".75"}


def clean_typography(text: str) -> str:
    """Plain spellings of what a hosted model types: "₹12 500" (narrow no-break space) is
    ₹12,500, "one‑third" (non-breaking hyphen) is "one-third", "8⅓ %" is "8.33%". Without
    this a correct answer reads as an invented figure."""
    for ch in _SPACES:
        text = text.replace(ch, " ")
    for ch in _DASHES:
        text = text.replace(ch, "-")
    text = re.sub(r"(?<=\d) (?=\d{3}\b)", ",", text)          # "12 500" -> "12,500"
    for frac, dec in _VULGAR.items():
        text = re.sub(rf"(\d){frac}", rf"\1{dec}", text)
    return re.sub(r"(?<=\d) +%", "%", text)


def normalise_markers(answer: str) -> str:
    """The answer with every citation marker spelled [Source N] or [Source N, M], so the
    page can draw it as a button and the checks read it, and with typographic variants
    made plain (clean_typography). A "[Source N]" left as the template placeholder
    cites nothing and is removed."""
    def fix(m: re.Match) -> str:
        nums = re.findall(r"\d+", m.group(1))
        return f"[Source {', '.join(nums)}]"

    return _LOOSE_MARK.sub(fix, _PLACEHOLDER.sub("", clean_typography(answer or "")))


def _acts_in(answer: str, evidence: str) -> list[str]:
    """Acts the answer names that the corpus does not hold and the evidence does not
    mention. A model that answers from memory names the Act it remembers ("the Patents
    Act, 1970"); a faithful answer names an Act that is in its sources."""
    from rag import scope

    seen = re.sub(r"[^a-z0-9 ]+", " ", evidence.lower().replace("-", " "))
    seen = re.sub(r"\s+", " ", seen)
    out: list[str] = []
    for name in scope.unknown_acts(answer):
        norm = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("-", " "))).strip()
        core = re.sub(r"^(the )", "", norm)
        if core and core not in seen and name not in out:
            out.append(name)
    return out


def verify(answer: str, source_texts: list[str], source_titles: Optional[list[str]] = None) -> dict:
    """The verdict on an answer given the passages it was shown (numbered from 1).

    state: "answered" when no figure or quotation conflicts with the cited text and at
    least one source is cited; "partial" when something conflicts, or nothing is cited;
    "not_found" for an abstention. Sentences that carry no citation are counted
    (n_uncited) and listed, but they do not by themselves make a correct answer
    partial: a small model often cites the lead sentence and not its continuations,
    and what can be checked about them (every figure, against all the sources) is."""
    answer = normalise_markers(answer)
    n = len(source_texts)
    titles = " ".join(source_titles or [])
    claims: list[Claim] = []
    cited_all: list[int] = []
    invalid: list[int] = []
    abstained = bool(_ABSTAIN.search(answer or ""))
    unsupported_all: list[str] = []
    unsupported_acts: list[str] = []

    for sent in split_sentences(answer or ""):
        if _ABSTAIN.search(sent):
            continue
        marks = _markers(sent)
        valid = [m for m in marks if 1 <= m <= n]
        bad = [m for m in marks if not 1 <= m <= n]
        invalid += [m for m in bad if m not in invalid]
        cited_all += [m for m in valid if m not in cited_all]
        plain = re.sub(r"\s+([.,;:])", r"\1", _CITE.sub("", sent)).strip()
        claim = Claim(text=plain, sources=valid)

        # where the sentence's numbers and quotes must be found: its cited passages,
        # or every passage when it names none
        evidence = with_fraction_rates(
            "\n".join(source_texts[m - 1] for m in valid) if valid else "\n".join(source_texts))
        nums = unsupported_numbers([plain], evidence)
        if nums:
            claim.issues.append("not in the cited text: " + ", ".join(nums))
            unsupported_all += [x for x in nums if x not in unsupported_all]
        for act in _acts_in(plain, evidence + "\n" + titles):
            claim.issues.append(f"names an Act that the sources do not mention: {act}")
            if act not in unsupported_acts:
                unsupported_acts.append(act)
        for q in (a for a in _QUOTE.findall(plain) if len(a.split()) >= 4):
            if ground(q, evidence) is None:
                claim.issues.append(f"quotation not found: “{q[:60]}{'…' if len(q) > 60 else ''}”")
        if bad:
            claim.issues.append("cites a source that was not provided: " + ", ".join(f"[{m}]" for m in bad))
        if claim.issues:
            claim.status = "unsupported"
        elif not valid and _asserts(sent):
            claim.status, claim.issues = "uncited", ["states something without citing a source"]
        claims.append(claim)

    conflicts = [c for c in claims if c.status == "unsupported"]
    if abstained and (not claims or not cited_all):
        # "Not found in the loaded corpus", with at most commentary on why: an abstention
        state = "not_found"
    elif not cited_all and not abstained:
        state = "partial"
    elif conflicts:
        state = "partial"
    else:
        state = "answered"
    return {
        "state": state,
        "grounded": state == "answered",
        "abstained": abstained,
        "cited_sources": sorted(cited_all),
        "invalid_citations": sorted(invalid),
        "unsupported_numbers": unsupported_all,
        "unsupported_acts": unsupported_acts,
        "claims": [c.as_dict() for c in claims],
        "n_supported": sum(c.status == "supported" for c in claims),
        "n_claims": len(claims),
        "n_uncited": sum(c.status == "uncited" for c in claims),
        "n_conflicts": len(conflicts),
        "answer": answer,
    }


def needs_revision(verdict: dict) -> bool:
    """A draft is worth one rewrite when it states an amount or a quotation the cited
    text does not contain, or cites a source it was not given."""
    return bool(verdict["unsupported_numbers"] or verdict["invalid_citations"] or verdict.get("unsupported_acts")
                or any(c["status"] == "unsupported" for c in verdict["claims"]))


def revision_note(verdict: dict) -> str:
    lines = []
    for c in verdict["claims"]:
        if c["status"] == "unsupported":
            lines.append(f"- “{c['text'][:140]}”: {'; '.join(c['issues'])}")
    return "\n".join(lines[:6])


def short(answer: str, limit: int = 600) -> Optional[str]:
    answer = (answer or "").strip()
    return answer if len(answer) <= limit else answer[:limit].rsplit(" ", 1)[0] + "…"
