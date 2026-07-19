"""Common helpers for code-first reference models."""
from __future__ import annotations

from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    DataProperty,
    Multiplicity,
    ObjectProperty,
    Package,
)

# Namespace for PSA-aligned grid ontology reference models.
# This is a placeholder URI; it should be replaced by an official PSA URI
# once the governance process assigns one.
NAMESPACE_CORE = "https://grid-ontology.org/psa/v0.2/core"
NAMESPACE_EQUIPMENT = "https://grid-ontology.org/psa/v0.2/equipment"


def cls(
    name: str,
    *,
    namespace: str = NAMESPACE_CORE,
    description: str | None = None,
    parents: list[ClassRef] | None = None,
    attributes: list[DataProperty] | None = None,
    associations: list[ObjectProperty] | None = None,
) -> ClassDef:
    """Build a ClassDef with a stable IRI."""
    return ClassDef(
        iri=f"{namespace}#{name}",
        name=name,
        description=description,
        parents=parents or [],
        attributes=attributes or [],
        associations=associations or [],
    )


def attr(
    name: str,
    data_type: str = "xsd:string",
    *,
    multiplicity: str = "0..1",
    description: str | None = None,
    required: bool = False,
) -> DataProperty:
    """Build a DataProperty."""
    min_count, max_count = _parse_multiplicity(multiplicity)
    return DataProperty(
        name=name,
        data_type=data_type,
        multiplicity=Multiplicity(min=min_count, max=max_count, raw=multiplicity),
        description=description,
        required=required,
    )


def assoc(
    name: str,
    target_package: str,
    target_class: str,
    *,
    multiplicity: str = "0..*",
    description: str | None = None,
    is_aggregation: bool = False,
    inverse_name: str | None = None,
) -> ObjectProperty:
    """Build an ObjectProperty (association end)."""
    min_count, max_count = _parse_multiplicity(multiplicity)
    return ObjectProperty(
        name=name,
        target=ClassRef(package=target_package, class_name=target_class),
        multiplicity=Multiplicity(min=min_count, max=max_count, raw=multiplicity),
        description=description,
        is_aggregation=is_aggregation,
        inverse_name=inverse_name,
    )


def cref(package: str, class_name: str) -> ClassRef:
    """Build a ClassRef."""
    return ClassRef(package=package, class_name=class_name)


def _parse_multiplicity(raw: str) -> tuple[int, int | None]:
    """Parse '0..1', '1..*', '0..*' into (min, max)."""
    parts = raw.split("..")
    if len(parts) != 2:
        raise ValueError(f"Unsupported multiplicity: {raw}")
    min_count = int(parts[0])
    max_count: int | None = None if parts[1] == "*" else int(parts[1])
    return min_count, max_count


def make_package(
    name: str,
    namespace: str,
    classes: list[ClassDef],
    *,
    package_id: str | None = None,
    version: str = "0.1.0",
) -> Package:
    """Build a Package with stable IRI and optional PSA metadata."""
    return Package(
        iri=f"{namespace}",
        name=name,
        classes=classes,
        package_id=package_id,
        version=version,
    )
