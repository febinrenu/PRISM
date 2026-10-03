"""
Income Tax Return Statistics (Income Tax Department), individual returns.

Each annual report has, for individuals:
    2.1   Range of Gross Total Income    — returns and total GTI per income band
    2.10  Range of Returned Income       — returns and total returned income
    2.11  Range of Tax Payable           — returns and total tax payable

`parse_report` reads these tables from the PDF into band rows (rupees). The
rows are the calibration targets for the taxpayer population and the
observed outcomes for the back-tests; every row keeps the table and page it
came from.
"""
import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import fitz

from config import BASE_DIR

RAW_DIR = BASE_DIR / "data" / "raw" / "cbdt"
OUT_DIR = BASE_DIR / "simulation" / "population" / "targets"

TABLES = {"gti": "Range of Gross Total Income", "returned": "Range of Returned Income",
          "tax": "Range of Tax Payable"}

_NUM = r"-?[\d,]+(?:\.\d+)?"
_RANGE_RE = re.compile(
    r"^\s*(?:(<\s*0)|(=\s*0)|>\s*(" + _NUM + r")\s*(?:and\s*<\s*=\s*(" + _NUM + r"))?)\s*$", re.I)


def _num(tok: str) -> Optional[float]:
    tok = tok.strip()
    if tok in ("-", "", "—"):
        return 0.0
    try:
        return float(tok.replace(",", ""))
    except ValueError:
        return None


@dataclass
class BandRow:
    ay: str
    table: str          # gti | returned | tax
    lower: float        # rupees, exclusive (">lower")
    upper: Optional[float]  # rupees, inclusive ("<= upper"); None = open top band
    returns: float
    total_inr: float    # sum over the band, rupees
    source: str         # "<file> table 2.1 p.21"


def _find_page(doc: "fitz.Document", title: str) -> Optional[int]:
    for i, page in enumerate(doc):
        if i < 5:
            continue  # table of contents
        t = page.get_text()
        if re.search(r"Individual\W{0,4}\s*(?:-\s*)?" + re.escape(title), t):
            return i
    return None


def parse_table(doc: "fitz.Document", key: str, ay: str, fname: str) -> list[BandRow]:
    page_no = _find_page(doc, TABLES[key])
    if page_no is None:
        return []
    lines = [ln.strip() for ln in doc[page_no].get_text().split("\n")]
    rows: list[BandRow] = []
    i = 0
    while i < len(lines):
        m = _RANGE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        if m.group(1):          # "< 0"
            lower, upper = float("-inf"), 0.0
        elif m.group(2):        # "= 0"
            lower, upper = -0.5, 0.0
        else:
            lower = _num(m.group(3))
            upper = _num(m.group(4)) if m.group(4) else None
        nums = []
        j = i + 1
        stop = False
        while j < len(lines) and len(nums) < 2 and not stop:
            # Values are usually one per line, but some rows print two on
            # one line ("24,180,972   1,170,209.54").
            for tok in lines[j].split():
                v = _num(tok)
                if v is None:
                    stop = True
                    break
                nums.append(v)
            j += 1
        if len(nums) == 2:
            rows.append(BandRow(ay=ay, table=key, lower=lower, upper=upper, returns=nums[0],
                                total_inr=nums[1] * 1e7, source=f"{fname} table {TABLES[key]} p.{page_no + 1}"))
        i = j
    return rows


def _ay_of(fname: str, doc: "fitz.Document") -> Optional[str]:
    m = re.search(r"Assessment Year\s*(20\d\d)\s*-\s*(\d\d)", doc[0].get_text())
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"AY[_ -]?(20\d\d)-(\d\d)", fname)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def parse_report(path: Path) -> list[BandRow]:
    with fitz.open(path) as doc:
        ay = _ay_of(path.name, doc)
        if ay is None:
            return []
        rows = []
        for key in TABLES:
            rows += parse_table(doc, key, ay, path.name)
    return rows


def parse_all(raw_dir: Path = RAW_DIR) -> list[BandRow]:
    rows = []
    for p in sorted(raw_dir.glob("*.pdf")):
        if "Time-Series" in p.name:
            continue
        rows += parse_report(p)
    return rows


def write_targets(rows: list[BandRow], out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ay in sorted({r.ay for r in rows}):
        p = out_dir / f"cbdt_individuals_ay{ay.replace('-', '_')}.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(rows[0])))
            w.writeheader()
            for r in rows:
                if r.ay == ay:
                    w.writerow(asdict(r))
        paths.append(p)
    return paths


def load_targets(ay: str, table: str = "gti", out_dir: Path = OUT_DIR) -> list[BandRow]:
    p = out_dir / f"cbdt_individuals_ay{ay.replace('-', '_')}.csv"
    rows = []
    with open(p, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["table"] != table:
                continue
            rows.append(BandRow(ay=r["ay"], table=r["table"], lower=float(r["lower"]),
                                upper=float(r["upper"]) if r["upper"] not in ("", "None") else None,
                                returns=float(r["returns"]), total_inr=float(r["total_inr"]), source=r["source"]))
    return rows
