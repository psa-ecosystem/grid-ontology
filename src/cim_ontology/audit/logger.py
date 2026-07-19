"""结构化日志（设计规范 §7.5）。"""
from __future__ import annotations

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """配置 structlog 输出。"""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
    )


log = structlog.get_logger()
