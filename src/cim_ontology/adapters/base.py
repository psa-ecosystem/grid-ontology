"""OutputAdapter 抽象接口与注册中心（设计规范 §6.1）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from cim_ontology.ir.models import OntologyIR


@dataclass
class EmitResult:
    """适配器输出结果。"""

    files: list[Path]
    stats: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class VerifyResult:
    """适配器验证结果。"""

    passed: bool
    issues: list = field(default_factory=list)
    roundtrip_match: bool = False


class OutputAdapter(ABC):
    """所有输出适配器的抽象基类。"""

    target_format: ClassVar[str]

    @abstractmethod
    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        ...

    @abstractmethod
    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        ...


ADAPTERS: dict[str, type[OutputAdapter]] = {}


def get_adapter(fmt: str) -> OutputAdapter:
    """根据格式名获取适配器实例。"""
    if fmt not in ADAPTERS:
        raise ValueError(
            f"Unknown format: {fmt!r}. Available: {list(ADAPTERS.keys())}"
        )
    return ADAPTERS[fmt]()


def register_adapter(fmt: str, adapter_cls: type[OutputAdapter]) -> None:
    """注册适配器（供插件扩展）。"""
    ADAPTERS[fmt] = adapter_cls