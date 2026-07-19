"""LLM 缓存测试。"""
import tempfile
from pathlib import Path

import pytest

from cim_ontology.reviewer.cache import LLMCache


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "llm_cache.db"


class TestLLMCache:
    def test_miss_returns_none(self, cache_path):
        cache = LLMCache(path=cache_path)
        assert cache.get("unknown_id") is None

    def test_put_and_get(self, cache_path):
        cache = LLMCache(path=cache_path)
        cache.put("case_1", '{"corrected": {"class_name": "A"}, "confidence": 0.9}')
        assert cache.get("case_1") == '{"corrected": {"class_name": "A"}, "confidence": 0.9}'

    def test_persistence_across_instances(self, cache_path):
        c1 = LLMCache(path=cache_path)
        c1.put("case_x", "value_x")
        c2 = LLMCache(path=cache_path)
        assert c2.get("case_x") == "value_x"