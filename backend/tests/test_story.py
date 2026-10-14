"""Landing-story snapshot: sourced, consistent with the paper, deterministic."""
import json
import re

import pytest

from simulation.experiment import story

needs_results = pytest.mark.skipif(
    not (story.RESULTS_DIR / f"{story.FOCUS_SET}__{story.FOCUS_SYSTEM}.json").exists(),
    reason="experiment results are not present (they are not in the repository)")


# ── the pipeline section: built from the tracked demo document only ────────

@pytest.fixture(scope="module")
def pipe():
    return story.pipeline()


def test_pipeline_numbers_are_the_document_stats(pipe):
    part, _ = pipe
    stats = json.loads(story.DEMO_RESULT.read_text(encoding="utf-8"))["stats"]
    n = part["numbers"]
    assert n["pages"]["value"] == f"{stats['total_pages']:,}"
    assert n["clauses"]["value"] == f"{stats['total_clauses']:,}"
    assert n["nodes"]["value"] == f"{stats['graph_nodes']:,}"
    for k, v in stats["entity_type_counts"].items():
        assert n[f"entity@{k}"]["value"] == f"{v:,}"
    for entry in n.values():
        assert (story.ROOT / entry["source"]["file"]).exists()


def test_pipeline_samples_quote_their_clauses(pipe):
    part, _ = pipe
    assert len(part["samples"]) == 3
    for smp in part["samples"]:
        assert smp["entities"] and smp["causal"]
        for _, a, b in smp["entities"]:
            assert 0 <= a < b <= len(smp["text"])
        for c0, c1, a0, a1, risk in smp["causal"]:
            assert c0 < c1 <= len(smp["text"]) and a0 < a1 <= len(smp["text"])
            assert risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert story.pipeline()[0]["samples"] == part["samples"]


def test_pipeline_graph_sample_is_a_forest(pipe):
    _, graph = pipe
    assert len(graph["nodes"]) <= story.GRAPH_CAP
    for i, row in enumerate(graph["nodes"]):
        assert row[1] < i
    assert all(graph["nodes"][b][0] == graph["types"].index("entity") for _, b in graph["links"])
    assert all(graph["nodes"][h["i"]][0] == graph["types"].index("clause") for h in graph["hubs"])


def test_chat_is_a_real_retrieval():
    core = json.loads(story.CORE_OUT.read_text(encoding="utf-8"))
    chat = core["chat"]
    assert chat["qid"] == story.CHAT_QID and len(chat["citations"]) == 5
    assert [c["rank"] for c in chat["citations"]] == [1, 2, 3, 4, 5]
    assert any(c["relevant"] for c in chat["citations"])


@pytest.fixture(scope="module")
def built():
    return story.build()


@needs_results
def test_snapshot_files_are_current():
    stale = [str(p) for p, fresh in story.export(check=True) if not fresh]
    assert not stale, f"run `python -m cli story-export`: {stale}"


@needs_results
def test_every_number_comes_from_the_paper(built):
    core = built[0]
    tex = story.NUMBERS_TEX.read_text(encoding="utf-8")
    for key, entry in core["numbers"].items():
        assert entry["source"] == {"file": "paper/tables/numbers.tex", "key": key}
        assert "res@" + key + "\\endcsname{" + entry["value"] + "}" in tex


@needs_results
def test_sources_resolve(built):
    core, pop, const = built[:3]
    files = [c["source"]["file"] for c in core["matrix"]["cells"] if "source" in c]
    files += [core["focus"]["source"]["file"], core["injection"]["source"]["file"],
              core["behaviour"]["source"]["file"], const["source"]["file"], core["curve"]["source"]["system"]]
    for f in files:
        assert (story.ROOT / f).exists(), f


@needs_results
def test_matrix_matches_the_paper(built):
    core = built[0]
    nums = core["numbers"]
    for s in core["matrix"]["systems"]:
        cells = [c for c in core["matrix"]["cells"] if c["system"] == s["id"]]
        assembled = [c for c in cells if c.get("status") == "assembled"]
        assert str(len(assembled)) == nums[f"assembled@{s['id']}"]["value"]
        assert str(sum(c["flips"] for c in assembled)) == nums[f"flips@{s['id']}"]["value"]
        worst = max((c["revenue_error_crore"] for c in assembled), default=0)
        assert f"{worst:,.0f}" == nums[f"maxreverr@{s['id']}"]["value"]


@needs_results
def test_focus_case_is_the_marginal_relief_misread(built):
    core = built[0]
    f = core["focus"]
    assert f["expert"]["marginal_relief"] is True and f["extracted"]["marginal_relief"] is False
    assert f["param_diff"] == ["regimes.new.rebate.marginal_relief"]
    gap = core["curve"]["largest_gap"]
    assert gap["system"] > gap["expert"]
    # The quoted span is a substring of the provision text it cites.
    for e in f["effects"]:
        if e.get("span"):
            a, b = e["span"]
            assert f["text"][a:b] == e["quote"]


@needs_results
def test_population_is_weighted_and_complete(built):
    pop = built[1]
    assert pop["columns"] == ["income", "returns", "decile", "tax_before", "tax_expert", "tax_system"]
    incomes = [r[0] for r in pop["rows"]]
    assert incomes == sorted(incomes)
    assert {r[2] for r in pop["rows"]} == set(range(1, 11))
    assert abs(sum(r[1] for r in pop["rows"]) - pop["returns_total"]) / pop["returns_total"] < 1e-3


@needs_results
def test_constellation_parents_precede_children(built):
    const = built[2]
    for i, n in enumerate(const["nodes"]):
        assert n["p"] < i
    for t in const["thread"]:
        assert const["nodes"][t]["k"] == "section"


@needs_results
def test_api_serves_the_snapshot():
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/api/research/story")
    assert r.status_code == 200 and r.json()["version"] == 1
    d = c.get("/api/research/population/2026-27").json()
    assert len(d["deciles"]) == 10 and d["system"] is None
    d = c.get(f"/api/research/population/{story.FOCUS_SET}/{story.FOCUS_SYSTEM}").json()
    assert d["system"] == story.FOCUS_SYSTEM
    assert c.get("/api/research/population/1999-00").status_code == 404
    assert re.match(r"\d{4}-\d{2}", d["ay"])
