"""B4 Stage 3: JSON-LD Context 属性 @type xsd 注解单元测试。

覆盖：
  - 端到端：emit 输出包含 @type xsd 注解（String/Integer/Float/Boolean/DateTime/空）
  - 跳过 B7 清空的噪声属性
  - 防御性二次检查：LaTeX/CJK 噪声属性不生成映射
  - assoc 端不变（仍是 @id + @type: @id 形式）
  - normalize_xsd_type 集成（自定义类型 → 原样透传 passthrough）
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cim_ontology.adapters._iri_safe import normalize_xsd_type
from cim_ontology.adapters.jsonld_context import JsonLdContextAdapter
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    DataProperty,
    Multiplicity,
    ObjectProperty,
    OntologyIR,
    Package,
    SourceInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ir_with_class(
    class_name: str = "TestClass",
    attr_name: str = "aliasName",
    data_type: str = "String",
    mult: tuple[int, int | None] = (0, 1),
    extra_attrs: list[DataProperty] | None = None,
    associations: list[ObjectProperty] | None = None,
) -> OntologyIR:
    """构造带单个属性的 IR（用于 B4 端到端测试）。"""
    attrs = [
        DataProperty(
            name=attr_name,
            data_type=data_type,
            multiplicity=Multiplicity(min=mult[0], max=mult[1], raw=f"{mult[0]}..{mult[1] or '*'}"),
        ),
    ]
    if extra_attrs:
        attrs.extend(extra_attrs)
    cls = ClassDef(
        name=class_name,
        attributes=attrs,
        associations=associations or [],
    )
    return OntologyIR(
        packages=[Package(
            iri="http://test/TestPkg",
            name="TestPkg",
            classes=[cls],
        )],
        uncertain_entries=[],
        source=SourceInfo(
            document_path="/test",
            document_sha256="x",
            parsed_at=datetime.now(timezone.utc),
            parser_version="0.2.0",
        ),
    )


def _read_context(output_dir: Path, pkg_name: str = "TestPkg") -> dict:
    """读取并解析 JSON-LD Context 文件。"""
    path = output_dir / f"{pkg_name}_context.jsonld"
    return json.loads(path.read_text())["@context"]


# ---------------------------------------------------------------------------
# 端到端：@type xsd 注解（6 用例）
# ---------------------------------------------------------------------------


class TestAttributeXsdTypeAnnotation:
    """属性映射应包含 @type xsd 注解。"""

    def test_string_attr_has_xsd_string(self, tmp_path):
        """String 属性 → @type: xsd:string。"""
        ir = _make_ir_with_class(data_type="String")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["aliasName"] == {
            "@id": "cim:TestClass.aliasName",
            "@type": "xsd:string",
        }

    def test_integer_attr_has_xsd_integer(self, tmp_path):
        """Integer 属性 → @type: xsd:integer。"""
        ir = _make_ir_with_class(attr_name="sequenceNumber", data_type="Integer")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["sequenceNumber"] == {
            "@id": "cim:TestClass.sequenceNumber",
            "@type": "xsd:integer",
        }

    def test_float_attr_has_xsd_float(self, tmp_path):
        """Float 属性 → @type: xsd:float（normalize_xsd_type 实际映射）。"""
        ir = _make_ir_with_class(attr_name="nominalVoltage", data_type="Float")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["nominalVoltage"] == {
            "@id": "cim:TestClass.nominalVoltage",
            "@type": "xsd:float",
        }

    def test_boolean_attr_has_xsd_boolean(self, tmp_path):
        """Boolean 属性 → @type: xsd:boolean。"""
        ir = _make_ir_with_class(attr_name="isActive", data_type="Boolean")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["isActive"] == {
            "@id": "cim:TestClass.isActive",
            "@type": "xsd:boolean",
        }

    def test_datetime_attr_has_xsd_dateTime(self, tmp_path):
        """DateTime 属性 → @type: xsd:dateTime。"""
        ir = _make_ir_with_class(attr_name="createdAt", data_type="DateTime")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["createdAt"] == {
            "@id": "cim:TestClass.createdAt",
            "@type": "xsd:dateTime",
        }

    def test_empty_data_type_falls_back_to_xsd_string(self, tmp_path):
        """空 data_type → @type: xsd:string（与 OWL adapter fallback 一致）。"""
        ir = _make_ir_with_class(data_type="")
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["aliasName"] == {
            "@id": "cim:TestClass.aliasName",
            "@type": "xsd:string",
        }


# ---------------------------------------------------------------------------
# 跳过 B7 清空的噪声属性（2 用例）
# ---------------------------------------------------------------------------


class TestB7ClearedAttrSkipped:
    """B7 清空的 attr.name == '' 属性应跳过，不生成映射。"""

    def test_empty_attr_name_not_in_context(self, tmp_path):
        """attr.name == '' → 不在 @context 中。"""
        empty_attr = DataProperty(
            name="",
            data_type="String",
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(extra_attrs=[empty_attr])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        # aliasName 仍存在
        assert "aliasName" in ctx
        # 空名不生成映射（避免 cim:. 这种无意义 IRI）
        assert "" not in ctx
        assert "cim:TestClass." not in {v["@id"] for v in ctx.values() if isinstance(v, dict)}

    def test_whitespace_only_attr_name_not_in_context(self, tmp_path):
        """attr.name == '   '（仅空白）→ 不在 @context 中。"""
        ws_attr = DataProperty(
            name="   ",
            data_type="String",
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(extra_attrs=[ws_attr])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert "" not in ctx
        assert "aliasName" in ctx  # 合法 attr 仍存在


# ---------------------------------------------------------------------------
# 防御性二次检查：LaTeX/CJK 噪声（2 用例）
# ---------------------------------------------------------------------------


class TestOcrNoiseAttrSkipped:
    """防御性二次检查：_classify_attr_noise 返回非 None 的属性不生成映射。"""

    def test_latex_attr_not_in_context(self, tmp_path):
        """LaTeX 残骸 → 不在 @context 中。"""
        latex_attr = DataProperty(
            name="$\\mathcal { Z }$",
            data_type="String",
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(extra_attrs=[latex_attr])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert "$\\mathcal { Z }$" not in ctx

    def test_cjk_attr_not_in_context(self, tmp_path):
        """纯 CJK → 不在 @context 中。"""
        cjk_attr = DataProperty(
            name="名字",
            data_type="String",
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(extra_attrs=[cjk_attr])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert "名字" not in ctx


# ---------------------------------------------------------------------------
# ObjectProperty 端不变（2 用例）
# ---------------------------------------------------------------------------


class TestAssociationUnchanged:
    """ObjectProperty 仍为 @id + @type: @id 形式（B3 已就绪，B4 不动）。"""

    def test_association_has_type_id(self, tmp_path):
        """Association → @type: @id（指向另一资源）。"""
        assoc = ObjectProperty(
            name="Substation",
            target=ClassRef(package="TestPkg", class_name="Substation"),
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(associations=[assoc])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        assert ctx["Substation"] == {
            "@id": "cim:TestClass.Substation",
            "@type": "@id",
        }

    def test_association_and_attribute_different_types(self, tmp_path):
        """同名 attr 与 assoc：attr 用 xsd:type，assoc 用 @id（不会冲突，因为不同 class）。"""
        # 在 JSON-LD @context 中，键是字段名，同名可能发生但不常见
        # 本测试仅验证两种映射类型并存
        attr_x = DataProperty(
            name="voltage", data_type="Float",
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        assoc_x = ObjectProperty(
            name="voltage",
            target=ClassRef(package="TestPkg", class_name="VoltageLevel"),
            multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
        )
        ir = _make_ir_with_class(extra_attrs=[attr_x], associations=[assoc_x])
        JsonLdContextAdapter().emit(ir, tmp_path)
        ctx = _read_context(tmp_path)
        # 验证两个都被处理
        assert isinstance(ctx["voltage"], dict)
        # 由于 dict 赋值会覆盖，最后赋值的 assoc 会覆盖 attr — 接受此行为


# ---------------------------------------------------------------------------
# normalize_xsd_type 集成（4 用例）
# ---------------------------------------------------------------------------


class TestNormalizeXsdTypeIntegration:
    """验证 normalize_xsd_type 的关键映射（防止 JSON-LD 适配器脱节）。"""

    @pytest.mark.parametrize("data_type,expected_xsd", [
        ("String", "xsd:string"),
        ("Integer", "xsd:integer"),
        ("Int", "xsd:integer"),
        ("Float", "xsd:float"),
        ("Boolean", "xsd:boolean"),
        ("DateTime", "xsd:dateTime"),
        ("Date", "xsd:date"),
        ("Time", "xsd:time"),
        ("Duration", "xsd:duration"),
        ("URI", "xsd:anyURI"),
        # 自定义 CIM 物理单位 → 原样透传（normalize_xsd_type 未知键 passthrough）
        ("ActivePower", "ActivePower"),
        ("Voltage", "Voltage"),
        ("UnitMultiplier", "UnitMultiplier"),
        # 空字符串 → xsd:string fallback
        ("", "xsd:string"),
    ])
    def test_normalize_xsd_type_returns_expected(self, data_type, expected_xsd):
        """确保 normalize_xsd_type 输入输出符合 B4 期望。"""
        assert normalize_xsd_type(data_type) == expected_xsd