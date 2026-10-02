"""
Template-matching benchmark (Module C novelty).

Without a gold "correct template per clause" set (which no public dataset
provides for Indian statute), we report the honest, measurable proxies:

  - coverage@threshold : fraction of obligation-bearing clauses for which the
    semantic matcher confidently assigns *some* template (score ≥ threshold).
    This is the precision@1 analogue: the matcher's first choice is accepted.
  - mean_top_score     : mean cosine of the top template match on positives.
  - negative_coverage  : fraction of non-obligation clauses that (undesirably)
    still match a template — a false-positive proxy.

An in-domain gold set with template labels can later replace `is_causal` with
`gold_template` to compute true P@1.
"""
from simulation.templates import match_template


def evaluate_template_matching(gold: list[dict]) -> dict:
    pos = [g for g in gold if g.get("is_causal")]
    neg = [g for g in gold if not g.get("is_causal")]

    pos_matches = [match_template(g["text"]) for g in pos]
    neg_matches = [match_template(g["text"]) for g in neg]

    matched_pos = [m for m in pos_matches if m is not None]
    coverage = round(len(matched_pos) / len(pos), 4) if pos else 0.0
    mean_score = round(sum(m.score for m in matched_pos) / len(matched_pos), 4) if matched_pos else None
    neg_coverage = round(sum(1 for m in neg_matches if m is not None) / len(neg), 4) if neg else None

    # Distribution of which templates fired (useful qualitative table).
    hist: dict[str, int] = {}
    for m in matched_pos:
        hist[m.key] = hist.get(m.key, 0) + 1

    return {
        "n_positive": len(pos),
        "n_negative": len(neg),
        "coverage_at_threshold": coverage,
        "mean_top_score": mean_score,
        "negative_coverage": neg_coverage,
        "template_histogram": dict(sorted(hist.items(), key=lambda kv: -kv[1])),
    }
