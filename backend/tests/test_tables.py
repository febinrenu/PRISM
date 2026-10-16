"""Rebuilt rate tables (pipeline.statute.tables) and the structured
extraction condition that uses them. Offline: no model is called."""
import hashlib
import json
import shutil
from collections import Counter

import pytest

from pipeline.statute import tables as T
from pipeline.statute.corpus import CORPUS_DIR

FINANCE_ACTS = sorted(p.parent for p in CORPUS_DIR.glob("FA*/*/tables.json") if (p.parent / "text.txt").exists())
needs_corpus = pytest.mark.skipif(not (CORPUS_DIR / "FA2025" / "enacted" / "text.txt").exists(),
                                  reason="statute corpus not parsed (python -m cli ingest && python -m cli parse)")


def _chars(s: str) -> Counter:
    return Counter(c for c in s if not c.isspace() and c != "|")


# ── the rebuilt views ────────────────────────────────────────────────────────

@needs_corpus
def test_views_are_built_from_the_current_text():
    for base in FINANCE_ACTS:
        key = f"{base.parent.name}/{base.name}"
        data = json.loads((base / "tables.json").read_text(encoding="utf-8"))
        text = (base / "text.txt").read_text(encoding="utf-8")
        assert data["text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest(), key
        assert data["unplaced_pdf_tables"] == 0, key
        assert T.load(key), key


@needs_corpus
def test_rebuilt_rows_only_reorder_the_canonical_text():
    """A rebuilt row has exactly the characters of the canonical span it is
    cited to (in another order); the few rows that cannot be cited exactly
    are flagged."""
    rows = inexact = 0
    for base in FINANCE_ACTS:
        text = (base / "text.txt").read_text(encoding="utf-8")
        for t in T.load(f"{base.parent.name}/{base.name}"):
            for r in t.rows:
                rows += 1
                same = _chars(r.label + "".join(r.cells)) == _chars(text[r.start:r.end])
                assert same == r.exact or (not r.exact and not same), r.text
                if not r.exact:
                    inexact += 1
                    # an inexact span still holds every character of the row
                    assert not (_chars(r.label + "".join(r.cells)) - _chars(text[r.start:r.end])), r.text
    assert rows > 150
    assert inexact <= 0.03 * rows


@needs_corpus
def test_interleaved_schedule_is_rebuilt():
    """FA 2025 First Schedule Part I Para A (I): the canonical text holds the
    rate column's lines out of order; the rebuilt row reads as printed."""
    tabs = T.load("FA2025/enacted")
    two = [t for t in tabs if t.kind == "two_column"]
    row = two[0].rows[1]
    assert row.label == "(2)"
    assert row.cells == ["where the total income exceeds Rs. 2,50,000 but does not exceed Rs. 5,00,000",
                         "5 per cent. of the amount by which the total income exceeds Rs. 2,50,000;"]
    text = (CORPUS_DIR / "FA2025" / "enacted" / "text.txt").read_text(encoding="utf-8")
    assert "5 per cent. of the amount by which the total income exceeds Rs. 2,50,000" not in text


@needs_corpus
def test_a_table_across_a_page_break_is_stitched():
    """FA 2023 Part III Para A (III): row (1) at the foot of one page, rows
    (2) and (3) at the head of the next."""
    stitched = [t for t in T.load("FA2023/enacted") if t.kind == "two_column" and t.page == 77 and len(t.rows) == 3]
    assert stitched and [r.label for r in stitched[0].rows] == ["(1)", "(2)", "(3)"]


@needs_corpus
def test_every_slab_target_has_its_table():
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import PROVISION_SETS, units_for
    for name, spec in PROVISION_SETS.items():
        units = build_units(*spec["statute"])
        for target, path in spec["targets"].items():
            if ".slabs" not in target:
                continue
            for u in units_for(path, units):
                tabs = T.tables_in(u.statute, u.start, u.end)
                assert tabs, (name, target)
                assert all(T._RATE_RE.search(r.cells[-1]) for t in tabs for r in t.rows), (name, target)


@needs_corpus
def test_a_stale_view_is_never_used(tmp_path, monkeypatch):
    src = CORPUS_DIR / "FA2025" / "enacted"
    dst = tmp_path / "FA2025" / "enacted"
    dst.mkdir(parents=True)
    shutil.copy(src / "tables.json", dst / "tables.json")
    (dst / "text.txt").write_text((src / "text.txt").read_text(encoding="utf-8") + " changed", encoding="utf-8")
    monkeypatch.setattr(T, "CORPUS_DIR", tmp_path)
    T.load.cache_clear()
    try:
        assert T.load("FA2025/enacted") == []
    finally:
        T.load.cache_clear()


def test_boxed_tables_keep_only_rate_rows():
    text = ("namely:—\nTABLE\nSl. No. | Total income | Rate of tax\n(1) | (2) | (3)\n"
            "1. | Upto Rs. 3,00,000 | Nil\n2. From Rs. 3,00,001 to Rs. 7,00,000 | 5 per cent.\n"
            "3. Above Rs. 7,00,000 | 10 per cent.\n(ii) next clause\n")
    tabs = T.boxed_tables(text, [])
    assert len(tabs) == 1
    assert [r.text for r in tabs[0].rows] == ["1. Upto Rs. 3,00,000 | Nil",
                                              "2. From Rs. 3,00,001 to Rs. 7,00,000 | 5 per cent.",
                                              "3. Above Rs. 7,00,000 | 10 per cent."]
    # each row is cited to its own line of the text
    assert [text[r.start:r.end] for r in tabs[0].rows] == ["1. | Upto Rs. 3,00,000 | Nil",
                                                           "2. From Rs. 3,00,001 to Rs. 7,00,000 | 5 per cent.",
                                                           "3. Above Rs. 7,00,000 | 10 per cent."]
    # a wrapped header table is not a rate table
    assert T.boxed_tables("TABLE\nSl. | Population of | Within distance\nNo. | municipality | aerially\n", []) == []


# ── grounding, prompts, schema ───────────────────────────────────────────────

def test_quote_from_a_rebuilt_row_is_cited_to_the_canonical_row():
    from pipeline.extraction.grounding import ground, ground_structured
    source = "(2) where the total income exceeds Rs. 5 | income exceeds Rs. 5;\n5 per cent. of the amount by which the total\n(3) next"
    row = "(2) where the total income exceeds Rs. 5 | 5 per cent. of the amount by which the total income exceeds Rs. 5;"
    end = source.index("\n(3)")
    g = ground_structured(row, source, [(row, 0, end)])
    assert g is not None and g.method.startswith("table_") and (g.start, g.end) == (0, end)
    assert g.text == source[:end]
    # an exact quote of the provision text keeps its own, tighter span
    q = "where the total income exceeds Rs. 5"
    g2 = ground_structured(q, source, [(row, 0, end)])
    assert g2.method == "exact" and g2.text == q
    # the original grounding is unchanged by the new path
    assert ground(row, source) is None or ground(row, source).method == "fuzzy"


def test_v3_prompt_is_unchanged():
    """Headline cache keys depend on the v3 prompt text: it must not move."""
    from pipeline.extraction import prompts
    assert prompts.EXTRACTION_PROMPT_VERSION == 3
    digest = hashlib.sha256(prompts.EXTRACTION_PROMPT_V1.encode("utf-8")).hexdigest()
    assert digest == V3_PROMPT_SHA256


V3_PROMPT_SHA256 = "65d33d47d3bb643a26e9305f8e72a9f705eefcdfdeff43288317083cdab4e2a8"


@needs_corpus
def test_structured_prompt_example_is_from_no_act():
    from pipeline.extraction import prompts
    assert "7,000 plus 15 per cent." in prompts._RATE_TABLE_GUIDE
    for text in CORPUS_DIR.glob("*/*/text.txt"):
        body = text.read_text(encoding="utf-8")
        assert "7,000 plus 15 per cent" not in body and "3,50,001" not in body, text


def test_repair_prompt_names_the_check_not_a_value():
    from pipeline.extraction import prompts
    out = prompts.render_repair("PROMPT", '{"rules": []}', "old.slabs.below_60", "no open top band")
    assert "no open top band" in out and "upper: null" in out
    assert prompts.render_repair("P", "{}", "t", "something new").count("structural check failed") == 1


def test_schema_variants():
    from pipeline.extraction.schema import answer_schema, fingerprint
    strict, lenient = answer_schema(True), answer_schema(False)
    eff_s = strict["properties"]["rules"]["items"]["properties"]["effects"]["items"]
    eff_l = lenient["properties"]["rules"]["items"]["properties"]["effects"]["items"]
    assert set(eff_s["required"]) == set(eff_s["properties"]) and eff_s["additionalProperties"] is False
    assert eff_l["required"] == ["kind", "quote"]
    assert fingerprint(strict) != fingerprint(lenient)


def test_strict_shaped_answer_validates():
    """A strict-schema answer carries every field, null where unused; the
    extractor drops the nulls and validates the effect by its kind."""
    from pipeline.extraction.extractor import to_record
    from pipeline.extraction.schema import _EFFECT_FIELDS
    from pipeline.extraction.units import Unit
    text = "1. Upto Rs. 3,00,000 | Nil\n2. Above Rs. 3,00,000 | 5 per cent."
    unit = Unit(unit_id="u1", statute="X/enacted", path="X/s1", kind="section", start=100, end=100 + len(text), text=text)
    blank = {k: None for k in _EFFECT_FIELDS}
    eff = [dict(blank, kind="slab_row", lower=0, upper=300000, rate=0.0, regime="new", quote="1. Upto Rs. 3,00,000 | Nil"),
           dict(blank, kind="slab_row", lower=300000, rate=0.05, quote="2. Above Rs. 3,00,000 | 5 per cent.")]
    rule = {"modality": "obligation", "subject": None, "agent_class": None, "conditions": [], "action": None,
            "consequence": None, "exceptions": [], "cross_refs": [], "effects": eff}
    rec, stats = to_record(unit, "gpt-oss-120b", json.dumps({"rules": [rule]}), model="m", model_version=None,
                           cache_key="k", rows=[], prompt_version=4)
    effects = rec.rules[0].effects
    assert [(e.lower, e.upper, e.rate) for e in effects] == [(0, 300000, 0.0), (300000, None, 0.05)]
    assert effects[0].regime == "new" and effects[1].regime == "both"
    assert effects[0].source_span.start == 100 and stats["effects_invalid"] == 0
    assert rec.rules[0].provenance.prompt_version == 4


def test_json_mode_cache_keys_unchanged():
    from pipeline.extraction.backends import SYSTEMS, request_options
    from pipeline.extraction.schema import answer_schema
    for s in SYSTEMS.values():
        assert request_options(s, None) == (dict(s.options) or None)
    assert request_options(SYSTEMS["gpt-oss-120b"], answer_schema(True))["strict"] is True


def test_refused_schema_falls_back_to_json_mode(tmp_path, monkeypatch):
    from pipeline.extraction import backends, cache
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = []

    def fake(system, prompt, temperature, seed, timeout, schema=None):
        calls.append(schema is not None)
        if schema is not None:
            raise backends.SchemaUnsupported("refused")
        return '{"rules": []}', None

    monkeypatch.setitem(backends._PROVIDERS, "ollama", fake)
    monkeypatch.setattr(backends, "_ollama_digest", lambda m: None)
    res = backends.generate_json("phi3.5", "p", schema={"type": "object"}, prompt_version=4)
    assert res.decoding == "json_fallback" and calls == [True, False]
    again = backends.generate_json("phi3.5", "p", schema={"type": "object"}, prompt_version=4)
    assert again.cached and again.decoding == "json_fallback"


# ── the rule baseline and the structured run ─────────────────────────────────

@needs_corpus
def test_rules_read_the_rebuilt_schedule():
    from pipeline.extraction.rule_based import extract_unit
    from pipeline.extraction.structured import unit_rows
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import PROVISION_SETS, units_for
    spec = PROVISION_SETS["FA2025_old_schedule"]
    u = units_for(spec["targets"]["old.slabs.below_60"], build_units(*spec["statute"]))[0]
    _, rows = unit_rows(u)
    before, _ = extract_unit(u)
    after, _ = extract_unit(u, rows=rows)
    slabs = [(e.lower, e.upper, e.rate) for r in after.rules for e in r.effects if e.kind == "slab_row"]
    assert slabs == [(0, 250000, 0.0), (250000, 500000, 0.05), (500000, 1000000, 0.2), (1000000, None, 0.3)]
    assert slabs != [(e.lower, e.upper, e.rate) for r in before.rules for e in r.effects if e.kind == "slab_row"]
    for r in after.rules:
        for e in r.effects:
            assert u.text[e.source_span.start - u.start:e.source_span.end - u.start] == e.source_span.text


@needs_corpus
def test_rules_scope_tables_by_year():
    from pipeline.extraction.rule_based import extract_unit
    from pipeline.extraction.structured import unit_rows
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import PROVISION_SETS, units_for
    spec = PROVISION_SETS["FA2024N2_budget"]
    u = units_for(spec["targets"]["new.slabs"], build_units(*spec["statute"]))[0]
    rec, _ = extract_unit(u, rows=unit_rows(u)[1])
    years = Counter(e.applies_to_ay for r in rec.rules for e in r.effects if e.kind == "slab_row")
    assert years == {"2024-25": 6, "2025-26": 6}


@needs_corpus
def test_structured_rules_run_fixes_the_interleaved_sets():
    from simulation.experiment import structured_run
    for name in ("FA2025_old_schedule", "FA2026_old_schedule_ITA2025"):
        r = structured_run.run_set(name, "rules")
        assert r["complete"] and r["first_pass"]["population"]["flip_rate"] == 0.0, name
        assert all(c["exact_match_rate"] == 1.0 for c in r["first_pass"]["comparisons"].values()), name
        assert r["repaired"] is None and r["repair_log"] == []


@needs_corpus
def test_repair_round_end_to_end(tmp_path, monkeypatch):
    """A scripted model drops the top band; the assembler's check is sent
    back once; the corrected answer assembles. Both passes are kept."""
    from pipeline.extraction import backends, cache
    from simulation.experiment import structured_run
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    rows = [(0, 250000, 0.0, "1. Up to Rs. 2,50,000 | Nil"),
            (250000, 500000, 0.05, "2. From Rs. 2,50,001 to Rs. 5,00,000 | 5 per cent."),
            (500000, 750000, 0.10, "3. From Rs. 5,00,001 to Rs. 7,50,000 | 10 per cent."),
            (750000, 1000000, 0.15, "4. From Rs. 7,50,001 to Rs. 10,00,000 | 15 per cent."),
            (1000000, 1250000, 0.20, "5. From Rs. 10,00,001 to Rs. 12,50,000 | 20 per cent."),
            (1250000, 1500000, 0.25, "6. From Rs. 12,50,001 to Rs. 15,00,000 | 25 per cent."),
            (1500000, None, 0.30, "7. Above Rs. 15,00,000 | 30 per cent.:")]
    prompts_seen = []

    def fake(system, prompt, temperature, seed, timeout, schema=None):
        prompts_seen.append(prompt)
        keep = rows if "YOUR EARLIER ANSWER" in prompt else rows[:-1]
        eff = [{"kind": "slab_row", "lower": lo, "upper": up, "rate": rt, "regime": "new", "quote": q}
               for lo, up, rt, q in keep]
        return json.dumps({"rules": [{"modality": "obligation", "effects": eff}]}), None

    monkeypatch.setitem(backends._PROVIDERS, "ollama", fake)
    monkeypatch.setattr(backends, "_ollama_digest", lambda m: None)
    r = structured_run.run_set("FA2020_new_regime", "phi3.5")
    assert r["complete_first_pass"] is False and r["complete"] is True
    assert [x["reason"] for x in r["first_pass"]["review"]] == ["no open top band"]
    assert r["repair_log"] == [{"target": "new.slabs", "path": "FA2020/s53/q1/s115BAC/(1)", "reason": "no open top band",
                                "status": ["ok"], "effects": 7, "fixed": True}]
    assert r["repaired"]["population"]["flip_rate"] == 0.0
    assert len(prompts_seen) == 2 and "TABLES IN THIS PROVISION" in prompts_seen[0]
    assert "no upper limit (upper: null)" in prompts_seen[1]
    # no expert value reaches the model: the repair prompt adds only the check
    assert prompts_seen[1].startswith(prompts_seen[0].rstrip())


def test_structured_table_counts(tmp_path, monkeypatch):
    import reproduce
    from simulation.experiment.provision_sets import PROVISION_SETS

    def res(complete, flip):
        return {"complete": complete, "population": {"flip_rate": flip}, "review": []}
    head = [{"set": s, "system": "x", **res(i % 2 == 0, 0.0 if i % 2 == 0 else 1.0)} for i, s in enumerate(PROVISION_SETS)]
    runs = []
    for i, s in enumerate(PROVISION_SETS):
        first = res(i > 0, 0.0 if i > 0 else 1.0)
        rep = res(True, 0.5) if i == 0 else None
        runs.append({"set": s, "system": "x", "variant": "tables+schema", "repair": True, "first_pass": first,
                     "repaired": rep, "repair_log": [{"x": 1}] if i == 0 else [], "complete": True,
                     "complete_first_pass": i > 0})
    monkeypatch.setattr(reproduce, "TABLES", tmp_path)
    p = reproduce.structured_tables(head, runs)[0]
    lines = p.with_suffix(".csv").read_text(encoding="utf-8").splitlines()
    n = len(PROVISION_SETS)
    assert lines[1].endswith(f"{n // 2 + n % 2}/{n},{n // 2 + n % 2}/{n},,,")
    assert lines[2] == f'x,"tables+schema, first pass",{n - 1}/{n},{n - 1}/{n},,,'
    assert lines[3] == f'x,"tables+schema, after one repair",{n}/{n},{n - 1}/{n},1,1,1'


def test_structured_route(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from main import app
    from simulation.experiment import structured_run
    c = TestClient(app)
    monkeypatch.setattr(structured_run, "STRUCTURED_DIR", tmp_path / "none")
    assert c.get("/api/research/structured").status_code == 404
    monkeypatch.setattr(structured_run, "load_runs", lambda: [{"set": "x"}])
    monkeypatch.setattr(structured_run, "summary", lambda head, runs: [{"system": "s", "variants": []}])
    d = c.get("/api/research/structured").json()
    assert d["systems"] == [{"system": "s", "variants": []}] and "held-out" in d["note"]
