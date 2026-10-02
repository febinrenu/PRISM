"""
Phase 3, Module G — LLM-assisted gold evaluation set builder.

Produces three gold sets for the IEEE paper from a real analysed document
(default: the Income Tax Bill demo), then a human reviews/corrects them:

  ner_gold.json   — up to 200 clauses, each with candidate entity spans
  causal_gold.json— up to 100 clauses, each with a candidate is_causal label
                    (+ condition/action/consequence spans when available)
  rag_qa.json     — up to 50 question→source-clause pairs for retrieval eval

Candidates are BOOTSTRAPPED from artifacts already on disk — the rule-based NER
entities and the Phase-2 LLM extractions — so this runs instantly with no new
model calls. Each item carries `"reviewed": false`; `review_gold.py` is the
human-in-the-loop step that flips it to true (optionally editing labels). The
paper reports these as "LLM-assisted, human-reviewed" — which is exactly what
they are. `run_benchmark.py --gold` then scores the live systems against the
REVIEWED items.

    python -m eval.gold_builder --doc demo_income_tax_2025
"""
import argparse
import json
import random
from pathlib import Path
from typing import Optional

from config import BASE_DIR
from storage import store

GOLD_DIR = BASE_DIR / "data" / "eval" / "gold"

_ENTITY_LABELS = ("OBLIGATION", "RIGHT", "PENALTY", "THRESHOLD", "ACTOR", "BENEFICIARY")


def _clause_entities(clause) -> list[dict]:
    return [
        {"text": e.text, "label": e.label, "start": e.start, "end": e.end,
         "confidence": e.confidence}
        for e in clause.entities
        if e.label in _ENTITY_LABELS
    ]


def build_ner_gold(clauses, limit: int, rng: random.Random) -> list[dict]:
    """Sample prose clauses that carry entities; the rule-based NER output is the
    candidate labelling for a reviewer to confirm/correct."""
    pool = [c for c in clauses if c.clause_type != "table" and _clause_entities(c)]
    rng.shuffle(pool)
    items = []
    for c in pool[:limit]:
        items.append({
            "clause_id": c.clause_id, "page": c.page, "text": c.text[:1200],
            "candidate_entities": _clause_entities(c),
            "gold_entities": _clause_entities(c),  # reviewer edits this in place
            "reviewed": False,
        })
    return items


def build_causal_gold(clauses, limit: int, rng: random.Random) -> list[dict]:
    """Balance clauses the LLM marked causal against clauses it marked non-causal
    (or that lack any causal signal), so the binary metric isn't degenerate."""
    causal, noncausal = [], []
    for c in clauses:
        if c.clause_type == "table":
            continue
        ex = c.llm_extraction
        has_signal = bool(c.causal_patterns) or (ex and ex.is_causal)
        label = bool(ex.is_causal) if (ex and ex.is_causal is not None) else has_signal
        item = {
            "clause_id": c.clause_id, "page": c.page, "text": c.text[:1200],
            "candidate_is_causal": label,
            "gold_is_causal": label,
            "candidate_spans": {
                "condition": ex.condition if ex else None,
                "action": ex.action if ex else None,
                "consequence": ex.consequence if ex else None,
            } if ex else {"condition": None, "action": None, "consequence": None},
            "reviewed": False,
        }
        (causal if label else noncausal).append(item)

    rng.shuffle(causal)
    rng.shuffle(noncausal)
    half = max(1, limit // 2)
    items = causal[:half] + noncausal[: limit - min(half, len(causal))]
    rng.shuffle(items)
    return items[:limit]


# Question stems, anchored on a DISTINCTIVE phrase from the clause so retrieval
# targets that specific clause (a generic "what is the penalty?" retrieves the
# same handful of clauses for every item → useless recall). {anchor} is the most
# content-bearing entity mention in the clause.
_Q_STEMS = {
    "PENALTY": "What penalty applies in relation to {anchor}?",
    "THRESHOLD": "What threshold or rate applies to {anchor}?",
    "OBLIGATION": "What obligation does the statute impose regarding {anchor}?",
    "RIGHT": "What right or entitlement does the statute grant regarding {anchor}?",
    "BENEFICIARY": "What does the statute provide for {anchor}?",
}
_LABEL_PRIORITY = ("PENALTY", "THRESHOLD", "OBLIGATION", "RIGHT", "BENEFICIARY")


def _pick_anchor(clause, label: str) -> Optional[str]:
    """The longest entity mention of `label` (most distinctive), cleaned."""
    cands = [e.text.strip() for e in clause.entities if e.label == label and len(e.text.strip()) > 3]
    if not cands:
        return None
    anchor = max(cands, key=len)
    return anchor[:80]


def _llm_question(clause_text: str) -> Optional[str]:
    """Ask the local LLM for one specific, self-contained question this clause
    answers. Returns None if Ollama is unreachable/parse fails."""
    import httpx

    from config import OLLAMA_MODEL, OLLAMA_URL

    prompt = (
        "Read this legal clause and write ONE specific question that this clause "
        "directly answers. The question must be self-contained and mention the "
        "concrete subject (amount, section, party, or action) so it could be "
        "found by search. Return only the question.\n\nClause:\n"
        + clause_text[:900]
    )
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.2, "num_predict": 60}},
            timeout=60.0,
        )
        r.raise_for_status()
        q = (r.json().get("response") or "").strip().strip('"').split("\n")[0]
        return q if len(q) > 15 else None
    except Exception:
        return None


def build_rag_qa(clauses, limit: int, rng: random.Random, use_llm: bool = False) -> list[dict]:
    """Question → ground-truth source clause pairs, for a retrieval@k eval:
    does the RAG retriever surface the clause each question was generated from?

    Two question sources:
      - template (default): anchored on a distinctive entity mention — fast, no
        model calls, but weaker (generic verb anchors don't pinpoint a clause).
      - LLM (`use_llm`): a specific self-contained question per clause — much
        better retrieval targets; ~50 Ollama calls, run once.
    """
    # Prefer clauses with distinctive content (thresholds/penalties) as anchors.
    candidates = []
    for c in clauses:
        if c.clause_type == "table" or len(c.text.strip()) < 60:
            continue
        labels = {e.label for e in c.entities}
        anchor_lbl = next((l for l in _LABEL_PRIORITY if l in labels), None)
        if anchor_lbl is None:
            continue
        candidates.append((c, anchor_lbl))

    rng.shuffle(candidates)
    pool, seen = [], set()
    for c, lbl in candidates:
        if len(pool) >= limit:
            break
        anchor = _pick_anchor(c, lbl)
        question = None
        if use_llm:
            question = _llm_question(c.text)
        if not question:
            if not anchor:
                continue
            question = _Q_STEMS[lbl].format(anchor=anchor)
        if question in seen:
            continue
        seen.add(question)
        pool.append({
            "question": question,
            "answer_excerpt": c.text[:400],
            "gold_clause_id": c.clause_id,
            "gold_page": c.page,
            "based_on": lbl,
            "anchor": anchor,
            "question_source": "llm" if use_llm and question not in _Q_STEMS.values() else "template",
            "reviewed": False,
        })
    return pool


def build(doc_id: str, seed: int = 42, ner_n: int = 200, causal_n: int = 100,
          rag_n: int = 50, llm_questions: bool = False) -> dict:
    result = store.get_result(doc_id)
    if result is None:
        raise ValueError(f"No analysis results for {doc_id}. Analyse it first.")
    rng = random.Random(seed)
    clauses = result.clauses

    ner = build_ner_gold(clauses, ner_n, rng)
    causal = build_causal_gold(clauses, causal_n, rng)
    rag = build_rag_qa(clauses, rag_n, rng, use_llm=llm_questions)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"doc_id": doc_id, "seed": seed, "note": "LLM-assisted bootstrap; set reviewed=true after human check."}
    (GOLD_DIR / "ner_gold.json").write_text(
        json.dumps({"meta": meta, "items": ner}, ensure_ascii=False, indent=2), encoding="utf-8")
    (GOLD_DIR / "causal_gold.json").write_text(
        json.dumps({"meta": meta, "items": causal}, ensure_ascii=False, indent=2), encoding="utf-8")
    (GOLD_DIR / "rag_qa.json").write_text(
        json.dumps({"meta": meta, "items": rag}, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ner": len(ner), "causal": len(causal), "rag_qa": len(rag), "dir": str(GOLD_DIR)}


def load_gold(name: str, reviewed_only: bool = False) -> list[dict]:
    """Load a gold set by name ('ner' | 'causal' | 'rag_qa')."""
    path = GOLD_DIR / f"{name}_gold.json" if name in ("ner", "causal") else GOLD_DIR / "rag_qa.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    return [it for it in items if it.get("reviewed")] if reviewed_only else items


def main() -> None:
    ap = argparse.ArgumentParser(description="Build LLM-assisted gold eval sets.")
    ap.add_argument("--doc", default="demo_income_tax_2025")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ner-n", type=int, default=200)
    ap.add_argument("--causal-n", type=int, default=100)
    ap.add_argument("--rag-n", type=int, default=50)
    ap.add_argument("--llm-questions", action="store_true",
                    help="generate specific RAG questions with the LLM (better retrieval eval; ~50 Ollama calls)")
    args = ap.parse_args()
    summary = build(args.doc, args.seed, args.ner_n, args.causal_n, args.rag_n, args.llm_questions)
    print(json.dumps(summary, indent=2))
    print("\n[next] Review & correct: python -m eval.review_gold --set causal")


if __name__ == "__main__":
    main()
