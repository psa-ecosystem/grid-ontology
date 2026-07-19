"""Equipment Ontology.

Specialized grid equipment classes built on top of the Core Domain Model.
"""
from __future__ import annotations

from cim_ontology.ir.models import ClassDef

from ._common import (
    NAMESPACE_EQUIPMENT,
    assoc,
    attr,
    cls,
    cref,
    make_package,
)

PACKAGE_NAME = "GridEquipment"
PACKAGE_ID = "power.equipment"
PACKAGE_VERSION = "0.1.0"


def build_equipment_model() -> list[ClassDef]:
    """Return the Equipment Ontology class definitions."""
    equipment_parent = cref("GridCore", "Equipment")

    transformer = cls(
        "Transformer",
        namespace=NAMESPACE_EQUIPMENT,
        description="A static device that transfers electrical energy between circuits through electromagnetic induction.",
        parents=[equipment_parent],
        attributes=[
            attr("ratedCapacity", "xsd:double", description="Rated apparent power in MVA."),
            attr("primaryVoltage", "xsd:double", description="Primary rated voltage in kV."),
            attr("secondaryVoltage", "xsd:double", description="Secondary rated voltage in kV."),
            attr("manufacturer", "xsd:string"),
            attr("windingType", "xsd:string", description="e.g., twoWinding, threeWinding, auto."),
        ],
        associations=[
            assoc(
                "installedIn",
                "GridCore",
                "Location",
                multiplicity="0..1",
                description="The location where the transformer is installed.",
            ),
            assoc(
                "operatedBy",
                "GridCore",
                "Organization",
                multiplicity="0..1",
                description="Organization responsible for operating the transformer.",
            ),
        ],
    )

    breaker = cls(
        "Breaker",
        namespace=NAMESPACE_EQUIPMENT,
        description="A switching device capable of making, carrying, and breaking currents under normal and fault conditions.",
        parents=[equipment_parent],
        attributes=[
            attr("ratedCurrent", "xsd:double", description="Rated continuous current in A."),
            attr("breakingCapacity", "xsd:double", description="Short-circuit breaking capacity in kA."),
            attr("mechanism", "xsd:string", description="e.g., spring, hydraulic, pneumatic."),
            attr("isOpen", "xsd:boolean", description="Current switch position."),
        ],
    )

    line = cls(
        "Line",
        namespace=NAMESPACE_EQUIPMENT,
        description="A conductor or group of conductors used to transfer electrical energy between two points.",
        parents=[equipment_parent],
        attributes=[
            attr("length", "xsd:double", description="Line length in km."),
            attr("conductorType", "xsd:string"),
            attr("ratedCurrent", "xsd:double"),
        ],
    )

    cable = cls(
        "Cable",
        namespace=NAMESPACE_EQUIPMENT,
        description="An insulated conductor typically installed underground or underwater.",
        parents=[equipment_parent],
        attributes=[
            attr("length", "xsd:double", description="Cable length in km."),
            attr("insulationType", "xsd:string"),
            attr("ratedVoltage", "xsd:double"),
        ],
    )

    protection_device = cls(
        "ProtectionDevice",
        namespace=NAMESPACE_EQUIPMENT,
        description="A device that detects abnormal conditions and initiates isolation of faulty equipment.",
        parents=[equipment_parent],
        attributes=[
            attr("protectionType", "xsd:string", description="e.g., overcurrent, differential, distance."),
            attr("settingGroup", "xsd:string"),
            attr("relayModel", "xsd:string"),
        ],
    )

    meter = cls(
        "Meter",
        namespace=NAMESPACE_EQUIPMENT,
        description="A device that measures and records electrical quantities.",
        parents=[equipment_parent],
        attributes=[
            attr("meterId", "xsd:string", required=True),
            attr("meterType", "xsd:string", description="e.g., energy, power quality, demand."),
            attr("communicationProtocol", "xsd:string"),
        ],
        associations=[
            assoc(
                "measures",
                "GridCore",
                "Measurement",
                multiplicity="0..*",
                description="Measurements collected by this meter.",
            ),
        ],
    )

    return [transformer, breaker, line, cable, protection_device, meter]


def build_equipment_package():
    """Build the Equipment Ontology package."""
    return make_package(
        PACKAGE_NAME,
        NAMESPACE_EQUIPMENT,
        build_equipment_model(),
        package_id=PACKAGE_ID,
        version=PACKAGE_VERSION,
    )
