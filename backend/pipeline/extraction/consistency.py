"""
Self-consistency confidence for extracted rules.

A language model's self-reported confidence is close to 1.0 whatever it says
(0.9–1.0 on every v1 extraction, including misattached ones). Instead each
provision is extracted once greedily (temperature 0) and k more times by
sampling (temperature 0.7, seeds 1…k). For every greedy rule:

    rule confidence     share of samples containing a matching rule
                        (eval.v2.scoring.match_rules on span overlap / effects)
    effect confidence   share of samples whose matching rule has an effect of
                        the same kind with identical numeric fields

The greedy extraction is what is used; the samples only measure how stable
it is. Calibration (ECE) of these confidences is measured against the human
gold, and low-confidence rules can be routed to review.
"""
from eval.v2.scoring import NormRule, from_record, match_rules
from models.rules import ExtractionRecord
from pipeline.extraction.extractor import extract_unit
from pipeline.extraction.units import Unit

SAMPLE_TEMPERATURE = 0.7
_NUMERIC_SKIP = {"regime", "age_band", "applies_to_ay", "trigger", "description", "operation", "taxpayer"}


def _numeric(d: dict) -> tuple:
    return tuple(sorted((k, round(float(v), 6)) for k, v in d.items()
                        if k not in _NUMERIC_SKIP and isinstance(v, (int, float)) and not isinstance(v, bool)))


def _effect_supported(effect: tuple[str, dict], rule: NormRule) -> bool:
    kind, fields = effect
    target = _numeric(fields)
    return any(k == kind and _numeric(f) == target for k, f in rule.effects)


def score_against_samples(greedy: ExtractionRecord, samples: list[ExtractionRecord]) -> ExtractionRecord:
    g = from_record(greedy, "x").rules
    rule_hits = [0] * len(g)
    eff_hits = [[0] * len(r.effects) for r in g]
    usable = [s for s in samples if s.status == "ok"]
    for s in usable:
        sr = from_record(s, "x").rules
        for i, j in match_rules(g, sr):
            rule_hits[i] += 1
            for e, eff in enumerate(g[i].effects):
                if _effect_supported(eff, sr[j]):
                    eff_hits[i][e] += 1
    n = max(len(usable), 1)
    greedy.rule_confidence = [round(h / n, 4) for h in rule_hits]
    greedy.effect_confidence = [[round(h / n, 4) for h in row] for row in eff_hits]
    for rule, conf in zip(greedy.rules, greedy.rule_confidence):
        rule.provenance.samples = len(usable) + 1
        rule.provenance.agreement = conf
    return greedy


def extract_with_consistency(unit: Unit, system: str, k: int = 5, use_cache: bool = True) -> tuple[ExtractionRecord, dict]:
    greedy, stats = extract_unit(unit, system, temperature=0.0, seed=0, use_cache=use_cache)
    if greedy.status != "ok" or not greedy.rules:
        return greedy, stats
    samples = [extract_unit(unit, system, temperature=SAMPLE_TEMPERATURE, seed=s, use_cache=use_cache)[0]
               for s in range(1, k + 1)]
    failed = next((s for s in samples if s.status == "error"), None)
    if failed is not None:
        # A sample lost to a failed call would count as disagreement and lower
        # the confidence; report the failure instead (it is retried on rerun).
        return greedy.model_copy(update={"status": "error", "error": failed.error}), stats
    rec = score_against_samples(greedy, samples)
    stats = dict(stats)
    stats["samples"] = k
    stats["sample_failures"] = sum(1 for s in samples if s.status != "ok")
    return rec, stats
