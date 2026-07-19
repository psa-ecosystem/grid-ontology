"""PSA-aligned grid ontology reference models (code-first).

This module provides code-first ontology definitions that complement the
CIM Markdown extraction pipeline. Models are expressed directly as
`OntologyIR` instances and can be emitted through the existing adapters.

v0.2 scope:
- Core Domain Model (Asset, Equipment, Location, Organization, Work, Event, Measurement)
- Equipment Ontology (Transformer, Breaker, Line, Cable, ProtectionDevice, Meter)
- Transformer Semantic Package
"""

from .core import build_core_model
from .equipment import build_equipment_model
from .transformer_package import build_transformer_package

__all__ = [
    "build_core_model",
    "build_equipment_model",
    "build_transformer_package",
]
