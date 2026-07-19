"""LLM Provider 基类（共享重试/超时逻辑）。

设计原则（OCP，开闭原则）：
  - 基类提供 review() 通用骨架（指数退避 + 重试次数控制 + 超时占位）
  - 子类只需实现 _call(prompt) -> str 纯调用
  - 新增 Provider 不修改基类（P2-C-T3 DeepSeekProvider 即按此扩展）

为何把退避策略放在基类：
  - P2-B 中 ClaudeProvider 的 1s/2s/4s 退避已是行业最佳实践
  - 多个 Provider 重复此逻辑会引入漂移风险（不同 Provider 不同间隔）
  - 集中到基类可统一未来调整（如改为 jittered backoff）

为何 timeout_s 当前只是占位：
  - Anthropic SDK 接受 timeout= 关键字
  - httpx 接受 timeout= 参数
  - 各 Provider 构造位置不同，统一通过 self._timeout_s 暴露
  - 子类在 _call 中按需传递（见 providers_claude.py / providers_ollama.py）
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt


class BaseProvider(LLMProvider, ABC):
    """LLM Provider 基类。

    提供：
      - review()：含指数退避重试的入口
      - _call()：子类必须实现的纯调用抽象方法
      - 默认参数：DEFAULT_MAX_RETRIES=3，DEFAULT_TIMEOUT_S=60

    子类实现 _call(prompt) 时，只需关心单次 API 调用本身：
    不需要捕获/重试/退避——这些由基类 review() 统一处理。
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_TIMEOUT_S = 60

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._max_retries = max_retries
        self._timeout_s = timeout_s

    def review(self, prompt: ReviewPrompt) -> str:
        """带指数退避的复审调用。

        退避策略：最多 max_retries 次尝试，失败间隔 1s/2s/4s/...
        返回：_call() 的首次成功返回值
        抛出：所有重试失败后的最后一次异常（不吞错，由 LLMReviewer 决定 fallback）
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return self._call(prompt)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
        # 重试耗尽：抛出最后一个异常（保留原始 traceback）
        assert last_error is not None
        raise last_error

    @abstractmethod
    def _call(self, prompt: ReviewPrompt) -> str:
        """子类实现：实际调用 LLM API 并返回响应文本。

        设计要求：
          - 单次调用语义（不内置重试；重试由 review() 统一处理）
          - 失败时让异常自然向上抛（由基类捕获并退避）
          - 可使用 self._timeout_s 控制客户端超时（如适用）
        """
        ...