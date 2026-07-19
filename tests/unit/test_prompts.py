"""Prompt 构建器测试。"""
from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.prompts import build_review_prompt


def test_build_review_prompt_includes_raw_text():
    entry = UncertainEntry(
        case_id="Wires::row3",
        source_table=150,
        package="Wires",
        raw_text="Meastrement",
        rule_attempt={"value": "Measurement"},
        uncertainty_reason="class_name_typo",
        context_snippet="前后文",
    )
    prompt = build_review_prompt(
        entry,
        known_namespaces=["cim", "rdfs"],
        known_classes=["Measurement", "IdentifiedObject"],
    )
    assert "Meastrement" in prompt.user
    assert "cim" in prompt.user
    assert "Measurement" in prompt.user
    assert len(prompt.system) > 0


def test_prompt_requires_json_output():
    entry = UncertainEntry(
        case_id="t",
        source_table=0,
        package="X",
        raw_text="foo",
        rule_attempt={},
        uncertainty_reason="class_name_typo",
    )
    prompt = build_review_prompt(entry, [], [])
    assert "JSON" in prompt.user or "json" in prompt.user
