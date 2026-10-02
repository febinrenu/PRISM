"""
Statute corpus on disk.

    data/corpus/sources.json                       which statutes, from where
    data/corpus/{id}/{version}/source.pdf          downloaded PDF (git-ignored)
    data/corpus/{id}/{version}/source.json         URL, SHA-256, size, fetch time
    data/corpus/{id}/{version}/ast.json            parsed structure (see parser.py)

A statute is identified by (id, version), e.g. ("ITA2025", "amended_fa2026").
"""
import hashlib
import json
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from config import BASE_DIR

CORPUS_DIR = BASE_DIR / "data" / "corpus"
SOURCES_PATH = CORPUS_DIR / "sources.json"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


@dataclass(frozen=True)
class StatuteSource:
    id: str
    title: str
    act_no: str
    version: str
    kind: str
    domain: str
    urls: tuple[str, ...]

    @property
    def dir(self) -> Path:
        return CORPUS_DIR / self.id / self.version

    @property
    def pdf_path(self) -> Path:
        return self.dir / "source.pdf"

    @property
    def key(self) -> str:
        return f"{self.id}/{self.version}"


def load_sources() -> list[StatuteSource]:
    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    return [
        StatuteSource(
            id=s["id"], title=s["title"], act_no=s["act_no"], version=s["version"],
            kind=s["kind"], domain=s["domain"], urls=tuple(s["urls"]),
        )
        for s in data["statutes"]
    ]


def get_source(statute_id: str, version: Optional[str] = None) -> StatuteSource:
    matches = [s for s in load_sources() if s.id == statute_id and (version is None or s.version == version)]
    if not matches:
        raise KeyError(f"Unknown statute {statute_id}" + (f"/{version}" if version else ""))
    return matches[0]


def _ssl_context():
    """Verify against the operating system's trust store when `truststore` is
    available (some government sites serve chains that certifi lacks)."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(source: StatuteSource, force: bool = False, timeout: float = 180.0) -> dict:
    """Download the statute PDF from the first URL that serves a real PDF.
    Records the URL and SHA-256 in source.json. If a PDF is already present
    and its hash matches the record, nothing is downloaded."""
    record_path = source.dir / "source.json"
    if not force and source.pdf_path.exists() and record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("sha256") == sha256_file(source.pdf_path):
            return {**record, "downloaded": False}

    errors = []
    source.dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": _UA},
                      verify=_ssl_context()) as client:
        for url in source.urls:
            try:
                r = client.get(url)
            except httpx.HTTPError as e:
                errors.append(f"{url}: {e}")
                continue
            if r.status_code != 200 or b"%PDF-" not in r.content[:1024]:
                errors.append(f"{url}: HTTP {r.status_code}, not a PDF")
                continue
            tmp = source.pdf_path.with_suffix(".pdf.tmp")
            tmp.write_bytes(r.content)
            tmp.replace(source.pdf_path)
            record = {
                "id": source.id,
                "version": source.version,
                "title": source.title,
                "act_no": source.act_no,
                "url": url,
                "sha256": sha256_file(source.pdf_path),
                "bytes": len(r.content),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            return {**record, "downloaded": True}
    raise RuntimeError(f"Could not download {source.key}:\n  " + "\n  ".join(errors))


def verify(source: StatuteSource) -> bool:
    """True when the local PDF matches the recorded hash."""
    record_path = source.dir / "source.json"
    if not (source.pdf_path.exists() and record_path.exists()):
        return False
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return record.get("sha256") == sha256_file(source.pdf_path)
