"""JSON-LD Context 适配器测试。"""
import json

import pytest

from cim_ontology.adapters.jsonld_context import JsonLdContextAdapter
from cim_ontology.ir.models import ClassDef, DataProperty, Multiplicity, OntologyIR, Package


@pytest.fixture
def ir_simple():
    return OntologyIR(packages=[Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject", attributes=[
            DataProperty(name="mRID", data_type="xsd:string",
                         multiplicity=Multiplicity(min=1, max=1, raw="1..1")),
        ])],
    )])


class TestJsonLdContextAdapter:
    def test_emits_context_per_package(self, ir_simple, tmp_path):
        adapter = JsonLdContextAdapter()
        adapter.emit(ir_simple, tmp_path)
        assert (tmp_path / "A_context.jsonld").exists()

    def test_context_has_vocab_and_cim(self, ir_simple, tmp_path):
        adapter = JsonLdContextAdapter()
        adapter.emit(ir_simple, tmp_path)
        ctx = json.loads((tmp_path / "A_context.jsonld").read_text())
        assert "@context" in ctx
        assert ctx["@context"]["@vocab"] == "http://iec.ch/TC57/2024/CIM-schema-cim17#"
