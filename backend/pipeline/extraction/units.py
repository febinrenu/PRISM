"""
Extraction units: the pieces of a statute sent to an extractor.

A unit is a provision with everything that qualifies it — a section, or one
sub-section of a long section, together with its clauses, provisos and
explanations — so a model never sees half a rule. Nothing is truncated:
a section too long for one unit is split along its children, and each
child carries the section's number, heading and opening words (its
"chapeau") as context. Finance Act insertions (quoted provisions) become
units of their own with the amending words as context.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

from pipeline.statute.corpus import CORPUS_DIR

MAX_UNIT_CHARS = 3500
_CONTAINER_KINDS = {"chapter", "part", "schedule", "heading"}


@dataclass
class Unit:
    unit_id: str                 # node_id of the provision
    statute: str                 # "FA2025/enacted"
    path: str
    kind: str
    start: int                   # offsets into the statute canonical text
    end: int
    text: str
    context: str = ""            # section number/heading/chapeau for split units
    section: str = ""
    heading: str = ""
    quoted: bool = False
    children: list[str] = field(default_factory=list)


def load_statute(statute: str, version: str) -> tuple[dict, str]:
    base = CORPUS_DIR / statute / version
    ast = json.loads((base / "ast.json").read_text(encoding="utf-8"))
    text = (base / "text.txt").read_text(encoding="utf-8")
    return ast, text


def build_units(statute: str, version: str, max_chars: int = MAX_UNIT_CHARS,
                ast: Optional[dict] = None, text: Optional[str] = None) -> list[Unit]:
    if ast is None or text is None:
        ast, text = load_statute(statute, version)
    key = f"{statute}/{version}"
    nodes = {n["node_id"]: n for n in ast["nodes"]}
    units: list[Unit] = []

    def unit_from(n: dict, context: str, section: dict) -> Unit:
        return Unit(unit_id=n["node_id"], statute=key, path=n["path"], kind=n["kind"],
                    start=n["start"], end=n["end"], text=text[n["start"]:n["end"]], context=context,
                    section=section.get("number", ""), heading=section.get("heading", ""),
                    quoted=n.get("quoted", False), children=n.get("children", []))

    def split(n: dict, section: dict, context: str) -> None:
        """Emit `n` whole if it fits, else its own words as context plus one
        unit per child (recursively)."""
        if n["end"] - n["start"] <= max_chars or not n.get("children"):
            u = unit_from(n, context, section)
            if len(u.text) > max_chars:
                # A single paragraph longer than the budget (rare: long tables).
                # Kept whole; the extractor's context window is sized for it.
                pass
            units.append(u)
            return
        own = text[n["start"]:n["own_end"]].strip()
        child_context = (context + "\n" if context else "") + (own[:600] if own else "")
        for cid in n["children"]:
            c = nodes.get(cid)
            if c is None or c["kind"] in _CONTAINER_KINDS:
                continue
            split(c, section, child_context)

    for n in ast["nodes"]:
        if n["kind"] == "section" and not n.get("quoted"):
            head = f"Section {n['number']}" + (f" — {n['heading']}" if n.get("heading") else "")
            split(n, n, head)
        elif n["kind"] == "schedule":
            # Schedules (rate tables, penalty lists) hold some of the most
            # consequential rules; split them along Parts / paragraphs.
            head = n.get("heading") or "Schedule"
            sched = {"number": f"Schedule {n.get('number') or ''}".strip(), "heading": head}
            for cid in n.get("children", []):
                c = nodes.get(cid)
                if c is None:
                    continue
                if c["kind"] in ("part", "heading") and c.get("children"):
                    part_head = head + " — " + text[c["start"]:c["own_end"]].strip()[:120]
                    for gid in c["children"]:
                        g = nodes.get(gid)
                        if g is not None and g["kind"] not in _CONTAINER_KINDS:
                            split(g, sched, part_head)
                elif c["kind"] not in _CONTAINER_KINDS:
                    split(c, sched, head)
    units.sort(key=lambda u: u.start)
    return units
