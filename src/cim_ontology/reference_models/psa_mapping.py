"""PSA primitive mapping registry for reference models.

This module explicitly records how grid-ontology concepts map to
PSA Core Semantic Model primitives. It is used for validation and
documentation, not for runtime behavior.
"""
from __future__ import annotations

from enum import Enum


class PSAPrimitive(str, Enum):
    """The six PSA primitives."""

    ENTITY = "Entity"
    ATTRIBUTE = "Attribute"
    RELATION = "Relation"
    ACTION = "Action"
    RULE = "Rule"
    EVIDENCE = "Evidence"


PSA_PRIMITIVE_MAP: dict[str, PSAPrimitive] = {}


def map_concept(fully_qualified_name: str, primitive: PSAPrimitive) -> None:
    """Register a grid-ontology concept's PSA primitive mapping."""
    PSA_PRIMITIVE_MAP[fully_qualified_name] = primitive


def get_primitive(fully_qualified_name: str) -> PSAPrimitive | None:
    """Return the PSA primitive for a given concept, or None."""
    return PSA_PRIMITIVE_MAP.get(fully_qualified_name)


def register_core_mappings() -> None:
    """Register default mappings for the Core Domain Model."""
    core_entities = [
        "Asset",
        "Location",
        "Organization",
        "Equipment",
        "Measurement",
        "Work",
        "Event",
    ]
    for name in core_entities:
        map_concept(f"GridCore::{name}", PSAPrimitive.ENTITY)


def register_equipment_mappings() -> None:
    """Register default mappings for the Equipment Ontology."""
    equipment_entities = [
        "Transformer",
        "Breaker",
        "Line",
        "Cable",
        "ProtectionDevice",
        "Meter",
    ]
    for name in equipment_entities:
        map_concept(f"GridEquipment::{name}", PSAPrimitive.ENTITY)


def register_transformer_package_mappings() -> None:
    """Register default mappings for the Transformer Semantic Package."""
    for name in ["PowerTransformer", "TransformerEnd", "Terminal"]:
        map_concept(f"TransformerPackage::{name}", PSAPrimitive.ENTITY)


# Auto-register defaults on import.
register_core_mappings()
register_equipment_mappings()
register_transformer_package_mappings()
