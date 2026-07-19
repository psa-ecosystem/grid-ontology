"""P2-D 测试：Stage 2 reviewer 50+ OCR 噪声样本参数化测试。

v1.5 P2 任务：扩样从 14 → 50 个 OCR 噪声样本，覆盖更全面的 reviewer 行为。
测试不实际调用 LLM，使用 FakeProvider 模拟确定性响应。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cim_ontology.ir.models import UncertainEntry
from cim_ontology.observability import Metrics
from cim_ontology.reviewer.cache import LLMCache
from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt
from cim_ontology.reviewer.reviewer import LLMReviewer


# ---------------------------------------------------------------------------
# 加载 fixture
# ---------------------------------------------------------------------------


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "ocr_noise_samples.json"


def _load_ocr_samples() -> list[dict[str, Any]]:
    """加载 50+ OCR 噪声样本。"""
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


OCR_SAMPLES = _load_ocr_samples()


# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------


class _BatchFakeProvider(LLMProvider):
    """测试用假 Provider：review() 接收 ReviewPrompt，返回 JSON array。

    行为：从 prompt.user 中提取 case_id，按 ground_truth 映射生成响应。
    """

    def __init__(self, ground_truth: dict[str, dict[str, Any]] | None = None):
        self._ground_truth = ground_truth or {}
        self.call_count = 0
        self.last_prompt: ReviewPrompt | None = None

    def review(self, prompt: ReviewPrompt) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        # 从 prompt.user 提取 case_id 列表
        import re
        ids = re.findall(r'"case_id":\s*"([^"]+)"', prompt.user)
        results = []
        for cid in ids:
            if cid in self._ground_truth:
                results.append(self._ground_truth[cid])
            else:
                results.append({
                    "case_id": cid,
                    "decision": "reject",
                    "reason": "no ground truth",
                })
        return json.dumps(results)


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


def _make_uncertain_entry(sample: dict[str, Any]) -> UncertainEntry:
    """从 fixture 样本构造 UncertainEntry。"""
    return UncertainEntry(
        case_id=sample["case_id"],
        source_table=sample["source_table"],
        package=sample["package"],
        raw_text=sample["raw_text"],
        rule_attempt=sample["rule_attempt"],
        uncertainty_reason=sample["uncertainty_reason"],
    )


def _sample_response(sample: dict[str, Any]) -> dict[str, Any]:
    """从样本生成 LLM 响应项。"""
    if sample["expected_correction"]:
        return {
            "case_id": sample["case_id"],
            "decision": "accept",
            "new_name": sample["expected_correction"],
            "confidence": 0.9,
            "notes": f"auto-corrected from {sample['category']}",
        }
    return {
        "case_id": sample["case_id"],
        "decision": "reject",
        "new_name": sample["raw_text"],
        "confidence": 0.3,
        "notes": f"rejected: {sample['category']}",
    }


# ---------------------------------------------------------------------------
# 测试 1: fixture 完整性
# ---------------------------------------------------------------------------


class TestFixtureIntegrity:
    """fixture 文件完整性测试。"""

    def test_minimum_50_samples(self):
        """至少 50 个样本（v1.5 P2 目标）。"""
        assert len(OCR_SAMPLES) >= 50, f"样本数 {len(OCR_SAMPLES)} < 50"

    def test_all_samples_have_required_fields(self):
        """所有样本都有必需字段。"""
        for sample in OCR_SAMPLES:
            assert "case_id" in sample
            assert "raw_text" in sample
            assert "category" in sample
            assert "expected_correction" in sample

    def test_unique_case_ids(self):
        """case_id 唯一。"""
        ids = [s["case_id"] for s in OCR_SAMPLES]
        assert len(ids) == len(set(ids)), "case_id 重复"

    def test_category_coverage(self):
        """覆盖所有关键类别。"""
        cats = {s["category"] for s in OCR_SAMPLES}
        expected = {"typo", "multiplicity_leak", "clean_name"}
        assert expected.issubset(cats), f"缺少类别: {expected - cats}"


# ---------------------------------------------------------------------------
# 测试 2: 各类别样本数
# ---------------------------------------------------------------------------


class TestCategoryDistribution:
    """各类别样本数 sanity check（确保覆盖多样）。"""

    def test_multiplicity_leak_at_least_10(self):
        """multiplicity_leak 至少 10 个样本。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "multiplicity_leak")
        assert count >= 10

    def test_clean_name_at_least_5(self):
        """clean_name 至少 5 个样本（baseline）。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "clean_name")
        assert count >= 5

    def test_typo_at_least_3(self):
        """typo 至少 3 个样本。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "typo")
        assert count >= 3

    def test_latex_artifact_present(self):
        """latex_artifact 至少 1 个样本。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "latex_artifact")
        assert count >= 1

    def test_case_error_present(self):
        """case_error 至少 1 个样本。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "case_error")
        assert count >= 1

    def test_namespace_pollution_present(self):
        """namespace_pollution 至少 1 个样本。"""
        count = sum(1 for s in OCR_SAMPLES if s["category"] == "namespace_pollution")
        assert count >= 1


# ---------------------------------------------------------------------------
# 测试 3: reviewer 对 50+ 样本的处理
# ---------------------------------------------------------------------------


class TestReviewerHandlesAllSamples:
    """reviewer 必须能处理所有 50+ 样本（不崩溃、返回结果）。"""

    @pytest.mark.parametrize("sample", OCR_SAMPLES, ids=lambda s: s["case_id"])
    def test_reviewer_processes_sample(self, sample, tmp_path):
        """每个样本都能被 reviewer.review_batch 接收并返回结果。"""
        entry = _make_uncertain_entry(sample)
        ground_truth = {sample["case_id"]: _sample_response(sample)}
        provider = _BatchFakeProvider(ground_truth=ground_truth)
        cache = LLMCache(path=tmp_path / "cache.db")
        metrics = Metrics()
        known = [sample["expected_correction"]] if sample["expected_correction"] else []
        reviewer = LLMReviewer(
            provider=provider, cache=cache, metrics=metrics, known_classes=known,
        )

        result = reviewer.review_batch([entry])
        assert sample["case_id"] in result


# ---------------------------------------------------------------------------
# 测试 4: 批处理所有 50+ 样本（单次 LLM 调用）
# ---------------------------------------------------------------------------


class TestBatchReviewAllSamples:
    """一次性批处理所有 50+ 样本（仿 Stage 2 e2e 行为）。"""

    def test_single_batch_handles_all_samples(self, tmp_path):
        """单次 LLM 调用处理所有 50+ 样本。"""
        entries = [_make_uncertain_entry(s) for s in OCR_SAMPLES]
        ground_truth = {s["case_id"]: _sample_response(s) for s in OCR_SAMPLES}
        provider = _BatchFakeProvider(ground_truth=ground_truth)
        cache = LLMCache(path=tmp_path / "cache.db")
        metrics = Metrics()
        known = sorted({
            s["expected_correction"] for s in OCR_SAMPLES if s["expected_correction"]
        })
        reviewer = LLMReviewer(
            provider=provider, cache=cache, metrics=metrics, known_classes=known,
        )

        result = reviewer.review_batch(entries)
        assert len(result) == len(OCR_SAMPLES)
        for sample in OCR_SAMPLES:
            assert sample["case_id"] in result
        # 单次 LLM 调用（批处理节省网络往返）
        assert provider.call_count == 1


# ---------------------------------------------------------------------------
# 测试 5: 按类别分组的 acceptance rate
# ---------------------------------------------------------------------------


class TestAcceptanceRateByCategory:
    """按类别验证 reviewer 的处理结果（ground truth 应被正确接受）。"""

    @pytest.mark.parametrize("category", [
        "typo", "latex_artifact", "multiplicity_leak",
        "case_error", "namespace_pollution", "clean_name",
    ])
    def test_category_samples_processed(self, category, tmp_path):
        """同类别样本应被 reviewer 接收并处理。"""
        samples = [s for s in OCR_SAMPLES if s["category"] == category]
        if not samples:
            pytest.skip(f"无 {category} 样本")
        entries = [_make_uncertain_entry(s) for s in samples]
        ground_truth = {s["case_id"]: _sample_response(s) for s in samples}
        provider = _BatchFakeProvider(ground_truth=ground_truth)
        cache = LLMCache(path=tmp_path / "cache.db")
        metrics = Metrics()
        known = sorted({
            s["expected_correction"] for s in samples if s["expected_correction"]
        })
        reviewer = LLMReviewer(
            provider=provider, cache=cache, metrics=metrics, known_classes=known,
        )

        result = reviewer.review_batch(entries)
        # 所有样本应被处理（即使 reject 也是合法结果）
        assert len(result) == len(samples)
        for sample in samples:
            assert sample["case_id"] in result


# ---------------------------------------------------------------------------
# 测试 6: 已知类名校验（business check）
# ---------------------------------------------------------------------------


class TestKnownClassValidation:
    """known_classes 校验：expected_correction 不在 known_classes 时应被 reject。"""

    def test_unknown_correction_rejected(self, tmp_path):
        """expected_correction 不在 known_classes 中时，reviewer 应 reject 该样本。"""
        sample = OCR_SAMPLES[0]  # noise_sample_1: Meastrement → Measurement
        entry = _make_uncertain_entry(sample)
        provider = _BatchFakeProvider(ground_truth={
            sample["case_id"]: {
                "case_id": sample["case_id"],
                "decision": "accept",
                "new_name": "Measurement",
            }
        })
        cache = LLMCache(path=tmp_path / "cache.db")
        metrics = Metrics()
        # known_classes 故意不包含 "Measurement"
        reviewer = LLMReviewer(
            provider=provider, cache=cache, metrics=metrics,
            known_classes=["OtherClass1", "OtherClass2"],
        )

        result = reviewer.review_batch([entry])
        # result[case_id] 应为 None（business check reject：new_name 不在 known_classes）
        assert result[sample["case_id"]] is None
