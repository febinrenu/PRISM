#!/usr/bin/env python
"""
Regenerates THIRD_PARTY_LICENSES.md from what is actually installed.

    python tools/third_party_licenses.py            # run with the backend's virtual environment

Python: every distribution that backend/requirements.txt pulls in (its transitive closure), read
from the installed package metadata. JavaScript: the production dependency tree of frontend/ from
`npm ls --omit=dev`. Models, datasets and fonts are not packages; their terms are the MANUAL table
below, kept by hand because no metadata carries them.
"""
import importlib.metadata as md
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "THIRD_PARTY_LICENSES.md"

BSD_LOOSE = "BSD (3-clause unless the project says otherwise)"

# Names a package's metadata uses for one licence, folded to its SPDX identifier.
SPDX = {
    "apache 2.0": "Apache-2.0", "apache software license": "Apache-2.0", "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0", "apache license version 2.0": "Apache-2.0",
    "apache 2.0 license": "Apache-2.0", "apache-2.0": "Apache-2.0",
    "mit license": "MIT", "mit": "MIT", "isc license": "ISC", "isc": "ISC",
    "bsd license": BSD_LOOSE, "bsd": BSD_LOOSE,
    "3-clause bsd license": "BSD-3-Clause", "python software foundation license": "PSF-2.0",
    "dual license": "Apache-2.0 OR BSD-3-Clause",   # python-dateutil
    "sil open font license": "OFL-1.1",
}
# Longer declarations folded by prefix (the rest must match exactly: "BSD" is not "BSD-3-Clause").
PREFIXES = {
    "dual licensed - gnu affero gpl 3.0": "AGPL-3.0-only OR Artifex Commercial",
    "see license at https://gsap.com": "GSAP standard 'no charge' licence",
    "standard 'no charge' license": "GSAP standard 'no charge' licence",
}


def spdx(raw: str) -> str:
    raw = " ".join(raw.split())
    low = raw.lower()
    if low in SPDX:
        return SPDX[low]
    for k, v in PREFIXES.items():
        if low.startswith(k):
            return v
    return raw or "UNKNOWN"


def py_license(d: md.Distribution) -> str:
    m = d.metadata
    expr = (m.get("License-Expression") or "").strip()
    if expr:
        return expr
    lic = (m.get("License") or "").strip()
    if lic and len(lic) < 80 and "\n" not in lic:
        return spdx(lic)
    classes = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    classes = [c for c in classes if c != "OSI Approved"]
    if classes:
        return spdx(" / ".join(classes))
    return spdx(lic.splitlines()[0][:60]) if lic else "UNKNOWN"


def _name(requirement: str) -> str:
    return re.split(r"[\[<>=!~; (]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def python_closure() -> list[tuple[str, str, str]]:
    dists = {d.metadata["Name"].lower().replace("_", "-"): d for d in md.distributions()}
    lines = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    todo = [_name(x.split("#")[0]) for x in lines if x.split("#")[0].strip() and not x.startswith(("-", "http"))]
    seen: dict[str, md.Distribution] = {}
    while todo:
        name = todo.pop()
        d = dists.get(name)
        if d is None or name in seen:
            continue
        seen[name] = d
        todo.extend(_name(r) for r in (d.requires or []) if "extra ==" not in r)
    return sorted(((d.metadata["Name"], d.version, py_license(d)) for d in seen.values()), key=lambda r: r[0].lower())


def npm_tree() -> list[tuple[str, str, str]]:
    front = ROOT / "frontend"
    out = subprocess.run("npm ls --omit=dev --all --parseable", cwd=front, shell=True, capture_output=True, text=True).stdout
    seen: dict[str, tuple[str, str, str]] = {}
    for p in filter(None, out.splitlines()):
        f = Path(p) / "package.json"
        if not f.exists():
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        name, ver = j.get("name"), j.get("version")
        if not name or not ver or name == "prism-frontend":
            continue
        lic = j.get("license")
        if isinstance(lic, dict):
            lic = lic.get("type")
        if not lic and j.get("licenses"):
            lic = " OR ".join(x.get("type", "?") for x in j["licenses"])
        if not lic and (Path(p) / "LICENSE").exists():
            first = (Path(p) / "LICENSE").read_text(encoding="utf-8", errors="ignore").lstrip()[:40]
            lic = "MIT" if first.startswith("MIT License") else None
        seen[f"{name}@{ver}"] = (name, ver, spdx(str(lic or "UNKNOWN")))
    return sorted(seen.values(), key=lambda r: r[0].lower())


# Not packages: models, datasets, fonts. Terms as published by each owner at the time of writing;
# check the linked card before redistributing anything. A row with no terms is a heading.
MANUAL = [
    ("Models run locally or through a provider", "", ""),
    ("microsoft/Phi-3.5-mini-instruct (local default for extraction and Ask)", "MIT", "model card"),
    ("openai/gpt-oss-120b, gpt-oss-20b (hosted through Groq)", "Apache-2.0", "model card"),
    ("Gemma 2 2B (local, evaluation only)", "Gemma Terms of Use (not an OSI licence)", "model card"),
    ("Llama 3.1 8B (batch evaluation)", "Llama 3.1 Community License (not an OSI licence)", "model card"),
    ("Mistral 7B (batch evaluation)", "Apache-2.0", "model card"),
    ("Other hosted systems named in the evaluation (Qwen, Gemma 4, Nemotron)", "per each model's card; they differ", "provider"),
    ("sentence-transformers/all-MiniLM-L6-v2 (embeddings)", "Apache-2.0", "model card"),
    ("cross-encoder/ms-marco-MiniLM-L-6-v2 (re-ranker)", "Apache-2.0", "model card"),
    ("BAAI/bge-small-en-v1.5 (retrieval benchmark only)", "MIT", "model card"),
    ("spaCy en_core_web_sm", "MIT", "spaCy models"),
    ("RapidOCR / PP-OCR models (scanned pages)", "Apache-2.0", "RapidOCR"),
    ("Data", "", ""),
    ("Statute texts (India Code, e-Gazette, Lok Sabha Bill)", "Government of India publications; see DATA.md", "DATA.md"),
    ("Income Tax Return Statistics and Budget Speech figures", "Government of India publications; extracted tables only", "DATA.md"),
    ("PLFS / HCES microdata", "MoSPI registered-user terms; never redistributed", "DATA.md"),
    ("Human annotations produced for PRISM", "CC BY 4.0", "DATA.md"),
    ("LEDGAR as packaged in LexGLUE (retained record of the v1 evaluation, unused)", "see the LexGLUE dataset card", "dataset card"),
    ("Fonts", "", ""),
    ("Geist, Geist Mono (Vercel)", "SIL Open Font License 1.1", "geist package"),
    ("Instrument Serif (Google Fonts), self-hosted in frontend/public/fonts", "SIL Open Font License 1.1", "Google Fonts"),
]

NOTES = """\
## Terms that need attention

| Component | Terms | What it means here |
|---|---|---|
| **PyMuPDF** (`pymupdf`) | AGPL-3.0, or a commercial licence from Artifex | PRISM reads PDFs with it. The AGPL's network clause applies to anyone who offers a modified PRISM as a service while it is linked in. A closed or commercial deployment needs Artifex's commercial licence or a different PDF reader (the reader sits behind `pipeline/pdf_parser.py` and `pipeline/pdftext/`). |
| **psycopg** | LGPL-3.0 | Used unmodified as a library, which the LGPL allows. |
| **GSAP** (`gsap`, `@gsap/react`) | GSAP "Standard 'no charge' licence" (not an OSI licence) | Free to use, including commercially, but not to build a tool that competes with GSAP's own. Used for the landing page's motion. |
| **Gemma, Llama** | Vendor model licences | Their acceptable-use terms apply to anything built with the weights. They are used only to measure the systems in the evaluation, not shipped. |
| **certifi, hypothesis, tqdm, orjson** | MPL-2.0 (file-level copyleft) | Used unmodified. |
"""


def table(rows) -> str:
    return "| Package | Version | Licence |\n|---|---|---|\n" + "\n".join(f"| {n} | {v} | {lic} |" for n, v, lic in rows) + "\n"


def summary(rows) -> str:
    counts = Counter(lic for _, _, lic in rows)
    return "| Licence | Packages |\n|---|---:|\n" + "\n".join(f"| {lic} | {n} |" for lic, n in counts.most_common()) + "\n"


def main() -> None:
    py, js = python_closure(), npm_tree()
    parts = [
        "# Third-party licences\n\n",
        "PRISM's own code is Apache-2.0 (see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)). It depends on the "
        "components below, each under its own terms.\n\n",
        "This file is generated by `tools/third_party_licenses.py` from the installed package metadata, so it lists "
        "what is there rather than what was remembered. Metadata is only as good as each project's own declaration; "
        "read a package's licence file before redistributing it.\n\n",
        NOTES, "\n",
        f"## Python: {len(py)} packages (`backend/requirements.txt` and everything it installs)\n\n",
        summary(py), "\n<details><summary>Every package</summary>\n\n", table(py), "\n</details>\n\n",
        f"## JavaScript: {len(js)} packages (production tree of `frontend/`)\n\n",
        summary(js), "\n<details><summary>Every package</summary>\n\n", table(js), "\n</details>\n\n",
        "## Models, data and fonts\n\n| Item | Terms | Source |\n|---|---|---|\n",
    ]
    for item, terms, src in MANUAL:
        parts.append(f"| **{item}** | | |\n" if not terms else f"| {item} | {terms} | {src} |\n")
    OUT.write_text("".join(parts), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(py)} Python, {len(js)} JavaScript packages")


if __name__ == "__main__":
    sys.exit(main())
