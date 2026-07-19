"""Claude API Provider（设计规范 §5.3）。

P2-B 生产化强化：
  - 指数退避重试（最多 3 次，间隔 1s/2s/4s）→ 抽到 BaseProvider
  - 超时控制（默认 60s）→ 通过 self._timeout_s 透传给 Anthropic 客户端
  - 失败时抛出原始异常（不吞错），由 LLMReviewer 决定 fallback 策略

P2-C-T1 重构：
  - 改为继承 BaseProvider
  - 删除内嵌 review() 重试循环（由基类 review() 统一提供）
  - 实现 _call(prompt) → 仅保留单次 API 调用语义
"""
from __future__ import annotations

import os

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_base import BaseProvider


class ClaudeProvider(BaseProvider):
    """Anthropic Claude API Provider。"""

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = BaseProvider.DEFAULT_MAX_RETRIES,
        timeout_s: int = BaseProvider.DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未设置")
        self._model = model or self.DEFAULT_MODEL
        # 调用基类初始化（存储 _max_retries / _timeout_s）
        super().__init__(max_retries=max_retries, timeout_s=timeout_s)
        # 延迟导入 anthropic（避免测试时强制依赖）
        from anthropic import Anthropic
        self._client = Anthropic(
            api_key=self._api_key,
            timeout=self._timeout_s,
        )

    def _call(self, prompt: ReviewPrompt) -> str:
        """单次调用 Claude API。重试由基类 review() 统一处理。"""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
        )
        return response.content[0].text