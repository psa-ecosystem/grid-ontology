"""LLM Reviewer 三层熔断测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.ir.models import (
    ClassDef,
    IRStats,
    Multiplicity,
    OntologyIR,
    Package,
    UncertainEntry,
)
from cim_ontology.reviewer.providers import MockProvider, ReviewPrompt
from cim_ontology.reviewer.reviewer import LLMReviewer


@pytest.fixture
def mock_dir(tmp_path):
    d = tmp_path / "llm"
    d.mkdir()
    (d / "default.json").write_text(
        json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.9})
    )
    return d


@pytest.fixture
def ir_with_uncertain():
    pkg = Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="Meastrement")],  # OCR 噪声；P2-B 修订为 Measurement
    )
    return OntologyIR(
        packages=[pkg],
        uncertain_entries=[UncertainEntry(
            case_id="A::row1", source_table=1, package="A",
            raw_text="Meastrement", rule_attempt={"value": "Measurement"},
            uncertainty_reason="class_name_typo",
        )],
    )


class TestLLMReviewer:
    def test_review_applies_correction(self, ir_with_uncertain, mock_dir):
        provider = MockProvider(fixtures_dir=mock_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=["Measurement"])
        result_ir = reviewer.review(ir_with_uncertain)
        # 修订已应用 → uncertain 条目数减少
        assert len(result_ir.uncertain_entries) == 0

    def test_fallback_on_invalid_json(self, ir_with_uncertain, tmp_path):
        bad_dir = tmp_path / "bad_llm"
        bad_dir.mkdir()
        (bad_dir / "default.json").write_text("{invalid json")
        provider = MockProvider(fixtures_dir=bad_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=[])
        result_ir = reviewer.review(ir_with_uncertain)
        # JSON 失败 → fallback 保留 uncertain 条目
        assert len(result_ir.uncertain_entries) >= 1

    def test_fallback_on_business_validation(self, ir_with_uncertain, tmp_path):
        bad_dir = tmp_path / "bad_biz_llm"
        bad_dir.mkdir()
        (bad_dir / "default.json").write_text(
            json.dumps({"corrected": {"class_name": "NonExistentXYZ"}, "confidence": 0.9})
        )
        provider = MockProvider(fixtures_dir=bad_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=["Measurement"])
        result_ir = reviewer.review(ir_with_uncertain)
        # 业务校验失败 → fallback
        assert len(result_ir.uncertain_entries) >= 1