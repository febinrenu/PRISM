"""
Version identifiers for every artefact format PRISM produces.

Each number is bumped whenever the corresponding format or behaviour changes,
and every run manifest records all of them, so a stored result can always be
traced to the exact parser / prompt / schema that produced it.
"""
PRISM_VERSION = "3.0.0-dev"

# Clause/statute structure produced by the segmenter or statute parser.
PARSER_VERSION = 1
# Rule schema (LegalRule and effect kinds).
RULE_SCHEMA_VERSION = 1
# Extraction prompt templates (mirrors pipeline.llm_extractor.PROMPT_VERSION).
PROMPT_VERSION = 2
# Executable rule DSL and engines.
DSL_VERSION = 1
# Evaluation-set manifest format.
EVAL_SET_VERSION = 1


def versions() -> dict:
    return {
        "prism": PRISM_VERSION,
        "parser": PARSER_VERSION,
        "rule_schema": RULE_SCHEMA_VERSION,
        "prompt": PROMPT_VERSION,
        "dsl": DSL_VERSION,
        "eval_set": EVAL_SET_VERSION,
    }
