"""LLM Provider 单元测试。"""
import json

import pytest

from cim_ontology.reviewer.providers import (
    LLMProvider,
    MockProvider,
    ReviewPrompt,
)


@pytest.fixture
def mock_dir(tmp_path):
    """临时 mock 目录。"""
    d = tmp_path / "llm_fixtures"
    d.mkdir()
    (d / "default.json").write_text(
        json.dumps({"corrected": {}, "confidence": 0.5, "notes": "default"})
    )
    (d / "Meastrement.json").write_text(
        json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.98, "notes": "OCR 修正"})
    )
    return d


class TestMockProvider:
    def test_returns_default_when_no_match(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        prompt = ReviewPrompt(system="s", user="u", raw_text="Anything")
        result = p.review(prompt)
        data = json.loads(result)
        assert data["confidence"] == 0.5

    def test_returns_specific_fixture_when_match(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        prompt = ReviewPrompt(system="s", user="u", raw_text="Meastrement")
        result = p.review(prompt)
        data = json.loads(result)
        assert data["corrected"]["class_name"] == "Measurement"

    def test_protocol_compliance(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        assert isinstance(p, LLMProvider)