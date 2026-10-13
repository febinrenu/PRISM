"""Check that the manuscript compiles against its generated inputs:
every \\res{} key is defined in tables/numbers.tex, every \\cref target has a
label, every \\input exists and every citation is in the bibliography.

    python paper/check_manuscript.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    tex = (HERE / "sn-article.tex").read_text(encoding="utf-8")
    numbers = (HERE / "tables" / "numbers.tex").read_text(encoding="utf-8")
    bib = (HERE / "sn-article.bib").read_text(encoding="utf-8")
    tables = "".join(p.read_text(encoding="utf-8") for p in (HERE / "tables").glob("*.tex"))

    keys = set(re.findall(r"\\res\{([^}]*)\}", tex))
    defined = set(re.findall(r"\\csname res@(.*?)\\endcsname", numbers))
    labels = set(re.findall(r"\\label\{([^}]*)\}", tex + tables))
    refs = {x.strip() for g in re.findall(r"\\[cC]ref\{([^}]*)\}", tex) for x in g.split(",")}
    inputs = re.findall(r"\\input\{([^}]*)\}", tex)
    cites = {x.strip() for g in re.findall(r"\\cite[pt]?\{([^}]*)\}", tex) for x in g.split(",")}

    problems = []
    problems += [f"undefined result: {k}" for k in sorted(keys - defined)]
    problems += [f"missing label: {r}" for r in sorted(refs - labels)]
    problems += [f"missing input: {i}" for i in inputs if not (HERE / f"{i}.tex").exists()]
    problems += [f"missing citation: {c}" for c in sorted(cites) if "{" + c + "," not in bib]
    for p in problems:
        print(p)
    print(f"{len(keys)} results, {len(refs)} references, {len(inputs)} inputs, {len(cites)} citations: "
          + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
