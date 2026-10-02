"""
PRISM evaluation orchestrator (Module G).

Runs every benchmark and writes machine-readable results + paper-quality charts
to backend/eval/results/. Designed to degrade gracefully: a missing service
(Ollama), missing optional dep (seqeval/matplotlib), or missing dataset (CUAD)
downgrades that one section to a note instead of crashing the run.

Usage (from backend/):
    python -m eval.run_benchmark
    python -m eval.run_benchmark --limit 100 --with-llm --doc demo_income_tax_2025
"""
import argparse
import json
from pathlib import Path

from config import BASE_DIR

RESULTS_DIR = BASE_DIR / "eval" / "results"


def _log(msg: str) -> None:
    print(f"[eval] {msg}", flush=True)


def run(limit: int = 200, with_llm: bool = False, doc_id: str | None = None,
        gold: bool = False) -> dict:
    from eval import causal_eval, ner_eval, sim_validity
    from eval.datasets_cuad import load_eval_set

    results: dict = {"sections": {}}

    # ── In-domain human-reviewed gold (Income Tax Bill) — Module G ──────────────
    if gold:
        from eval.gold_eval import run_gold_eval
        _log("in-domain gold eval (reviewed Indian-statute clauses)…")
        results["sections"]["gold_domain"] = run_gold_eval(with_llm=with_llm)

    # ── Dataset ────────────────────────────────────────────────────────────────
    gold, source = load_eval_set(limit=limit)
    results["dataset"] = {"source": source, "n": len(gold)}
    _log(f"dataset: {source} ({len(gold)} clauses)")

    # ── NER ──────────────────────────────────────────────────────────────────────
    _log("NER presence eval…")
    results["sections"]["ner_presence"] = ner_eval.evaluate_ner_presence(gold)
    span_gold = [g for g in gold if g.get("entities")]
    if span_gold:
        results["sections"]["ner_spans"] = ner_eval.evaluate_ner_spans(span_gold) or {
            "note": "seqeval not installed"
        }

    # ── Causal extraction ────────────────────────────────────────────────────────
    _log("causal (rule-based)…")
    causal = {"rule_based": causal_eval.evaluate_rule_based(gold)}
    if with_llm:
        _log("causal (LLM zero-shot)… this calls Ollama per clause")
        llm_res = causal_eval.evaluate_llm(gold)
        causal["llm"] = llm_res if llm_res is not None else {"note": "Ollama unreachable"}
    results["sections"]["causal"] = causal

    # ── Template matching P@1 (Module C novelty) ─────────────────────────────────
    try:
        from eval.template_eval import evaluate_template_matching
        _log("template-matching P@1…")
        results["sections"]["template_matching"] = evaluate_template_matching(gold)
    except Exception as e:
        results["sections"]["template_matching"] = {"note": f"unavailable: {e}"}

    # ── Simulation sampler fidelity (KL) + external anchor ───────────────────────
    _log("simulation sampler fidelity (KL) + external anchor…")
    results["sections"]["sim_validity"] = {
        "nsso": sim_validity.income_kl(calibration_mode="nsso"),
        "legacy": sim_validity.income_kl(calibration_mode="legacy"),
        "external_anchor": sim_validity.external_anchor(),
    }

    # ── LIME fidelity (only if a doc with cached explanations is given) ──────────
    if doc_id:
        from eval import lime_fidelity
        from storage import store
        result = store.get_result(doc_id)
        if result is not None:
            # Discover cached explanations from disk — the in-result lime_available
            # flag isn't persisted when an explanation is generated.
            clause_ids = store.list_lime_clause_ids(doc_id)
            if not clause_ids:
                clause_ids = [c.clause_id for c in result.clauses if c.lime_available]
            _log(f"LIME fidelity over {len(clause_ids)} explained clauses…")
            results["sections"]["lime"] = lime_fidelity.evaluate_lime(doc_id, clause_ids)
        else:
            results["sections"]["lime"] = {"note": f"no analysis for {doc_id}"}

    _write(results)
    _maybe_charts(results)
    return results


def _write(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "benchmark.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Flat CSV of the headline scalars for quick pasting into a results table.
    rows = ["metric,value"]
    causal = results["sections"].get("causal", {})
    for sysname, r in causal.items():
        if isinstance(r, dict) and "f1" in r:
            rows.append(f"causal_{sysname}_f1,{r['f1']}")
            rows.append(f"causal_{sysname}_precision,{r['precision']}")
            rows.append(f"causal_{sysname}_recall,{r['recall']}")
    ner = results["sections"].get("ner_presence", {})
    if "macro_f1" in ner:
        rows.append(f"ner_presence_macro_f1,{ner['macro_f1']}")
    sim = results["sections"].get("sim_validity", {})
    for mode in ("nsso", "legacy"):
        if mode in sim and sim[mode].get("mean_kl") is not None:
            rows.append(f"sim_kl_{mode},{sim[mode]['mean_kl']}")
    (RESULTS_DIR / "summary.csv").write_text("\n".join(rows), encoding="utf-8")
    _log(f"wrote {RESULTS_DIR / 'benchmark.json'} and summary.csv")


def _maybe_charts(results: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        _log("matplotlib not installed — skipping charts")
        return

    # Causal F1 by system
    causal = {k: v for k, v in results["sections"].get("causal", {}).items()
              if isinstance(v, dict) and "f1" in v}
    if causal:
        fig, ax = plt.subplots(figsize=(5, 3.2))
        names = list(causal)
        ax.bar(names, [causal[n]["f1"] for n in names], color="#C5A880")
        ax.set_ylim(0, 1)
        ax.set_ylabel("F1")
        ax.set_title("Causal-clause detection F1 by system")
        fig.tight_layout()
        fig.savefig(RESULTS_DIR / "causal_f1.png", dpi=150)
        plt.close(fig)

    # Sim validity KL: nsso vs legacy
    sim = results["sections"].get("sim_validity", {})
    modes = [m for m in ("nsso", "legacy") if sim.get(m, {}).get("mean_kl") is not None]
    if modes:
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.bar(modes, [sim[m]["mean_kl"] for m in modes], color=["#8CBDA5", "#D88D93"])
        ax.set_ylabel("mean KL(sim ‖ reference)")
        ax.set_title("Simulation income validity (lower = better)")
        fig.tight_layout()
        fig.savefig(RESULTS_DIR / "sim_validity.png", dpi=150)
        plt.close(fig)

    _log(f"wrote charts to {RESULTS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRISM evaluation benchmark")
    parser.add_argument("--limit", type=int, default=200, help="max eval clauses")
    parser.add_argument("--with-llm", action="store_true", help="also run the Ollama LLM system")
    parser.add_argument("--doc", type=str, default=None, help="doc_id for LIME fidelity")
    parser.add_argument("--gold", action="store_true", help="evaluate against in-domain reviewed gold sets")
    args = parser.parse_args()
    out = run(limit=args.limit, with_llm=args.with_llm, doc_id=args.doc, gold=args.gold)
    print(json.dumps(out["sections"].get("causal", {}), indent=2))
