"""P1 测试：跨包引用自动推断（_infer_refs.infer_cross_package_refs）。

背景：cim-base-full.md Stage 1+2 解析后 `ir.cross_package_refs = []`（空），
但 ClassDef.parents/associations 实际有 375+ 个跨包引用，导致：
  - OWL 缺 `owl:imports` 声明
  - Python Types 缺 `from Core_types import ...`（运行时会 ImportError）

`infer_cross_package_refs` 扫描所有 ClassDef.parents/associations，
从 (cls, parent/assoc.target) 重建 (from_pkg, to_pkg, via_class)。
"""
from cim_ontology.cleaner._infer_refs import infer_cross_package_refs
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    DataProperty,
    ObjectProperty,
    Package,
)

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _pkg(name: str, classes: list[ClassDef] | None = None) -> Package:
    """构造测试用 Package。"""
    return Package(
        iri=f"http://x#{name}",
        name=name,
        classes=classes or [],
    )


def _cls(
    name: str,
    *,
    parents: list[ClassRef] | None = None,
    associations: list[ObjectProperty] | None = None,
    attrs: int = 0,
) -> ClassDef:
    """构造指定 parents/associations 的 ClassDef。"""
    return ClassDef(
        name=name,
        attributes=[
            DataProperty(name=f"attr_{i}", data_type="xsd:string")
            for i in range(attrs)
        ],
        parents=parents or [],
        associations=associations or [],
    )


# ---------------------------------------------------------------------------
# 基础场景
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsBasic:
    """基础场景：空输入、无引用、自引用、同包不引用。"""

    def test_empty_packages_returns_empty(self):
        """空列表 → 空结果。"""
        assert infer_cross_package_refs([]) == []

    def test_no_parents_or_assocs_returns_empty(self):
        """无继承/关联 → 空结果。"""
        pkgs = [
            _pkg("Core", [_cls("A")]),
            _pkg("Wires", [_cls("B")]),
        ]
        assert infer_cross_package_refs(pkgs) == []

    def test_within_package_references_not_cross_pkg(self):
        """同包内的父类引用不应被推断为跨包引用。"""
        pkgs = [
            _pkg("Core", [
                _cls("Parent"),
                _cls("Child", parents=[ClassRef(package="Core", class_name="Parent")]),
            ]),
        ]
        assert infer_cross_package_refs(pkgs) == []

    def test_reference_to_unknown_class_ignored(self):
        """引用不存在的 class（不在任何包中）应被静默忽略。"""
        pkgs = [
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="NonExistentClass"),
                ]),
            ]),
        ]
        # 目标类不在任何包中 → 不应被推断为 ref
        assert infer_cross_package_refs(pkgs) == []

    def test_parent_with_none_class_name_skipped(self):
        """Stage 2 清空的 parent class_name 应被跳过，不产生跨包引用。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name=None),
                ]),
            ]),
        ]
        assert infer_cross_package_refs(pkgs) == []


# ---------------------------------------------------------------------------
# 跨包 parent 引用
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsParent:
    """跨包继承引用。"""

    def test_simple_parent_ref(self):
        """Wires::ACLineSegment 继承 Core::IdentifiedObject → 1 个 ref。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        assert len(refs) == 1
        assert refs[0].from_package == "Wires"
        assert refs[0].to_package == "Core"
        assert refs[0].via_class == "IdentifiedObject"
        assert refs[0].via_property == "parent:ACLineSegment"

    def test_multiple_parents_different_packages(self):
        """多个跨包父类 → 多个 ref。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject"), _cls("PowerSystemResource")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                    ClassRef(package="Core", class_name="PowerSystemResource"),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        assert len(refs) == 2
        # 排序：按 (from, to, via) 字典序
        assert refs[0].via_class == "IdentifiedObject"
        assert refs[1].via_class == "PowerSystemResource"


# ---------------------------------------------------------------------------
# 跨包 association 引用
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsAssoc:
    """跨包关联端引用。"""

    def test_simple_assoc_ref(self):
        """Wires::ACLineSegment 关联 Core::Substation → 1 个 ref。"""
        pkgs = [
            _pkg("Core", [_cls("Substation")]),
            _pkg("Wires", [
                _cls("ACLineSegment", associations=[
                    ObjectProperty(
                        name="ToSubstation",
                        target=ClassRef(package="Core", class_name="Substation"),
                    ),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        assert len(refs) == 1
        assert refs[0].from_package == "Wires"
        assert refs[0].to_package == "Core"
        assert refs[0].via_class == "Substation"
        # via_property 是 assoc.name（不是 parent:xxx）
        assert refs[0].via_property == "ToSubstation"

    def test_empty_target_class_name_skipped(self):
        """空 class_name 的 assoc 目标应被跳过（不 crash）。"""
        pkgs = [
            _pkg("Core", [_cls("Substation")]),
            _pkg("Wires", [
                _cls("ACLineSegment", associations=[
                    # 正常
                    ObjectProperty(
                        name="ToSubstation",
                        target=ClassRef(package="Core", class_name="Substation"),
                    ),
                    # OCR 噪声：空 class_name
                    ObjectProperty(
                        name="Container",
                        target=ClassRef(package="Core", class_name=""),
                    ),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        # 只有 1 个有效 ref（空 class_name 的被静默跳过）
        assert len(refs) == 1
        assert refs[0].via_class == "Substation"


# ---------------------------------------------------------------------------
# 跨包混合 + 去重 + 排序
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsDedupAndSort:
    """去重与排序：同一 (from, to, via) 只出现一次，按字典序排序。"""

    def test_multiple_classes_same_target_deduped(self):
        """多个类引用同一目标 → 去重为 1 个 ref。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                ]),
                _cls("Breaker", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                ]),
                _cls("Switch", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        # 3 个类都引用 IdentifiedObject，但 (Wires, Core, IdentifiedObject) 只算 1 次
        assert len(refs) == 1
        assert refs[0].from_package == "Wires"
        assert refs[0].to_package == "Core"
        assert refs[0].via_class == "IdentifiedObject"
        # via_property 取最新一次扫描到的（顺序不保证，但应是 parent:某 class）
        assert refs[0].via_property.startswith("parent:")

    def test_results_sorted_alphabetically(self):
        """结果按 (from_package, to_package, via_class) 字典序排序。"""
        pkgs = [
            _pkg("Core", [_cls("A"), _cls("B"), _cls("C")]),
            _pkg("Domain", [_cls("D")]),
            _pkg("Wires", [
                _cls("Z", parents=[ClassRef(package="Core", class_name="A")]),
                _cls("Y", parents=[ClassRef(package="Core", class_name="B")]),
                _cls("X", parents=[ClassRef(package="Domain", class_name="D")]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        keys = [(r.from_package, r.to_package, r.via_class) for r in refs]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# 真实 CIM 样本
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsCimReal:
    """真实 CIM 跨包引用样本。"""

    def test_wires_inherits_from_core(self):
        """Wires::ACLineSegment 继承 Core::IdentifiedObject（标准 CIM 模式）。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject"), _cls("PowerSystemResource")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                    ClassRef(package="Core", class_name="PowerSystemResource"),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        # 2 个不同 parent → 2 个 ref（dedup 键是 (from, to, via_class)）
        assert len(refs) == 2
        via_classes = {r.via_class for r in refs}
        assert via_classes == {"IdentifiedObject", "PowerSystemResource"}
        assert all(r.from_package == "Wires" and r.to_package == "Core" for r in refs)

    def test_three_package_chain(self):
        """三包链：Production → Wires → Core（Production 间接通过 Wires 引用 Core）。"""
        pkgs = [
            _pkg("Core", [_cls("IdentifiedObject")]),
            _pkg("Wires", [
                _cls("ACLineSegment", parents=[
                    ClassRef(package="Core", class_name="IdentifiedObject"),
                ]),
            ]),
            _pkg("Production", [
                _cls("GeneratingUnit", parents=[
                    ClassRef(package="Wires", class_name="ACLineSegment"),
                ]),
            ]),
        ]
        refs = infer_cross_package_refs(pkgs)
        # 2 个 ref：Wires→Core + Production→Wires
        keys = {(r.from_package, r.to_package) for r in refs}
        assert keys == {("Wires", "Core"), ("Production", "Wires")}


# ---------------------------------------------------------------------------
# 不修改入参
# ---------------------------------------------------------------------------


class TestInferCrossPackageRefsImmutability:
    """不修改入参（immutability / KISS）。"""

    def test_does_not_mutate_input_packages(self):
        """输入 packages 不应被修改（无 in-place 变更）。"""
        core = _pkg("Core", [_cls("IdentifiedObject")])
        wires = _pkg("Wires", [
            _cls("ACLineSegment", parents=[
                ClassRef(package="Core", class_name="IdentifiedObject"),
            ]),
        ])
        # 深拷贝以记录原始状态
        from copy import deepcopy
        core_before = deepcopy(core)
        wires_before = deepcopy(wires)

        infer_cross_package_refs([core, wires])

        # 验证：classes 数量和内容不变
        assert len(core.classes) == len(core_before.classes)
        assert core.classes[0].name == core_before.classes[0].name
        assert len(wires.classes) == len(wires_before.classes)
        assert wires.classes[0].name == wires_before.classes[0].name
        assert wires.classes[0].parents[0].class_name == wires_before.classes[0].parents[0].class_name
