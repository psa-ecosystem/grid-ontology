"""DeepSeek V4 Provider（OpenAI 兼容模式，P2-C-T3）。

DeepSeek API 同时支持 OpenAI 兼容端点（默认）和 Anthropic 兼容端点。
本 Provider 选择 OpenAI 模式，复用 openai SDK + BaseProvider 重试骨架。

API 文档：https://api-docs.deepseek.com/

P2-C-T1 升级：
  - 继承 BaseProvider，遵循"实现 _call() 而非 review()"的 OCP 约束
  - 复用基类的指数退避重试（1s/2s/4s）与 60s 超时占位
"""
from __future__ import annotations

import os

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_base import BaseProvider


class DeepSeekProvider(BaseProvider):
    """DeepSeek V4 Provider（OpenAI 兼容）。默认模型 deepseek-v4-flash。

    v1.2.2 修复：max_tokens 默认值从 2048 提升到 4096，
    支持 ≤14 条样本的批量响应不被截断（每条 ~150-250 chars + JSON 包装）。
    """

    DEFAULT_MODEL = "deepseek-v4-flash"
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_retries: int = BaseProvider.DEFAULT_MAX_RETRIES,
        timeout_s: int = BaseProvider.DEFAULT_TIMEOUT_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(max_retries=max_retries, timeout_s=timeout_s)
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未设置")
        self._model = model or self.DEFAULT_MODEL
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._max_tokens = max_tokens
        # 延迟导入 openai（避免测试时强制依赖）
        from openai import OpenAI

        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout_s,
        )

    def _call(self, prompt: ReviewPrompt) -> str:
        """调用 DeepSeek Chat Completions API（OpenAI 兼容）。

        失败时让异常自然向上抛，由 BaseProvider.review() 处理重试。
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            max_tokens=self._max_tokens,
        )
        content = response.choices[0].message.content
        if content is None:
            # DeepSeek 在工具调用场景下 content 可能为 None
            # 返回空字符串，由 reviewer fallback 机制处理
            return ""
        return content