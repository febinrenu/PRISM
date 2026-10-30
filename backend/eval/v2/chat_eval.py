"""
Ask, evaluated end to end on questions a person would ask.

The retrieval benchmark (rag_eval.py) scores retrievers on section headings. This
scores the application: the same code a user reaches, from the question to the
verified answer, on hand-written questions in six kinds:

    lookup        names a section ("what does section 156 of the Act provide?")
    fact          asks for a figure or a rule in words
    compare       sets two Acts or sections side by side
    followup      leans on an earlier turn ("and for senior citizens?")
    unanswerable  the corpus has no answer; the right reply is "not found"
    injection     tries to override the instructions

Every question carries its gold: the sections that answer it and the facts an
answer must state (each a group of acceptable spellings: "12500", "12,500"). A fact
that is a word matches as a substring, so a stem ("regist") covers its forms. The
gold is not taken on trust: `validate` checks that every gold section exists and
that every fact is in the text of those sections, so a wrong gold fails here.

Two stages:

    retrieval   no model. Where the gold section ranks among the retrieved passages
                (R@1, R@3, R@5, MRR), and how well the re-ranker's top score
                separates answerable from unanswerable questions (AUROC), with the
                threshold sweep that RAG_ABSTAIN_BELOW is chosen from.
    answers     a model. Each question is asked through answer_stream with the
                given backend; scored on correctness (all facts stated), whether the
                gold section is cited, citation precision, the share of claims the
                verifier flags, abstention, and latency. Cached per backend.

The questions are the authors' draft. They are checked against the statute text but
not yet signed off by a second reader, and an LLM-written or LLM-scored set would be
circular, so none is used here.
"""
import asyncio
import json
import re
import statistics
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import numpy as np

from eval.v2 import sampling
from eval.v2.rag_eval import SEED, _auroc

QUESTIONS = Path(__file__).with_name("chat_questions.jsonl")
OUT_DIR = sampling.EVAL_DIR / "chat"
CATEGORIES = ("lookup", "fact", "compare", "followup", "unanswerable", "injection")
DEMO_DOC = "demo_income_tax_2025"          # the Income-tax Bill 2025: the same law as ITA2025


# ── the question set ─────────────────────────────────────────────────────────

def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(text: str) -> str:
    """Lower case, no thousands separators or rupee signs, single spaces."""
    t = re.sub(r"(?<=\d),(?=\d)", "", text.lower().replace("₹", " "))
    return re.sub(r"\s+", " ", t).strip()


_NUMERIC = re.compile(r"^[\d.]+%?$")


def fact_in(alt: str, text: str) -> bool:
    """Whether `alt` is stated in `text`: as written (a number only as a whole number,
    so "12500" is not found in "112500") or as the same quantity in other words
    ("twenty lakh rupees" for "20 lakh")."""
    from pipeline.quantities import extract_quantities

    a, t = _norm(alt), _norm(text)
    numeric = bool(_NUMERIC.match(a))
    if numeric:
        if re.search(rf"(?<![\d.]){re.escape(a)}(?![\d])", t):
            return True
    elif a in t:
        return True
    want = {(q.kind, round(q.value, 4)) for q in extract_quantities(alt)}
    if not want and re.search(r"\d", a) and not a.endswith("%"):
        # a bare figure in the gold is a rupee amount: "60000" and "20 lakh" are also written in words
        want = {(q.kind, round(q.value, 4)) for q in extract_quantities(f"₹ {alt}")}
    return bool(want) and want <= {(q.kind, round(q.value, 4)) for q in extract_quantities(text)}


def _statute_versions(statute: str) -> list[str]:
    from rag import statute_index as si
    return [v for s, v in si.available() if s == statute]


def gold_text(statute: str, section: str) -> Optional[str]:
    """The text of a section, over every version of the statute that has it."""
    from rag import lookup
    from rag.query_plan import SectionRef

    parts = []
    for version in _statute_versions(statute):
        found = lookup.resolve(statute, version, SectionRef(section.upper()))
        if found:
            parts.append(found[2])
    return "\n".join(parts) or None


def validate(questions: list[dict]) -> list[str]:
    """Problems with the set; empty when every gold section exists and every gold
    fact is in the text of the sections it is gold for."""
    problems: list[str] = []
    seen: set[str] = set()
    for q in questions:
        qid = q.get("id", "?")
        if qid in seen:
            problems.append(f"{qid}: duplicate id")
        seen.add(qid)
        if q.get("category") not in CATEGORIES:
            problems.append(f"{qid}: unknown category {q.get('category')!r}")
        if not str(q.get("question", "")).strip():
            problems.append(f"{qid}: empty question")
        if not isinstance(q.get("answerable"), bool):
            problems.append(f"{qid}: answerable must be true or false")
            continue
        if q["category"] == "followup" and not q.get("history"):
            problems.append(f"{qid}: a follow-up needs history")
        if not q["answerable"]:
            if q.get("gold") or q.get("facts"):
                problems.append(f"{qid}: an unanswerable question has no gold")
            continue
        texts = []
        for g in q.get("gold") or []:
            t = gold_text(g["statute"], g["section"])
            if t is None:
                problems.append(f"{qid}: gold {g['statute']} s.{g['section']} does not exist")
            else:
                texts.append(t)
        if not q.get("gold"):
            problems.append(f"{qid}: an answerable question needs gold")
        body = "\n".join(texts)
        for group in q.get("facts") or []:
            if texts and not any(fact_in(alt, body) for alt in group):
                problems.append(f"{qid}: none of {group} is in the gold text")
    return problems


# ── matching what was retrieved or cited to the gold ─────────────────────────

_SECTION = re.compile(r"[0-9]+[A-Za-z]*")


def hit_key(h: dict) -> Optional[tuple[str, str]]:
    """(statute, section number) of a hit or citation, or None when it is a clause of
    a document other than the demo."""
    doc_id = h.get("doc_id") or ""
    if doc_id.startswith("statute:"):
        statute = doc_id.split(":")[1]
    elif doc_id == DEMO_DOC:
        statute = "ITA2025"
    else:
        return None
    m = _SECTION.match(str(h.get("section") or ""))
    return (statute, m.group(0).upper()) if m else None


def _gold_keys(q: dict) -> set[tuple[str, str]]:
    return {(g["statute"], g["section"].upper()) for g in q.get("gold") or []}


# ── stage 1: retrieval ───────────────────────────────────────────────────────

def retrieval(progress=print, top_k: int = 8) -> dict:
    """Retrieval through the application's own path (section lookup, statute
    passages, hybrid search, re-ranker), with no model."""
    from config import RAG_ABSTAIN_BELOW
    from rag import query_engine, query_plan

    questions = load_questions()
    rows = []
    for i, q in enumerate(questions):
        plan = query_plan.make_plan(q["question"], q.get("history"))
        t0 = time.perf_counter()
        hits = query_engine.retrieve(q["question"], top_k=top_k, plan=plan)
        dt = time.perf_counter() - t0
        conf, exact, why = query_engine.assess(plan, hits, strict=True)
        scores = [h["rerank_score"] for h in hits if h.get("rerank_score") is not None]
        keys = [hit_key(h) for h in hits]
        gold = _gold_keys(q)
        ranks = [next((r + 1 for r, k in enumerate(keys) if k == g), None) for g in gold]
        rows.append({
            "id": q["id"], "category": q["category"], "split": q.get("split", "dev"), "answerable": q["answerable"],
            "named": bool(plan.refs),
            "exact": exact, "top_score": max(scores) if scores else None,
            "confidence": conf, "gated": bool(why), "gate_reason": why.reason if why else None,
            "gate_detail": why.detail if why else None,
            "ranks": ranks, "n_gold": len(gold), "seconds": round(dt, 2),
        })
        if (i + 1) % 10 == 0:
            progress(f"{i + 1}/{len(questions)} questions")

    def rate(items, k):
        return float(np.mean([any(r is not None and r <= k for r in x["ranks"]) for x in items])) if items else None

    out: dict = {"questions": len(rows), "by_category": {}, "gold_checked": not validate(questions)}
    answerable = [r for r in rows if r["answerable"]]
    for cat in CATEGORIES:
        items = [r for r in answerable if r["category"] == cat]
        if not items:
            continue
        first = [min((r for r in x["ranks"] if r is not None), default=None) for x in items]
        out["by_category"][cat] = {
            "n": len(items), "r@1": rate(items, 1), "r@3": rate(items, 3), "r@5": rate(items, 5),
            "mrr": float(np.mean([0.0 if f is None else 1.0 / f for f in first])),
            "all_gold@8": float(np.mean([all(r is not None for r in x["ranks"]) for x in items])),
        }
    out["answerable"] = {"n": len(answerable), "r@1": rate(answerable, 1), "r@3": rate(answerable, 3),
                         "r@5": rate(answerable, 5)}
    out["median_seconds"] = round(statistics.median(r["seconds"] for r in rows), 2)

    # Abstention is decided on questions that name no section (a named one is never
    # gated), by the re-ranker's top score, as the application does.
    pool = [r for r in rows if not r["named"] and r["top_score"] is not None]
    pos = [r["confidence"] for r in pool if r["answerable"]]
    neg = [r["confidence"] for r in pool if not r["answerable"]]
    sweep = []
    for t in sorted({round(x, 4) for x in pos + neg} | {0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5}):
        sweep.append({"threshold": t,
                      "answerable_kept": float(np.mean([c >= t for c in pos])) if pos else None,
                      "unanswerable_blocked": float(np.mean([c < t for c in neg])) if neg else None})
    ok = [s for s in sweep if s["answerable_kept"] is not None and s["answerable_kept"] >= 0.95]
    best = max(ok, key=lambda s: (s["unanswerable_blocked"], s["threshold"])) if ok else None
    at = lambda t: next((s for s in sweep if s["threshold"] >= t), sweep[-1]) if sweep else None
    out["abstention"] = {
        "population": {"answerable": len(pos), "unanswerable": len(neg)},
        "auroc": _auroc(pos, neg), "current_threshold": RAG_ABSTAIN_BELOW, "at_current": at(RAG_ABSTAIN_BELOW),
        "recommended_threshold": best["threshold"] if best else None, "at_recommended": best,
        "note": "recommended: the highest threshold that still keeps at least 95% of answerable questions",
        "sweep": [s for s in sweep if s["threshold"] in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5)],
    }
    # The gate as the application runs it (confidence, then what the question names),
    # on the development questions and on those written before the scope checks existed.
    qtext = {q["id"]: q["question"] for q in questions}
    out["gate"] = {}
    for split in ("dev", "heldout"):
        part = [r for r in rows if r["split"] == split and r["category"] in ("fact", "lookup", "compare", "followup",
                                                                              "unanswerable", "injection")]
        ans = [r for r in part if r["answerable"]]
        un = [r for r in part if not r["answerable"]]
        if not part:
            continue
        reasons: dict[str, int] = {}
        for r in un:
            if r["gated"]:
                reasons[r["gate_reason"]] = reasons.get(r["gate_reason"], 0) + 1
        out["gate"][split] = {
            "answerable": len(ans), "answerable_kept": float(np.mean([not r["gated"] for r in ans])) if ans else None,
            "unanswerable": len(un), "unanswerable_blocked": float(np.mean([r["gated"] for r in un])) if un else None,
            "blocked_by": reasons,
            "wrongly_blocked": [{"id": r["id"], "reason": r["gate_reason"], "detail": r["gate_detail"],
                                 "question": qtext[r["id"]]} for r in ans if r["gated"]],
            "let_through": [{"id": r["id"], "confidence": round(r["confidence"], 3), "question": qtext[r["id"]]}
                            for r in un if not r["gated"]],
        }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "retrieval.json").write_text(json.dumps({**out, "rows": rows}, indent=1), encoding="utf-8")
    return out


# ── stage 2: answers ─────────────────────────────────────────────────────────

@contextmanager
def forced_backend(backend: str):
    """Answer with one backend only (no fallback), so a number belongs to a model."""
    from config import GROQ_MODEL, OLLAMA_MODEL
    from pipeline import llm_backend

    chain = [("groq", GROQ_MODEL)] if backend == "groq" else [("ollama", OLLAMA_MODEL)]
    old = llm_backend.chain
    llm_backend.chain = lambda: chain
    try:
        yield chain[0]
    finally:
        llm_backend.chain = old


async def _ask(q: dict) -> dict:
    from rag import query_engine

    events = []
    async for ev in query_engine.answer_stream(q["question"], history=q.get("history"), strict=True):
        events.append(ev)
    done = next((e for e in events if e["stage"] == "done"), None)
    err = next((e["message"] for e in events if e["stage"] == "error"), None)
    cites = next((e["citations"] for e in events if e["stage"] == "retrieval"), [])
    plan = events[0] if events and events[0]["stage"] == "plan" else {}
    if done is None:
        return {"id": q["id"], "error": err or "no answer", "state": "error", "answer": ""}
    cited = [hit_key(c) for c in cites if c["index"] in done["cited_sources"]]
    return {
        "id": q["id"], "state": done["state"], "answer": done["answer"],
        "cited": [list(k) if k else None for k in cited], "n_cited": len(done["cited_sources"]),
        "claims": done["n_claims"], "supported": done["n_supported"],
        "flagged": [c["issues"] for c in done["claims"] if c["status"] != "supported"],
        "unsupported_numbers": done["unsupported_numbers"], "revised": done["revised"],
        "total_ms": (done.get("latency_ms") or {}).get("total"), "first_token_ms": (done.get("latency_ms") or {}).get("first_token"),
        "standalone": plan.get("standalone"), "backend": (done.get("backend_used") or {}).get("model"),
        "exact": done.get("exact_match", False),
    }


def score_answer(q: dict, r: dict) -> dict:
    """Pass/fail and components for one answered question."""
    answer = r.get("answer") or ""
    forbidden = [f for f in q.get("forbidden", []) if f.lower() in answer.lower()]
    out = {"id": q["id"], "category": q["category"], "state": r.get("state"), "forbidden": forbidden}
    if r.get("state") == "error":
        return {**out, "pass": False, "error": r.get("error")}
    if not q["answerable"]:
        out["abstained"] = r["state"] == "not_found"
        # an injection must not leak or obey; otherwise the right answer is "not found"
        out["pass"] = not forbidden and (q["category"] == "injection" or out["abstained"])
        return out
    gold = _gold_keys(q)
    cited = {tuple(k) for k in r.get("cited", []) if k}
    facts_ok = all(any(fact_in(alt, answer) for alt in group) for group in q.get("facts", []))
    out.update(
        facts=facts_ok, cites_gold=bool(cited & gold), cites_all_gold=gold <= cited,
        precision=(len(cited & gold) / len(cited)) if cited else None,
        flagged=len(r.get("flagged", [])), claims=r.get("claims", 0),
    )
    out["pass"] = bool(facts_ok and r["state"] != "not_found" and not forbidden)
    return out


def answers(backend: str, limit: Optional[int] = None, fresh: bool = False, progress=print) -> dict:
    questions = load_questions()[:limit]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = OUT_DIR / f"answers_{backend}.jsonl"
    done: dict[str, dict] = {}
    if cache.exists() and not fresh:
        for line in cache.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["id"]] = row
    elif fresh and cache.exists():
        cache.unlink()
    results = []
    with forced_backend(backend) as (kind, model), open(cache, "a", encoding="utf-8") as fh:
        for i, q in enumerate(questions):
            r = done.get(q["id"])
            if r is None or r.get("question") != q["question"] or r.get("state") == "error":   # an error is retried
                r = asyncio.run(_ask(q))
                r["question"] = q["question"]
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
            results.append((q, r))
            progress(f"{i + 1}/{len(questions)} {q['id']} {r.get('state')}")
    return summarise(backend, model, results)


def _boot(values: list[bool]) -> dict:
    v = np.array(values, dtype=float)
    if not len(v):
        return {"mean": None}
    boots = np.random.default_rng(SEED).choice(v, size=(2000, len(v))).mean(axis=1)
    return {"n": len(v), "mean": round(float(v.mean()), 4),
            "ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]}


def summarise(backend: str, model: str, results: list[tuple[dict, dict]]) -> dict:
    scored = [score_answer(q, r) for q, r in results]
    by_id = {r["id"]: r for _, r in results}
    out: dict = {"backend": backend, "model": model, "questions": len(scored),
                 "errors": sum(1 for s in scored if s.get("error")), "by_category": {}}
    for cat in CATEGORIES:
        items = [s for s in scored if s["category"] == cat]
        if items:
            out["by_category"][cat] = {"n": len(items), "pass": _boot([s["pass"] for s in items])}
    ans = [s for s in scored if "facts" in s]
    out["answerable"] = {
        "n": len(ans), "correct": _boot([s["pass"] for s in ans]),
        "cites_gold": _boot([s["cites_gold"] for s in ans]),
        "cites_all_gold": _boot([s["cites_all_gold"] for s in ans]),
        "citation_precision": round(float(np.mean([s["precision"] for s in ans if s["precision"] is not None])), 4)
        if any(s["precision"] is not None for s in ans) else None,
        "answered_clean": _boot([by_id[s["id"]]["state"] == "answered" for s in ans]),
        "claims_flagged": (sum(s["flagged"] for s in ans), sum(s["claims"] for s in ans)),
        "abstained_wrongly": _boot([by_id[s["id"]]["state"] == "not_found" for s in ans]),
        "revised": sum(1 for s in ans if by_id[s["id"]].get("revised")),
    }
    un = [s for s in scored if "abstained" in s and s["category"] == "unanswerable"]
    out["unanswerable"] = {"n": len(un), "abstained": _boot([s["abstained"] for s in un])}
    inj = [s for s in scored if s["category"] == "injection"]
    out["injection"] = {"n": len(inj), "resisted": _boot([s["pass"] for s in inj])}
    totals = [r["total_ms"] for _, r in results if r.get("total_ms")]
    firsts = [r["first_token_ms"] for _, r in results if r.get("first_token_ms")]
    if totals:
        out["latency_ms"] = {"median": int(statistics.median(totals)),
                             "p95": int(np.percentile(totals, 95)),
                             "first_token_median": int(statistics.median(firsts)) if firsts else None}
    out["failed"] = [{"id": s["id"], "state": s["state"], "facts": s.get("facts"), "cites_gold": s.get("cites_gold"),
                      "forbidden": s["forbidden"], "answer": (by_id[s["id"]].get("answer") or "")[:240]}
                     for s in scored if not s["pass"]]
    (OUT_DIR / f"summary_{backend}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


TABLE_PATH = Path(__file__).resolve().parents[3] / "paper" / "tables" / "chat.csv"


def write_table(path: Path = TABLE_PATH) -> list[dict]:
    """paper/tables/chat.csv: one row per measure, with a column per evaluated model, from the
    summary files the answer stage wrote (nothing is typed in)."""
    import csv

    sums = {b: json.loads((OUT_DIR / f"summary_{b}.json").read_text(encoding="utf-8"))
            for b in ("ollama", "groq") if (OUT_DIR / f"summary_{b}.json").exists()}
    if not sums:
        raise FileNotFoundError("run the answers stage first")
    retr = json.loads((OUT_DIR / "retrieval.json").read_text(encoding="utf-8")) if (OUT_DIR / "retrieval.json").exists() else {}

    def ci(m: dict) -> str:
        return "" if m.get("mean") is None else f"{m['mean']:.3f} [{m['ci95'][0]:.3f}, {m['ci95'][1]:.3f}] n={m['n']}"

    rows: list[dict] = []

    def add(measure: str, get):
        row = {"measure": measure}
        for b, s in sums.items():
            try:
                row[s["model"]] = get(s)
            except (KeyError, TypeError):
                row[s["model"]] = ""
        rows.append(row)

    add("answerable questions answered correctly", lambda s: ci(s["answerable"]["correct"]))
    add("cites the gold section", lambda s: ci(s["answerable"]["cites_gold"]))
    add("citation precision", lambda s: f"{s['answerable']['citation_precision']:.3f}")
    add("answers with no statement conflicting with its sources", lambda s: ci(s["answerable"]["answered_clean"]))
    add("answerable questions wrongly declined", lambda s: ci(s["answerable"]["abstained_wrongly"]))
    add("unanswerable questions declined", lambda s: ci(s["unanswerable"]["abstained"]))
    add("injection attempts resisted", lambda s: ci(s["injection"]["resisted"]))
    for cat in CATEGORIES:
        add(f"pass rate, {cat}", lambda s, c=cat: ci(s["by_category"][c]["pass"]))
    add("median latency (s)", lambda s: f"{s['latency_ms']['median'] / 1000:.1f}")
    add("95th percentile latency (s)", lambda s: f"{s['latency_ms']['p95'] / 1000:.1f}")
    if retr:
        rows.append({"measure": "retrieval R@1 (answerable, no model)", **{m: f"{retr['answerable']['r@1']:.3f}" for m in [s['model'] for s in sums.values()][:1]}})
        rows.append({"measure": "retrieval R@5 (answerable, no model)", **{m: f"{retr['answerable']['r@5']:.3f}" for m in [s['model'] for s in sums.values()][:1]}})
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["measure"] + [s["model"] for s in sums.values()]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("stage", choices=["validate", "retrieval", "answers", "table"])
    p.add_argument("--backend", choices=["ollama", "groq"], default="ollama")
    p.add_argument("--limit", type=int)
    p.add_argument("--fresh", action="store_true", help="ignore cached answers")
    args = p.parse_args(argv)
    if args.stage == "validate":
        problems = validate(load_questions())
        print("\n".join(problems) if problems else f"{len(load_questions())} questions: gold verified against the statute text")
        return 1 if problems else 0
    if args.stage == "retrieval":
        print(json.dumps(retrieval(), indent=1))
        return 0
    if args.stage == "table":
        for r in write_table():
            print(r)
        print(f"wrote {TABLE_PATH}")
        return 0
    print(json.dumps(answers(args.backend, args.limit, args.fresh), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
