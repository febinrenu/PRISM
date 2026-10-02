"""Disk-backed store — round-trips survive a cache wipe (simulated restart)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    import config
    from storage import store

    monkeypatch.setattr(config, "STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
    store._meta_store.clear()
    store._result_store.clear()
    store._embeddings_cache.clear()
    yield store
    store._meta_store.clear()
    store._result_store.clear()
    store._embeddings_cache.clear()


def _wipe_caches(store):
    store._meta_store.clear()
    store._result_store.clear()
    store._embeddings_cache.clear()


def test_meta_and_result_roundtrip(isolated_store):
    store = isolated_store
    from models.schemas import AnalysisResult, Clause, DocumentMeta, GraphData

    meta = DocumentMeta(doc_id="t1", filename="x.pdf", pages=3, file_size_kb=10.0, pdf_path="p.pdf")
    store.save_meta(meta)

    clause = Clause(
        clause_id="t1_c0000", doc_id="t1", page=1, section_hierarchy=["1"],
        text="The assessee shall file the return.", char_start=0, char_end=35,
    )
    result = AnalysisResult(doc_id="t1", clauses=[clause], graph=GraphData(nodes=[], edges=[]), stats={"total_clauses": 1})
    store.save_result(result)

    _wipe_caches(store)  # simulate restart

    reloaded_meta = store.get_meta("t1")
    assert reloaded_meta is not None and reloaded_meta.pdf_path == "p.pdf"
    assert reloaded_meta.status == "complete"  # save_result marks complete
    reloaded = store.get_result("t1")
    assert reloaded is not None and reloaded.clauses[0].clause_id == "t1_c0000"
    import config
    # Relative stored paths resolve against the backend directory.
    assert store.get_path("t1") == str(config.BASE_DIR / "p.pdf")


def test_pdf_paths_are_portable(isolated_store):
    store = isolated_store
    import config

    inside = config.BASE_DIR / "data" / "demo" / config.DEMO_PDF_NAME
    assert store.to_stored_path(str(inside)) == f"data/demo/{config.DEMO_PDF_NAME}"
    # An absolute path recorded on another machine is re-rooted under this
    # checkout when the file exists here.
    foreign = rf"D:\elsewhere\prism\backend\data\demo\{config.DEMO_PDF_NAME}"
    assert store.resolve_stored_path(foreign) == str(config.BASE_DIR / "data" / "demo" / config.DEMO_PDF_NAME)
    assert store.resolve_stored_path(None) is None


@pytest.mark.parametrize("bad", ["..", "../etc", "a/b", "a\\b", "x.y", "", "a" * 65])
def test_invalid_doc_ids_are_rejected(isolated_store, bad):
    store = isolated_store
    assert not store.is_valid_doc_id(bad)
    assert store.get_meta(bad) is None
    assert store.get_result(bad) is None
    with pytest.raises(store.InvalidDocId):
        store.load_embeddings(bad)


def test_embeddings_roundtrip(isolated_store):
    store = isolated_store
    arr = np.random.default_rng(0).random((5, 384)).astype(np.float32)
    store.save_embeddings("t2", arr)

    _wipe_caches(store)

    loaded = store.load_embeddings("t2")
    assert loaded is not None
    np.testing.assert_allclose(loaded, arr)
    assert store.load_embeddings("missing") is None


def test_llm_and_lime_caches(isolated_store):
    store = isolated_store
    store.save_llm_extractions("t3", {"model": "phi3.5", "entries": {"c1": {"key": "abc"}}})
    payload = {"fingerprint": "f1", "lime_tokens": []}
    store.save_lime("t3", "c1", "proxy", payload)

    assert store.load_llm_extractions("t3")["entries"]["c1"]["key"] == "abc"
    assert store.load_lime("t3", "c1", "proxy")["fingerprint"] == "f1"
    assert store.load_lime("t3", "c1", "llm") is None


def test_update_result_mutates_atomically(isolated_store):
    store = isolated_store
    from models.schemas import AnalysisResult, Clause, DocumentMeta, GraphData

    store.save_meta(DocumentMeta(doc_id="t4", filename="y.pdf", pages=1, file_size_kb=1.0))
    clause = Clause(
        clause_id="t4_c0000", doc_id="t4", page=1, section_hierarchy=[],
        text="Where default occurs, a penalty shall be levied.", char_start=0, char_end=48,
    )
    store.save_result(AnalysisResult(doc_id="t4", clauses=[clause], graph=GraphData(nodes=[], edges=[]), stats={}))

    def mutate(result):
        result.clauses[0].lime_available = True

    store.update_result("t4", mutate)
    _wipe_caches(store)
    assert store.get_result("t4").clauses[0].lime_available is True
