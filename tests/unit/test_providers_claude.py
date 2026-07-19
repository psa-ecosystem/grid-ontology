"""Claude Provider 测试（使用 unittest.mock）。"""
import json
from unittest.mock import MagicMock, patch

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_claude import ClaudeProvider


@pytest.fixture
def mock_response():
    return {
        "content": [{"text": json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.95})}]
    }


class TestClaudeProvider:
    def test_review_returns_text(self, mock_response, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        provider = ClaudeProvider()
        with patch.object(provider._client.messages, "create") as mock_create:
            mock_create.return_value = MagicMock(content=[MagicMock(text=json.dumps(mock_response["content"][0]["text"]))])
            prompt = ReviewPrompt(system="s", user="u")
            result = provider.review(prompt)
            assert "Measurement" in result or "corrected" in result

    def test_requires_api_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ClaudeProvider()
