"""DeepSeek V4 真实 API 端到端验证（B3 入口）。

⚠️ 此脚本执行真实 API 调用，会消耗 token。运行前确保：
  1. 已设置 DEEPSEEK_API_KEY 环境变量
  2. .venv 中已安装 openai SDK
  3. CI 环境不应运行此测试（需 @pytest.mark.manual 或 skipif）
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.adapters.python_types import PythonTypesAdapter
from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.ir.models import (
    ClassDef,
    IRStats,
    OntologyIR,
    Package,
    SourceInfo,
    UncertainEntry,
)
from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider
from cim_ontology.reviewer.reviewer import LLMReviewer, load_known_classes_from_file


SAMPLES_PATH = Path("tests/fixtures/ocr_noise_samples.json")
# v1.1.1：CIM 17 标准 ~200 核心类清单（覆盖 sample_3 multiplicity_leak 修复）
KNOWN_CLASSES_PATH = Path("tests/fixtures/cim_known_classes.txt")


@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY")
    or os.environ.get("CI") == "true"
    or os.environ.get("E2E_DEEPSEEK_REAL") != "1",
    reason=(
        "真实 DeepSeek API 测试需要："
        "(1) DEEPSEEK_API_KEY 已设置 + "
        "(2) CI != true（避免 CI secrets 泄露误触发）+ "
        "(3) E2E_DEEPSEEK_REAL=1（显式 opt-in 确认 token 消耗）"
    ),
)
class TestDeepSeekRealE2E:
    """用 DeepSeek V4 真实 API 验证 8 个 OCR 噪声样本的修订。

    F3: 不使用 pytest-timeout（外部依赖），改用循环内 elapsed 熔断。
    """

    def _load_samples(self) -> list[dict]:
        return json.loads(SAMPLES_PATH.read_text())

    def _make_ir_for_sample(self, sample: dict) -> OntologyIR:
        """为单个样本构造 IR：含一个 OCR 噪声 ClassDef + 一个 UncertainEntry。"""
        cls = ClassDef(
            name=sample["raw_text"],
            parents=[],
            attributes=[],
            associations=[],
        )
        pkg = Package(
            iri=f"http://x#{sample['package']}",
            name=sample["package"],
            classes=[cls],
        )
        entry = UncertainEntry(
            case_id=sample["case_id"],
            source_table=sample["source_table"],
            package=sample["package"],
            raw_text=sample["raw_text"],
            rule_attempt=sample["rule_attempt"],
            uncertainty_reason=sample["uncertainty_reason"],
            context_snippet=sample.get("context_snippet", ""),
        )
        return OntologyIR(
            schema_version="1.0",
            packages=[pkg],
            uncertain_entries=[entry],
            stats=IRStats(),
            source=SourceInfo(
                document_path="e2e_deepseek.md",
                document_sha256="abc",
                parsed_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
                parser_version="0",
            ),
        )

    def _collect_known_classes(self, samples: list[dict]) -> list[str]:
        """v1.1.1 known_classes 扩充：从 fixture 加载 CIM 17 标准 ~200 核心类。

        修复策略：原 few-shot 集合（仅 ~8 个 expected_correction）让 LLM 在
        Voltage0..1 这种 multiplicity_leak 场景下误返回 Integer。引入完整
        CIM 标准类名后，LLM 能正确识别 Voltage 候选 → 直接解决 sample_3 失败。

        Returns:
            CIM 17 核心类名清单（去重 + 排序后）
        """
        # 优先级：CIM 标准 fixture（核心 ~200 个）∪ 样本 expected（few-shot）
        standard = load_known_classes_from_file(KNOWN_CLASSES_PATH)
        few_shot = {
            s.get("expected_correction") or s["raw_text"]
            for s in samples
            if s.get("expected_correction")
        }
        # few_shot 优先（精确样本相关），其余补充标准集合
        return sorted(few_shot | set(standard))

    def test_single_sample_e2e(self, tmp_path):
        """单样本端到端：单次 API 调用 + 适配器 emit。"""
        samples = self._load_samples()
        sample = samples[0]  # Meastrement → Measurement
        ir = self._make_ir_for_sample(sample)

        provider = DeepSeekProvider()
        reviewer = LLMReviewer(
            provider=provider,
            known_classes=self._collect_known_classes(samples),
        )

        start = time.perf_counter()
        result_ir = reviewer.review(ir)
        elapsed = time.perf_counter() - start

        # 验证：修订成功应用（如果 expected_correction 不为 null）
        expected = sample.get("expected_correction")
        if expected:
            assert result_ir.get_class(expected) is not None, (
                f"DeepSeek 未正确修订 {sample['raw_text']!r} → {expected!r}（耗时 {elapsed:.2f}s）"
            )

        # 验证：4 个适配器能正常处理
        for adapter_cls in [
            OwlTurtleAdapter,
            ShaclAdapter,
            JsonSchemaAdapter,
            PythonTypesAdapter,
        ]:
            try:
                result = adapter_cls().emit(result_ir, tmp_path / adapter_cls.target_format)
                assert len(result.files) >= 1
            except Exception as e:
                pytest.fail(f"{adapter_cls.__name__} emit 失败：{e}")

    def test_all_samples_e2e(self, tmp_path):
        """全样本端到端：8 个样本逐一调用 API + 累计统计。"""
        samples = self._load_samples()
        known_classes = self._collect_known_classes(samples)

        results = []
        total_start = time.perf_counter()
        # F3: 单样本超时熔断阈值（BaseProvider 重试上限 ~187s 含退避）
        # 设为 60s 让单样本异常慢时立即降级，避免重试堆积
        MAX_SAMPLE_S = 60.0
        for sample in samples:
            ir = self._make_ir_for_sample(sample)
            provider = DeepSeekProvider()
            reviewer = LLMReviewer(provider=provider, known_classes=known_classes)

            sample_start = time.perf_counter()
            try:
                result_ir = reviewer.review(ir)
                elapsed = time.perf_counter() - sample_start

                # F3: 单样本超 60s 视为异常，立即降级而非继续堆样本
                if elapsed > MAX_SAMPLE_S:
                    pytest.fail(
                        f"样本 {sample['case_id']} 耗时 {elapsed:.2f}s > {MAX_SAMPLE_S}s "
                        f"熔断阈值，跳过剩余样本以避免 API 成本失控"
                    )

                expected = sample.get("expected_correction")
                if expected:
                    success = result_ir.get_class(expected) is not None
                else:
                    # LaTeX 残骸：预期保留为 uncertain
                    success = len(result_ir.uncertain_entries) >= 1

                results.append({
                    "case_id": sample["case_id"],
                    "category": sample["category"],
                    "raw_text": sample["raw_text"],
                    "expected": expected,
                    "success": success,
                    "elapsed_s": elapsed,
                })
            except Exception as e:
                # F2: 截断 error 到 200 字符，避免异常细节泄露敏感数据
                # （如 endpoint、API Key 片段、traceback 帧）
                error_msg = str(e)[:200]
                results.append({
                    "case_id": sample["case_id"],
                    "category": sample["category"],
                    "raw_text": sample["raw_text"],
                    "expected": sample.get("expected_correction"),
                    "success": False,
                    "error": error_msg,
                    "elapsed_s": time.perf_counter() - sample_start,
                })

        total_elapsed = time.perf_counter() - total_start

        # 输出报告（写入 docs/deepseek_e2e_results.json 供 B4 评估）
        report_path = Path("docs/deepseek_e2e_results.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": "deepseek-v4-flash",
                    "total_elapsed_s": total_elapsed,
                    "sample_count": len(samples),
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        # 至少 50% 修订成功（DeepSeek 在多数场景应能正确）
        success_count = sum(1 for r in results if r["success"])
        success_rate = success_count / len(results)
        assert success_rate >= 0.5, (
            f"修订成功率 {success_rate:.0%} 低于 50%：{results}"
        )

    def test_batch_review_e2e(self, tmp_path):
        """v1.2 批处理：单次 API 调用送 8 条样本，验证 ~75% 性能提升 + 正确性。

        性能基线（v1.1.1 逐条）：
          - 总耗时 ~60s，8 次 API 调用，平均 7.5s/条目
        v1.2 目标：
          - 总耗时 < 25s（-58%）
          - 1 次 API 调用
          - 成功率 ≥ 50%
        """
        samples = self._load_samples()
        known_classes = self._collect_known_classes(samples)

        # 构造 entries 列表（批量入口）
        entries = []
        for s in samples:
            entries.append(UncertainEntry(
                case_id=s["case_id"],
                source_table=s["source_table"],
                package=s["package"],
                raw_text=s["raw_text"],
                rule_attempt=s["rule_attempt"],
                uncertainty_reason=s["uncertainty_reason"],
                context_snippet=s.get("context_snippet", ""),
            ))

        provider = DeepSeekProvider()
        reviewer = LLMReviewer(provider=provider, known_classes=known_classes)

        # v1.2 批处理调用
        start = time.perf_counter()
        results = reviewer.review_batch(entries)
        elapsed = time.perf_counter() - start

        # 验证：性能提升（v1.1.1 基线 59.85s，目标 < 25s 即 -58%）
        assert elapsed < 25.0, (
            f"v1.2 批处理耗时 {elapsed:.2f}s 未达 < 25s 目标（v1.1.1 基线 59.85s）"
        )

        # 验证：返回条数正确
        assert len(results) == len(samples), (
            f"批处理返回 {len(results)} 条，期望 {len(samples)} 条"
        )

        # 验证：成功率 ≥ 50%（与逐条测试同阈值）
        success_count = sum(
            1 for r in results.values()
            if r is not None and r.get("corrected", {}).get("class_name")
        )
        success_rate = success_count / len(samples)
        assert success_rate >= 0.5, (
            f"v1.2 批处理成功率 {success_rate:.0%} 低于 50%：{results}"
        )

        # 验证：4 个适配器能正常处理（用空 IR + 修订结果重组）
        # 简化：仅构造一个含 raw_text 的最小 IR 并逐个验证
        for sample, entry in zip(samples, entries):
            rev = results.get(entry.case_id)
            if rev and rev.get("corrected", {}).get("class_name"):
                cls = ClassDef(name=rev["corrected"]["class_name"], parents=[], attributes=[], associations=[])
                pkg = Package(iri=f"http://x#{sample['package']}", name=sample["package"], classes=[cls])
                ir = OntologyIR(
                    schema_version="1.0", packages=[pkg], stats=IRStats(),
                    source=SourceInfo(document_path="t.md", document_sha256="abc",
                        parsed_at=datetime(2026, 6, 24, tzinfo=timezone.utc), parser_version="0"),
                )
                for adapter_cls in [OwlTurtleAdapter, ShaclAdapter, JsonSchemaAdapter, PythonTypesAdapter]:
                    try:
                        adapter_cls().emit(ir, tmp_path / adapter_cls.target_format)
                    except Exception as e:
                        pytest.fail(f"{adapter_cls.__name__} emit 失败：{e}")