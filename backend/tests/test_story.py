"""Landing-story snapshot: sourced, consistent with the paper, deterministic."""
import json
import re

import pytest

from simulation.experiment import story


@pytest.fixture(scope="module")
def built():
    return story.build()


def test_snapshot_files_are_current():
    stale = [str(p) for p, fresh in story.export(check=True) if not fresh]
    assert not stale, f"run `python -m cli story-export`: {stale}"


def test_every_number_comes_from_the_paper(built):
    core, _, _ = built
    tex = story.NUMBERS_TEX.read_text(encoding="utf-8")
    for key, entry in core["numbers"].items():
        assert entry["source"] == {"file": "paper/tables/numbers.tex", "key": key}
        assert "res@" + key + "\\endcsname{" + entry["value"] + "}" in tex


def test_sources_resolve(built):
    core, pop, const = built
    files = [c["source"]["file"] for c in core["matrix"]["cells"] if "source" in c]
    files += [core["focus"]["source"]["file"], core["injection"]["source"]["file"],
              core["behaviour"]["source"]["file"], const["source"]["file"], core["curve"]["source"]["system"]]
    for f in files:
        assert (story.ROOT / f).exists(), f


def test_matrix_matches_the_paper(built):
    core, _, _ = built
    nums = core["numbers"]
    for s in core["matrix"]["systems"]:
        cells = [c for c in core["matrix"]["cells"] if c["system"] == s["id"]]
        assembled = [c for c in cells if c.get("status") == "assembled"]
        assert str(len(assembled)) == nums[f"assembled@{s['id']}"]["value"]
        assert str(sum(c["flips"] for c in assembled)) == nums[f"flips@{s['id']}"]["value"]
        worst = max((c["revenue_error_crore"] for c in assembled), default=0)
        assert f"{worst:,.0f}" == nums[f"maxreverr@{s['id']}"]["value"]


def test_focus_case_is_the_marginal_relief_misread(built):
    core, _, _ = built
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


def test_population_is_weighted_and_complete(built):
    _, pop, _ = built
    assert pop["columns"] == ["income", "returns", "decile", "tax_before", "tax_expert", "tax_system"]
    incomes = [r[0] for r in pop["rows"]]
    assert incomes == sorted(incomes)
    assert {r[2] for r in pop["rows"]} == set(range(1, 11))
    assert abs(sum(r[1] for r in pop["rows"]) - pop["returns_total"]) / pop["returns_total"] < 1e-3


def test_constellation_parents_precede_children(built):
    _, _, const = built
    for i, n in enumerate(const["nodes"]):
        assert n["p"] < i
    for t in const["thread"]:
        assert const["nodes"][t]["k"] == "section"


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
