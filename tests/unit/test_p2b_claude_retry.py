"""P2-B 单元测试：ClaudeProvider 重试 + 超时（不依赖 anthropic SDK）。"""
import time

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_claude import ClaudeProvider


class _FakeMessagesAPI:
    """模拟 anthropic client.messages。"""

    def __init__(self, fail_times: int = 0, fail_with: type[Exception] = RuntimeError):
        self.fail_times = fail_times
        self.fail_with = fail_with
        self.call_count = 0

    def create(self, **kwargs):  # noqa: ARG002
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise self.fail_with(f"simulated API failure #{self.call_count}")
        # 成功响应（最小化 anthropic Message 结构）
        return type("Msg", (), {
            "content": [type("Block", (), {"text": "ok"})()],
        })()


class _FakeAnthropic:
    def __init__(self, fail_times: int = 0):
        self.messages = _FakeMessagesAPI(fail_times=fail_times)


def test_review_succeeds_on_first_attempt(monkeypatch):
    """无失败：1 次调用即成功。"""
    fake_client = _FakeAnthropic(fail_times=0)

    def fake_init(api_key, timeout):
        return fake_client

    monkeypatch.setattr("anthropic.Anthropic", fake_init)
    provider = ClaudeProvider(api_key="test-key", max_retries=3)
    # 替换 _client 为 fake（绕开 Anthropic SDK 真实构造）
    provider._client = fake_client

    out = provider.review(ReviewPrompt(system="s", user="u"))
    assert out == "ok"
    assert fake_client.messages.call_count == 1


def test_review_retries_then_succeeds(monkeypatch):
    """前 2 次失败，第 3 次成功 → 应重试 3 次后成功返回。"""
    fake_client = _FakeAnthropic(fail_times=2)

    def fake_init(api_key, timeout):
        return fake_client

    monkeypatch.setattr("anthropic.Anthropic", fake_init)
    provider = ClaudeProvider(api_key="test-key", max_retries=3, timeout_s=10)
    provider._client = fake_client

    out = provider.review(ReviewPrompt(system="s", user="u"))
    assert out == "ok"
    assert fake_client.messages.call_count == 3


def test_review_exhausts_retries(monkeypatch):
    """所有重试都失败 → 抛出最后一个异常。"""
    fake_client = _FakeAnthropic(fail_times=10)  # always fail

    def fake_init(api_key, timeout):
        return fake_client

    monkeypatch.setattr("anthropic.Anthropic", fake_init)
    provider = ClaudeProvider(api_key="test-key", max_retries=3, timeout_s=10)
    provider._client = fake_client

    with pytest.raises(RuntimeError, match="simulated API failure #3"):
        provider.review(ReviewPrompt(system="s", user="u"))
    assert fake_client.messages.call_count == 3


def test_review_exponential_backoff(monkeypatch):
    """验证指数退避：尝试 N 次时 sleep 总时长 ≈ 1+2+4+...+2^(N-2)。"""
    fake_client = _FakeAnthropic(fail_times=2)
    sleep_calls: list[float] = []

    def fake_sleep(s):
        sleep_calls.append(s)

    def fake_init(api_key, timeout):
        return fake_client

    monkeypatch.setattr("anthropic.Anthropic", fake_init)
    monkeypatch.setattr("time.sleep", fake_sleep)

    provider = ClaudeProvider(api_key="test-key", max_retries=3)
    provider._client = fake_client

    provider.review(ReviewPrompt(system="s", user="u"))
    # 3 次尝试 → 第 1 次后 sleep(1)、第 2 次后 sleep(2)
    assert sleep_calls == [1, 2]