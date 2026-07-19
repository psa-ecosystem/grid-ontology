"""Builder for combining reference models into a single OntologyIR."""
from __future__ import annotations

from datetime import datetime, timezone

from cim_ontology.ir.models import IRStats, OntologyIR, SourceInfo

from .core import build_core_package
from .equipment import build_equipment_package
from .transformer_package import build_transformer_package_bundle


def build_reference_ontology() -> OntologyIR:
    """Build a complete PSA-aligned grid ontology reference model.

    Combines Core Domain Model, Equipment Ontology, and Transformer
    Semantic Package into a single OntologyIR instance that can be
    consumed by the existing adapters.
    """
    packages = [
        build_core_package(),
        build_equipment_package(),
        build_transformer_package_bundle(),
    ]

    all_classes = [c for pkg in packages for c in pkg.classes]
    all_attrs = [a for c in all_classes for a in c.attributes]
    all_assocs = [a for c in all_classes for a in c.associations]

    return OntologyIR(
        schema_version="1.0",
        source=SourceInfo(
            document_path="reference-models://code-first",
            document_sha256="0" * 64,
            parsed_at=datetime.now(timezone.utc),
            parser_version="reference_models.v0.2",
        ),
        packages=packages,
        stats=IRStats(
            package_count=len(packages),
            class_count=len(all_classes),
            attribute_count=len(all_attrs),
            association_count=len(all_assocs),
            enumeration_count=0,
            uncertain_count=0,
        ),
    )
