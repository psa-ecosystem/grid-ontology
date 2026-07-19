"""JSON Schema 适配器测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.ir.models import ClassDef, DataProperty, Multiplicity, OntologyIR, Package


@pytest.fixture
def ir_simple():
    return OntologyIR(packages=[Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject", attributes=[
            DataProperty(name="mRID", data_type="xsd:string",
                         multiplicity=Multiplicity(min=1, max=1, raw="1..1"), required=True),
            DataProperty(name="name", data_type="xsd:string",
                         multiplicity=Multiplicity(min=0, max=1, raw="0..1")),
        ])],
    )])


class TestJsonSchemaAdapter:
    def test_emits_schema(self, ir_simple, tmp_path):
        adapter = JsonSchemaAdapter()
        adapter.emit(ir_simple, tmp_path)
        assert (tmp_path / "A_schema.json").exists()

    def test_required_fields(self, ir_simple, tmp_path):
        adapter = JsonSchemaAdapter()
        adapter.emit(ir_simple, tmp_path)
        schema = json.loads((tmp_path / "A_schema.json").read_text())
        ident = schema["properties"]["IdentifiedObject"]
        assert "mRID" in ident["required"]
        assert "name" not in ident["required"]
