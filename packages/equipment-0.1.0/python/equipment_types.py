"""Python types for PSA package."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Transformer:
    """A static device that transfers electrical energy between circuits through electromagnetic induction."""
    id: str
    ratedCapacity: float = None
    primaryVoltage: float = None
    secondaryVoltage: float = None
    manufacturer: str = None
    windingType: str = None
    installedIn: Optional[str] = None
    operatedBy: Optional[str] = None

@dataclass(frozen=True)
class Breaker:
    """A switching device capable of making, carrying, and breaking currents under normal and fault conditions."""
    id: str
    ratedCurrent: float = None
    breakingCapacity: float = None
    mechanism: str = None
    isOpen: bool = None

@dataclass(frozen=True)
class Line:
    """A conductor or group of conductors used to transfer electrical energy between two points."""
    id: str
    length: float = None
    conductorType: str = None
    ratedCurrent: float = None

@dataclass(frozen=True)
class Cable:
    """An insulated conductor typically installed underground or underwater."""
    id: str
    length: float = None
    insulationType: str = None
    ratedVoltage: float = None

@dataclass(frozen=True)
class ProtectionDevice:
    """A device that detects abnormal conditions and initiates isolation of faulty equipment."""
    id: str
    protectionType: str = None
    settingGroup: str = None
    relayModel: str = None

@dataclass(frozen=True)
class Meter:
    """A device that measures and records electrical quantities."""
    id: str
    meterId: str
    meterType: str = None
    communicationProtocol: str = None
    measures: list[str] = None
