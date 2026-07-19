"""P2-C-T3 单元测试：DeepSeekProvider（OpenAI 兼容模式）。

覆盖：
  - 构造期校验（env / 默认模型 / 自定义模型 / 自定义 base_url）
  - review() 重试骨架（首次成功 / 重试后成功 / 重试耗尽）
  - chat.completions endpoint 调用正确性
  - get_provider() 工厂在 DEEPSEEK_API_KEY 存在时选择 DeepSeekProvider
"""
from __future__ import annotations

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt


class _FakeChatCompletionsAPI:
    """模拟 openai client.chat.completions。"""

    def __init__(self, fail_times: int = 0, fail_with: type[Exception] = RuntimeError):
        self.fail_times = fail_times
        self.fail_with = fail_with
        self.call_count = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise self.fail_with(f"simulated API failure #{self.call_count}")
        # 模拟 OpenAI ChatCompletion 响应（最小化）
        msg = type("Message", (), {"content": "ok"})()
        choice = type("Choice", (), {"message": msg})()
        return type("Response", (), {"choices": [choice]})()


class _FakeChatNamespace:
    def __init__(self, fail_times: int = 0):
        self.completions = _FakeChatCompletionsAPI(fail_times=fail_times)


class _FakeOpenAIClient:
    def __init__(self, fail_times: int = 0):
        self.chat = _FakeChatNamespace(fail_times=fail_times)


# ---------------------------------------------------------------------------
# 构造期测试
# ---------------------------------------------------------------------------


def test_deepseek_init_without_api_key_raises(monkeypatch):
    """未设置 DEEPSEEK_API_KEY 且未传 api_key → RuntimeError。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider()


def test_deepseek_init_with_api_key_succeeds(monkeypatch):
    """设置 DEEPSEEK_API_KEY 后构造成功（用 fake client 绕开真实 HTTP）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-dummy")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake = _FakeOpenAIClient()

    def fake_init(**kwargs):
        return fake

    monkeypatch.setattr("openai.OpenAI", fake_init)
    provider = DeepSeekProvider()
    assert provider._api_key == "sk-test-dummy"
    assert provider._client is fake


def test_deepseek_init_uses_default_model(monkeypatch):
    """默认模型为 deepseek-v4-flash。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeOpenAIClient())
    provider = DeepSeekProvider()
    assert provider._model == "deepseek-v4-flash"
    assert provider.DEFAULT_MODEL == "deepseek-v4-flash"


def test_deepseek_init_accepts_custom_model(monkeypatch):
    """可传入自定义模型（如 deepseek-v4-pro）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeOpenAIClient())
    provider = DeepSeekProvider(model="deepseek-v4-pro")
    assert provider._model == "deepseek-v4-pro"


# ---------------------------------------------------------------------------
# review() 重试骨架
# ---------------------------------------------------------------------------


def test_deepseek_review_succeeds_on_first_attempt(monkeypatch):
    """无失败：1 次调用即成功。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake_client = _FakeOpenAIClient(fail_times=0)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)

    provider = DeepSeekProvider(max_retries=3)
    out = provider.review(ReviewPrompt(system="sys", user="usr"))
    assert out == "ok"
    assert fake_client.chat.completions.call_count == 1


def test_deepseek_review_retries_then_succeeds(monkeypatch):
    """前 2 次失败，第 3 次成功 → 应重试 3 次后成功返回。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake_client = _FakeOpenAIClient(fail_times=2)
    # 跳过 sleep 加速测试
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)

    provider = DeepSeekProvider(max_retries=3, timeout_s=10)
    out = provider.review(ReviewPrompt(system="sys", user="usr"))
    assert out == "ok"
    assert fake_client.chat.completions.call_count == 3


def test_deepseek_review_exhausts_retries(monkeypatch):
    """所有重试都失败 → 抛出最后一个异常。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake_client = _FakeOpenAIClient(fail_times=10)  # 永远失败
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)

    provider = DeepSeekProvider(max_retries=3, timeout_s=10)
    with pytest.raises(RuntimeError, match="simulated API failure #3"):
        provider.review(ReviewPrompt(system="sys", user="usr"))
    assert fake_client.chat.completions.call_count == 3


def test_deepseek_review_uses_openai_chat_completions_endpoint(monkeypatch):
    """验证 _call() 实际命中 chat.completions.create 且参数正确。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake_client = _FakeOpenAIClient(fail_times=0)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)

    provider = DeepSeekProvider(model="deepseek-v4-pro")
    provider.review(ReviewPrompt(system="sys-content", user="usr-content"))

    kwargs = fake_client.chat.completions.last_kwargs
    assert kwargs is not None
    assert kwargs["model"] == "deepseek-v4-pro"
    assert isinstance(kwargs["messages"], list)
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "sys-content"
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "usr-content"


# ---------------------------------------------------------------------------
# get_provider() 工厂集成
# ---------------------------------------------------------------------------


def test_get_provider_selects_deepseek_when_env_set(monkeypatch):
    """当 DEEPSEEK_API_KEY 设置时，get_provider 返回 DeepSeekProvider。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-dummy-for-test")
    # 确保不选 Mock/CI 分支
    monkeypatch.delenv("CI", raising=False)
    # 用 fake client 避免实际初始化 OpenAI 客户端时基线问题
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeOpenAIClient())

    from cim_ontology.reviewer.providers import get_provider
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    provider = get_provider()
    assert isinstance(provider, DeepSeekProvider)


# ---------------------------------------------------------------------------
# P2-C-T4：边界条件与响应解析
# ---------------------------------------------------------------------------


def test_deepseek_call_uses_correct_max_tokens(monkeypatch):
    """验证 _call() 传递 max_tokens=4096（v1.2.2 提升，支持 ≤14 样本批量）。

    v1.2.2 之前为 2048：14 样本批量响应 ~2500 chars，触发 JSON 中段截断。
    ClaudeProvider 对齐参考：保留 2048；DeepSeek 因批处理路径更长需独立调优。
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    fake_client = _FakeOpenAIClient(fail_times=0)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: fake_client)

    provider = DeepSeekProvider()
    provider.review(ReviewPrompt(system="s", user="u"))

    kwargs = fake_client.chat.completions.last_kwargs
    assert kwargs.get("max_tokens") == 4096


def test_deepseek_call_handles_none_content(monkeypatch):
    """DeepSeek 在工具调用场景下 content 可能为 None → 返回空字符串。"""

    class _NoneContentAPI(_FakeChatCompletionsAPI):
        def create(self, **kwargs):
            self.last_kwargs = kwargs
            self.call_count += 1
            # 模拟 content=None
            msg = type("Message", (), {"content": None})()
            choice = type("Choice", (), {"message": msg})()
            return type("Response", (), {"choices": [choice]})()

    class _NoneContentClient:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _NoneContentAPI()})()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _NoneContentClient())

    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    provider = DeepSeekProvider()
    out = provider.review(ReviewPrompt(system="s", user="u"))
    assert out == ""


def test_deepseek_provider_implements_llm_provider_protocol(monkeypatch):
    """DeepSeekProvider 必须实现 LLMProvider Protocol（runtime_checkable）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeOpenAIClient())

    from cim_ontology.reviewer.providers import LLMProvider
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    provider = DeepSeekProvider()
    # Protocol 检查（runtime_checkable）
    assert isinstance(provider, LLMProvider)


def test_deepseek_provider_inherits_base_provider(monkeypatch):
    """DeepSeekProvider 必须继承 BaseProvider（共享重试骨架）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeOpenAIClient())

    from cim_ontology.reviewer.providers_base import BaseProvider
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider

    provider = DeepSeekProvider()
    assert isinstance(provider, BaseProvider)


# ---------------------------------------------------------------------------
# P2-C-T4：与 LLMReviewer 的端到端集成
# ---------------------------------------------------------------------------


def test_deepseek_end_to_end_with_reviewer(monkeypatch, tmp_path):
    """DeepSeekProvider 作为 LLMReviewer 的后端，端到端修正 OCR 噪声类名。"""
    import json

    from cim_ontology.ir.models import (
        ClassDef,
        IRStats,
        OntologyIR,
        Package,
        SourceInfo,
        UncertainEntry,
    )
    from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider
    from cim_ontology.reviewer.reviewer import LLMReviewer

    # Fake DeepSeek 返回 valid JSON（修订 'BaseVoltae' → 'BaseVoltage'）
    class _ReviewAPI(_FakeChatCompletionsAPI):
        def create(self, **kwargs):
            self.last_kwargs = kwargs
            self.call_count += 1
            content = json.dumps({
                "corrected": {"class_name": "BaseVoltage"},
                "confidence": 0.9,
                "notes": "OCR 噪声修正",
            })
            msg = type("Message", (), {"content": content})()
            choice = type("Choice", (), {"message": msg})()
            return type("Response", (), {"choices": [choice]})()

    class _ReviewClient:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _ReviewAPI()})()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _ReviewClient())

    # 构造 IR
    cls = ClassDef(name="BaseVoltae", parents=[], attributes=[], associations=[])
    pkg = Package(
        iri="http://iec.ch/TC57/2024/CIM-schema-cim17#Core",
        name="Core",
        classes=[cls],
    )
    ir = OntologyIR(
        schema_version="1.0",
        packages=[pkg],
        uncertain_entries=[UncertainEntry(
            case_id="noise::BaseVoltae",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )],
        stats=IRStats(),
        source=SourceInfo(
            document_path="test.md",
            document_sha256="abc",
            parsed_at="2026-01-01T00:00:00Z",
            parser_version="0.0",
        ),
    )

    # Reviewer + DeepSeek
    provider = DeepSeekProvider()
    reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

    result = reviewer.review(ir)

    # 验证：DeepSeek 返回的修订被应用
    assert result.get_class("BaseVoltage") is not None
    assert result.get_class("BaseVoltae") is None
    assert len(result.uncertain_entries) == 0