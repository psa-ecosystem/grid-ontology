"""Property 测试的 IR 生成器策略。"""
from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import strategies as st

from cim_ontology.ir.models import (
    ClassDef,
    DataProperty,
    IRStats,
    Multiplicity,
    OntologyIR,
    Package,
    SourceInfo,
)


# 合法 Python 标识符字符（与适配器 _iri_safe 一致）
_safe_id_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
_pkg_name = st.text(
    alphabet=_safe_id_chars,
    min_size=3,
    max_size=20,
).filter(lambda s: s[0].isalpha() or s[0] == "_")
_class_name = st.text(
    alphabet=_safe_id_chars,
    min_size=3,
    max_size=30,
).filter(lambda s: s[0].isalpha() or s[0] == "_")
_attr_name = st.text(
    alphabet=_safe_id_chars,
    min_size=3,
    max_size=20,
).filter(lambda s: s[0].isalpha() or s[0] == "_")


# 简单 multiplicity 生成：0..1 或 0..*
def _multiplicity(draw) -> Multiplicity:
    """生成合法的 Multiplicity（0..1 或 0..*）。"""
    unbounded = draw(st.booleans())
    if unbounded:
        return Multiplicity(min=0, max=None, raw="0..*")
    return Multiplicity(min=0, max=1, raw="0..1")


@st.composite
def class_defs(draw, max_attrs: int = 5):
    """生成 ClassDef：含随机数量属性。"""
    n_attrs = draw(st.integers(min_value=0, max_value=max_attrs))
    attrs = [
        DataProperty(
            name=draw(_attr_name),
            data_type=draw(st.sampled_from([
                "xsd:string", "xsd:integer", "xsd:float",
                "xsd:boolean", "xsd:dateTime",
            ])),
            required=draw(st.booleans()),
            multiplicity=_multiplicity(draw),
        )
        for _ in range(n_attrs)
    ]
    return ClassDef(
        name=draw(_class_name),
        parents=[],
        attributes=attrs,
        associations=[],
    )


@st.composite
def irs(draw, max_packages: int = 5, max_classes: int = 10):
    """生成 OntologyIR：含随机包与类。"""
    n_pkgs = draw(st.integers(min_value=1, max_value=max_packages))
    packages = []
    for _ in range(n_pkgs):
        n_classes = draw(st.integers(min_value=1, max_value=max_classes))
        pkg_name = draw(_pkg_name)
        classes = [draw(class_defs()) for _ in range(n_classes)]
        packages.append(Package(
            iri=f"http://x#{pkg_name}",
            name=pkg_name,
            classes=classes,
        ))
    return OntologyIR(
        schema_version="1.0",
        packages=packages,
        uncertain_entries=[],
        stats=IRStats(),
        source=SourceInfo(
            document_path="t.md",
            document_sha256="abc",
            parsed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            parser_version="0",
        ),
    )


iris = irs()  # OntologyIR 策略别名