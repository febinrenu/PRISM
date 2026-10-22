"""The post-hoc rule baseline (rules-v2): its two fixes work, and version 1,
as reported, is unchanged."""
import json

import pytest

from pipeline.extraction.rule_based import _row_text, _slab_from_line
from pipeline.statute.corpus import CORPUS_DIR

needs_corpus = pytest.mark.skipif(not (CORPUS_DIR / "FA2024N2" / "enacted" / "text.txt").exists(),
                                  reason="corpus not parsed")
ROW = "(4) where the total income exceeds Rs. 10 ,00,000 | Rs. 1,10,000 plus 30 per cent. of the amount"


def test_split_figure_is_joined_in_v2_only():
    assert _slab_from_line(_row_text(ROW, 1))["lower"] == 10.0          # the reported defect, kept in v1
    assert _slab_from_line(_row_text(ROW, 2))["lower"] == 1000000.0
    # only a figure split before its comma is joined; other commas are left alone
    assert _row_text("Rs. 5,00,000 , and Rs. 7", 2) == "Rs. 5,00,000 , and Rs. 7"


@needs_corpus
def test_unlabelled_schedule_is_in_view_2_only():
    from pipeline.statute import tables as T
    v1 = {(t.start, t.end) for t in T.load("FA2024N2/enacted")}
    new = [t for t in T.load_v2("FA2024N2/enacted") if (t.start, t.end) not in v1]
    assert len(new) == 1 and new[0].page == 86 and all(r.exact and r.label == "" for r in new[0].rows)
    assert [r.cells[1].split(" per cent")[0][-2:].strip() for r in new[0].rows[1:]] == ["20", "30"]


@needs_corpus
def test_view_1_files_do_not_change():
    import hashlib

    from pipeline.statute import tables as T
    for key in ("FA2024N2/enacted", "FA2020/enacted"):
        st, ver = key.split("/")
        on_disk = (CORPUS_DIR / st / ver / "tables.json").read_text(encoding="utf-8")
        rebuilt = json.dumps(T.build(st, ver), indent=1, ensure_ascii=False)
        assert hashlib.sha256(on_disk.encode()).hexdigest() == hashlib.sha256(rebuilt.encode()).hexdigest(), key


@needs_corpus
def test_v2_reads_both_heldout_defects_and_v1_still_does_not():
    from pipeline.extraction.rule_based import extract_unit
    from pipeline.extraction.structured import extract_unit as structured_unit
    from pipeline.extraction.units import build_units
    from simulation.experiment.provision_sets import HELD_OUT_SETS, units_for

    def bands(rec):
        return [(e.lower, e.upper, e.rate) for r in rec.rules for e in r.effects if e.kind == "slab_row"]

    u = units_for(HELD_OUT_SETS["HO_FA2020_partIII"]["targets"]["old.slabs.60_to_80"], build_units("FA2020", "enacted"))[0]
    assert bands(extract_unit(u, version=1)[0])[-1][0] == 10.0
    assert bands(extract_unit(u, version=2)[0])[-1] == (1000000.0, None, 0.3)
    u = units_for(HELD_OUT_SETS["HO_FA2024N2_partIII"]["targets"]["old.slabs.80_plus"], build_units("FA2024N2", "enacted"))[0]
    assert bands(structured_unit(u, "rules")[0]) == []
    assert bands(structured_unit(u, "rules-v2")[0]) == [(0.0, 500000.0, 0.0), (500000.0, 1000000.0, 0.2),
                                                         (1000000.0, None, 0.3)]


def test_v2_results_stay_out_of_the_reported_tables():
    """rules-v2 writes to its own folder; the headline, structured and
    held-out loaders never see it."""
    from simulation.experiment import heldout, rules_v2, structured_run
    from simulation.experiment.stats import load_runs
    assert rules_v2.OUT_DIR.name == "rules_v2"
    assert not any(r["system"] == "rules-v2" for r in load_runs() + structured_run.load_runs() + heldout.load())
    assert "post-hoc" in rules_v2.NOTE and "not a held-out test" in rules_v2.NOTE
