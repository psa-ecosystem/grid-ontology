"""Metrics 单元测试（P3 observability）。"""
from __future__ import annotations

import threading

import pytest

from cim_ontology.observability import Metrics


class TestCounter:
    def test_inc_default_value_one(self):
        m = Metrics()
        m.inc("cim.calls")
        m.inc("cim.calls")
        snap = m.snapshot()
        assert len(snap["counters"]) == 1
        assert snap["counters"][0]["value"] == 2

    def test_inc_with_labels_separates_dimensions(self):
        m = Metrics()
        m.inc("cim.calls", labels={"outcome": "success"})
        m.inc("cim.calls", labels={"outcome": "failure"})
        m.inc("cim.calls", labels={"outcome": "success"})
        snap = m.snapshot()
        # 按 outcome 分组, success=2, failure=1
        counts = {c["labels"]["outcome"]: c["value"] for c in snap["counters"]}
        assert counts == {"success": 2, "failure": 1}

    def test_inc_with_explicit_value(self):
        m = Metrics()
        m.inc("cim.batch.size", value=14)
        snap = m.snapshot()
        assert snap["counters"][0]["value"] == 14

    def test_inc_rejects_non_positive(self):
        m = Metrics()
        with pytest.raises(ValueError, match="Counter 必须为正整数"):
            m.inc("cim.calls", value=0)
        with pytest.raises(ValueError, match="Counter 必须为正整数"):
            m.inc("cim.calls", value=-1)


class TestHistogram:
    def test_observe_records_values(self):
        m = Metrics()
        for v in [1.0, 2.0, 3.0]:
            m.observe("cim.latency", v)
        snap = m.snapshot()
        h = snap["histograms"][0]
        assert h["count"] == 3
        assert h["sum"] == 6.0
        assert h["min"] == 1.0
        assert h["max"] == 3.0
        assert h["mean"] == 2.0

    def test_observe_with_labels(self):
        m = Metrics()
        m.observe("cim.latency", 1.0, labels={"path": "single"})
        m.observe("cim.latency", 5.0, labels={"path": "batch"})
        snap = m.snapshot()
        means = {h["labels"]["path"]: h["mean"] for h in snap["histograms"]}
        assert means == {"single": 1.0, "batch": 5.0}


class TestGauge:
    def test_gauge_set_overwrites(self):
        m = Metrics()
        m.set_gauge("cim.batch.size", 8)
        m.set_gauge("cim.batch.size", 14)
        snap = m.snapshot()
        assert snap["gauges"][0]["value"] == 14.0


class TestSnapshot:
    def test_snapshot_is_json_serializable(self):
        import json
        m = Metrics()
        m.inc("cim.calls", labels={"outcome": "success"})
        m.observe("cim.latency", 1.23, labels={"path": "single"})
        m.set_gauge("cim.batch.size", 8)
        snap = m.snapshot()
        # 必须可 JSON 序列化（无 set/frozenset 残留）
        encoded = json.dumps(snap)
        assert "counters" in encoded
        assert "histograms" in encoded
        assert "gauges" in encoded

    def test_snapshot_empty(self):
        m = Metrics()
        snap = m.snapshot()
        assert snap == {"counters": [], "histograms": [], "gauges": []}


class TestReset:
    def test_reset_clears_all(self):
        m = Metrics()
        m.inc("cim.calls")
        m.observe("cim.latency", 1.0)
        m.set_gauge("cim.batch.size", 8)
        m.reset()
        snap = m.snapshot()
        assert snap == {"counters": [], "histograms": [], "gauges": []}


class TestThreadSafety:
    def test_concurrent_inc_no_lost_updates(self):
        """100 个线程并发 inc, 总数应 == 100 * inc_per_thread。"""
        m = Metrics()
        n_threads = 50
        inc_per_thread = 100

        def worker():
            for _ in range(inc_per_thread):
                m.inc("cim.calls", labels={"thread": "w"})

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = m.snapshot()
        assert len(snap["counters"]) == 1
        assert snap["counters"][0]["value"] == n_threads * inc_per_thread