"""IR-JSON Pydantic 模型定义。

对应设计规范 §3。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Multiplicity(BaseModel):
    """属性或关联的多重性。"""

    model_config = ConfigDict(frozen=True)

    min: int = Field(ge=0, description="最小基数")
    max: int | None = Field(default=None, description="最大基数；None 表示 *")
    raw: str = Field(description="原始字符串，如 0..*")

    @property
    def is_many(self) -> bool:
        """是否为多值。"""
        return self.max is None or self.max > 1


class ClassRef(BaseModel):
    """对另一个类的引用。

    v1.8.0 (P0 修复)：class_name 允许为 None，表示 OCR 噪声 target
    （如 "---"、纯 CJK、含 multiplicity 模式的不可恢复目标）。
    Stage 1 orchestrator.resolve_association_targets 显式设置 None
    标记不可恢复 target；下游 adapter 需要 None-safe 处理。
    """

    package: str
    class_name: str | None = None
    iri: str | None = None
    is_external: bool = False


class DataProperty(BaseModel):
    """OWL DatatypeProperty。"""

    name: str
    data_type: str = Field(default="string", description="XSD 类型，如 xsd:float")
    multiplicity: Multiplicity = Field(default_factory=lambda: Multiplicity(min=0, max=1, raw="0..1"))
    is_derived: bool = False
    is_enum: bool = False
    description: str | None = None
    required: bool = False
    inherited_from: str | None = Field(
        default=None,
        description="P2-A：从描述列抽取的 '继承自：X' 父类名（仅 OCR 文档）",
    )


class ObjectProperty(BaseModel):
    """OWL ObjectProperty（关联端）。"""

    name: str
    target: ClassRef
    multiplicity: Multiplicity = Field(default_factory=lambda: Multiplicity(min=0, max=1, raw="0..1"))
    is_aggregation: bool = False
    inverse_name: str | None = None
    description: str | None = None
    inherited_from: str | None = Field(
        default=None,
        description="P2-A：从描述列抽取的 '继承自：X' 父类名（仅 OCR 文档）",
    )


class Enumeration(BaseModel):
    """CIM 枚举类型。"""

    name: str
    values: list[str]
    description: str | None = None


class PrimitiveType(BaseModel):
    """CIM 基本类型。"""

    name: str
    base_type: str
    unit: str | None = None
    multiplier: str | None = None


class ClassDef(BaseModel):
    """一个 CIM 类定义。"""

    iri: str | None = None
    name: str
    description: str | None = None
    stereotype: str | None = None
    parents: list[ClassRef] = Field(default_factory=list)
    attributes: list[DataProperty] = Field(default_factory=list)
    associations: list[ObjectProperty] = Field(default_factory=list)
    source_table: int | None = None


class Package(BaseModel):
    """一个 CIM 包。"""

    iri: str
    name: str
    description: str | None = None
    classes: list[ClassDef] = Field(default_factory=list)
    enumerations: list[Enumeration] = Field(default_factory=list)
    primitive_types: list[PrimitiveType] = Field(default_factory=list)
    # PSA-specific metadata. Optional to keep backward compatibility with the
    # legacy CIM extraction pipeline; populated by code-first reference models.
    package_id: str | None = Field(
        default=None, description="PSA package ID, e.g. power.equipment.transformer"
    )
    version: str = Field(default="0.1.0", description="PSA package semantic version")


class CrossPackageRef(BaseModel):
    """跨包引用关系（用于构建依赖图）。"""

    from_package: str
    to_package: str
    via_class: str
    via_property: str


class UncertainEntry(BaseModel):
    """Stage 1 标记为不确定的条目（待 LLM 复审）。"""

    case_id: str
    source_table: int
    package: str
    raw_text: str
    rule_attempt: dict
    uncertainty_reason: str
    context_snippet: str = ""


class IRStats(BaseModel):
    """IR 内容的静态统计。"""

    package_count: int = 0
    class_count: int = 0
    attribute_count: int = 0
    association_count: int = 0
    enumeration_count: int = 0
    uncertain_count: int = 0


class SourceInfo(BaseModel):
    """输入文档来源信息。"""

    document_path: str
    document_sha256: str
    parsed_at: datetime
    parser_version: str


class OntologyIR(BaseModel):
    """IR-JSON 顶层模型。"""

    schema_version: Literal["1.0"] = "1.0"
    source: SourceInfo | None = None
    packages: list[Package] = Field(default_factory=list)
    uncertain_entries: list[UncertainEntry] = Field(default_factory=list)
    cross_package_refs: list[CrossPackageRef] = Field(default_factory=list)
    stats: IRStats = Field(default_factory=IRStats)

    def all_classes(self) -> list[ClassDef]:
        """所有包的所有类。"""
        return [c for pkg in self.packages for c in pkg.classes]

    def get_class(self, name: str) -> ClassDef | None:
        """按名查找类。"""
        for pkg in self.packages:
            for c in pkg.classes:
                if c.name == name:
                    return c
        return None

    def get_package(self, name: str) -> Package | None:
        """按名查找包。"""
        return next((p for p in self.packages if p.name == name), None)
