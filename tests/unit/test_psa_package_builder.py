"""Tests for PSA Semantic Package builder."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cim_ontology.psa import PackageNotFoundError, PSAPackageBuilder, build_psa_package
from cim_ontology.reference_models.builder import build_reference_ontology


@pytest.fixture
def reference_ir():
    return build_reference_ontology()


class TestPSAPackageBuilder:
    """PSA package builder tests."""

    def test_build_returns_package_directory(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        assert pkg_dir.exists()
        assert pkg_dir.name == "transformer-0.1.0"

    def test_required_files_exist(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        required = [
            "manifest.yaml",
            "README.md",
            "semantic-model/entities.yaml",
            "semantic-model/attributes.yaml",
            "semantic-model/relations.yaml",
            "semantic-model/enumerations.yaml",
            "ontology/transformer.owl",
            "constraints/transformer.shacl",
            "jsonld/transformer-context.jsonld",
            "jsonschema/transformer.schema.json",
            "python/transformer_types.py",
            "examples/transformer-instance.jsonld",
            "mappings/mapping-template.yaml",
            "tests/package-cts.yaml",
        ]
        for rel in required:
            assert (pkg_dir / rel).exists(), f"missing {rel}"

    def test_manifest_content(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        manifest = yaml.safe_load((pkg_dir / "manifest.yaml").read_text())
        assert manifest["package"]["id"] == "power.equipment.transformer"
        assert manifest["package"]["version"] == "0.1.0"
        assert manifest["package"]["producer"] == "grid-ontology"
        assert set(manifest["package"]["dependencies"]) == {"power.equipment", "power.grid.core"}

    def test_entities_yaml(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = yaml.safe_load((pkg_dir / "semantic-model" / "entities.yaml").read_text())
        names = {e["name"] for e in data["entities"]}
        assert names == {"PowerTransformer", "TransformerEnd", "Terminal"}
        pt = next(e for e in data["entities"] if e["name"] == "PowerTransformer")
        assert pt["iri"] == "https://grid-ontology.org/psa/v0.2/transformer/PowerTransformer"
        assert pt["parents"][0]["iri"] == "https://grid-ontology.org/psa/v0.2/equipment/Transformer"

    def test_attributes_yaml(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = yaml.safe_load((pkg_dir / "semantic-model" / "attributes.yaml").read_text())
        pt_attrs = [
            a
            for a in data["attributes"]
            if a["domain"]["entity_id"] == "power.equipment.transformer.PowerTransformer"
        ]
        names = {a["name"] for a in pt_attrs}
        assert names == {
            "ratedCapacity", "voltageLevel", "phaseCount", "manufacturer", "operationStatus",
        }

    def test_relations_yaml_cross_package_target(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = yaml.safe_load((pkg_dir / "semantic-model" / "relations.yaml").read_text())
        rel = next(r for r in data["relations"] if r["name"] == "installedIn")
        assert rel["target"]["entity_id"] == "power.grid.core.Location"
        assert rel["target"]["iri"] == "https://grid-ontology.org/psa/v0.2/core/Location"

    def test_enumerations_yaml(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = yaml.safe_load((pkg_dir / "semantic-model" / "enumerations.yaml").read_text())
        assert len(data["enumerations"]) == 1
        assert data["enumerations"][0]["name"] == "OperationStatus"
        values = {v["value"] for v in data["enumerations"][0]["values"]}
        assert values == {"Running", "OutOfService", "Maintenance", "Retired"}

    def test_owl_parses(self, reference_ir, tmp_path: Path) -> None:
        from rdflib import Graph

        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        g = Graph()
        g.parse(pkg_dir / "ontology" / "transformer.owl", format="turtle")
        assert len(g) > 0

    def test_shacl_parses(self, reference_ir, tmp_path: Path) -> None:
        from rdflib import Graph

        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        g = Graph()
        g.parse(pkg_dir / "constraints" / "transformer.shacl", format="turtle")
        assert len(g) > 0

    def test_jsonld_context_valid(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = json.loads((pkg_dir / "jsonld" / "transformer-context.jsonld").read_text())
        assert "@context" in data
        assert "PowerTransformer" in data["@context"]

    def test_jsonschema_valid(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        schema = json.loads((pkg_dir / "jsonschema" / "transformer.schema.json").read_text())
        assert "PowerTransformer" in schema["$defs"]

    def test_example_valid_json(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        example = json.loads((pkg_dir / "examples" / "transformer-instance.jsonld").read_text())
        assert "@graph" in example
        types = {node["@type"] for node in example["@graph"]}
        assert types == {"PowerTransformer", "TransformerEnd", "Terminal"}
        pt = next(n for n in example["@graph"] if n["@type"] == "PowerTransformer")
        assert pt["hasTransformerEnd"] == ["TransformerEnd001"]
        end = next(n for n in example["@graph"] if n["@type"] == "TransformerEnd")
        assert end["terminal"] == "Terminal001"

    def test_build_rejects_dangling_cross_ref(self, reference_ir, tmp_path: Path) -> None:
        from cim_ontology.ir.models import ClassRef, ObjectProperty

        pkg = reference_ir.get_package("TransformerPackage")
        assert pkg is not None
        pt = next(c for c in pkg.classes if c.name == "PowerTransformer")
        broken = pt.model_copy(update={
            "associations": pt.associations + [
                ObjectProperty(
                    name="feeds",
                    target=ClassRef(package="Ghost", class_name="Substation"),
                ),
            ],
        })
        broken_pkg = pkg.model_copy(update={
            "classes": [broken if c.name == "PowerTransformer" else c for c in pkg.classes],
        })
        broken_ir = reference_ir.model_copy(update={
            "packages": [
                broken_pkg if p.name == "TransformerPackage" else p
                for p in reference_ir.packages
            ],
        })
        with pytest.raises(ValueError, match="Ghost::Substation"):
            build_psa_package(broken_ir, "power.equipment.transformer", tmp_path)

    def test_cts_yaml(self, reference_ir, tmp_path: Path) -> None:
        pkg_dir = build_psa_package(reference_ir, "power.equipment.transformer", tmp_path)
        data = yaml.safe_load((pkg_dir / "tests" / "package-cts.yaml").read_text())
        assert data["cts"]["package_id"] == "power.equipment.transformer"
        case_ids = {c["id"] for c in data["cts"]["cases"]}
        assert case_ids == {"CTS-TP-001", "CTS-TP-002", "CTS-TP-003", "CTS-TP-004", "CTS-TP-005"}

    def test_build_all_packages(self, reference_ir, tmp_path: Path) -> None:
        for pkg in reference_ir.packages:
            if pkg.package_id:
                pkg_dir = build_psa_package(reference_ir, pkg.package_id, tmp_path)
                assert (pkg_dir / "manifest.yaml").exists()

    def test_package_not_found(self, reference_ir, tmp_path: Path) -> None:
        with pytest.raises(PackageNotFoundError):
            build_psa_package(reference_ir, "power.does.not.exist", tmp_path)

    def test_builder_class_api(self, reference_ir, tmp_path: Path) -> None:
        builder = PSAPackageBuilder(reference_ir, "power.equipment.transformer")
        pkg_dir = builder.build(tmp_path)
        assert pkg_dir.name == "transformer-0.1.0"
