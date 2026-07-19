"""Ollama 本地模型 Provider（设计规范 §5.8）。

P2-C-T1 升级：
  - 改为继承 BaseProvider，复用 3 次指数退避重试 + 60s 超时占位
  - 实现 _call() 单次 API 调用（保留 httpx 直调语义）
  - 默认 max_retries=3，timeout_s=60（与 ClaudeProvider 对齐）
"""
from __future__ import annotations

import httpx

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_base import BaseProvider


class OllamaProvider(BaseProvider):
    """本地 Ollama 模型 Provider。推荐 Qwen2.5-72B-Instruct（非 Coder 系列）。"""

    DEFAULT_MODEL = "qwen2.5:72b-instruct"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        model: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = BaseProvider.DEFAULT_MAX_RETRIES,
        timeout_s: int = BaseProvider.DEFAULT_TIMEOUT_S,
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._base_url = base_url.rstrip("/")
        # 调用基类初始化（存储 _max_retries / _timeout_s）
        super().__init__(max_retries=max_retries, timeout_s=timeout_s)

    def _call(self, prompt: ReviewPrompt) -> str:
        """单次调用 Ollama API。重试由基类 review() 统一处理。

        使用 self._timeout_s 作为客户端超时（默认 60s）。
        """
        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": f"{prompt.system}\n\n{prompt.user}",
                "stream": False,
            },
            timeout=float(self._timeout_s),
        )
        response.raise_for_status()
        return response.json()["response"]