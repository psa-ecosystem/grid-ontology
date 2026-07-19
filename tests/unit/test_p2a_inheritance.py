"""P2-A 单元测试：从表格描述列抽取 '继承自：X' 模式 → ClassDef.parents。

背景：OCR CIM 文档中继承关系不在叙述文字中，而是在属性/关联表的"描述"列
（如 `继承自：IdentifiedObject`）。本测试覆盖：
  1. `_extract_inherited_from` 的各种模式匹配
  2. `_parse_property_table` / `_parse_association_table` 写入 inherited_from
  3. `_apply_tables` 聚合 inherited_from → cls.parents（多重继承）
"""
import pytest

from cim_ontology.cleaner.orchestrator import (
    _extract_inherited_from,
    _parse_property_table,
    _parse_association_table,
    _apply_tables,
)
from cim_ontology.cleaner.table_extractor import Table
from cim_ontology.ir.models import ClassDef


class TestExtractInheritedFrom:
    """`_extract_inherited_from` 模式匹配测试。"""

    def test_full_width_colon(self):
        """全角冒号 `：` 是 OCR 主要格式。"""
        assert _extract_inherited_from("继承自：IdentifiedObject") == "IdentifiedObject"

    def test_half_width_colon(self):
        """半角冒号 `:` 也是合法格式。"""
        assert _extract_inherited_from("继承自:IdentifiedObject") == "IdentifiedObject"

    def test_with_surrounding_text(self):
        """描述列可能含其他文字（'继承' 前缀可省略）。"""
        assert _extract_inherited_from(
            "本处描述了类的一个浮点类型的固有属性 继承自：PowerSystemResource"
        ) == "PowerSystemResource"

    def test_no_inheritance_marker(self):
        """无 `继承自` 标记返回 None。"""
        assert _extract_inherited_from("电力系统资源的基准电压") is None

    def test_empty_string(self):
        """空字符串返回 None。"""
        assert _extract_inherited_from("") is None

    def test_none(self):
        """None 返回 None。"""
        assert _extract_inherited_from(None) is None

    def test_excess_whitespace(self):
        """容忍任意空白。"""
        assert _extract_inherited_from("继承   自  :  PowerSystemResource") == "PowerSystemResource"

    def test_class_name_with_chinese_suffix(self):
        """`继承自：类` 不应返回 `类`（非 CamelCase）。"""
        # `类` 不是 CamelCase（首字符是中文），regex 必须不匹配
        assert _extract_inherited_from("继承自 的 类") is None


class TestPropertyTableInheritedFrom:
    """属性表 → DataProperty.inherited_from。"""

    def test_extracts_inherited_from_desc_column(self):
        """描述列含 `继承自：X` → DataProperty.inherited_from 设为 X。"""
        table = Table(
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["nominalVoltage", "0..1", "Voltage", "电力系统资源的基准电压"],
                ["aliasName", "0..1", "String", "继承自：IdentifiedObject"],
                ["name", "0..1", "String", "继承自：IdentifiedObject"],
            ],
        )
        attrs = _parse_property_table(table)
        assert attrs[0].inherited_from is None
        assert attrs[1].inherited_from == "IdentifiedObject"
        assert attrs[2].inherited_from == "IdentifiedObject"


class TestAssociationTableInheritedFrom:
    """关联表 → ObjectProperty.inherited_from。"""

    def test_extracts_inherited_from_desc_column(self):
        table = Table(
            headers=["重数自", "名字", "重数到", "类型", "描述"],
            rows=[
                ["0..1", "Equipments", "0..*", "Equipment", "继承自：EquipmentContainer"],
                ["1..1", "Names", "0..*", "Name", "继承自:IdentifiedObject"],
            ],
        )
        assocs = _parse_association_table(table)
        assert assocs[0].inherited_from == "EquipmentContainer"
        assert assocs[1].inherited_from == "IdentifiedObject"


class TestApplyTablesAggregatesParents:
    """`_apply_tables` 聚合 inherited_from → cls.parents（多重继承）。"""

    def test_single_inheritance_from_attributes(self):
        """所有 attribute 都标记为继承自 X → cls.parents = [X]。"""
        cls = ClassDef(name="BaseVoltage")
        tables = [Table(
            kind="property",
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["aliasName", "0..1", "String", "继承自：IdentifiedObject"],
                ["name", "0..1", "String", "继承自：IdentifiedObject"],
                ["mRID", "0..1", "String", "继承自：IdentifiedObject"],
            ],
        )]
        _apply_tables(cls, tables)
        assert len(cls.parents) == 1
        assert cls.parents[0].class_name == "IdentifiedObject"

    def test_multiple_inheritance_from_attributes(self):
        """不同 attribute 继承自不同父类 → cls.parents 含多个。"""
        cls = ClassDef(name="ConductingEquipment")
        tables = [Table(
            kind="property",
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["aggregate", "0..1", "Boolean", "继承自：Equipment"],
                ["aliasName", "0..1", "String", "继承自：IdentifiedObject"],
            ],
        )]
        _apply_tables(cls, tables)
        parent_names = {p.class_name for p in cls.parents}
        assert "Equipment" in parent_names
        assert "IdentifiedObject" in parent_names

    def test_inheritance_from_associations(self):
        """关联表中的 inherited_from 也应被聚合。"""
        cls = ClassDef(name="Bay")
        tables = [
            Table(kind="property", headers=["名字", "重数", "类型", "描述"], rows=[]),
            Table(
                kind="association",
                headers=["重数自", "名字", "重数到", "类型", "描述"],
                rows=[
                    ["0..1", "Equipments", "0..*", "Equipment", "继承自：EquipmentContainer"],
                    ["1..1", "Names", "0..*", "Name", "继承自:IdentifiedObject"],
                ],
            ),
        ]
        _apply_tables(cls, tables)
        parent_names = {p.class_name for p in cls.parents}
        assert "EquipmentContainer" in parent_names
        assert "IdentifiedObject" in parent_names

    def test_no_inheritance_marker_no_parents(self):
        """无 inherited_from 时 cls.parents 保持为空。"""
        cls = ClassDef(name="MyClass")
        tables = [Table(
            kind="property",
            headers=["名字", "重数", "类型", "描述"],
            rows=[["voltage", "0..1", "Voltage", "线电压"]],
        )]
        _apply_tables(cls, tables)
        assert cls.parents == []

    def test_deduplicates_parents(self):
        """同一父类多次出现 → 只添加一次。"""
        cls = ClassDef(name="MyClass")
        tables = [Table(
            kind="property",
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["aliasName", "0..1", "String", "继承自：IdentifiedObject"],
                ["name", "0..1", "String", "继承自：IdentifiedObject"],
                ["mRID", "0..1", "String", "继承自:IdentifiedObject"],
            ],
        )]
        _apply_tables(cls, tables)
        assert len(cls.parents) == 1
        assert cls.parents[0].class_name == "IdentifiedObject"