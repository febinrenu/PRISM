"""
Answers recorded from the full system, replayed by the hosted demo.

The hosted demo has no language model. For the questions people are most likely to ask first, the
answer the full system gave (its model, its cited passages, its verification) was recorded by
tools/record_ask.py and is replayed here event for event, so the page behaves as it does live.
A question that was not recorded is answered by quoting the best-matching passages instead
(rag/extractive.py). A replay is always labelled as one.
"""
import asyncio
import json
import re
from functools import lru_cache
from typing import AsyncIterator, Optional

from rapidfuzz import fuzz

from config import BASE_DIR

FILE = BASE_DIR / "data" / "demo" / "ask_recordings.json"
MIN_MATCH = 93          # rapidfuzz ratio (0-100) between the asked and the recorded question

_WORDS = re.compile(r"[a-z0-9]+")


def _key(q: str) -> str:
    return " ".join(_WORDS.findall(q.lower()))


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))["recordings"]
    except (OSError, ValueError, KeyError):
        return []


def questions() -> list[str]:
    """The recorded questions that open a conversation, for the suggestions."""
    return [r["question"] for r in _load() if not r.get("after")]


def _best(question: str, earlier: list[str]) -> tuple[Optional[dict], float]:
    q = _key(question)
    best, best_score = None, 0.0
    for r in _load():
        if [_key(x) for x in r.get("after", [])] != earlier:
            continue
        score = fuzz.ratio(q, _key(r["question"]))
        if score > best_score:
            best, best_score = r, score
    return best, best_score


def find(question: str, history: Optional[list[dict]] = None, self_contained: bool = False) -> Optional[dict]:
    """The recording of this question given the same earlier user turns or, for a question that needs
    no earlier turn to be understood, the recording made with none; None when there is no match."""
    earlier = [_key(t["content"]) for t in (history or []) if t.get("role") == "user"]
    best, score = _best(question, earlier)
    if (best is None or score < MIN_MATCH) and earlier and self_contained:
        best, score = _best(question, [])
    return best if best is not None and score >= MIN_MATCH else None


async def replay(rec: dict) -> AsyncIterator[dict]:
    """The recorded events, with the answer streamed in small pieces."""
    for ev in rec["events"]:
        if ev["stage"] == "token":
            continue
        if ev["stage"] == "done":
            words = re.findall(r"\S+\s*", rec["answer"])
            for i in range(0, len(words), 3):
                yield {"stage": "token", "token": "".join(words[i:i + 3])}
                await asyncio.sleep(0.012)
            yield {**ev, "backend_used": {"kind": "recorded", "model": rec.get("model", "recorded answer"),
                                          "recorded": True}}
            return
        yield ev
