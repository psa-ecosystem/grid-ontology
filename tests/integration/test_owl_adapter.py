"""OWL/Turtle 适配器集成测试。"""
import pytest
from rdflib import OWL, RDF, RDFS, Graph, URIRef

from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    CrossPackageRef,
    Multiplicity,
    OntologyIR,
    Package,
    SourceInfo,
)


@pytest.fixture
def ir_two_packages():
    pkg_a = Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject")],
    )
    pkg_b = Package(
        iri="http://x#B", name="B",
        classes=[ClassDef(name="Specific", parents=[
            ClassRef(package="A", class_name="IdentifiedObject"),
        ])],
    )
    return OntologyIR(
        packages=[pkg_a, pkg_b],
        cross_package_refs=[
            CrossPackageRef(from_package="B", to_package="A",
                            via_class="Specific", via_property="parents"),
        ],
        source=SourceInfo(
            document_path="test.md", document_sha256="x" * 64,
            parsed_at="2026-06-22T00:00:00Z", parser_version="0.1.0",
        ),
    )


class TestOwlAdapter:
    def test_emits_per_package_files(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        result = adapter.emit(ir_two_packages, tmp_path)
        assert (tmp_path / "cim17_A.ttl").exists()
        assert (tmp_path / "cim17_B.ttl").exists()
        assert (tmp_path / "cim17_full.ttl").exists()

    def test_owl_imports_declared(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_B.ttl", format="turtle")
        # B 应该 import A
        import_found = any(
            str(o).endswith("_A") for s, p, o in g.triples((None, OWL.imports, None))
        )
        assert import_found

    def test_classes_serialized(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        # 至少存在 owl:Class
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) >= 2

    def test_parent_with_none_class_name_is_skipped(self, tmp_path):
        """Stage 2 清空的 parent class_name 不应让 OWL emit 崩溃。"""
        ir = OntologyIR(
            packages=[
                Package(
                    iri="http://x#Core",
                    name="Core",
                    classes=[
                        ClassDef(
                            name="NoisyChild",
                            parents=[ClassRef(package="Core", class_name=None)],
                        ),
                    ],
                ),
            ],
            source=SourceInfo(
                document_path="test.md",
                document_sha256="x" * 64,
                parsed_at="2026-06-22T00:00:00Z",
                parser_version="0.1.0",
            ),
        )

        OwlTurtleAdapter().emit(ir, tmp_path)

        graph = Graph()
        graph.parse(tmp_path / "cim17_full.ttl", format="turtle")
        child_iri = URIRef(
            "http://iec.ch/TC57/2024/CIM-schema-cim17#NoisyChild"
        )
        assert list(graph.objects(child_iri, RDFS.subClassOf)) == []

    def test_class_has_rdfs_label(self, ir_two_packages, tmp_path):
        """P1.2: 每个 ClassDef 应生成 rdfs:label（不仅是 rdf:type）。"""
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        from rdflib import RDFS as RDFS_NS
        cls_iri = URIRef("http://iec.ch/TC57/2024/CIM-schema-cim17#IdentifiedObject")
        labels = list(g.objects(cls_iri, RDFS_NS.label))
        assert len(labels) >= 1
        assert str(labels[0]) == "IdentifiedObject"

    def test_class_has_is_defined_by(self, ir_two_packages, tmp_path):
        """P1.2: 每个 ClassDef 应通过 rdfs:isDefinedBy 关联其包。"""
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        from rdflib import RDFS as RDFS_NS
        cls_iri = URIRef("http://iec.ch/TC57/2024/CIM-schema-cim17#IdentifiedObject")
        defs = list(g.objects(cls_iri, RDFS_NS.isDefinedBy))
        assert len(defs) >= 1

    def test_dataproperty_has_label(self, ir_two_packages_with_attrs, tmp_path):
        """P1.2: 每个 DataProperty 应生成 rdfs:label。"""
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages_with_attrs, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        from rdflib import RDFS as RDFS_NS
        prop_iri = URIRef("http://iec.ch/TC57/2024/CIM-schema-cim17#IdentifiedObject.mRID")
        labels = list(g.objects(prop_iri, RDFS_NS.label))
        assert len(labels) >= 1
        assert str(labels[0]) == "mRID"

    def test_full_doc_meets_triple_threshold(self, ir_realistic_full_doc, tmp_path):
        """P1.2: 真实规模 IR（10 包 × 100 类）应生成 ≥5000 triples。"""
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_realistic_full_doc, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        # 10 包 × 100 类 × ~5 attr/类 × 4 triples/attr ≈ 20000
        assert len(g) >= 5000


@pytest.fixture
def ir_two_packages_with_attrs():
    pkg_a = Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(
            name="IdentifiedObject",
            attributes=[ClassDef.AttributesType(name="mRID", data_type="string")] if hasattr(ClassDef, 'AttributesType') else [],
        )] if False else [ClassDef(
            name="IdentifiedObject",
            attributes=[
                __import__('cim_ontology.ir.models', fromlist=['DataProperty']).DataProperty(
                    name="mRID", data_type="string",
                ),
            ],
        )],
    )
    return OntologyIR(
        packages=[pkg_a],
        source=SourceInfo(
            document_path="test.md", document_sha256="x" * 64,
            parsed_at="2026-06-22T00:00:00Z", parser_version="0.1.0",
        ),
    )


@pytest.fixture
def ir_realistic_full_doc():
    """10 包 × 100 类，每类 ~5 attrs → 预期 ~20000 triples。"""
    from cim_ontology.ir.models import DataProperty
    packages = []
    for p in range(10):
        classes = []
        for c in range(100):
            attrs = [
                DataProperty(
                    name=f"attr_{i}",
                    data_type="string",
                    multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
                )
                for i in range(5)
            ]
            classes.append(ClassDef(name=f"Class_{p}_{c}", attributes=attrs))
        packages.append(Package(iri=f"http://x#{p}", name=f"Pkg_{p}", classes=classes))
    return OntologyIR(
        packages=packages,
        source=SourceInfo(
            document_path="test.md", document_sha256="x" * 64,
            parsed_at="2026-06-22T00:00:00Z", parser_version="0.1.0",
        ),
    )
