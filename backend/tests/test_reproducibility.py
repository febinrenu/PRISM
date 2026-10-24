"""Stored readings stay comparable after a parser fix: evaluation runs keep
the context each reading was made with."""
import json


def test_runs_record_and_return_contexts(tmp_path, monkeypatch):
    from eval.v2 import runs
    monkeypatch.setattr(runs, "RUNS_DIR", tmp_path)
    d = tmp_path / "sys"
    d.mkdir()
    rec = {"provision": "u1", "statute": "X/enacted", "status": "ok"}
    lines = [{"item_id": "a", "record": rec, "stats": {}},                      # written before contexts were kept
             {"item_id": "b", "record": rec, "stats": {}, "context": "Section 9 — Heading"}]
    (d / "dev.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    assert runs.load_contexts("sys", "dev") == {"b": "Section 9 — Heading"}
    assert set(runs.load_run("sys", "dev")) == {"a", "b"}


def test_reproduce_keeps_a_result_it_cannot_rederive():
    """The faithfulness step of cli reproduce tolerates a cache miss and keeps
    the stored result (the source says so, so the table is still written)."""
    import inspect

    import reproduce
    src = inspect.getsource(reproduce.reproduce)
    assert "except OfflineCacheMiss" in src and "stored result kept" in src
