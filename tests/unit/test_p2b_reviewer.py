"""P2-B 单元测试：LLM Reviewer 生产化强化。

覆盖三个高 ROI 修复：
  1. _review_one 的修订必须实际应用到 IR（修复 no-op bug）
  2. LLMCache 集成：命中 → 跳过 provider；未命中 → 写入缓存
  3. ClaudeProvider 错误传播：API 失败必须可被调用方捕获

v1.3 observability 集成测试（追加）：
  - metrics 在 review / review_batch 路径中正确埋点
  - path=single|batch 维度区分
  - fallback 计数器在错误路径递增
"""
import json
import pytest

from cim_ontology.ir.models import ClassDef, ClassRef, OntologyIR, Package, SourceInfo, UncertainEntry, IRStats
from cim_ontology.observability import Metrics
from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt
from cim_ontology.reviewer.cache import LLMCache
from cim_ontology.reviewer.reviewer import LLMReviewer


class FakeProvider(LLMProvider):
    """测试用假 Provider：返回预设 JSON。"""

    def __init__(self, response: str | dict, call_count: int = 0):
        self.response = response if isinstance(response, str) else json.dumps(response)
        self.call_count = call_count
        self.last_prompt: ReviewPrompt | None = None

    def review(self, prompt: ReviewPrompt) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


class FailingProvider(LLMProvider):
    """始终抛异常的 Provider。"""

    def review(self, prompt: ReviewPrompt) -> str:
        raise RuntimeError("API failure")


def _make_ir(uncertain_entries: list[UncertainEntry] | None = None) -> OntologyIR:
    """构造最小 IR：含一个 BaseVoltage 类（OCR 噪声候选）。"""
    cls = ClassDef(
        name="BaseVoltae",  # OCR 噪声（缺 'g'）
        parents=[],
        attributes=[],
        associations=[],
    )
    pkg = Package(
        iri="http://iec.ch/TC57/2024/CIM-schema-cim17#Core",
        name="Core",
        classes=[cls],
    )
    return OntologyIR(
        schema_version="1.0",
        packages=[pkg],
        uncertain_entries=uncertain_entries or [],
        stats=IRStats(),
        source=SourceInfo(
            document_path="test.md",
            document_sha256="abc",
            parsed_at="2026-01-01T00:00:00Z",
            parser_version="0.0",
        ),
    )


class TestReviewerAppliesCorrections:
    """Bug 修复：LLM 修订必须实际应用到 IR 中的类。"""

    def test_correction_applied_to_class_name(self):
        """LLM 修订 'BaseVoltae' → 'BaseVoltage' 必须修改 ClassDef.name。"""
        entry = UncertainEntry(
            case_id="test::BaseVoltae",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider({
            "corrected": {"class_name": "BaseVoltage"},
            "confidence": 0.9,
            "notes": "typo",
        })
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

        result = reviewer.review(ir)

        # 修订必须应用到 ClassDef.name
        cls = result.get_class("BaseVoltage")
        assert cls is not None, "修订后的类未出现在 IR 中"
        # uncertain_entries 应被消耗（不再保留）
        assert len(result.uncertain_entries) == 0, "已修订的条目仍在 uncertain 列表中"

    def test_correction_only_affects_target_class(self):
        """修订只影响目标类，其他类不受影响。"""
        entry = UncertainEntry(
            case_id="noise::BaseVoltae",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        # 添加一个无关的类
        ir = _make_ir([entry])
        other = ClassDef(name="OtherClass", parents=[], attributes=[], associations=[])
        ir.packages[0].classes.append(other)
        provider = FakeProvider({
            "corrected": {"class_name": "BaseVoltage"},
            "confidence": 0.9,
        })
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

        result = reviewer.review(ir)

        assert result.get_class("BaseVoltage") is not None
        assert result.get_class("OtherClass") is not None  # 不受影响
        assert result.get_class("BaseVoltae") is None  # 旧名已重命名


class TestReviewerCacheIntegration:
    """LLMCache 集成：命中跳过 Provider，未命中回写。"""

    def test_cache_hit_skips_provider(self, tmp_path):
        """缓存命中时 Provider 不被调用。"""
        cache = LLMCache(tmp_path / "reviews.db")
        case_id = "cached::entry"
        cached_response = json.dumps({
            "corrected": {"class_name": "BaseVoltage"},
            "confidence": 0.95,
        })
        cache.put(case_id, cached_response)

        provider = FakeProvider({"corrected": {}})  # 不应被调用
        reviewer = LLMReviewer(
            provider=provider,
            known_classes=["BaseVoltage"],
            cache=cache,
        )

        entry = UncertainEntry(
            case_id=case_id,
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        result = reviewer.review(ir)

        assert provider.call_count == 0, f"Provider 被调用了 {provider.call_count} 次（期望 0）"
        assert result.get_class("BaseVoltage") is not None

    def test_cache_miss_writes_back(self, tmp_path):
        """缓存未命中时回写。"""
        cache = LLMCache(tmp_path / "reviews.db")
        provider = FakeProvider({
            "corrected": {"class_name": "BaseVoltage"},
            "confidence": 0.9,
        })
        reviewer = LLMReviewer(
            provider=provider,
            known_classes=["BaseVoltage"],
            cache=cache,
        )

        entry = UncertainEntry(
            case_id="new::entry",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        reviewer.review(ir)

        # 验证 cache 已写入
        cached = cache.get("new::entry")
        assert cached is not None
        assert "BaseVoltage" in cached

    def test_no_cache_means_always_call_provider(self):
        """未配置 cache 时始终调用 Provider。"""
        provider = FakeProvider({
            "corrected": {"class_name": "BaseVoltage"},
            "confidence": 0.9,
        })
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

        entry = UncertainEntry(
            case_id="any::entry",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        reviewer.review(ir)

        assert provider.call_count == 1


class TestReviewerErrorHandling:
    """错误处理：Provider 失败 → fallback 保留 uncertain。"""

    def test_provider_failure_keeps_uncertain(self):
        """Provider 抛异常时，原 uncertain 条目被保留。"""
        entry = UncertainEntry(
            case_id="fail::entry",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        reviewer = LLMReviewer(provider=FailingProvider(), known_classes=["BaseVoltage"])

        result = reviewer.review(ir)

        # Provider 失败时：原类名保留，uncertain 条目保留
        assert result.get_class("BaseVoltae") is not None
        assert len(result.uncertain_entries) == 1

    def test_invalid_json_keeps_uncertain(self):
        """Provider 返回非 JSON → uncertain 保留。"""
        entry = UncertainEntry(
            case_id="badjson::entry",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider("not valid json {{")
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

        result = reviewer.review(ir)

        assert len(result.uncertain_entries) == 1

    def test_unknown_class_name_keeps_uncertain(self):
        """LLM 返回的 class_name 不在 known_classes 中 → uncertain 保留。"""
        entry = UncertainEntry(
            case_id="unknown::entry",
            source_table=0,
            package="Core",
            raw_text="BaseVoltae",
            rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider({
            "corrected": {"class_name": "HallucinatedClass"},
            "confidence": 0.9,
        })
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])

        result = reviewer.review(ir)

        # 业务校验失败：原类名保留，uncertain 保留
        assert len(result.uncertain_entries) == 1
        assert result.get_class("BaseVoltae") is not None


# ---------------------------------------------------------------------------
# v1.3 observability：Reviewer 集成 metrics 埋点测试
# ---------------------------------------------------------------------------


def _count_metric(snap: dict, name: str, **labels) -> int | float:
    """从 snapshot 中查找指定 (name, labels) 的指标值。"""
    label_key = frozenset(labels.items())
    for c in snap["counters"]:
        if c["name"] == name and frozenset(c["labels"].items()) == label_key:
            return c["value"]
    for h in snap["histograms"]:
        if h["name"] == name and frozenset(h["labels"].items()) == label_key:
            return h["count"]
    for g in snap["gauges"]:
        if g["name"] == name and frozenset(g["labels"].items()) == label_key:
            return g["value"]
    return 0


class TestReviewerMetrics:
    """v1.3 observability：Reviewer 必须在所有路径埋点。"""

    def test_review_single_emits_calls_and_corrections(self):
        """review() 路径：calls.success + corrections.applied=true 各 +1。"""
        entry = UncertainEntry(
            case_id="t1", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider({"corrected": {"class_name": "BaseVoltage"}, "confidence": 0.9})
        metrics = Metrics()
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"], metrics=metrics)

        reviewer.review(ir)

        snap = metrics.snapshot()
        assert _count_metric(snap, "reviewer.calls", outcome="success", path="single") == 1
        assert _count_metric(snap, "reviewer.corrections", applied="true", path="single") == 1

    def test_review_batch_emits_batch_size_gauge(self, tmp_path):
        """review_batch() 路径：batch.size gauge + calls.success + cache.misses。"""
        entries = [
            UncertainEntry(
                case_id=f"b{i}", source_table=0, package="Core",
                raw_text=f"BaseVoltae{i}", rule_attempt={"value": f"BaseVoltae{i}"},
                uncertainty_reason="ocr_noise",
            )
            for i in range(3)
        ]
        provider = FakeProvider([
            {"case_id": "b0", "corrected": {"class_name": "BaseVoltage0"}, "confidence": 0.9},
            {"case_id": "b1", "corrected": {"class_name": "BaseVoltage1"}, "confidence": 0.9},
            {"case_id": "b2", "corrected": {"class_name": "BaseVoltage2"}, "confidence": 0.9},
        ])
        metrics = Metrics()
        cache = LLMCache(path=tmp_path / "cache.db")
        reviewer = LLMReviewer(
            provider=provider,
            known_classes=["BaseVoltage0", "BaseVoltage1", "BaseVoltage2"],
            cache=cache,
            metrics=metrics,
        )

        results = reviewer.review_batch(entries)

        assert len(results) == 3
        snap = metrics.snapshot()
        # gauge: batch.size = 3
        assert _count_metric(snap, "reviewer.batch.size", path="batch") == 3
        # counter: calls.success path=batch = 1 (单次批处理 API 调用)
        assert _count_metric(snap, "reviewer.calls", outcome="success", path="batch") == 1
        # counter: cache.misses path=batch = 3 (3 个条目全 miss)
        assert _count_metric(snap, "reviewer.cache", result="miss", path="batch") == 3

    def test_review_batch_records_latency(self):
        """review_batch() 路径：latency.seconds 直方图至少 1 个观测值。"""
        entries = [
            UncertainEntry(
                case_id="lat", source_table=0, package="Core",
                raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
                uncertainty_reason="ocr_noise",
            )
        ]
        provider = FakeProvider([{"case_id": "lat", "corrected": {"class_name": "BaseVoltage"}, "confidence": 0.9}])
        metrics = Metrics()
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"], metrics=metrics)

        reviewer.review_batch(entries)

        snap = metrics.snapshot()
        # histogram count for reviewer.latency path=batch outcome=success >= 1
        for h in snap["histograms"]:
            if h["name"] == "reviewer.latency" and h["labels"].get("path") == "batch":
                assert h["count"] >= 1
                assert h["sum"] > 0
                return
        pytest.fail("latency histogram for batch path not found")

    def test_provider_failure_increments_fallbacks(self):
        """Provider 异常 → fallbacks.{provider_exception} +1。"""
        entry = UncertainEntry(
            case_id="fail", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        metrics = Metrics()
        reviewer = LLMReviewer(provider=FailingProvider(), known_classes=["BaseVoltage"], metrics=metrics)

        result = reviewer.review(ir)

        # uncertain 保留
        assert len(result.uncertain_entries) == 1
        snap = metrics.snapshot()
        assert _count_metric(snap, "reviewer.fallbacks", reason="provider_exception", path="single") == 1
        assert _count_metric(snap, "reviewer.calls", outcome="failure", path="single") == 1

    def test_invalid_json_increments_fallbacks(self):
        """JSON 解析失败 → fallbacks.{json_invalid} +1。"""
        entry = UncertainEntry(
            case_id="badjson", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        metrics = Metrics()
        reviewer = LLMReviewer(provider=FakeProvider("not a json"), known_classes=["BaseVoltage"], metrics=metrics)

        result = reviewer.review(ir)

        assert len(result.uncertain_entries) == 1
        snap = metrics.snapshot()
        assert _count_metric(snap, "reviewer.fallbacks", reason="json_invalid", path="single") == 1

    def test_business_invalid_class_increments_fallbacks(self):
        """业务校验失败（class_name 不在 known_classes）→ fallbacks.{business_invalid} +1。"""
        entry = UncertainEntry(
            case_id="biz", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        metrics = Metrics()
        reviewer = LLMReviewer(
            provider=FakeProvider({"corrected": {"class_name": "Hallucinated"}, "confidence": 0.9}),
            known_classes=["BaseVoltage"],
            metrics=metrics,
        )

        result = reviewer.review(ir)

        assert len(result.uncertain_entries) == 1
        snap = metrics.snapshot()
        assert _count_metric(snap, "reviewer.fallbacks", reason="business_invalid", path="single") == 1

    def test_cache_hit_increments_cache_hit_counter(self, tmp_path):
        """Cache 命中 → cache.{hit} +1, provider 不被调用。"""
        entry = UncertainEntry(
            case_id="hit", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider({"corrected": {"class_name": "BaseVoltage"}, "confidence": 0.9})
        metrics = Metrics()
        cache = LLMCache(path=tmp_path / "cache.db")
        # 预填 cache
        cache.put("hit", json.dumps({"corrected": {"class_name": "BaseVoltage"}, "confidence": 0.9}))
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"], cache=cache, metrics=metrics)

        result = reviewer.review(ir)

        # Provider 未被调用
        assert provider.call_count == 0
        snap = metrics.snapshot()
        assert _count_metric(snap, "reviewer.cache", result="hit", path="single") == 1
        assert _count_metric(snap, "reviewer.calls", outcome="success", path="single") == 0

    def test_default_metrics_instance_created(self):
        """未传 metrics 参数时, Reviewer 内部创建默认 Metrics（不应报错）。"""
        entry = UncertainEntry(
            case_id="def", source_table=0, package="Core",
            raw_text="BaseVoltae", rule_attempt={"value": "BaseVoltae"},
            uncertainty_reason="ocr_noise",
        )
        ir = _make_ir([entry])
        provider = FakeProvider({"corrected": {"class_name": "BaseVoltage"}, "confidence": 0.9})
        reviewer = LLMReviewer(provider=provider, known_classes=["BaseVoltage"])  # 无 metrics

        # 不应抛异常
        result = reviewer.review(ir)
        assert result.get_class("BaseVoltage") is not None