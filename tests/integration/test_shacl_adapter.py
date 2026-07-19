"""SHACL 适配器测试。"""
import pytest
from rdflib import Graph, Namespace, URIRef

from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.ir.models import (
    ClassDef, DataProperty, Multiplicity, OntologyIR, Package,
)


@pytest.fixture
def ir_with_required_attr():
    return OntologyIR(
        packages=[Package(
            iri="http://x#A", name="A",
            classes=[ClassDef(
                name="IdentifiedObject",
                attributes=[DataProperty(
                    name="mRID", data_type="xsd:string",
                    multiplicity=Multiplicity(min=1, max=1, raw="1..1"),
                    required=True,
                )],
            )],
        )],
    )


class TestShaclAdapter:
    def test_emits_shape(self, ir_with_required_attr, tmp_path):
        adapter = ShaclAdapter()
        result = adapter.emit(ir_with_required_attr, tmp_path)
        assert (tmp_path / "cim17_shapes.ttl").exists()

    def test_shape_has_min_count_for_required(self, ir_with_required_attr, tmp_path):
        adapter = ShaclAdapter()
        adapter.emit(ir_with_required_attr, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_shapes.ttl", format="turtle")
        SH = Namespace("http://www.w3.org/ns/shacl#")
        # 至少一个 minCount=1 约束
        triples_with_min = list(g.triples((None, SH.minCount, None)))
        assert len(triples_with_min) >= 1