"""IR 不变量属性测试（设计规范 §8.5）。"""
from hypothesis import given
from hypothesis import strategies as st

from cim_ontology.adapters._class_dedup import deduplicate_cross_package_classes
from cim_ontology.ir.models import (
    ClassDef,
    Multiplicity,
    OntologyIR,
    Package,
)


@st.composite
def ir_strategy(draw):
    """生成随机 IR。"""
    pkg_names = draw(st.lists(
        st.sampled_from(["A", "B", "C", "D"]),
        min_size=1, max_size=4, unique=True,
    ))
    packages = []
    for name in pkg_names:
        classes = []
        for i in range(draw(st.integers(min_value=1, max_value=5))):
            classes.append(ClassDef(name=f"Cls_{name}_{i}"))
        packages.append(Package(iri=f"http://x#{name}", name=name, classes=classes))
    return OntologyIR(packages=packages)


@st.composite
def ir_with_cross_pkg_dupes(draw):
    """生成含跨包重复的随机 IR（用于测试 class_dedup 不变量）。

    构造：
    - Core: n_unique 个 unique class + n_dupes 个 dup class
    - Domain: 同样 n_dupes 个 dup class（跨包重复）
    - Wires: 空（验证空包保留）
    """
    n_unique = draw(st.integers(min_value=2, max_value=8))
    n_dupes = draw(st.integers(min_value=1, max_value=5))
    packages = [
        Package(
            iri="http://x#Core",
            name="Core",
            classes=[
                ClassDef(name=f"Unique_{i}") for i in range(n_unique)
            ] + [
                ClassDef(name=f"Dup_{i}") for i in range(n_dupes)
            ],
        ),
        Package(
            iri="http://x#Domain",
            name="Domain",
            classes=[ClassDef(name=f"Dup_{i}") for i in range(n_dupes)],
        ),
        Package(iri="http://x#Wires", name="Wires", classes=[]),
    ]
    return OntologyIR(packages=packages)


class TestInvariants:
    @given(ir_strategy())
    def test_no_duplicate_class_names_within_package(self, ir):
        for pkg in ir.packages:
            names = [c.name for c in pkg.classes]
            assert len(names) == len(set(names)), f"包 {pkg.name} 存在重复类名"

    @given(ir_strategy())
    def test_all_classes_returns_all(self, ir):
        all_classes = ir.all_classes()
        expected = sum(len(p.classes) for p in ir.packages)
        assert len(all_classes) == expected

    @given(ir_strategy())
    def test_get_class_finds_existing(self, ir):
        for pkg in ir.packages:
            for cls in pkg.classes:
                assert ir.get_class(cls.name) is not None

    @given(ir_strategy())
    def test_get_class_returns_none_for_unknown(self, ir):
        assert ir.get_class("NonExistent_xyz_123") is None

    @given(st.integers(min_value=0, max_value=10), st.integers(min_value=0, max_value=10))
    def test_multiplicity_is_many_consistency(self, min_val, max_val):
        max_repr = max_val if max_val <= 1 else "*"
        m = Multiplicity(min=min_val, max=max_val, raw=f"{min_val}..{max_repr}")
        if max_val is None or max_val > 1:
            assert m.is_many is True
        else:
            assert m.is_many is False


class TestDedupInvariants:
    """v1.5 P1：deduplicate_cross_package_classes 不变量。"""

    @given(ir_with_cross_pkg_dupes())
    def test_no_duplicate_class_names_across_packages_after_dedup(self, ir):
        """跨包视角：同一 class name 应只出现一次。"""
        deduped = deduplicate_cross_package_classes(ir.packages)
        seen: dict[str, str] = {}
        for pkg in deduped:
            for cls in pkg.classes:
                assert cls.name not in seen, (
                    f"类 {cls.name} 既出现在 {seen[cls.name]} 又出现在 {pkg.name}"
                )
                seen[cls.name] = pkg.name

    @given(ir_with_cross_pkg_dupes())
    def test_no_duplicate_class_names_within_package_after_dedup(self, ir):
        """包内视角：同一 class name 在同一包内也应只出现一次。"""
        deduped = deduplicate_cross_package_classes(ir.packages)
        for pkg in deduped:
            names = [c.name for c in pkg.classes]
            assert len(names) == len(set(names)), (
                f"包 {pkg.name} dedup 后仍存在重复类名: "
                f"{[n for n in names if names.count(n) > 1]}"
            )

    @given(ir_with_cross_pkg_dupes())
    def test_package_count_unchanged_after_dedup(self, ir):
        """Package 数量保持不变。"""
        deduped = deduplicate_cross_package_classes(ir.packages)
        assert len(deduped) == len(ir.packages)

    @given(ir_with_cross_pkg_dupes())
    def test_package_names_unchanged_after_dedup(self, ir):
        """Package.name 集合保持不变。"""
        deduped = deduplicate_cross_package_classes(ir.packages)
        assert {p.name for p in deduped} == {p.name for p in ir.packages}

    @given(ir_with_cross_pkg_dupes())
    def test_total_class_count_drops_or_unchanged(self, ir):
        """总 ClassDef 数应 ≤ dedup 前（不会增加）。"""
        before = sum(len(p.classes) for p in ir.packages)
        deduped = deduplicate_cross_package_classes(ir.packages)
        after = sum(len(p.classes) for p in deduped)
        assert after <= before

    @given(ir_strategy())
    def test_dedup_is_noop_on_clean_input(self, ir):
        """无重复的 IR dedup 后应保持不变（class 数）。"""
        before = sum(len(p.classes) for p in ir.packages)
        deduped = deduplicate_cross_package_classes(ir.packages)
        after = sum(len(p.classes) for p in deduped)
        assert after == before

    def test_dedup_empty_input(self):
        """空输入返回空列表。"""
        assert deduplicate_cross_package_classes([]) == []
