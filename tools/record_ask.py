#!/usr/bin/env python
"""
Records answers from the full Ask system for the hosted demo to replay (backend/rag/recorded.py).

    cd backend && python ../tools/record_ask.py            # needs the local index and a model (Groq key or Ollama)

The hosted demo has no language model. This runs the real engine (planner, exact lookup, hybrid
retrieval, the model, the verifier) over a fixed set of questions and keeps every event it emits
and the model that wrote the answer, in backend/data/demo/ask_recordings.json. The set is the
questions people are most likely to ask first: a few conversations with follow-ups, the evaluation
set's lookups, facts and comparisons, and questions the corpus must decline.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("LLM_BACKEND", "groq")          # the hosted model writes better answers than the local one

from config import BASE_DIR  # noqa: E402
from rag import query_engine  # noqa: E402

OUT = BASE_DIR / "data" / "demo" / "ask_recordings.json"

FIRST = "What is the rebate under section 156 of the Income-tax Act, 2025?"
# the follow-up chips the Ask page offers after an answer, so a visitor who clicks one gets a real answer
CONVERSATIONS = [
    [FIRST, "What is the income limit for that rebate?"],
    [FIRST, "Show the full text of section 156"],
    [FIRST, "What are the conditions or exceptions?"],
    [FIRST, "Explain this with a worked example"],
    ["What does section 87A of the Income-tax Act, 1961 provide?", "What is the equivalent rebate in the 2025 Act?"],
    ["What is the penalty for under-reporting of income?", "What if it is misreporting?"],
]
DECLINED = [
    "How do I register a trademark in India?",
    "What is the Customs Act duty on gold?",
    "What is the penalty for driving without a licence in India?",
]


def evaluation_questions(limit_fact: int = 10) -> list[str]:
    rows = [json.loads(line) for line in (BASE_DIR / "eval" / "v2" / "chat_questions.jsonl").read_text(encoding="utf-8").splitlines()]
    out = [r["question"] for r in rows if r["category"] == "lookup"][:6]
    out += [r["question"] for r in rows if r["category"] == "fact"][:limit_fact]
    out += [r["question"] for r in rows if r["category"] == "compare"]
    return out


PRIMARY = os.environ.get("RECORD_MODEL", "openai/gpt-oss-120b")


async def record(question: str, history: list[dict], declined: bool = False) -> dict | None:
    """One recording. An answer from the fallback model (the hosted one was rate-limited) is made again."""
    for attempt in range(4):
        events = []
        async for ev in query_engine.answer_stream(question, history=history):
            events.append(ev)
        done = events[-1] if events else {}
        if done.get("stage") != "done":
            print(f"  skipped (no answer): {events[-1] if events else 'no events'}")
            return None
        model = (done.get("backend_used") or {}).get("model") or "unknown"
        if declined or model == PRIMARY or attempt == 3:
            break
        print(f"  answered by {model}; trying again for {PRIMARY}")
        await asyncio.sleep(25)
    # keep an answer whose every figure and quotation is in its sources, even if a sentence carries no marker
    clean = done.get("state") == "answered" or (
        done.get("state") == "partial" and not done.get("n_conflicts") and not done.get("unsupported_numbers"))
    clean = clean and bool(done.get("cited_sources"))           # an answer that cites nothing is not worth replaying
    if not declined and (not clean or model != PRIMARY):
        print(f"  dropped: {done.get('state')} ({done.get('n_conflicts')} conflicts) by {model}")
        return None
    return {
        "question": question,
        "after": [t["content"] for t in history if t["role"] == "user"],
        "answer": done["answer"],
        "model": model,
        "events": [e for e in events if e["stage"] != "token"],
    }


async def main() -> None:
    recordings: list[dict] = []
    done: dict[tuple, dict] = {}
    for convo in CONVERSATIONS:
        history: list[dict] = []
        for q in convo:
            key = (q, tuple(t["content"] for t in history if t["role"] == "user"))
            if key not in done:
                print(f"{len(done) + 1:>2}. {q}" + (f"   (after {len(history) // 2})" if history else ""))
                rec = await record(q, history)
                if rec is None:
                    break
                done[key] = rec
                recordings.append(rec)
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": done[key]["answer"]}]
    for q in evaluation_questions() + DECLINED:
        key = (q, ())
        if key in done:
            continue
        print(f"{len(done) + 1:>2}. {q}")
        rec = await record(q, [], declined=q in DECLINED)
        if rec:
            done[key] = rec
            recordings.append(rec)
    OUT.write_text(json.dumps({"recorded_with": os.environ.get("LLM_BACKEND"), "recordings": recordings},
                              ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(recordings)} recordings, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    asyncio.run(main())
