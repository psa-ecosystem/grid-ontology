"""P1 测试：Class 跨包去重（_class_dedup.deduplicate_cross_package_classes）。

背景：cim-base-full.md Stage 1+2 解析产生 304 个 ClassDef 在 >1 包中重复出现，
加上 181 个 intra-pkg 重复（OCR 变体合并后剩余）。绝大多数重复为空壳
（0 attrs / 0 parents / 0 assoc），少数含完整定义。

策略：richest wins — 对每个 class name 组选最丰富的 ClassDef（5-tuple 排序），
winner 留在原 Package 不动，其余 drop。
"""
import pytest

from cim_ontology.adapters._class_dedup import (
    _classdef_rank_key,
    deduplicate_cross_package_classes,
    RANK_DIMENSIONS,
)
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


def _make_pkg(name: str, classes: list[ClassDef] | None = None) -> Package:
    """构造测试用 Package（仿 test_pkg_dedup_fuzzy.py 模式）。"""
    return Package(
        iri=f"http://x#{name}",
        name=name,
        classes=classes or [],
    )


def _cls(
    name: str,
    *,
    attrs: int = 0,
    assocs: int = 0,
    parents: int = 0,
    desc: bool = False,
) -> ClassDef:
    """构造指定丰富度的 ClassDef。

    Args:
        name: 类名
        attrs: 属性数量（默认 0 = 空壳）
        assocs: 关联端数量
        parents: 父类引用数量
        desc: 是否有 description
    """
    return ClassDef(
        name=name,
        attributes=[
            DataProperty(name=f"attr_{i}", data_type="xsd:string")
            for i in range(attrs)
        ],
        associations=[
            ObjectProperty(name=f"assoc_{i}", target=ClassRef(package="X", class_name="Y"))
            for i in range(assocs)
        ],
        parents=[
            ClassRef(package="X", class_name=f"Parent_{i}")
            for i in range(parents)
        ],
        description="has description" if desc else None,
    )


# ---------------------------------------------------------------------------
# Ranking 算法
# ---------------------------------------------------------------------------


class TestClassDefRankKey:
    """_classdef_rank_key 排序测试。"""

    def test_more_attributes_wins(self):
        """主权重：attrs 越多 rank 越高。"""
        a = _classdef_rank_key(_cls("A", attrs=5), position=100)
        b = _classdef_rank_key(_cls("B", attrs=3), position=0)
        assert a > b

    def test_associations_break_tie(self):
        """attrs 相等时，assocs 越多 rank 越高。"""
        a = _classdef_rank_key(_cls("A", attrs=3, assocs=2), position=100)
        b = _classdef_rank_key(_cls("B", attrs=3, assocs=0), position=0)
        assert a > b

    def test_parents_break_tie(self):
        """attrs + assocs 相等时，parents 越多 rank 越高。"""
        a = _classdef_rank_key(_cls("A", attrs=3, assocs=2, parents=1), position=100)
        b = _classdef_rank_key(_cls("B", attrs=3, assocs=2, parents=0), position=0)
        assert a > b

    def test_description_breaks_tie(self):
        """前三维相等时，有 description 的胜出。"""
        a = _classdef_rank_key(_cls("A", attrs=3, desc=True), position=100)
        b = _classdef_rank_key(_cls("B", attrs=3, desc=False), position=0)
        assert a > b

    def test_first_occurrence_wins_on_all_tied(self):
        """所有维度相等时，position 越小（即越早出现）rank 越高（用 -position）。"""
        a = _classdef_rank_key(_cls("A"), position=5)
        b = _classdef_rank_key(_cls("B"), position=100)
        # -5 > -100，所以 a > b
        assert a > b

    def test_rank_dimensions_constant(self):
        """RANK_DIMENSIONS 常量暴露 5 个维度名（用于 structlog 文档）。"""
        assert len(RANK_DIMENSIONS) == 5
        assert "attribute_count" in RANK_DIMENSIONS
        assert "first_occurrence" in RANK_DIMENSIONS


# ---------------------------------------------------------------------------
# deduplicate_cross_package_classes 端到端
# ---------------------------------------------------------------------------


class TestDeduplicateCrossPackageClasses:
    """跨包 + intra-pkg 去重端到端测试。"""

    def test_empty_input(self):
        """空输入返回空列表。"""
        assert deduplicate_cross_package_classes([]) == []

    def test_no_duplicates_no_op(self):
        """无重复时返回深拷贝（不可变性）。"""
        pkgs = [
            _make_pkg("Core", [_cls("A", attrs=2)]),
            _make_pkg("Domain", [_cls("B", attrs=3)]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        assert len(result) == 2
        assert {p.name for p in result} == {"Core", "Domain"}
        # 类的属性应保持
        core = next(p for p in result if p.name == "Core")
        assert len(core.classes[0].attributes) == 2

    def test_single_package_unchanged(self):
        """单包输入也正常处理。"""
        pkgs = [_make_pkg("Core", [_cls("A", attrs=3)])]
        result = deduplicate_cross_package_classes(pkgs)
        assert len(result) == 1
        assert len(result[0].classes) == 1
        assert len(result[0].classes[0].attributes) == 3

    def test_drop_empty_shell_favoring_richer(self):
        """关键场景：Core 有 attrs，Domain 空壳 → 保留 Core。"""
        pkgs = [
            _make_pkg("Core", [_cls("IdentifiedObject", attrs=4)]),
            _make_pkg("Domain", [_cls("IdentifiedObject")]),  # 空壳
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        assert len(core.classes) == 1
        assert len(core.classes[0].attributes) == 4
        assert domain.classes == []  # 空壳被 drop

    def test_first_occurrence_wins_when_exactly_equal(self):
        """全 tie 时 first occurrence wins（用 position tie-breaker）。"""
        pkgs = [
            _make_pkg("Core", [_cls("Foo")]),
            _make_pkg("Domain", [_cls("Foo")]),
            _make_pkg("Wires", [_cls("Foo")]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        wires = next(p for p in result if p.name == "Wires")
        # 全部空壳 tie，position 最小（最早出现）= Core → 保留 Core
        assert len(core.classes) == 1
        assert domain.classes == []
        assert wires.classes == []

    def test_winner_stays_in_original_package(self):
        """关键不变量：winner 留在原 Package，不被搬运到别的包。"""
        pkgs = [
            _make_pkg("Wires", [_cls("EnergyConsumer", attrs=17, assocs=5)]),
            _make_pkg("Core", [_cls("EnergyConsumer", attrs=0)]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        wires = next(p for p in result if p.name == "Wires")
        core = next(p for p in result if p.name == "Core")
        # 富定义在 Wires，应留在 Wires
        assert len(wires.classes) == 1
        assert len(wires.classes[0].attributes) == 17
        assert core.classes == []

    def test_intra_package_duplicates_also_resolved(self):
        """关键不变量：intra-pkg 重复（同名类在同一包出现多次）也被清理。"""
        pkgs = [
            _make_pkg(
                "Core",
                [
                    _cls("IdentifiedObject"),  # 空壳
                    _cls("IdentifiedObject"),  # 空壳（OCR 变体残留）
                    _cls("IdentifiedObject", attrs=4),  # 富定义
                ],
            ),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        # 富定义胜出，其余 2 个空壳 drop
        assert len(result[0].classes) == 1
        assert len(result[0].classes[0].attributes) == 4

    def test_does_not_mutate_input(self):
        """深拷贝契约：不修改入参的 classes 列表。"""
        original_classes = [
            _cls("IdentifiedObject", attrs=4),
            _cls("IdentifiedObject"),
        ]
        pkgs = [_make_pkg("Core", list(original_classes))]
        deduplicate_cross_package_classes(pkgs)
        # 入参 classes 列表长度不变（2 个）
        assert len(pkgs[0].classes) == 2
        assert len(original_classes) == 2

    def test_returns_new_list_same_length(self):
        """Package 数量保持不变。"""
        pkgs = [
            _make_pkg("Core", [_cls("A", attrs=2)]),
            _make_pkg("Domain", [_cls("A")]),
            _make_pkg("Wires", [_cls("A", attrs=1)]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        assert len(result) == len(pkgs)
        assert {p.name for p in result} == {p.name for p in pkgs}

    def test_package_names_unchanged_after_dedup(self):
        """Package.name 保持不变（即使 classes 全 drop 也不删除 Package）。"""
        pkgs = [
            _make_pkg("AuxPkg", [_cls("Foo")]),
            _make_pkg("Core", [_cls("Foo", attrs=2)]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        aux = next(p for p in result if p.name == "AuxPkg")
        # AuxPkg 只含空壳 Foo，应被清空但 Package 本身保留
        assert aux.classes == []
        assert aux.name == "AuxPkg"

    def test_multiple_duplicate_groups_handled(self):
        """多组重复同时处理。"""
        pkgs = [
            _make_pkg("Core", [_cls("Foo", attrs=2), _cls("Bar", attrs=3)]),
            _make_pkg("Domain", [_cls("Foo"), _cls("Bar")]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        # Core 两个都胜出
        assert {c.name for c in core.classes} == {"Foo", "Bar"}
        assert domain.classes == []

    def test_class_only_in_one_package_unchanged(self):
        """只在一个包出现的类保持不变。"""
        pkgs = [
            _make_pkg("Core", [_cls("Universal", attrs=5)]),
            _make_pkg("Domain", [_cls("LocalOnly")]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        assert len(core.classes) == 1
        assert len(core.classes[0].attributes) == 5
        assert len(domain.classes) == 1
        assert domain.classes[0].name == "LocalOnly"

    def test_mixed_with_parents_breaks_tie(self):
        """attrs 相等时，parents 多的胜出。"""
        pkgs = [
            _make_pkg("Core", [_cls("Foo", attrs=2)]),
            _make_pkg("Domain", [_cls("Foo", attrs=2, parents=1)]),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        # Domain 有 parents，胜出（attrs 相等时 parents 多者胜）
        assert core.classes == []
        assert len(domain.classes) == 1
        assert len(domain.classes[0].parents) == 1


# ---------------------------------------------------------------------------
# cim-base-full.md 真实类样本
# ---------------------------------------------------------------------------


class TestCimRealClasses:
    """cim-base-full.md 实测样本（来自 cim-e2e-validation-report.md §2.3）。"""

    def test_identified_object_in_core(self):
        """IdentifiedObject：4 处（Core×3 空 + Core×1 富） → 保留 Core 富定义。"""
        pkgs = [
            _make_pkg(
                "Core",
                [
                    _cls("IdentifiedObject"),  # empty
                    _cls("IdentifiedObject"),  # empty
                    _cls("IdentifiedObject"),  # empty
                    _cls("IdentifiedObject", attrs=4, assocs=2),  # rich
                ],
            ),
            _make_pkg("Domain", [_cls("IdentifiedObject")]),  # cross-pkg dup
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        # Core 唯一保留富定义
        assert len(core.classes) == 1
        assert len(core.classes[0].attributes) == 4
        assert len(core.classes[0].associations) == 2
        # Domain 重复被 drop
        assert domain.classes == []

    def test_active_power_three_occurrences(self):
        """ActivePower：3 处（Domain×2 空 + Core×1 空 + Domain×1 富 3 attrs） → Domain 富胜出。"""
        pkgs = [
            _make_pkg("Core", [_cls("ActivePower")]),
            _make_pkg(
                "Domain",
                [
                    _cls("ActivePower"),
                    _cls("ActivePower"),
                    _cls("ActivePower", attrs=3),
                ],
            ),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        # Domain 富定义胜出（含 3 attrs）
        assert len(domain.classes) == 1
        assert len(domain.classes[0].attributes) == 3
        # Core 空壳被 drop
        assert core.classes == []

    def test_energy_consumer_four_occurrences(self):
        """EnergyConsumer：4 处（含 Wires 含 17 attrs 富定义） → Wires 富胜出。"""
        pkgs = [
            _make_pkg("Core", [_cls("EnergyConsumer")]),
            _make_pkg(
                "Wires",
                [
                    _cls("EnergyConsumer"),
                    _cls("EnergyConsumer"),
                    _cls("EnergyConsumer", attrs=11, assocs=8),  # rich 1
                    _cls("EnergyConsumer", attrs=17, parents=5, assocs=20),  # rich 2
                ],
            ),
        ]
        result = deduplicate_cross_package_classes(pkgs)
        wires = next(p for p in result if p.name == "Wires")
        core = next(p for p in result if p.name == "Core")
        # Wires 的富定义 2 胜出（17 attrs 最多）
        assert len(wires.classes) == 1
        assert len(wires.classes[0].attributes) == 17
        assert len(wires.classes[0].parents) == 5
        assert len(wires.classes[0].associations) == 20
        # Core 空壳被 drop
        assert core.classes == []

    def test_class_only_empty_shells_picks_first(self):
        """所有重复都是空壳 → first occurrence wins。"""
        pkgs = [
            _make_pkg("Core", [_cls("Empty")]),  # position 0
            _make_pkg("Domain", [_cls("Empty")]),  # position 1
            _make_pkg("Wires", [_cls("Empty")]),  # position 2
        ]
        result = deduplicate_cross_package_classes(pkgs)
        core = next(p for p in result if p.name == "Core")
        domain = next(p for p in result if p.name == "Domain")
        wires = next(p for p in result if p.name == "Wires")
        # Core 是 first occurrence，胜出
        assert len(core.classes) == 1
        assert core.classes[0].name == "Empty"
        # 其他包被 drop
        assert domain.classes == []
        assert wires.classes == []


# ---------------------------------------------------------------------------
# 集成测试：OWL adapter 规模验证
# ---------------------------------------------------------------------------


class TestClassDedupIntegration:
    """集成测试：deduplicate_cross_package_classes 与 OWL adapter 配合。"""

    def test_owl_class_count_drops_after_dedup(self, tmp_path):
        """OWL emit 后 cim17_full.ttl 中 owl:Class 计数 == 唯一类数。"""
        from rdflib import Graph, RDF, OWL

        from cim_ontology.adapters.owl import OwlTurtleAdapter
        from cim_ontology.ir.models import OntologyIR

        # 构造 5 个包，每个都重复 3 个类（共 3 unique classes，应去重为 3）
        n_pkgs = 5
        unique_classes = ["IdentifiedObject", "Foo", "Bar"]
        packages = [
            _make_pkg(
                f"Pkg{i}",
                [_cls(c, attrs=2) if i == 0 else _cls(c) for c in unique_classes],
            )
            for i in range(n_pkgs)
        ]
        ir = OntologyIR(
            base_iri="http://iec.ch/TC57/2024/CIM-schema-cim17#",
            version="cim17",
            packages=packages,
        )

        adapter = OwlTurtleAdapter()
        adapter.emit(ir, tmp_path)

        full_path = tmp_path / "cim17_full.ttl"
        assert full_path.exists()

        g = Graph()
        g.parse(full_path, format="turtle")
        classes = {str(s) for s, _, _ in g.triples((None, RDF.type, OWL.Class))}
        # 唯一类数应等于 3（去重后），而非 5 * 3 = 15
        assert len(classes) == 3

    def test_owl_class_metadata_preserved_after_dedup(self, tmp_path):
        """richest ClassDef 的属性元数据应保留在 OWL 输出中。"""
        from rdflib import Graph, RDF, OWL

        from cim_ontology.adapters.owl import OwlTurtleAdapter
        from cim_ontology.ir.models import OntologyIR

        # 富定义在 Wires，空壳在 Core
        packages = [
            _make_pkg("Core", [_cls("Foo")]),
            _make_pkg("Wires", [_cls("Foo", attrs=3)]),
        ]
        ir = OntologyIR(
            base_iri="http://iec.ch/TC57/2024/CIM-schema-cim17#",
            version="cim17",
            packages=packages,
        )

        adapter = OwlTurtleAdapter()
        adapter.emit(ir, tmp_path)

        # Wires 文件应包含 Foo 的 DatatypeProperty metadata
        wires_file = tmp_path / "cim17_Wires.ttl"
        assert wires_file.exists()
        g = Graph()
        g.parse(wires_file, format="turtle")
        # 3 个 DatatypeProperty（attr_0, attr_1, attr_2）
        from rdflib import RDF as RDF_NS, OWL as OWL_NS

        props = list(
            g.subjects(RDF_NS.type, OWL_NS.DatatypeProperty)
        )
        assert len(props) == 3