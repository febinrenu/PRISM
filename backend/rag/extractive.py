"""
An answer made only of what the statute says, for when no language model is available.

The hosted demo (and any deployment whose model is down) still has retrieval: the sections a question
names are fetched exactly and the rest are ranked. This module turns the best of them into an answer
by quoting them, each with its citation marker. Nothing is paraphrased, so every figure and
quotation in it is in its source by construction; the usual checker runs over it all the same.
"""
import re

_WS = re.compile(r"\s+")
LEAD = "No language model is available here, so this quotes the provisions that best match the question."
EXCERPT_CHARS = 460


def excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """The opening of `text`, whitespace collapsed, cut at the end of a sentence where there is one."""
    t = _WS.sub(" ", text).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(": "))
    return (cut[: end + 1] if end > limit * 0.5 else cut[: cut.rfind(" ")]).rstrip(" ,;:")


def where(hit: dict) -> str:
    name = hit.get("doc_name") or "the document"
    sec = (hit.get("section") or "").strip()
    head = (hit.get("heading") or "").strip()
    place = f"{name}, section {sec}" if sec and not sec.lower().startswith("section") else f"{name}, {sec}".rstrip(", ")
    return f"{place} ({head})" if head else place


def compose(hits: list[dict], limit: int = 3) -> str:
    """The answer text: a one-line lead, then each of the best passages quoted with its marker."""
    parts = [LEAD, ""]
    for i, h in enumerate(hits[:limit], 1):
        parts.append(f"{where(h)} [Source {i}]: “{excerpt(h['text'])}”")
        parts.append("")
    return "\n".join(parts).strip()
