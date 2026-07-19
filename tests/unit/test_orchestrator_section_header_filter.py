"""P1 测试：章节头 false-positive 过滤（orchestrator._SECTION_HEADER_RE）。

背景：cim-base-full.md 的章节编号（如 6.3、66、6.4.74）被误识为
class_name 前缀，导致 case_id 形如 "6.3::Core"、"66::Generation"、
"52::Class1"，污染 uncertain_entries。

修复：在 orchestrator 中检查 case_id 是否匹配 ^\\d+(\\.\\d+)*::，
匹配则视为章节头，直接 skip。
"""
import re

from cim_ontology.cleaner.orchestrator import _SECTION_HEADER_RE


class TestSectionHeaderFilter:
    """_SECTION_HEADER_RE 应准确识别章节头 false-positive。"""

    def test_single_digit_section(self):
        assert _SECTION_HEADER_RE.match("6::Class") is not None

    def test_dotted_section_path(self):
        assert _SECTION_HEADER_RE.match("6.3::Core") is not None

    def test_deep_section_path(self):
        assert _SECTION_HEADER_RE.match("6.4.74::ShortCircuitRotorKindenumeration") is not None

    def test_section_with_class1_placeholder(self):
        """cim-base-full.md 中典型噪声：52::Class1, 62::Domain。"""
        assert _SECTION_HEADER_RE.match("52::Class1") is not None
        assert _SECTION_HEADER_RE.match("62::Domain") is not None
        assert _SECTION_HEADER_RE.match("66::Generation") is not None

    def test_normal_class_id_not_filtered(self):
        """正常类名（不以数字开头）必须保留。"""
        assert _SECTION_HEADER_RE.match("ActivePower::") is None
        assert _SECTION_HEADER_RE.match("BaseVoltage::") is None
        # case_id 格式为 "<section_path>::<class_name>"，类名在 ::
        # 之后，前缀 section_path 也应被允许非数字开头
        assert _SECTION_HEADER_RE.match("Core::BaseVoltage") is None

    def test_section_number_only_no_class(self):
        """仅章节编号 + :: 也应匹配。"""
        assert _SECTION_HEADER_RE.match("6.3::") is not None
        assert _SECTION_HEADER_RE.match("6::") is not None

    def test_empty_string_not_filtered(self):
        """空字符串不应误匹配（防御性）。"""
        assert _SECTION_HEADER_RE.match("") is None

    def test_pattern_is_anchored(self):
        """模式必须 ^ 锚定，避免误匹配中段数字。"""
        # `Class6` 不应以数字开头
        assert _SECTION_HEADER_RE.match("Class6") is None
        # `Version1.0::Foo` 中 :: 前的部分不以数字开头
        assert _SECTION_HEADER_RE.match("Version1.0::Foo") is None
        # 但 `6.0::Foo` 是章节头
        assert _SECTION_HEADER_RE.match("6.0::Foo") is not None


class TestSectionHeaderFilterIntegration:
    """端到端验证：cim-base-full.md 上的实际效果。"""

    def test_orchestrator_constant_exists(self):
        """orchestrator 必须导出 _SECTION_HEADER_RE 常量。"""
        assert _SECTION_HEADER_RE is not None
        assert isinstance(_SECTION_HEADER_RE, re.Pattern)

    def test_remaining_uncertain_after_filter(self):
        """模拟 orchestrator 过滤后剩余 uncertain 数量（断言设计意图）。

        真实 cim-base-full.md Stage 1 产生 977 uncertain；
        23 个被 _SECTION_HEADER_RE 过滤（实测）；
        期望 LLM 处理后剩余 ~8 个真不确定（<31）。
        """
        # 此测试验证常量存在且可复用：实际端到端断言在 e2e 测试中。
        sample_uncertain = [
            "6.3::Core",                          # 章节头
            "6.4::Wires",                         # 章节头
            "52::Class1",                         # 章节头 + 占位符
            "::ActivePower",                      # 合法类（Stage 1 误判）
            "::AnleDerees",                       # OCR 噪声
        ]
        section_headers = [c for c in sample_uncertain if _SECTION_HEADER_RE.match(c)]
        real_uncertain = [c for c in sample_uncertain if not _SECTION_HEADER_RE.match(c)]
        assert len(section_headers) == 3
        assert len(real_uncertain) == 2
