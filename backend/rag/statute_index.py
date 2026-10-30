"""
The parsed statute corpus as a searchable part of the Ask index.

data/corpus holds twelve parsed statute texts (pipeline/statute). Each section is
split at its sub-section boundaries into passages of at most MAX_CHARS, embedded
with the same MiniLM encoder as the analysed documents, and stored in the same
Chroma collection under a doc_id "statute:<id>:<version>". Ask then answers from
exact statute text, cites a section, and can compare two Acts.

Indexing is idempotent and per statute: a stamp of the parsed file and the chunker
version is kept beside the collection, and a statute is re-indexed only when it
changed.
"""
import json
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from config import CHROMA_DIR
from pipeline.statute.corpus import CORPUS_DIR

CHUNKER_VERSION = 2
MAX_CHARS = 1600
# A section the law has since removed leaves a one-line stub ("88A. [Omitted by the
# Finance Act, 2005 …]") that carries no law but matches a query by its heading.
_STUB = re.compile(r"^\s*(?:[\w-]+\.\s*)?(?:\[\s*(?:omitted|repealed|\*\*\*)|\(?omitted\b)", re.IGNORECASE)
_STUB_MAX = 400
DOC_PREFIX = "statute:"
_STAMPS = "statute_stamps.json"
_lock = threading.Lock()


def doc_id_for(statute: str, version: str) -> str:
    return f"{DOC_PREFIX}{statute}:{version}"


def is_statute_doc(doc_id: str) -> bool:
    return bool(doc_id) and doc_id.startswith(DOC_PREFIX)


def split_doc_id(doc_id: str) -> tuple[str, str]:
    _, statute, version = doc_id.split(":", 2)
    return statute, version


@dataclass
class Passage:
    id: str
    doc_id: str
    doc_name: str
    section: str          # "156", or "First Schedule"
    heading: str
    node_path: str        # the section's path in the AST, e.g. "ITA2025/s156"
    first_label: str      # the first sub-provision in the passage, "(2)" or ""
    page: int
    text: str


@lru_cache(maxsize=16)
def _load(statute: str, version: str, stamp: str) -> tuple[dict, str]:
    base = CORPUS_DIR / statute / version
    ast = json.loads((base / "ast.json").read_text(encoding="utf-8"))
    text = (base / "text.txt").read_text(encoding="utf-8")
    return ast, text


def available() -> list[tuple[str, str]]:
    return sorted((p.parent.parent.name, p.parent.name) for p in CORPUS_DIR.glob("*/*/ast.json"))


def _stamp(statute: str, version: str) -> str:
    p = CORPUS_DIR / statute / version / "ast.json"
    s = p.stat()
    return f"{int(s.st_mtime)}:{s.st_size}:{CHUNKER_VERSION}"


def load_statute(statute: str, version: str) -> tuple[dict, str]:
    return _load(statute, version, _stamp(statute, version))


def title_of(statute: str, version: str) -> str:
    ast, _ = load_statute(statute, version)
    return ast.get("title") or statute


def _split_plain(text: str, max_chars: int) -> list[str]:
    """Greedy split of an unstructured run of text on line breaks, then on spaces."""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > max_chars:                  # a single enormous line
            cut = line.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:cut])
            line = line[cut:].lstrip()
        if cur and len(cur) + 1 + len(line) > max_chars:
            out.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return [p for p in (x.strip() for x in out) if p]


def _pieces(node: dict, by_id: dict, text: str, max_chars: int) -> list[tuple[str, str]]:
    """(label, text) pieces covering `node`, none longer than max_chars where the
    structure allows: whole when it fits, else its own opening words followed by
    its children, recursively; a leaf that is still too long is split on lines."""
    body = text[node["start"]:node["end"]]
    label = node.get("label") or ""
    if len(body) <= max_chars:
        return [(label, body)] if body.strip() else []
    kids = sorted((by_id[c] for c in node.get("children", []) if c in by_id), key=lambda n: n["start"])
    if not kids:
        return [(label, p) for p in _split_plain(body, max_chars)]
    out: list[tuple[str, str]] = []
    opening = text[node["start"]:kids[0]["start"]]
    if opening.strip():
        out += [(label, p) for p in _split_plain(opening, max_chars)]
    for k in kids:
        out += _pieces(k, by_id, text, max_chars)
    return out


def _pack(pieces: list[tuple[str, str]], max_chars: int) -> list[tuple[str, str]]:
    """Merge neighbouring small pieces into passages of up to max_chars."""
    out: list[tuple[str, str]] = []
    for label, body in pieces:
        if out and len(out[-1][1]) + 1 + len(body) <= max_chars:
            out[-1] = (out[-1][0], out[-1][1] + "\n" + body)
        else:
            out.append((label, body))
    return out


def passages(statute: str, version: str, max_chars: int = MAX_CHARS) -> list[Passage]:
    """Every passage of a statute: its sections and schedules, split to size."""
    ast, text = load_statute(statute, version)
    nodes = ast["nodes"]
    by_id = {n["node_id"]: n for n in nodes}
    title = ast.get("title") or statute
    doc_id = doc_id_for(statute, version)
    out: list[Passage] = []
    for n in nodes:
        if n["quoted"] or n["kind"] not in ("section", "schedule"):
            continue
        number = str(n.get("number") or n.get("label") or "")
        section = number if n["kind"] == "section" else (f"{number} Schedule".strip() or "Schedule")
        heading = n.get("heading") or ""
        whole = text[n["start"]:n["end"]]
        if len(whole) <= _STUB_MAX and _STUB.match(whole):
            continue            # a removed section: still reachable by number, not by search
        for k, (label, body) in enumerate(_pack(_pieces(n, by_id, text, max_chars), max_chars)):
            out.append(Passage(
                id=f"{doc_id}::{n['path']}#{k}", doc_id=doc_id, doc_name=title, section=section,
                heading=heading, node_path=n["path"], first_label=f"({label})" if label and label != number else "",
                page=int(n.get("page") or 0), text=body,
            ))
    return out


def embed_text(p: Passage) -> str:
    """What is embedded: the passage with its act, section and heading in front, so
    a query about 'rebate' finds section 156 even where the word is only in the heading."""
    return f"{p.doc_name}, section {p.section}. {p.heading}\n{p.text}"


def _stamps_path():
    return CHROMA_DIR / _STAMPS


def _read_stamps() -> dict:
    try:
        return json.loads(_stamps_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_stamps(stamps: dict) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _stamps_path().write_text(json.dumps(stamps), encoding="utf-8")


def pending() -> int:
    """How many statutes are not (yet) in the index, for a progress note in the UI."""
    stamps = _read_stamps()
    return sum(1 for s, v in available() if stamps.get(doc_id_for(s, v)) != _stamp(s, v))


def ensure_indexed(force: bool = False, log=print) -> dict:
    """Index every statute that is missing or changed. Returns {doc_id: passages}."""
    from pipeline.embedder import embed_texts
    from rag import corpus_builder

    done: dict[str, int] = {}
    with _lock:
        stamps = _read_stamps()
        collection = corpus_builder._get_collection()
        for statute, version in available():
            doc_id = doc_id_for(statute, version)
            stamp = _stamp(statute, version)
            if not force and stamps.get(doc_id) == stamp:
                continue
            ps = passages(statute, version)
            try:
                collection.delete(where={"doc_id": doc_id})
            except Exception:
                pass
            for i in range(0, len(ps), 256):
                batch = ps[i:i + 256]
                embs = embed_texts([embed_text(p) for p in batch])
                collection.add(
                    ids=[p.id for p in batch],
                    embeddings=[e.astype(float).tolist() for e in embs],
                    documents=[p.text for p in batch],
                    metadatas=[{
                        "doc_id": p.doc_id, "doc_name": p.doc_name, "clause_id": p.id,
                        "section": p.section, "heading": p.heading, "page": p.page,
                        "entity_types": "", "has_causal": False, "kind": "statute",
                        "node_path": p.node_path, "first_label": p.first_label,
                        "statute_key": f"{statute}/{version}",
                    } for p in batch],
                )
            stamps[doc_id] = stamp
            _write_stamps(stamps)
            done[doc_id] = len(ps)
            log(f"[ok] statute indexed: {doc_id} ({len(ps)} passages)")
    return done
