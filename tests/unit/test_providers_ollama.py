"""Ollama Provider 测试。"""
from unittest.mock import MagicMock, patch

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_ollama import OllamaProvider


class TestOllamaProvider:
    def test_review_calls_ollama(self):
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                json=lambda: {"response": '{"corrected": {}, "confidence": 0.8}'},
                raise_for_status=lambda: None,
            )
            provider = OllamaProvider(model="qwen2.5:72b-instruct", base_url="http://localhost:11434")
            prompt = ReviewPrompt(system="s", user="u")
            result = provider.review(prompt)
            assert "corrected" in result

    def test_default_model(self):
        provider = OllamaProvider()
        assert provider._model == "qwen2.5:72b-instruct"