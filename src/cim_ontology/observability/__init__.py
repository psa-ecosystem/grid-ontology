"""Observability 模块（P3 observability 强化）。

提供:
  - metrics: 轻量级 in-memory Counter/Histogram/Gauge + labels
"""
from cim_ontology.observability.metrics import Metrics

__all__ = ["Metrics"]