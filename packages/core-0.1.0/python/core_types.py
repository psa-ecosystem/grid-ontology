"""Python types for PSA package."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Asset:
    """A physical or logical resource that is owned or managed by a grid operator."""
    id: str
    assetId: str
    name: str = None
    status: str = None

@dataclass(frozen=True)
class Location:
    """A geographical or topological place where assets are installed."""
    id: str
    locationId: str
    name: str = None
    geoCoordinates: str = None

@dataclass(frozen=True)
class Organization:
    """A company, department, or organizational unit involved in grid operations."""
    id: str
    organizationId: str
    name: str
    role: str = None

@dataclass(frozen=True)
class Equipment:
    """A grid asset that performs an electrical or support function."""
    id: str
    equipmentId: str
    name: str = None
    operatingStatus: str = None
    commissioningDate: str = None

@dataclass(frozen=True)
class Measurement:
    """A quantified observation of a physical or logical quantity."""
    id: str
    measurementId: str
    measurementType: str = None
    unit: str = None
    value: float = None
    timestamp: str = None

@dataclass(frozen=True)
class Work:
    """A task, activity, or work order performed on grid assets."""
    id: str
    workId: str
    workType: str = None
    plannedStart: str = None
    plannedEnd: str = None
    status: str = None

@dataclass(frozen=True)
class Event:
    """An occurrence of significance to grid operations."""
    id: str
    eventId: str
    eventType: str = None
    occurredAt: str = None
    severity: str = None
