"""Python types for PSA package."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PowerTransformer:
    """A transformer in the power grid, specialized from Equipment."""
    id: str
    ratedCapacity: float = None
    voltageLevel: float = None
    phaseCount: int = None
    manufacturer: str = None
    operationStatus: str = None
    installedIn: Optional[str] = None
    hasTransformerEnd: list[str] = None

@dataclass(frozen=True)
class TransformerEnd:
    """A terminal point of a power transformer winding."""
    id: str
    endNumber: int
    ratedVoltage: float = None
    grounded: bool = None
    terminal: Optional[str] = None

@dataclass(frozen=True)
class Terminal:
    """A connection point for equipment in the grid."""
    id: str
    terminalId: str
    sequenceNumber: int = None
    connectedTo: list[str] = None

from enum import Enum

class OperationStatus(Enum):
    """Lifecycle operational state of a power transformer."""
    Running = "Running"
    OutOfService = "OutOfService"
    Maintenance = "Maintenance"
    Retired = "Retired"
