"""
Rule-based deontic modality, the transparent baseline the language models
are compared against.

Ordered patterns, most specific first:

    prohibition   "shall not", "no person shall", "shall in no case"
    deeming       "shall be deemed", "is deemed to"
    definition    '"X" means', '"X" includes', a clause of a definitions section
    power         "may" with an authority subject (Board, Officer, Government …)
    permission    "may", "entitled to", "eligible for"
    obligation    "shall", "must", "is required to", "liable to"
"""
import re
from typing import Optional

_PROHIBITION = re.compile(r"\b(?:shall|will|must)\s+not\b|\bno\s+(?:person|assessee|registered person|employer|data fiduciary|[a-z]+)\s+shall\b|\bshall\s+in\s+no\s+case\b|\bnot\s+be\s+(?:allowed|permitted|lawful)\b", re.I)
_DEEMING = re.compile(r"\b(?:shall\s+be|is|are)\s+deemed\b|\bdeemed\s+to\s+(?:be|have)\b", re.I)
_DEFINITION = re.compile(r"[“\"'‘][^”\"'’]{1,80}[”\"'’]\s+(?:means|includes|shall\s+mean|shall\s+include|has\s+the\s+meaning)\b", re.I)
_AUTHORITY = re.compile(r"\b(?:Board|Assessing Officer|Commissioner|Officer|Central Government|State Government|Government|Authority|Tribunal|Council|Data Protection Board|Inspector|proper officer|Director)\b")
_MAY = re.compile(r"\bmay\b(?!\s+be\s+called)(?!\s+extend\s+to)", re.I)
_PERMISSION = re.compile(r"\b(?:entitled\s+to|eligible\s+(?:for|to)|be\s+allowed\s+a\s+deduction|shall\s+be\s+allowed)\b", re.I)
_OBLIGATION = re.compile(r"\b(?:shall|must|is\s+required\s+to|are\s+required\s+to|liable\s+to)\b", re.I)


def modality(text: str, in_definitions: bool = False) -> Optional[str]:
    """The modality of a provision's operative words, or None (no rule)."""
    if not text or not text.strip():
        return None
    head = text[:600]
    if _DEFINITION.search(head) or (in_definitions and re.search(r"\bmeans\b|\bincludes\b", head)):
        return "definition"
    if _PROHIBITION.search(head):
        return "prohibition"
    if _DEEMING.search(head):
        return "deeming"
    m = _MAY.search(head)
    if m:
        before = head[max(0, m.start() - 160):m.start()]
        return "power" if _AUTHORITY.search(before) else "permission"
    if _PERMISSION.search(head):
        return "permission"
    if _OBLIGATION.search(head):
        return "obligation"
    return None
