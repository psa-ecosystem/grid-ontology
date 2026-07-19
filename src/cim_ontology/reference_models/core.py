"""Power Grid Core Domain Model.

These are PSA-aligned foundational concepts intended to serve as the
semantic backbone for more specialized domain ontologies (e.g., equipment,
topology, operation).
"""
from __future__ import annotations

from cim_ontology.ir.models import ClassDef

from ._common import NAMESPACE_CORE, attr, cls, make_package

PACKAGE_NAME = "GridCore"
PACKAGE_ID = "power.grid.core"
PACKAGE_VERSION = "0.1.0"


def build_core_model() -> list[ClassDef]:
    """Return the Core Domain Model class definitions."""
    asset = cls(
        "Asset",
        namespace=NAMESPACE_CORE,
        description="A physical or logical resource that is owned or managed by a grid operator.",
        attributes=[
            attr("assetId", "xsd:string", required=True, description="Unique asset identifier."),
            attr("name", "xsd:string", description="Human-readable name."),
            attr("status", "xsd:string", description="Lifecycle status, e.g., inService, retired."),
        ],
    )

    location = cls(
        "Location",
        namespace=NAMESPACE_CORE,
        description="A geographical or topological place where assets are installed.",
        attributes=[
            attr("locationId", "xsd:string", required=True),
            attr("name", "xsd:string"),
            attr("geoCoordinates", "xsd:string", description="Latitude/longitude or coordinate reference."),
        ],
    )

    organization = cls(
        "Organization",
        namespace=NAMESPACE_CORE,
        description="A company, department, or organizational unit involved in grid operations.",
        attributes=[
            attr("organizationId", "xsd:string", required=True),
            attr("name", "xsd:string", required=True),
            attr("role", "xsd:string", description="Role in the grid ecosystem, e.g., operator, maintainer."),
        ],
    )

    equipment = cls(
        "Equipment",
        namespace=NAMESPACE_CORE,
        parents=[],
        description="A grid asset that performs an electrical or support function.",
        attributes=[
            attr("equipmentId", "xsd:string", required=True),
            attr("name", "xsd:string"),
            attr("operatingStatus", "xsd:string", description="Operational state, e.g., inService, outOfService."),
            attr("commissioningDate", "xsd:date", multiplicity="0..1"),
        ],
    )

    measurement = cls(
        "Measurement",
        namespace=NAMESPACE_CORE,
        description="A quantified observation of a physical or logical quantity.",
        attributes=[
            attr("measurementId", "xsd:string", required=True),
            attr("measurementType", "xsd:string", description="e.g., voltage, current, temperature."),
            attr("unit", "xsd:string"),
            attr("value", "xsd:double", multiplicity="0..1"),
            attr("timestamp", "xsd:dateTime", multiplicity="0..1"),
        ],
    )

    work = cls(
        "Work",
        namespace=NAMESPACE_CORE,
        description="A task, activity, or work order performed on grid assets.",
        attributes=[
            attr("workId", "xsd:string", required=True),
            attr("workType", "xsd:string", description="e.g., inspection, maintenance, repair."),
            attr("plannedStart", "xsd:dateTime", multiplicity="0..1"),
            attr("plannedEnd", "xsd:dateTime", multiplicity="0..1"),
            attr("status", "xsd:string"),
        ],
    )

    event = cls(
        "Event",
        namespace=NAMESPACE_CORE,
        description="An occurrence of significance to grid operations.",
        attributes=[
            attr("eventId", "xsd:string", required=True),
            attr("eventType", "xsd:string", description="e.g., fault, alarm, switching."),
            attr("occurredAt", "xsd:dateTime", multiplicity="0..1"),
            attr("severity", "xsd:string", multiplicity="0..1"),
        ],
    )

    return [asset, location, organization, equipment, measurement, work, event]


def build_core_package():
    """Build the Core Domain Model package."""
    return make_package(
        PACKAGE_NAME,
        NAMESPACE_CORE,
        build_core_model(),
        package_id=PACKAGE_ID,
        version=PACKAGE_VERSION,
    )
