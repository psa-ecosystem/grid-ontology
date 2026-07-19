"""包依赖图与拓扑排序测试。"""
from cim_ontology.cleaner.dep_graph import (
    build_package_dependency_graph,
    topological_sort,
)
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    CrossPackageRef,
    Multiplicity,
    OntologyIR,
    Package,
)


def _ir_with_refs(refs: list[CrossPackageRef]) -> OntologyIR:
    """构造带跨包引用的 IR。"""
    pkg_a = Package(iri="http://x#A", name="A", classes=[
        ClassDef(name="A1", associations=[]),
    ])
    pkg_b = Package(iri="http://x#B", name="B", classes=[
        ClassDef(name="B1", associations=[]),
    ])
    return OntologyIR(
        packages=[pkg_a, pkg_b],
        cross_package_refs=refs,
    )


class TestBuildDependencyGraph:
    def test_simple_dependency(self):
        ir = _ir_with_refs([
            CrossPackageRef(from_package="B", to_package="A", via_class="B1", via_property="a"),
        ])
        g = build_package_dependency_graph(ir)
        assert "A" in g.nodes
        assert "B" in g.nodes
        # B 依赖 A（有边 A → B，被依赖方在前以便拓扑排序得到依赖优先序）
        assert "B" in list(g.successors("A"))


class TestTopologicalSort:
    def test_orders_by_dependency(self):
        ir = _ir_with_refs([
            CrossPackageRef(from_package="B", to_package="A", via_class="B1", via_property="a"),
        ])
        g = build_package_dependency_graph(ir)
        ordered = topological_sort(g)
        # A 在 B 前
        assert ordered.index("A") < ordered.index("B")

    def test_independent_packages_in_any_order(self):
        pkg_a = Package(iri="http://x#A", name="A", classes=[])
        pkg_b = Package(iri="http://x#B", name="B", classes=[])
        ir = OntologyIR(packages=[pkg_a, pkg_b])
        g = build_package_dependency_graph(ir)
        ordered = topological_sort(g)
        assert set(ordered) == {"A", "B"}