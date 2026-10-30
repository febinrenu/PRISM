"""
Whether a question is about what the corpus covers.

The re-ranker's top score separates answerable from unanswerable questions (AUROC
0.85 on the retrieval benchmark, 0.90 here) but not cleanly: "how do I register a
trademark?" scores high against the statutes' registration provisions. Three
further checks look at what the question *names*, each of which says why:

  unknown Act      the question names a statute the corpus does not hold ("the
                   Customs Act", "the Companies Act", "GDPR") and none it does
  unknown term     a noun the corpus does not use (or uses once or twice) that
                   appears in none of the best passages ("trademark")
  other law        the question is about a State or a foreign country's law, and
                   retrieval is not confident anyway ("stamp duty in Maharashtra")

A question that names a section is never turned away: the section is fetched.
These are heuristics tuned on a small development set and tested on questions
written before the checks existed (eval/v2/chat_eval.py reports both).
"""
import re
from dataclasses import dataclass
from typing import Optional

from rag import statute_index
from rag.query_plan import Plan

# What the corpus is about, for the reply: the statutes' own titles are added at run time.
_KNOWN_ACT_KEYS = (
    "income tax act", "income tax bill", "central goods and services tax", "goods and services tax", "gst act",
    "cgst", "digital personal data protection", "dpdp", "code on wages", "wages code", "finance act",
    "finance no 2 act",
)
# Acronyms a question about the corpus may use freely.
_KNOWN_ACRONYMS = {
    "GST", "CGST", "SGST", "IGST", "UTGST", "GSTIN", "TDS", "TCS", "PAN", "ITR", "HRA", "LTCG", "STCG", "AOP", "BOI",
    "HUF", "ITC", "NRI", "AY", "FY", "DPO", "DPDP", "ITA", "LLP", "EPF", "ESI", "TAN", "AAR", "CBDT", "ITAT", "CIT",
    "AO", "RBI", "SEBI", "FEMA", "VDA", "NPS", "ULIP", "ESOP", "SFT", "PF", "UN", "OECD", "MAT", "AMT", "TRC",
}
_ACT_NAME = re.compile(
    r"\b((?:[A-Z][\w'&.-]*|of|and|the|on|for)(?:\s+(?:[A-Z][\w'&.-]*|of|and|the|on|for)){0,6}\s+"
    r"(?:Act|Code|Bill|Rules|Scheme|Yojana|Treaty|Convention|Regulations))\b")
_ACRONYM = re.compile(r"\b[A-Z]{3,9}\b")
# A capitalised word that opens a sentence is not part of an Act's name ("Which Act ...").
_LEAD = {"what", "which", "who", "whom", "whose", "how", "when", "where", "why", "does", "do", "did", "is", "are", "was",
         "can", "could", "should", "will", "tell", "explain", "state", "under", "in", "about", "compare", "describe",
         "list", "define", "show", "read", "give", "according", "per", "as", "to", "for", "of"}

_STATES = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir", "jammu", "kashmir", "ladakh",
    "puducherry", "pondicherry", "chandigarh", "lakshadweep", "andaman",
)
_COUNTRIES = (
    "united states", "united kingdom", "great britain", "britain", "england", "scotland", "france", "germany",
    "china", "japan", "canada", "australia", "singapore", "russia", "brazil", "south africa", "new zealand",
    "switzerland", "italy", "spain", "ireland", "netherlands", "united arab emirates", "dubai", "saudi arabia",
    "pakistan", "bangladesh", "sri lanka", "nepal", "european union", "america", "mauritius",
)
_CAPS_PLACES = re.compile(r"\b(?:US|USA|UK|UAE|EU)\b")
_PLACES = re.compile(r"\b(" + "|".join(sorted(_STATES + _COUNTRIES, key=len, reverse=True)) + r")\b", re.IGNORECASE)

# Rare-term rule: a noun used by at most this many passages (or none) counts as rare.
RARE_DF = 2
# The other-law rule applies only below this retrieval confidence.
PLACE_CONFIDENCE = 0.5
# An unknown acronym is a weaker sign than an unknown Act: it can be a form name.
ACRONYM_CONFIDENCE = 0.9


@dataclass
class Verdict:
    reason: str              # unknown_act | unknown_term | other_law | low_confidence
    detail: list[str]
    message: str

    def as_dict(self) -> dict:
        return {"reason": self.reason, "detail": self.detail}


def covered_titles() -> list[str]:
    """The statutes the corpus holds, once each (a statute with two versions is one)."""
    seen: dict[str, str] = {}
    for statute, version in statute_index.available():
        try:
            title = statute_index.title_of(statute, version)
        except (OSError, ValueError, KeyError):
            continue
        seen.setdefault(statute, re.sub(r"\s*\(as amended.*\)$", "", title).strip())
    return list(seen.values())


def _norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("-", " "))
    n = re.sub(r"\b(the|of|and)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _is_known_act(name: str) -> bool:
    n = _norm(name)
    pad = f" {n} "
    return any(f" {_norm(k)} " in pad or _norm(k) in n for k in _KNOWN_ACT_KEYS)


def unknown_acts(question: str) -> list[str]:
    """Statutes and schemes the question names that the corpus does not hold."""
    out: list[str] = []
    for m in _ACT_NAME.finditer(question):
        # "the Customs Act and Finance Act" names two statutes
        for piece in re.split(r"\s+and\s+(?=[A-Z][\w'&.-]*(?:\s+[A-Z][\w'&.-]*)*\s+(?:Act|Code|Bill|Rules)\b)", m.group(1)):
            words = piece.split()
            while words and words[0].lower() in _LEAD | {"the", "and", "on"}:
                words.pop(0)
            name = " ".join(words)
            if len(words) < 2 or not any(w[0].isupper() for w in words[:-1]):
                continue                                 # "the Act": no name in it
            if not _is_known_act(name) and name not in out:
                out.append(name)
    return out


def names_known_act(plan: Plan) -> bool:
    """The question names a statute the corpus holds ("the CGST Act", "the Income-tax Act, 1961")."""
    return bool(plan.acts) or any(_is_known_act(m.group(1)) for m in _ACT_NAME.finditer(plan.standalone))


def unknown_acronyms(question: str, vocab: Optional[dict] = None) -> list[str]:
    """Capitalised acronyms the corpus does not use (GDPR, MGNREGA)."""
    out = []
    for m in _ACRONYM.finditer(question):
        a = m.group(0)
        if a in _KNOWN_ACRONYMS or a in out:
            continue
        if vocab is not None and a.lower() in vocab:
            continue
        out.append(a)
    return out


def places(question: str) -> list[str]:
    found = [m.group(1).title() for m in _PLACES.finditer(question)]
    found += _CAPS_PLACES.findall(question)
    return list(dict.fromkeys(found))


def _nouns(text: str) -> list[str]:
    """Nouns of at least four letters, lower-cased. Without spaCy, none (the rule is off)."""
    try:
        from pipeline.legal_ner import _get_nlp
        nlp = _get_nlp()[0]
        doc = nlp(text)
        return [t.text.lower() for t in doc if t.pos_ in ("NOUN", "PROPN") and t.is_alpha and len(t.text) >= 4]
    except Exception:
        return []


def _stem(word: str) -> str:
    return word[:5]


def rare_terms_missing(question: str, hits: list[dict], index) -> list[str]:
    """Rare nouns of the question, when none of them occurs in the best passages.

    `index` is the corpus's BM25 index; a noun absent from its vocabulary, or in at
    most RARE_DF passages, is rare. If the question has such nouns and the top five
    passages contain none of their stems, the passages are about something else."""
    if index is None or not hits:
        return []
    rare = []
    for t in _nouns(question):
        df = index.document_frequency(t)
        if (df is None or df <= RARE_DF) and t not in rare:
            rare.append(t)
    if not rare:
        return []
    stems = {_stem(w) for w in re.findall(r"[a-z]+", " ".join(h["text"].lower() for h in hits[:5]))}
    missing = [t for t in rare if _stem(t) not in stems]
    return missing if len(missing) == len(rare) else []


def _covers() -> str:
    titles = covered_titles()
    return ("The corpus holds " + ", ".join(titles) + " (and any document you have analysed).") if titles else ""


def check(plan: Plan, hits: list[dict], confidence: float, index=None) -> Optional[Verdict]:
    """A reason the corpus cannot answer this question, or None when it can be tried.

    Not applied to a question that names a section: that section is fetched."""
    if plan.refs:
        return None
    q = plan.standalone
    known = names_known_act(plan)
    unknown = unknown_acts(q)
    if unknown and not known:
        return Verdict("unknown_act", unknown,
                       f"The corpus has no {', '.join(unknown)}. {_covers()}")
    acro = unknown_acronyms(q, index.vocab if index is not None else None)
    if acro and not known and confidence < ACRONYM_CONFIDENCE:
        return Verdict("unknown_term", acro, f"{', '.join(acro)} does not appear in the corpus. {_covers()}")
    where = places(q)
    if where and not known and confidence < PLACE_CONFIDENCE:
        return Verdict("other_law", where, f"The corpus covers central Indian statutes; it has nothing on the law of "
                                           f"{', '.join(where)}. {_covers()}")
    if not known:
        missing = rare_terms_missing(q, hits, index)
        if missing:
            return Verdict("unknown_term", missing,
                           f"The corpus does not discuss {', '.join(missing)}: none of the closest passages mention "
                           f"{'it' if len(missing) == 1 else 'them'}. {_covers()}")
    return None
