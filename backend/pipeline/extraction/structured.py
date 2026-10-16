"""
The structured extraction condition.

The headline study gives every system the provision's canonical text and asks
for JSON. Most failures there happen after reading, when the answer is
assembled into a schedule ("no slab rows", "no open top band"), and two of
the provision sets have rate tables whose canonical text interleaves the two
columns. This condition changes three things, each something a deployed
system can do without knowing the answer:

  1. tables   the provision's rate tables rebuilt row by row from the PDF
              (pipeline.statute.tables) are added to the prompt; quotes may
              be grounded in a rebuilt row and are cited to that row's span
              of the canonical text
  2. schema   decoding is constrained to the answer's JSON schema where the
              provider supports it (pipeline.extraction.schema)
  3. repair   when assembly fails a structural check, the system is shown
              its answer and the check that failed (in general terms, with
              no values) and asked once to correct it

The first pass and the repaired result are reported separately, so the
effect of the repair round is measured, not hidden.
"""
from dataclasses import dataclass
from typing import Optional

from models.rules import ExtractionRecord
from pipeline.extraction import prompts
from pipeline.extraction.backends import SYSTEMS, BackendError, generate_json
from pipeline.extraction.extractor import to_record
from pipeline.extraction.schema import answer_schema
from pipeline.extraction.units import Unit
from pipeline.statute import tables as statute_tables


@dataclass
class Attempt:
    """One model call for one unit, kept so a repair can show the answer."""
    prompt: str
    raw: str
    decoding: str
    cache_key: str


def unit_rows(unit: Unit) -> tuple[str, list[tuple[str, int, int]]]:
    """(rendered tables for the prompt, rebuilt rows as (text, start, end)
    relative to unit.text)."""
    tabs = statute_tables.tables_in(unit.statute, unit.start, unit.end)
    rows = [(r.text, r.start - unit.start, r.end - unit.start) for t in tabs for r in t.rows]
    return statute_tables.render(tabs), rows


def _schema_for(system: str, use_schema: bool) -> Optional[dict]:
    if not use_schema or SYSTEMS[system].provider == "batch":
        return None
    return answer_schema(strict=SYSTEMS[system].strict_schema)


def _call(unit: Unit, system: str, prompt: str, version: int, rows, *, use_schema: bool,
          use_cache: bool) -> tuple[ExtractionRecord, dict, Optional[Attempt]]:
    try:
        res = generate_json(system, prompt, temperature=0.0, seed=0, prompt_version=version,
                            use_cache=use_cache, schema=_schema_for(system, use_schema))
    except BackendError as e:
        return ExtractionRecord(provision=unit.unit_id, statute=unit.statute, status="error", error=str(e)[:300]), {}, None
    rec, stats = to_record(unit, system, res.text, model=res.model, model_version=res.model_version,
                           cache_key=res.cache_key, rows=rows, prompt_version=version)
    stats.update(cached=res.cached, elapsed_ms=res.elapsed_ms, decoding=res.decoding)
    return rec, stats, Attempt(prompt=prompt, raw=res.text, decoding=res.decoding, cache_key=res.cache_key)


def extract_unit(unit: Unit, system: str, *, use_schema: bool = True,
                 use_cache: bool = True) -> tuple[ExtractionRecord, dict, Optional[Attempt]]:
    rendered, rows = unit_rows(unit)
    if system == "rules":
        from pipeline.extraction.rule_based import extract_unit as rb
        rec, stats = rb(unit, rows=rows)
        stats["tables"] = len(rows)
        return rec, stats, None
    prompt = prompts.render_structured(unit.text, unit.context, rendered)
    rec, stats, attempt = _call(unit, system, prompt, prompts.STRUCTURED_PROMPT_VERSION, rows,
                                use_schema=use_schema, use_cache=use_cache)
    stats["tables"] = len(rows)
    return rec, stats, attempt


def repair_unit(unit: Unit, system: str, attempt: Attempt, target: str, reason: str, *,
                use_schema: bool = True, use_cache: bool = True) -> tuple[ExtractionRecord, dict, Optional[Attempt]]:
    _, rows = unit_rows(unit)
    prompt = prompts.render_repair(attempt.prompt, attempt.raw, target, reason)
    return _call(unit, system, prompt, prompts.REPAIR_PROMPT_VERSION, rows,
                 use_schema=use_schema, use_cache=use_cache)


def repairable(reason: str) -> bool:
    """A failure the system can be told about in general terms."""
    return any(k in reason for k in prompts.CHECKS)
