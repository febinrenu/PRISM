"""
Basic pipeline tests — run with: python -m pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_clause_segmenter_basic():
    from pipeline.pdf_parser import PageData
    from pipeline.clause_segmenter import segment_clauses

    page = PageData(
        page_num=1,
        width=595,
        height=842,
        text=(
            "1. Definitions\n"
            "In this Act, unless the context otherwise requires, the following expressions shall have the meanings hereby assigned to them.\n"
            "2. Levy of tax\n"
            "Every person who has an annual income exceeding five lakh rupees shall be liable to pay income tax at the rate of twenty percent.\n"
            "Provided that where such income does not exceed ten lakh rupees, the tax shall be computed at the reduced rate."
        ),
        blocks=[],
        char_offset=0,
    )
    clauses = segment_clauses([page])
    assert len(clauses) >= 2, f"Expected at least 2 clauses, got {len(clauses)}"
    print(f"✓ Segmented {len(clauses)} clauses")


def test_legal_ner_basic():
    from pipeline.legal_ner import extract_entities

    text = (
        "Every assessee shall be liable to pay a penalty of ten thousand rupees "
        "if the income exceeds five lakh rupees and the return is not filed within "
        "the prescribed time."
    )
    entities = extract_entities(text)
    labels = {e.label for e in entities}
    assert len(entities) > 0, "Expected at least 1 entity"
    print(f"✓ Found {len(entities)} entities: {labels}")


def test_causal_detector_basic():
    from pipeline.causal_detector import detect_causal_patterns

    text = (
        "If the assessee fails to furnish the return of income within the time allowed, "
        "the Assessing Officer shall impose a penalty of five thousand rupees."
    )
    patterns = detect_causal_patterns(text, "test_clause_001")
    assert len(patterns) > 0, "Expected at least 1 causal pattern"
    print(f"✓ Found {len(patterns)} causal patterns: {[p.pattern_type for p in patterns]}")


def test_threshold_extraction():
    from pipeline.legal_ner import extract_entities

    text = "The tax rate shall be 20% on income exceeding Rs. 5,00,000."
    entities = extract_entities(text)
    threshold_ents = [e for e in entities if e.label == "THRESHOLD"]
    assert len(threshold_ents) > 0, "Expected THRESHOLD entities"
    print(f"✓ Found {len(threshold_ents)} THRESHOLD entities: {[e.text for e in threshold_ents]}")


if __name__ == "__main__":
    print("Running PRISM pipeline tests...\n")
    test_clause_segmenter_basic()
    test_legal_ner_basic()
    test_causal_detector_basic()
    test_threshold_extraction()
    print("\n✓ All tests passed!")
