"""P3-A-T4 测试：json_schema.py 应用 OCR 鲁棒属性名清洗。"""
import json
import pytest

from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.ir.models import (
    ClassDef,
    DataProperty,
    IRStats,
    OntologyIR,
    Package,
    SourceInfo,
)


def _make_ir_with_attrs(attr_names: list[str]) -> OntologyIR:
    """构造含指定属性名的 IR（用于验证清洗行为）。"""
    cls = ClassDef(
        name="TestClass",
        parents=[],
        attributes=[
            DataProperty(name=n, data_type="xsd:string", required=False)
            for n in attr_names
        ],
        associations=[],
    )
    pkg = Package(iri="http://x#T", name="Test", classes=[cls])
    return OntologyIR(
        schema_version="1.0",
        packages=[pkg],
        uncertain_entries=[],
        stats=IRStats(),
        source=SourceInfo(
            document_path="t.md",
            document_sha256="abc",
            parsed_at="2026-01-01T00:00:00Z",
            parser_version="0",
        ),
    )


class TestJsonSchemaAttrSlug:
    """OCR 噪声属性名应被清洗为安全 slug。"""

    def test_clean_attr_name_passes_through(self, tmp_path):
        """合法属性名原样保留。"""
        ir = _make_ir_with_attrs(["Voltage", "Current"])
        adapter = JsonSchemaAdapter()
        result = adapter.emit(ir, tmp_path)

        schema = json.loads((tmp_path / "Test_schema.json").read_text())
        assert "Voltage" in schema["properties"]["TestClass"]["properties"]
        assert "Current" in schema["properties"]["TestClass"]["properties"]

    def test_latex_attr_name_sanitized(self, tmp_path):
        """LaTeX 残骸属性名应被清洗为 ocr_noise_attr。"""
        ir = _make_ir_with_attrs([r"\mathcal{Z}"])
        adapter = JsonSchemaAdapter()
        adapter.emit(ir, tmp_path)

        schema = json.loads((tmp_path / "Test_schema.json").read_text())
        props = schema["properties"]["TestClass"]["properties"]
        # OCR 噪声命中 → 占位符
        assert "ocr_noise_attr" in props
        assert r"\mathcal{Z}" not in props

    def test_multiplicity_leak_sanitized(self, tmp_path):
        """多重性泄露（如 '0..1'）应被清洗。"""
        ir = _make_ir_with_attrs(["Voltage0..1"])
        adapter = JsonSchemaAdapter()
        adapter.emit(ir, tmp_path)

        schema = json.loads((tmp_path / "Test_schema.json").read_text())
        props = schema["properties"]["TestClass"]["properties"]
        assert "ocr_noise_attr" in props
        assert "Voltage0..1" not in props

    def test_special_chars_replaced_with_underscore(self, tmp_path):
        """特殊字符（如连字符、空格）应被替换为下划线。"""
        ir = _make_ir_with_attrs(["name-with-dashes"])
        adapter = JsonSchemaAdapter()
        adapter.emit(ir, tmp_path)

        schema = json.loads((tmp_path / "Test_schema.json").read_text())
        props = schema["properties"]["TestClass"]["properties"]
        assert "name_with_dashes" in props
        assert "name-with-dashes" not in props

    def test_required_list_uses_sanitized_names(self, tmp_path):
        """required 列表也必须使用清洗后的名字（保持与 properties key 一致）。"""
        attr = DataProperty(name=r"\mathcal{Z}", data_type="xsd:string", required=True)
        cls = ClassDef(name="TestClass", parents=[], attributes=[attr], associations=[])
        pkg = Package(iri="http://x#T", name="Test", classes=[cls])
        ir = OntologyIR(
            schema_version="1.0",
            packages=[pkg],
            uncertain_entries=[],
            stats=IRStats(),
            source=SourceInfo(
                document_path="t.md",
                document_sha256="abc",
                parsed_at="2026-01-01T00:00:00Z",
                parser_version="0",
            ),
        )

        adapter = JsonSchemaAdapter()
        adapter.emit(ir, tmp_path)

        schema = json.loads((tmp_path / "Test_schema.json").read_text())
        cls_schema = schema["properties"]["TestClass"]
        # required 列表中的名字必须与 properties key 一致
        assert "ocr_noise_attr" in cls_schema.get("required", [])

    def test_emitted_json_is_valid(self, tmp_path):
        """emitted JSON 必须可被 json.loads 解析（核心不变性）。"""
        ir = _make_ir_with_attrs([r"\mathcal{Z}", "voltage", "0..1", "name with space"])
        adapter = JsonSchemaAdapter()
        adapter.emit(ir, tmp_path)

        # 必须能解析
        schema_file = tmp_path / "Test_schema.json"
        content = schema_file.read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert "properties" in parsed
