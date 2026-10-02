"""
Shared test isolation: no test touches the real user database or RAG index.

The SQLite auth database and the ChromaDB directory are redirected to a
per-session temp directory before any test runs. Tests that need an isolated
document store use the `isolated_store` / `api` fixtures in their own modules.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session", autouse=True)
def _isolate_db_and_corpus(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("prism_state")

    from db import database
    mp.setattr(database, "_SQLITE_PATH", root / "prism.db")

    from rag import corpus_builder
    mp.setattr(corpus_builder, "CHROMA_DIR", root / "chromadb")
    mp.setattr(corpus_builder, "_client", None, raising=False)
    mp.setattr(corpus_builder, "_collection", None, raising=False)

    yield root
    mp.undo()
