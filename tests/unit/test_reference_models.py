"""Tests for PSA-aligned reference models."""
from __future__ import annotations

import pytest

from cim_ontology.reference_models import (
    build_core_model,
    build_equipment_model,
    build_transformer_package,
)
from cim_ontology.reference_models.builder import build_reference_ontology
from cim_ontology.reference_models.psa_mapping import (
    PSAPrimitive,
    get_primitive,
)


class TestCoreDomainModel:
    """Core Domain Model tests."""

    def test_core_classes_count(self) -> None:
        classes = build_core_model()
        names = {c.name for c in classes}
        assert names == {"Asset", "Location", "Organization", "Equipment", "Measurement", "Work", "Event"}

    def test_equipment_inherits_from_core(self) -> None:
        equipment = next(c for c in build_core_model() if c.name == "Equipment")
        assert equipment.iri is not None
        assert "core" in equipment.iri

    def test_asset_has_required_identifier(self) -> None:
        asset = next(c for c in build_core_model() if c.name == "Asset")
        asset_id = next(a for a in asset.attributes if a.name == "assetId")
        assert asset_id.required is True


class TestEquipmentOntology:
    """Equipment Ontology tests."""

    def test_equipment_classes_count(self) -> None:
        classes = build_equipment_model()
        names = {c.name for c in classes}
        assert names == {"Transformer", "Breaker", "Line", "Cable", "ProtectionDevice", "Meter"}

    def test_transformer_attributes(self) -> None:
        transformer = next(c for c in build_equipment_model() if c.name == "Transformer")
        attr_names = {a.name for a in transformer.attributes}
        assert "ratedCapacity" in attr_names
        assert "primaryVoltage" in attr_names
        assert "manufacturer" in attr_names

    def test_transformer_has_installed_in_relation(self) -> None:
        transformer = next(c for c in build_equipment_model() if c.name == "Transformer")
        assoc_names = {a.name for a in transformer.associations}
        assert "installedIn" in assoc_names


class TestTransformerPackage:
    """Transformer Semantic Package tests."""

    def test_transformer_package_classes_count(self) -> None:
        classes = build_transformer_package()
        names = {c.name for c in classes}
        assert names == {"PowerTransformer", "TransformerEnd", "Terminal"}

    def test_power_transformer_parent(self) -> None:
        pt = next(c for c in build_transformer_package() if c.name == "PowerTransformer")
        assert len(pt.parents) == 1
        assert pt.parents[0].class_name == "Transformer"
        assert pt.parents[0].package == "GridEquipment"

    def test_power_transformer_attributes(self) -> None:
        pt = next(c for c in build_transformer_package() if c.name == "PowerTransformer")
        attr_names = {a.name for a in pt.attributes}
        assert "ratedCapacity" in attr_names
        assert "voltageLevel" in attr_names
        assert "phaseCount" in attr_names
        assert "manufacturer" in attr_names
        assert "operationStatus" in attr_names

    def test_power_transformer_has_transformer_end_relation(self) -> None:
        pt = next(c for c in build_transformer_package() if c.name == "PowerTransformer")
        assoc_names = {a.name for a in pt.associations}
        assert "hasTransformerEnd" in assoc_names
        assert "connectedTo" not in assoc_names  # moved to Terminal

    def test_transformer_end_links_to_terminal(self) -> None:
        end = next(c for c in build_transformer_package() if c.name == "TransformerEnd")
        assoc_names = {a.name for a in end.associations}
        assert "terminal" in assoc_names

    def test_terminal_has_connected_to_relation(self) -> None:
        terminal = next(c for c in build_transformer_package() if c.name == "Terminal")
        assoc_names = {a.name for a in terminal.associations}
        assert "connectedTo" in assoc_names

    def test_operation_status_enum(self) -> None:
        from cim_ontology.reference_models.transformer_package import build_transformer_package_bundle

        package = build_transformer_package_bundle()
        assert len(package.enumerations) == 1
        enum = package.enumerations[0]
        assert enum.name == "OperationStatus"
        assert set(enum.values) == {"Running", "OutOfService", "Maintenance", "Retired"}


class TestReferenceOntologyBuilder:
    """Builder integration tests."""

    def test_build_reference_ontology(self) -> None:
        ir = build_reference_ontology()
        assert ir.schema_version == "1.0"
        assert len(ir.packages) == 3
        assert ir.stats.class_count == 16
        assert ir.stats.package_count == 3

    def test_all_packages_have_psa_metadata(self) -> None:
        ir = build_reference_ontology()
        expected = {
            "GridCore": ("power.grid.core", "0.1.0"),
            "GridEquipment": ("power.equipment", "0.1.0"),
            "TransformerPackage": ("power.equipment.transformer", "0.1.0"),
        }
        for pkg in ir.packages:
            pkg_id, version = expected[pkg.name]
            assert pkg.package_id == pkg_id
            assert pkg.version == version

    def test_all_classes_have_iri(self) -> None:
        ir = build_reference_ontology()
        for cls in ir.all_classes():
            assert cls.iri is not None
            assert cls.iri.startswith("https://grid-ontology.org/psa/v0.2/")


class TestPSAPrimitiveMapping:
    """PSA primitive mapping tests."""

    @pytest.mark.parametrize(
        ("concept", "expected"),
        [
            ("GridCore::Asset", PSAPrimitive.ENTITY),
            ("GridCore::Equipment", PSAPrimitive.ENTITY),
            ("GridEquipment::Transformer", PSAPrimitive.ENTITY),
            ("GridEquipment::Breaker", PSAPrimitive.ENTITY),
            ("TransformerPackage::PowerTransformer", PSAPrimitive.ENTITY),
        ],
    )
    def test_entity_mappings(self, concept: str, expected: PSAPrimitive) -> None:
        assert get_primitive(concept) == expected

    def test_unknown_concept_returns_none(self) -> None:
        assert get_primitive("GridCore::Unknown") is None
