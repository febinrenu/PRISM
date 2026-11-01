#!/usr/bin/env python
"""
Assembles deploy/api/: the hosted demo's API as a Vercel Python function.

    python tools/build_hosted_bundle.py             # then: cd deploy/api && vercel deploy --prod

Run it with the project's environment (it copies lime and SALib from there).

What goes in: the backend's code, the lightweight requirements (backend/requirements.vercel.txt:
no PyTorch, spaCy, ChromaDB or OCR), the parsed statutes (text and tree, not the source PDFs),
the analysed demo documents with their PDFs, the recorded research results, and what the hosted
mode searches and replays (data/demo/passages.jsonl.gz, data/demo/ask_recordings.json).
What stays out: tests, caches, raw downloads, the vector index, uploads and every secret.
"""
import importlib.metadata as md
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT = ROOT / "deploy" / "api"

CODE_DIRS = ["auth", "db", "eval", "models", "pipeline", "policy", "rag", "routers", "services",
             "simulation", "storage"]
CODE_FILES = ["main.py", "config.py", "prism_version.py"]
SKIP_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_SUFFIX = {".pyc", ".pdf"}                       # the corpus PDFs; the demo PDFs are copied on their own

DEMO_DOCS = ["demo_income_tax_2025", "41f81963-1809-467d-aeb4-885564035ff7", "a6f7cc86-f612-4c3f-bdfc-4c20c92c503c"]


def copy_tree(src: Path, dst: Path, *, keep_pdf: bool = False) -> None:
    for p in src.rglob("*"):
        if any(part in SKIP_NAMES for part in p.parts) or p.is_dir():
            continue
        if p.suffix in SKIP_SUFFIX and not (keep_pdf and p.suffix == ".pdf"):
            continue
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def vendor(package: str, distribution: str) -> None:
    """Copy an installed pure-Python package into the bundle, with its licence, instead of installing it
    (its metadata declares dependencies the parts used here never import)."""
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.origin:
        sys.exit(f"{package} is not installed in this environment; run the builder with the project's venv")
    copy_tree(Path(spec.origin).parent, OUT / package)
    for f in md.distribution(distribution).files or []:
        if "LICENSE" in f.name.upper():
            shutil.copy2(f.locate(), OUT / f"{package}.{f.name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():                          # start clean, but keep the Vercel project link
        if old.name not in (".vercel", ".env.local"):
            shutil.rmtree(old) if old.is_dir() else old.unlink()

    for d in CODE_DIRS:
        copy_tree(BACKEND / d, OUT / d)
    for f in CODE_FILES:
        shutil.copy2(BACKEND / f, OUT / f)
    vendor("lime", "lime")
    vendor("SALib", "SALib")

    data = BACKEND / "data"
    copy_tree(data / "corpus", OUT / "data" / "corpus")                    # ast.json, text.txt, source.json, tables.json
    copy_tree(data / "demo", OUT / "data" / "demo", keep_pdf=True)         # the demo PDF, passages, recordings
    for doc in DEMO_DOCS:
        copy_tree(data / "store" / doc, OUT / "data" / "store" / doc)
        pdf = data / "uploads" / f"{doc}.pdf"
        if pdf.exists():
            (OUT / "data" / "uploads").mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, OUT / "data" / "uploads" / pdf.name)
    copy_tree(data / "experiments", OUT / "data" / "experiments")
    for sub in ("eval/v2/manifest.json",):
        src = data / sub
        if src.exists():
            (OUT / "data" / sub).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, OUT / "data" / sub)

    # what story.py reads from the repository, under repo/ (config: a bundled repo/ directory is the repo root)
    for name in ("numbers.tex",):
        src = ROOT / "paper" / "tables" / name
        if src.exists():
            (OUT / "repo" / "paper" / "tables").mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, OUT / "repo" / "paper" / "tables" / name)

    shutil.copy2(BACKEND / "requirements.vercel.txt", OUT / "requirements.txt")
    (OUT / ".python-version").write_text("3.12\n", encoding="utf-8")
    (OUT / "vercel.json").write_text(json.dumps({
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "functions": {"main.py": {"maxDuration": 60}},
    }, indent=2) + "\n", encoding="utf-8")
    (OUT / ".vercelignore").write_text("__pycache__\n*.pyc\n.env\n.env.local\n.venv\n", encoding="utf-8")

    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    count = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"wrote {OUT.relative_to(ROOT)}: {count} files, {size / 1e6:.0f} MB")


if __name__ == "__main__":
    sys.exit(main())
