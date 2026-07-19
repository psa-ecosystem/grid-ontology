"""P2-C-T1 单元测试：BaseProvider 共享重试/超时逻辑。

测试覆盖（最少 5 个）：
  1. 首次成功 → sleep 不被调用
  2. N 次重试后成功 → sleep 调用次数 = N-1，序列 [1, 2, 4, ...]
  3. 重试耗尽 → 抛出最后一次异常
  4. max_retries=1 → 仅一次尝试，无重试
  5. timeout_s 参数被接受并存储（占位语义，未来传递给底层 client）
"""
from __future__ import annotations

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt


class _StubProvider:
    """最小化 BaseProvider 子类，用于测试重试骨架。

    不实际调用任何 LLM；通过 _call 直接读取预设行为。
    """

    def __init__(
        self,
        fail_times: int = 0,
        fail_with: type[Exception] = RuntimeError,
        return_value: str = "ok",
        max_retries: int = 3,
        timeout_s: int = 60,
    ):
        # 延迟导入避免循环依赖（base 还未实现时也要能 import 测试）
        from cim_ontology.reviewer.providers_base import BaseProvider

        class _Impl(BaseProvider):
            def __init__(self_inner, max_retries, timeout_s):  # noqa: N805
                super().__init__(max_retries=max_retries, timeout_s=timeout_s)

            def _call(self_inner, prompt: ReviewPrompt) -> str:  # noqa: N805
                _StubProvider._calls += 1
                if _StubProvider._calls <= self._fail_times:
                    raise self._fail_with(f"simulated #{_StubProvider._calls}")
                return self._return_value

        _StubProvider._calls = 0
        self._fail_times = fail_times
        self._fail_with = fail_with
        self._return_value = return_value
        self.impl = _Impl(max_retries=max_retries, timeout_s=timeout_s)

    @property
    def calls(self) -> int:
        return _StubProvider._calls

    def review(self, prompt: ReviewPrompt) -> str:
        return self.impl.review(prompt)


def test_first_attempt_success_no_sleep(monkeypatch):
    """首次成功 → sleep 不被调用。"""
    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    provider = _StubProvider(fail_times=0, return_value="first-try")
    out = provider.review(ReviewPrompt(system="s", user="u"))

    assert out == "first-try"
    assert provider.calls == 1
    assert sleep_calls == [], f"首次成功不应 sleep，实际 {sleep_calls}"


def test_retry_then_success_backoff_sequence(monkeypatch):
    """重试 N-1 次后成功 → sleep 调用次数 = N-1，序列 [1, 2, 4, ...]。"""
    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    # fail_times=3, max_retries=5 → 前 3 次失败，第 4 次成功
    provider = _StubProvider(fail_times=3, max_retries=5)
    out = provider.review(ReviewPrompt(system="s", user="u"))

    assert out == "ok"
    assert provider.calls == 4
    # 4 次尝试 → 3 次 sleep：第 1 次后 sleep(1)、第 2 次后 sleep(2)、第 3 次后 sleep(4)
    assert sleep_calls == [1, 2, 4], f"退避序列错误：{sleep_calls}"


def test_retry_exhausted_raises_last_error(monkeypatch):
    """重试耗尽 → 抛出最后一次异常（不是第一次）。"""
    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    # fail_times=10 (always), max_retries=3 → 3 次都失败
    provider = _StubProvider(fail_times=10, max_retries=3)

    with pytest.raises(RuntimeError, match="simulated #3"):
        provider.review(ReviewPrompt(system="s", user="u"))

    assert provider.calls == 3
    # 3 次尝试 → 2 次 sleep：sleep(1)、sleep(2)
    assert sleep_calls == [1, 2]


def test_max_retries_one_no_retry(monkeypatch):
    """max_retries=1 → 仅一次尝试，无 sleep，无重试。"""
    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    provider = _StubProvider(fail_times=10, max_retries=1)

    with pytest.raises(RuntimeError, match="simulated #1"):
        provider.review(ReviewPrompt(system="s", user="u"))

    assert provider.calls == 1
    assert sleep_calls == [], f"max_retries=1 不应 sleep，实际 {sleep_calls}"


def test_timeout_s_parameter_accepted_and_stored():
    """timeout_s 参数必须被接受并存储（占位语义，未来传递给底层 client）。"""
    from cim_ontology.reviewer.providers_base import BaseProvider

    class _M(BaseProvider):
        def _call(self, prompt: ReviewPrompt) -> str:
            return "ok"

    p = _M(max_retries=3, timeout_s=42)
    assert p._max_retries == 3
    assert p._timeout_s == 42


def test_default_constants():
    """验证默认常量值与设计一致（max_retries=3, timeout_s=60）。"""
    from cim_ontology.reviewer.providers_base import BaseProvider

    assert BaseProvider.DEFAULT_MAX_RETRIES == 3
    assert BaseProvider.DEFAULT_TIMEOUT_S == 60