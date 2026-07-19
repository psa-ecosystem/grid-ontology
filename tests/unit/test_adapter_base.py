"""OutputAdapter 基类测试。"""
from pathlib import Path

from cim_ontology.adapters.base import (
    ADAPTERS,
    EmitResult,
    OutputAdapter,
    VerifyResult,
    get_adapter,
)


class _StubAdapter:
    target_format = "stub"

    def emit(self, ir, output_dir):
        return EmitResult(files=[], stats={}, warnings=[], duration_ms=0)

    def verify(self, ir, emitted):
        return VerifyResult(passed=True, issues=[], roundtrip_match=True)


class TestRegistry:
    def test_register_adapter(self):
        ADAPTERS["stub"] = _StubAdapter
        try:
            adapter = get_adapter("stub")
            assert isinstance(adapter, _StubAdapter)
        finally:
            del ADAPTERS["stub"]

    def test_unknown_format_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown format"):
            get_adapter("nonexistent_format_xyz")


def test_emit_result_fields():
    r = EmitResult(files=[Path("a")], stats={"classes": 10}, warnings=[], duration_ms=100)
    assert r.duration_ms == 100
    assert r.stats["classes"] == 10