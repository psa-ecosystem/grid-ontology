"""PipelineError 与严重性分级（设计规范 §7.1）。"""
from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """错误严重性分级。"""

    FATAL = "fatal"    # 输入不可读，立即退出
    ERROR = "error"    # 单包/单格式失败，跳过继续
    WARN = "warn"      # 单条记录可疑，标记不确定
    INFO = "info"      # 进度/统计


class PipelineError(Exception):
    """流水线错误。"""

    def __init__(
        self,
        severity: Severity,
        stage: str,
        message: str,
        location: str = "",
        raw_input: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.severity = severity
        self.stage = stage
        self.message = message
        self.location = location
        self.raw_input = raw_input
        self.suggestion = suggestion
        super().__init__(self._format())

    def _format(self) -> str:
        loc = f"[{self.location}] " if self.location else ""
        sug = f"\n  建议: {self.suggestion}" if self.suggestion else ""
        return f"{self.severity.value.upper()}: {loc}{self.message}{sug}"
