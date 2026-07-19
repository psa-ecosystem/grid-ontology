"""P1 测试：Package OCR 模糊合并（_pkg_dedup.merge_fuzzy_duplicate_packages）。

背景：cim-base-full.md Stage 1 产生 6 对 OCR 噪声包变体：
  - Packae1 / Package1
  - GenerationTraininSimulation / GenerationTrainingSimulation
  - Euivalents / Equivalents
  - AuxiliarEuiment / AuxiliaryEquipment
  - DiaramLaout / DiagramLayout
  - OerationalLimits / OperationalLimits

精确名匹配无法识别，导致 OWL/SHACL 产物文件名带 OCR 噪声
（如 cim17_Packae1.ttl）。模糊合并规范化到规范名（最长名）。
"""
import pytest

from cim_ontology.adapters._pkg_dedup import (
    merge_fuzzy_duplicate_packages,
    merge_duplicate_packages,
    _find_fuzzy_groups,
    DEFAULT_FUZZY_THRESHOLD,
)
from cim_ontology.ir.models import ClassDef, Package


# 6 对 cim-base-full.md 真实 OCR 变体（来自 cim-e2e-validation-report.md §2.2）
CIM_OCR_VARIANTS = [
    ("Packae1", "Package1", 1),
    ("GenerationTraininSimulation", "GenerationTrainingSimulation", 1),
    ("Euivalents", "Equivalents", 1),
    ("AuxiliarEuiment", "AuxiliaryEquipment", 3),
    ("DiaramLaout", "DiagramLayout", 4),
    ("OerationalLimits", "OperationalLimits", 2),
]


def _make_pkg(name: str, classes: list[str] | None = None) -> Package:
    return Package(
        iri=f"http://x#{name}",
        name=name,
        classes=[ClassDef(name=c) for c in (classes or [])],
    )


# ---------------------------------------------------------------------------
# 核心算法：_find_fuzzy_groups
# ---------------------------------------------------------------------------


class TestFindFuzzyGroups:
    """下标分组算法测试。"""

    def test_exact_match_groups_together(self):
        """distance=0 但 length_diff=0 → _find_fuzzy_groups 不合并。

        精确匹配（distance=0）由 merge_duplicate_packages 前置处理，
        _find_fuzzy_groups 专注于 length_diff ≥ 1 的 OCR 变体场景。
        """
        groups = _find_fuzzy_groups(["Packae1", "Packae1"], threshold=2)
        assert groups == []  # length_diff=0 被 length_diff ≥ 1 防线拦截

    def test_levenshtein_1_groups_together(self):
        groups = _find_fuzzy_groups(["Packae1", "Package1"], threshold=2)
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1]

    def test_common_prefix_not_required_anymore(self):
        """v1.4：移除共同前缀防御（OerationalLimits/OperationalLimits 前 3 字符不同）。"""
        # 旧版会用共同前缀防御拒绝这两个
        groups = _find_fuzzy_groups(["OerationalLimits", "OperationalLimits"], threshold=2)
        assert len(groups) == 1  # 新版：长度差 ≤ 1 + distance ≤ 2 → 合并

    def test_length_diff_blocks_merge(self):
        """长度差 > 1 → 不合并。"""
        groups = _find_fuzzy_groups(["Foo", "FooBar"], threshold=3)
        assert groups == []  # 长度差 3 > 1

    def test_threshold_respected(self):
        groups = _find_fuzzy_groups(["Packae1", "Package1"], threshold=0)
        assert groups == []  # distance=1 > threshold=0

    def test_short_string_skipped(self):
        """短字符串不参与模糊匹配（防御性，len < 4 跳过）。"""
        groups = _find_fuzzy_groups(["Foo", "Fox"], threshold=3)
        assert groups == []  # len 3 < 4

    def test_multiple_groups_disjoint(self):
        """3 个名字形成 2 个独立组。"""
        groups = _find_fuzzy_groups(
            ["Package1", "Packae1", "DiagramLayout", "DiaramLaout"],
            threshold=3,
        )
        assert len(groups) == 2
        flat = sorted(sum(groups, []))
        assert flat == [0, 1, 2, 3]

    def test_cim_ocr_pair_oerational_operational(self):
        """实测 cim-base-full.md 关键 pair：OerationalLimits/OperationalLimits。"""
        groups = _find_fuzzy_groups(["OerationalLimits", "OperationalLimits"], threshold=3)
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1]


# ---------------------------------------------------------------------------
# merge_fuzzy_duplicate_packages
# ---------------------------------------------------------------------------


class TestMergeFuzzyDuplicatePackages:
    """端到端：6 对 OCR 变体 → 合并为 6 个规范包。"""

    @pytest.mark.parametrize(
        "ocr_name,canon_name,distance",
        CIM_OCR_VARIANTS,
        ids=[f"{a}_vs_{b}" for a, b, _ in CIM_OCR_VARIANTS],
    )
    def test_ocr_variant_pairs_merged(self, ocr_name, canon_name, distance):
        """每对 OCR 变体应合并为规范名（较长的那个）。"""
        pkgs = [_make_pkg(ocr_name, ["Cls1"]), _make_pkg(canon_name, ["Cls2"])]
        result = merge_fuzzy_duplicate_packages(pkgs)
        # 同一对应合并为 1 个
        assert len(result) == 1
        # 规范名 = 较长的那个
        assert result[0].name == canon_name
        # 两个 ClassDef 都被保留
        class_names = sorted(c.name for c in result[0].classes)
        assert class_names == ["Cls1", "Cls2"]

    def test_all_six_cim_ocr_pairs_at_once(self):
        """一次性处理 6 对 cim-base-full.md OCR 变体。"""
        pkgs = []
        for ocr, canon, _ in CIM_OCR_VARIANTS:
            pkgs.append(_make_pkg(ocr, [f"{ocr}_cls"]))
            pkgs.append(_make_pkg(canon, [f"{canon}_cls"]))
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 6
        result_names = {p.name for p in result}
        expected = {canon for _, canon, _ in CIM_OCR_VARIANTS}
        assert result_names == expected

    def test_no_op_when_no_fuzzy_match(self):
        """完全不同的包名应保持不变。"""
        pkgs = [_make_pkg("Core"), _make_pkg("Wires"), _make_pkg("Domain")]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 3
        assert {p.name for p in result} == {"Core", "Wires", "Domain"}

    def test_empty_input(self):
        assert merge_fuzzy_duplicate_packages([]) == []

    def test_single_package(self):
        result = merge_fuzzy_duplicate_packages([_make_pkg("Foo")])
        assert len(result) == 1
        assert result[0].name == "Foo"

    def test_exact_duplicate_also_merged(self):
        """distance=0 仍满足阈值（fuzzy subsumes exact）。"""
        pkgs = [_make_pkg("Core", ["A"]), _make_pkg("Core", ["B"])]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 1
        assert sorted(c.name for c in result[0].classes) == ["A", "B"]

    def test_classes_deduped_within_group(self):
        """合并后同名 classes 仍按先到先得去重。"""
        pkgs = [
            _make_pkg("Packae1", ["Shared"]),
            _make_pkg("Package1", ["Shared", "NewOne"]),
        ]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 1
        class_names = [c.name for c in result[0].classes]
        assert "Shared" in class_names
        assert "NewOne" in class_names
        assert class_names.count("Shared") == 1

    def test_threshold_customization(self):
        """threshold=0 时仅合并精确匹配。"""
        pkgs = [_make_pkg("Packae1"), _make_pkg("Package1")]
        # threshold=0 → 不合并（distance=1）
        result = merge_fuzzy_duplicate_packages(pkgs, threshold=0)
        assert len(result) == 2
        # threshold=2 → 合并
        result = merge_fuzzy_duplicate_packages(pkgs, threshold=2)
        assert len(result) == 1

    def test_no_cross_group_collision(self):
        """不同前缀的相似名不应被错误合并（如 Bar/Baz 距离 2 但不合并）。"""
        # Bar/Baz 前缀不同 (Bar vs Baz)
        pkgs = [_make_pkg("Bar"), _make_pkg("Baz")]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 2

    def test_false_positive_production_protection_not_merged(self):
        """Production/Protection 同长度 false-positive 不合并（cim-base-full.md 实测）。

        关键洞察：OCR 噪声几乎总会插入/删除字符（产生长度差 ≥ 1），
        而两个真不同的短缩略词（如 Production/Protection）通常同长度。
        本测试验证：length_diff=0 时拒绝合并（防御 2a）。
        """
        # 长度差 0（都是 10），distance=2 → 应被拒绝
        groups = _find_fuzzy_groups(["Production", "Protection"], threshold=3)
        assert groups == []

        # 端到端：保持为 2 个独立 Package
        pkgs = [_make_pkg("Production", ["Generator"]), _make_pkg("Protection", ["Breaker"])]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 2
        assert {p.name for p in result} == {"Production", "Protection"}

    def test_same_length_blocked_even_when_distance_under_threshold(self):
        """同长度 + 距离小（如 FooBaz/FooBar）：不应合并（length_diff=0 防线）。"""
        # FooBaz/FooBar: dist=2, len_diff=0 → 拒绝
        groups = _find_fuzzy_groups(["FooBaz", "FooBar"], threshold=3)
        assert groups == []


# ---------------------------------------------------------------------------
# 与 merge_duplicate_packages 的关系
# ---------------------------------------------------------------------------


class TestRelationshipWithExactMerge:
    """fuzzy merge 是 exact merge 的超集。"""

    def test_exact_merge_unchanged(self):
        """merge_duplicate_packages 行为不变（精确匹配语义保留）。"""
        pkgs = [
            _make_pkg("Core", ["A"]),
            _make_pkg("Core", ["B"]),
        ]
        result = merge_duplicate_packages(pkgs)
        assert len(result) == 1
        assert sorted(c.name for c in result[0].classes) == ["A", "B"]

    def test_fuzzy_merge_handles_exact_duplicates(self):
        """fuzzy merge 自然覆盖 exact merge（distance=0 ≤ 2）。"""
        pkgs = [
            _make_pkg("Core", ["A"]),
            _make_pkg("Core", ["B"]),
        ]
        result = merge_fuzzy_duplicate_packages(pkgs)
        assert len(result) == 1
        assert sorted(c.name for c in result[0].classes) == ["A", "B"]
