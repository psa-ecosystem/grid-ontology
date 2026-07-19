"""Lightweight in-memory metrics primitives（P3 observability）。

设计原则（KISS / YAGNI）：
  - 三种原始类型：Counter（单调递增）/ Histogram（值分布）/ Gauge（瞬时值）
  - 可选 labels（dict）支持维度切分（如 outcome=success / category=typo）
  - 线程安全（threading.Lock）
  - 无外部依赖（避免 Prometheus client 等重型库）
  - snapshot() 返回 JSON 友好 dict，便于嵌入审计报告

使用示例::

    metrics = Metrics()
    metrics.inc("reviewer.calls", labels={"outcome": "success"})
    metrics.observe("reviewer.latency", 1.23, labels={"path": "batch"})
    metrics.set_gauge("reviewer.batch.size", 8)
    snapshot = metrics.snapshot()
"""
from __future__ import annotations

from threading import Lock
from typing import Any


class Metrics:
    """In-memory 指标收集器（Counter / Histogram / Gauge + labels）。

    Attributes:
        counters: 计数器（单调递增），key = (name, frozenset(labels))
        histograms: 直方图（值列表），key 同上
        gauges: 仪表盘（最新值），key 同上
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, frozenset[tuple[str, str]]], int] = {}
        self._histograms: dict[tuple[str, frozenset[tuple[str, str]]], list[float]] = {}
        self._gauges: dict[tuple[str, frozenset[tuple[str, str]]], float] = {}

    @staticmethod
    def _make_key(name: str, labels: dict[str, Any] | None) -> tuple[str, frozenset[tuple[str, str]]]:
        """生成 (name, frozenset(labels)) 元组作为内部 key。

        frozenset 不可变，可哈希；空 labels 统一为 frozenset() 便于查找。
        """
        if not labels:
            return (name, frozenset())
        return (name, frozenset((str(k), str(v)) for k, v in labels.items()))

    def inc(self, name: str, labels: dict[str, Any] | None = None, value: int = 1) -> None:
        """Counter 单调递增。

        Args:
            name: 指标名（推荐 snake_case + 点分命名空间，如 `reviewer.calls`）
            labels: 可选标签字典（维度切分，如 {"outcome": "success"}）
            value: 增量（默认 1，必须 > 0；Counter 不允许负数）
        """
        if value <= 0:
            raise ValueError(f"Counter 必须为正整数, got {value}")
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

    def observe(self, name: str, value: float, labels: dict[str, Any] | None = None) -> None:
        """Histogram 记录一个观测值（如延迟、批量大小）。

        Args:
            name: 指标名
            value: 观测值
            labels: 可选标签字典
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms.setdefault(key, []).append(float(value))

    def set_gauge(self, name: str, value: float, labels: dict[str, Any] | None = None) -> None:
        """Gauge 设置瞬时值（如当前并发数、缓存大小）。

        Args:
            name: 指标名
            value: 当前值
            labels: 可选标签字典
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = float(value)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """导出当前所有指标的 JSON 友好快照。

        Returns:
            {
                "counters": [{"name", "labels", "value"}, ...],
                "histograms": [{"name", "labels", "count", "sum", "min", "max", "mean"}, ...],
                "gauges": [{"name", "labels", "value"}, ...]
            }
        """
        with self._lock:
            counters = [
                {"name": n, "labels": dict(labels), "value": v}
                for (n, labels), v in sorted(self._counters.items())
            ]
            histograms = []
            for (n, labels), values in sorted(self._histograms.items()):
                if values:
                    histograms.append({
                        "name": n,
                        "labels": dict(labels),
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / len(values),
                    })
                else:
                    histograms.append({
                        "name": n,
                        "labels": dict(labels),
                        "count": 0,
                        "sum": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "mean": 0.0,
                    })
            gauges = [
                {"name": n, "labels": dict(labels), "value": v}
                for (n, labels), v in sorted(self._gauges.items())
            ]
        return {"counters": counters, "histograms": histograms, "gauges": gauges}

    def reset(self) -> None:
        """清空所有指标（用于测试隔离）。"""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()