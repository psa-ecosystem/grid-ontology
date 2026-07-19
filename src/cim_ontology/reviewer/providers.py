"""LLM Provider 协议与实现（设计规范 §5.3）。

支持：
  - MockProvider：测试桩，无网络依赖
  - ClaudeProvider：Claude API（Task 14 实现）
  - OllamaProvider：本地 Ollama（Task 15 实现）
  - DeepSeekProvider：DeepSeek V4 OpenAI 兼容（P2-C-T3 实现）
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class ReviewPrompt:
    """发送给 LLM 的完整提示。"""

    system: str
    user: str
    raw_text: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """LLM Provider 协议。"""

    def review(self, prompt: ReviewPrompt) -> str:
        """返回 LLM 响应（JSON 字符串）。"""
        ...


class MockProvider:
    """确定性 Mock Provider，用于测试与 CI。"""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures = fixtures_dir

    def review(self, prompt: ReviewPrompt) -> str:
        # Stage 5: semantic_<class_name>.json 优先匹配（raw_text=class_name）
        semantic_fixture = self._fixtures / f"semantic_{prompt.raw_text}.json"
        if semantic_fixture.exists():
            return semantic_fixture.read_text(encoding="utf-8")
        for fixture in self._fixtures.glob("*.json"):
            if fixture.stem in prompt.raw_text:
                return fixture.read_text(encoding="utf-8")
        default = self._fixtures / "default.json"
        if default.exists():
            return default.read_text(encoding="utf-8")
        return json.dumps({"corrected": {}, "confidence": 0.0, "notes": "no fixture"})


def get_provider(fixtures_dir: Path | None = None) -> LLMProvider:
    """Provider 工厂（CI 环境强制 Mock）。

    优先级（P2-C-T3 更新）：
      1. CI=true → MockProvider
      2. DEEPSEEK_API_KEY → DeepSeekProvider（P2-C 默认）
      3. ANTHROPIC_API_KEY → ClaudeProvider
      4. USE_OLLAMA → OllamaProvider
      5. 兜底 → MockProvider
    """
    if os.environ.get("CI") == "true":
        import structlog
        log = structlog.get_logger()
        log.info("ci_detected_using_mock_provider")
        return MockProvider(fixtures_dir=fixtures_dir or Path("tests/fixtures/llm"))

    # P2-C: DeepSeek 优先（新的默认 Provider）
    if os.environ.get("DEEPSEEK_API_KEY"):
        from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider
        return DeepSeekProvider()

    if os.environ.get("ANTHROPIC_API_KEY"):
        from cim_ontology.reviewer.providers_claude import ClaudeProvider
        return ClaudeProvider()

    if os.environ.get("USE_OLLAMA"):
        from cim_ontology.reviewer.providers_ollama import OllamaProvider
        return OllamaProvider()

    return MockProvider(fixtures_dir=fixtures_dir or Path("tests/fixtures/llm"))