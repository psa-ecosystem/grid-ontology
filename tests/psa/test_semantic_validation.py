"""Deep semantic validation for PSA Semantic Packages (CTS-TP-004).

These tests go beyond "artifact exists and parses": they prove the
generated SHACL shapes and JSON Schema actually accept the package's own
example instance, and reject violating instances.

Covers CTS gaps GAP-001 (SHACL validation) and GAP-002 (JSON Schema
validation) from docs/governance/cts-gap-register.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pyshacl import validate as shacl_validate
from rdflib import RDF, Graph, Literal, URIRef

from cim_ontology.psa import build_psa_package
from cim_ontology.reference_models.builder import build_reference_ontology

NS = "https://grid-ontology.org/psa/v0.2/transformer/"


@pytest.fixture(scope="module")
def transformer_pkg(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ir = build_reference_ontology()
    out = tmp_path_factory.mktemp("psa")
    return build_psa_package(ir, "power.equipment.transformer", out)


def _load_example_as_rdf(pkg_dir: Path) -> Graph:
    """Parse the example JSON-LD offline by injecting the package's local context."""
    example = json.loads((pkg_dir / "examples" / "transformer-instance.jsonld").read_text())
    context = json.loads((pkg_dir / "jsonld" / "transformer-context.jsonld").read_text())
    example["@context"] = context["@context"]
    return Graph().parse(data=json.dumps(example), format="json-ld")


def _load_shapes(pkg_dir: Path) -> Graph:
    return Graph().parse(pkg_dir / "constraints" / "transformer.shacl", format="turtle")


class TestSHACLValidation:
    """GAP-001: SHACL shapes are executed, not just parsed."""

    def test_example_conforms_to_shapes(self, transformer_pkg: Path) -> None:
        data = _load_example_as_rdf(transformer_pkg)
        shapes = _load_shapes(transformer_pkg)
        conforms, _, report = shacl_validate(data, shacl_graph=shapes)
        assert conforms, report

    def test_missing_required_relation_violates(self, transformer_pkg: Path) -> None:
        """PowerTransformer without hasTransformerEnd must fail sh:minCount 1."""
        shapes = _load_shapes(transformer_pkg)
        inst = URIRef("https://example.org/instance/BadPT")
        data = Graph()
        data.add((inst, RDF.type, URIRef(f"{NS}PowerTransformer")))
        data.add((inst, URIRef(f"{NS}PowerTransformer.ratedCapacity"), Literal(100.0)))
        conforms, _, report = shacl_validate(data, shacl_graph=shapes)
        assert not conforms
        assert "hasTransformerEnd" in report

    def test_wrong_datatype_violates(self, transformer_pkg: Path) -> None:
        """phaseCount as a string must fail sh:datatype xsd:integer."""
        shapes = _load_shapes(transformer_pkg)
        inst = URIRef("https://example.org/instance/BadPT2")
        data = Graph()
        data.add((inst, RDF.type, URIRef(f"{NS}PowerTransformer")))
        data.add((inst, URIRef(f"{NS}PowerTransformer.phaseCount"), Literal("three")))
        data.add((inst, URIRef(f"{NS}PowerTransformer.hasTransformerEnd"), URIRef("https://example.org/instance/TE1")))
        conforms, _, report = shacl_validate(data, shacl_graph=shapes)
        assert not conforms
        assert "phaseCount" in report

    def test_missing_required_attribute_violates(self, transformer_pkg: Path) -> None:
        """TransformerEnd without endNumber must fail sh:minCount 1."""
        shapes = _load_shapes(transformer_pkg)
        inst = URIRef("https://example.org/instance/BadTE")
        data = Graph()
        data.add((inst, RDF.type, URIRef(f"{NS}TransformerEnd")))
        conforms, _, report = shacl_validate(data, shacl_graph=shapes)
        assert not conforms
        assert "endNumber" in report


class TestJSONSchemaValidation:
    """GAP-002: JSON Schema is executed against the example, not just parsed."""

    def _load_schema(self, pkg_dir: Path) -> dict:
        return json.loads((pkg_dir / "jsonschema" / "transformer.schema.json").read_text())

    def _load_example(self, pkg_dir: Path) -> dict:
        return json.loads((pkg_dir / "examples" / "transformer-instance.jsonld").read_text())

    def test_example_validates_against_schema(self, transformer_pkg: Path) -> None:
        import jsonschema

        schema = self._load_schema(transformer_pkg)
        example = self._load_example(transformer_pkg)
        jsonschema.validate(example, schema)  # raises on failure

    def test_node_missing_required_attribute_fails(self, transformer_pkg: Path) -> None:
        import jsonschema

        schema = self._load_schema(transformer_pkg)
        example = self._load_example(transformer_pkg)
        end = next(n for n in example["@graph"] if n["@type"] == "TransformerEnd")
        del end["endNumber"]  # required on TransformerEnd
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(example, schema)

    def test_node_with_wrong_type_fails(self, transformer_pkg: Path) -> None:
        import jsonschema

        schema = self._load_schema(transformer_pkg)
        example = self._load_example(transformer_pkg)
        pt = next(n for n in example["@graph"] if n["@type"] == "PowerTransformer")
        pt["phaseCount"] = "three"  # schema expects integer
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(example, schema)

    def test_node_with_unknown_property_fails(self, transformer_pkg: Path) -> None:
        import jsonschema

        schema = self._load_schema(transformer_pkg)
        example = self._load_example(transformer_pkg)
        pt = next(n for n in example["@graph"] if n["@type"] == "PowerTransformer")
        pt["unknownField"] = 1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(example, schema)


class TestCTSDeclarationCoverage:
    """Every check string in package-cts.yaml maps to an executable test class here."""

    def test_cts_cases_documented(self, transformer_pkg: Path) -> None:
        cts = yaml.safe_load((transformer_pkg / "tests" / "package-cts.yaml").read_text())
        cases = {c["id"] for c in cts["cts"]["cases"]}
        assert cases == {"CTS-TP-001", "CTS-TP-002", "CTS-TP-003", "CTS-TP-004", "CTS-TP-005"}
