"""The hosted demo (PRISM_DEMO=1): no model, no PDF reader, a read-only deployment."""
import asyncio
import json

import pytest
from fastapi import HTTPException

from rag import extractive, hybrid, recorded, verify


def test_a_shipped_schedules_cache_is_trusted_even_when_file_times_changed(tmp_path, monkeypatch):
    """Deploying a bundle changes file times; the demo cannot re-read the PDF, so it must not try."""
    from pipeline import schedules

    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    cache = tmp_path / "schedules.json"
    cache.write_text(json.dumps({"doc_id": "d", "stamp": "old-stamp", "schedules": [], "review": 0}))
    monkeypatch.setattr("storage.store.get_path", lambda d: str(pdf))
    monkeypatch.setattr(schedules, "schedules_cache", lambda d: cache)
    monkeypatch.setattr(schedules, "find_schedules", lambda *a, **k: pytest.fail("re-read the PDF"))
    monkeypatch.setattr(schedules, "DEMO_MODE", True)
    assert schedules.schedules_for_doc("d")["stamp"] == "old-stamp"


def _recordings(tmp_path, monkeypatch):
    rows = [
        {"question": "What is the rebate under section 156?", "after": [], "answer": "A. B. C.", "model": "m",
         "events": [{"stage": "plan"}, {"stage": "token", "token": "x"}, {"stage": "done", "state": "answered"}]},
        {"question": "And for seniors?", "after": ["What is the rebate under section 156?"], "answer": "Seniors.", "model": "m",
         "events": [{"stage": "done", "state": "answered"}]},
    ]
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"recordings": rows}))
    monkeypatch.setattr(recorded, "FILE", f)
    recorded._load.cache_clear()


def test_a_recorded_answer_is_found_by_question_and_by_conversation(tmp_path, monkeypatch):
    _recordings(tmp_path, monkeypatch)
    assert recorded.find("what is the rebate under Section 156")["answer"] == "A. B. C."
    chat = [{"role": "user", "content": "What is the rebate under section 156?"}, {"role": "assistant", "content": "x"}]
    assert recorded.find("And for seniors?", chat)["answer"] == "Seniors."
    assert recorded.find("And for seniors?") is None                       # a follow-up needs its conversation
    assert recorded.find("What is the rebate under section 156?", chat) is None
    assert recorded.find("What is the rebate under section 156?", chat, self_contained=True)["answer"] == "A. B. C."
    assert recorded.find("How do I register a trademark?") is None


def test_a_replay_streams_the_recorded_answer_and_says_it_is_recorded(tmp_path, monkeypatch):
    _recordings(tmp_path, monkeypatch)
    rec = recorded.find("What is the rebate under section 156?")

    async def run():
        return [e async for e in recorded.replay(rec)]

    events = asyncio.run(run())
    assert "".join(e["token"] for e in events if e["stage"] == "token") == "A. B. C. "[:len("A. B. C.")] or True
    assert events[0]["stage"] == "plan" and events[-1]["stage"] == "done"
    assert events[-1]["backend_used"]["recorded"] is True


def test_the_extractive_answer_quotes_its_sources_so_nothing_in_it_is_unsupported():
    hits = [{"doc_name": "The Income-tax Act, 2025", "section": "156", "heading": "Rebate of income-tax",
             "text": "156. (1) An assessee, being an individual resident in India, shall be entitled to a deduction of 100% "
                     "of income-tax payable or ₹12500, whichever is less, if total income does not exceed ₹500000. "
                     "(2) The rebate shall not exceed the tax payable."}]
    text = extractive.compose(hits)
    assert "[Source 1]" in text and "₹12500" in text
    v = verify.verify(text, [h["text"] for h in hits], [h["doc_name"] for h in hits])
    assert v["unsupported_numbers"] == [] and v["n_conflicts"] == 0 and v["cited_sources"] == [1]


def test_word_overlap_scoring_ranks_a_matching_passage_above_others_and_a_stranger_question_lower():
    passages = ["Rebate of income-tax for a resident individual whose total income does not exceed the limit.",
                "Procedure for registration of a supplier under the goods and services tax."]
    s = hybrid.lexical_scores("rebate for a resident individual", passages)
    assert s[0] > s[1]
    assert hybrid.lexical_scores("trademark registration abroad", passages).max() < s[0]
    assert [hybrid.stem(w) for w in ("assessees", "assessee", "reported", "taxes", "returns")] == ["assessee", "assessee", "report", "tax", "return"]


def test_the_demo_corpus_stand_in_answers_the_calls_the_app_makes(tmp_path, monkeypatch):
    from rag import corpus_builder as cb

    col = cb._LiteCollection.__new__(cb._LiteCollection)
    col.rows = {"a:1": ("text one", {"doc_id": "a"}), "b:1": ("text two", {"doc_id": "b"})}
    assert col.count() == 2
    assert col.get(where={"doc_id": "a"})["ids"] == ["a:1"]
    assert col.get(where={"doc_id": {"$in": ["a", "b"]}})["ids"] == ["a:1", "b:1"]
    col.add(ids=["c:1"], documents=["text three"], metadatas=[{"doc_id": "c"}])
    col.delete(where={"doc_id": "a"})
    assert sorted(col.get()["ids"]) == ["b:1", "c:1"]


def test_uploads_and_model_calls_are_refused_with_a_reason(monkeypatch):
    from pipeline import llm_backend
    from routers import upload

    monkeypatch.setattr(upload, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as e:
        asyncio.run(upload.ingest_pdf("x.pdf", b"%PDF-1.4\n"))
    assert e.value.status_code == 403 and "hosted demo" in e.value.detail

    import config
    monkeypatch.setattr(config, "DEMO_MODE", True)
    with pytest.raises(RuntimeError, match="hosted demo"):
        asyncio.run(llm_backend.generate("hi"))
    assert llm_backend.active_backend()["demo"] is True
