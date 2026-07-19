"""Transformer Semantic Package.

A focused PSA-facing package centered on power transformer semantics.
"""
from __future__ import annotations

from cim_ontology.ir.models import ClassDef, Enumeration

from ._common import assoc, attr, cls, cref, make_package

PACKAGE_NAME = "TransformerPackage"
PACKAGE_ID = "power.equipment.transformer"
PACKAGE_VERSION = "0.1.0"
NAMESPACE_TRANSFORMER = "https://grid-ontology.org/psa/v0.2/transformer"


def _build_operation_status_enum() -> Enumeration:
    """Operational status enumeration for power transformers."""
    return Enumeration(
        name="OperationStatus",
        values=["Running", "OutOfService", "Maintenance", "Retired"],
        description="Lifecycle operational state of a power transformer.",
    )


def build_transformer_package() -> list[ClassDef]:
    """Return the Transformer Semantic Package class definitions."""
    transformer = cls(
        "PowerTransformer",
        namespace=NAMESPACE_TRANSFORMER,
        description="A transformer in the power grid, specialized from Equipment.",
        parents=[cref("GridEquipment", "Transformer")],
        attributes=[
            attr("ratedCapacity", "xsd:double", description="Rated apparent power in MVA."),
            attr("voltageLevel", "xsd:double", description="Nominal voltage level in kV."),
            attr("phaseCount", "xsd:integer", description="Number of phases (e.g., 1 or 3)."),
            attr("manufacturer", "xsd:string"),
            attr(
                "operationStatus",
                "xsd:string",
                description="Operational state: Running, OutOfService, Maintenance, Retired.",
            ),
        ],
        associations=[
            assoc(
                "installedIn",
                "GridCore",
                "Location",
                multiplicity="0..1",
            ),
            assoc(
                "hasTransformerEnd",
                PACKAGE_NAME,
                "TransformerEnd",
                multiplicity="1..*",
            ),
        ],
    )

    transformer_end = cls(
        "TransformerEnd",
        namespace=NAMESPACE_TRANSFORMER,
        description="A terminal point of a power transformer winding.",
        attributes=[
            attr("endNumber", "xsd:integer", required=True),
            attr("ratedVoltage", "xsd:double"),
            attr("grounded", "xsd:boolean"),
        ],
        associations=[
            assoc(
                "terminal",
                PACKAGE_NAME,
                "Terminal",
                multiplicity="0..1",
            ),
        ],
    )

    terminal = cls(
        "Terminal",
        namespace=NAMESPACE_TRANSFORMER,
        description="A connection point for equipment in the grid.",
        attributes=[
            attr("terminalId", "xsd:string", required=True),
            attr("sequenceNumber", "xsd:integer"),
        ],
        associations=[
            assoc(
                "connectedTo",
                PACKAGE_NAME,
                "Terminal",
                multiplicity="0..*",
                description="Electrical connectivity to another terminal.",
            ),
        ],
    )

    return [transformer, transformer_end, terminal]


def build_transformer_package_bundle():
    """Build the Transformer Semantic Package as a Package object."""
    package = make_package(
        PACKAGE_NAME,
        NAMESPACE_TRANSFORMER,
        build_transformer_package(),
        package_id=PACKAGE_ID,
        version=PACKAGE_VERSION,
    )
    package.enumerations.append(_build_operation_status_enum())
    return package
