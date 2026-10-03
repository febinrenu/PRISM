"""Silver training data: targets are verbatim, parseable and leak-free."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "training"))

import build_dataset as bd  # noqa: E402
from pipeline.extraction.extractor import to_record  # noqa: E402
from pipeline.extraction.units import Unit  # noqa: E402

TEXT = ("In section 87A of the Income-tax Act, for the words \"seven hundred thousand rupees\", the words "
        "\"twelve hundred thousand rupees\" shall be substituted and for the words \"twenty-five thousand rupees\", "
        "the words \"sixty thousand rupees\" shall be substituted.")
UNIT = Unit(unit_id="u1", statute="FA2025/enacted", path="FA2025/s20", kind="section", start=0, end=len(TEXT), text=TEXT)
RAW = json.dumps({"rules": [{
    "modality": "deeming", "subject": None, "agent_class": "individual",
    "conditions": [], "action": "the words \"twelve hundred thousand rupees\" shall be substituted",
    "consequence": None, "exceptions": [], "cross_refs": ["section 87A of the Income-tax Act"],
    "effects": [{"kind": "rebate", "max_income": 1200000, "max_rebate": 60000, "marginal_relief": False,
                 "regime": "new", "quote": "twelve hundred thousand rupees"}],
}]})


def _record(raw: str):
    return to_record(UNIT, "teacher", raw, model="m", model_version=None, cache_key="k")[0]


def test_target_round_trips_through_the_production_parser():
    rec = _record(RAW)
    assert rec.status == "ok" and rec.hallucinated_fields == 0
    ex = bd.example(UNIT, rec)
    target = ex["completion"][0]["content"]
    for quote in [r["action"] for r in json.loads(target)["rules"]] + ["section 87A of the Income-tax Act"]:
        assert quote in TEXT
    again = _record(target)
    assert bd.teachers_agree(rec, again, "u1")
    assert ex["prompt"][0]["content"].endswith(TEXT + "\n")


def test_teachers_disagree_on_a_number():
    a = _record(RAW)
    b = _record(RAW.replace("60000", "25000"))
    assert not bd.teachers_agree(a, b, "u1")


def test_ngram_overlap_detects_quoted_text():
    grams = bd.ngrams(TEXT)
    assert bd.overlap(TEXT, grams) == 1.0
    assert bd.overlap("A registered person shall furnish a return for every tax period within the prescribed time.", grams) == 0.0
