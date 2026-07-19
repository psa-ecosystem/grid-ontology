"""错误处理与审计模块测试。"""
import pytest

from cim_ontology.audit.errors import (
    PipelineError,
    Severity,
)


class TestPipelineError:
    def test_basic_message(self):
        e = PipelineError(
            severity=Severity.ERROR,
            stage="emit",
            message="适配器失败",
        )
        assert "ERROR" in str(e)
        assert "适配器失败" in str(e)

    def test_with_suggestion(self):
        e = PipelineError(
            severity=Severity.WARN,
            stage="ingest",
            message="包解析失败",
            suggestion="检查章节完整性",
            location="Wires",
        )
        msg = str(e)
        assert "[Wires]" in msg
        assert "建议" in msg

    def test_severity_levels(self):
        for level in Severity:
            e = PipelineError(severity=level, stage="x", message="y")
            assert level.value in str(e).lower() or level.name in str(e)
