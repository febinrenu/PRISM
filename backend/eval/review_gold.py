"""
Phase 3, Module G — gold-set review tool (human-in-the-loop).

Flips bootstrap candidates to `reviewed: true` once a human has confirmed them.
Three modes:

  --sample N     mark N random items reviewed (the honest "review a sample" path
                 the paper describes — the rest stay unreviewed and unused)
  --accept-all   mark every item reviewed (only if you've eyeballed the whole set)
  (default)      interactive: show each item, [a]ccept / [e]dit / [s]kip / [q]uit

For causal items, edit flips gold_is_causal. For NER, edit opens the entity list
as JSON to correct. rag_qa items are accept/skip only.

    python -m eval.review_gold --set causal --sample 40
"""
import argparse
import json
import random
from pathlib import Path

from eval.gold_builder import GOLD_DIR


def _path(name: str) -> Path:
    return GOLD_DIR / ("rag_qa.json" if name == "rag_qa" else f"{name}_gold.json")


def _save(name: str, data: dict) -> None:
    _path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(name: str) -> dict:
    p = _path(name)
    if not p.exists():
        raise SystemExit(f"[error] {p} not found. Run: python -m eval.gold_builder")
    return json.loads(p.read_text(encoding="utf-8"))


def sample_review(name: str, n: int, seed: int) -> None:
    data = _load(name)
    items = data["items"]
    idx = list(range(len(items)))
    random.Random(seed).shuffle(idx)
    for i in idx[:n]:
        items[i]["reviewed"] = True
    _save(name, data)
    print(f"[ok] Marked {min(n, len(items))} / {len(items)} '{name}' items reviewed.")


def accept_all(name: str) -> None:
    data = _load(name)
    for it in data["items"]:
        it["reviewed"] = True
    _save(name, data)
    print(f"[ok] Marked all {len(data['items'])} '{name}' items reviewed.")


def interactive(name: str) -> None:
    data = _load(name)
    items = data["items"]
    print(f"Reviewing {len(items)} '{name}' items. [a]ccept [e]dit [s]kip [q]uit\n")
    for i, it in enumerate(items):
        if it.get("reviewed"):
            continue
        print(f"--- {i + 1}/{len(items)} (clause {it.get('clause_id', it.get('gold_clause_id'))}) ---")
        print(it.get("text", it.get("question", ""))[:400])
        if name == "causal":
            print(f"candidate is_causal = {it['candidate_is_causal']}")
        elif name == "ner":
            print("entities:", json.dumps(it["gold_entities"], ensure_ascii=False))
        try:
            choice = input("[a/e/s/q] > ").strip().lower()
        except EOFError:
            print("\n[non-interactive stdin — use --sample or --accept-all]")
            return
        if choice == "q":
            break
        if choice == "s":
            continue
        if choice == "e":
            if name == "causal":
                it["gold_is_causal"] = not it["candidate_is_causal"]
                print(f"  flipped → {it['gold_is_causal']}")
            elif name == "ner":
                raw = input("  paste corrected entities JSON (or blank to keep): ").strip()
                if raw:
                    try:
                        it["gold_entities"] = json.loads(raw)
                    except json.JSONDecodeError:
                        print("  invalid JSON — kept candidate")
        it["reviewed"] = True
        _save(name, data)
    print("[ok] Saved.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Review PRISM gold eval sets.")
    ap.add_argument("--set", required=True, choices=["ner", "causal", "rag_qa"])
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--accept-all", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    if args.accept_all:
        accept_all(args.set)
    elif args.sample > 0:
        sample_review(args.set, args.sample, args.seed)
    else:
        interactive(args.set)


if __name__ == "__main__":
    main()
