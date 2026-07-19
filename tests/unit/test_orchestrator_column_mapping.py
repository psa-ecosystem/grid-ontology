"""P1.3 单元测试：表头关键字驱动的列映射（OCR 列序容错）。

背景：OCR 表格实际列序与原 markdown 不同（property 表为"名字|重数|类型|描述"，
association 表为"重数自|名字|重数到|类型|描述"）。本测试验证 orchestrator
根据表头关键字动态定位列，不再硬编码列索引。
"""
import pytest

from cim_ontology.cleaner.orchestrator import (
    _parse_property_table,
    _parse_association_table,
    _parse_inheritance_table,
)
from cim_ontology.cleaner.table_extractor import Table


class TestPropertyTableHeaderDriven:
    """属性表：按表头关键字定位列。"""

    def test_ocr_native_order_name_mult_type_desc(self):
        """OCR 真实列序：名字 | 重数 | 类型 | 描述。"""
        table = Table(
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["voltage", "0..1", "Voltage", "线电压"],
                ["ampRating", "1..1", "CurrentFlow", "额定电流"],
            ],
        )
        attrs = _parse_property_table(table)
        assert len(attrs) == 2
        # 关键：name 应在"名字"列, type 在"类型"列, mult 在"重数"列
        assert attrs[0].name == "voltage"
        assert attrs[0].data_type == "Voltage"
        assert attrs[0].multiplicity.min == 0
        assert attrs[0].multiplicity.max == 1
        assert attrs[1].name == "ampRating"
        assert attrs[1].data_type == "CurrentFlow"
        assert attrs[1].multiplicity.min == 1
        assert attrs[1].multiplicity.max == 1

    def test_native_markdown_order_name_type_mult(self):
        """原 markdown 列序：名字 | 类型 | 基数（兼容性测试）。"""
        table = Table(
            headers=["名字", "类型", "基数"],
            rows=[
                ["voltage", "Voltage", "0..1"],
                ["ampRating", "CurrentFlow", "1..1"],
            ],
        )
        attrs = _parse_property_table(table)
        assert len(attrs) == 2
        assert attrs[0].name == "voltage"
        assert attrs[0].data_type == "Voltage"
        assert attrs[1].name == "ampRating"
        assert attrs[1].data_type == "CurrentFlow"

    def test_missing_mult_column_defaults(self):
        """缺失"重数"列时回退到默认 0..1。"""
        table = Table(
            headers=["名字", "类型"],
            rows=[["voltage", "Voltage"]],
        )
        attrs = _parse_property_table(table)
        assert len(attrs) == 1
        assert attrs[0].multiplicity.min == 0
        assert attrs[0].multiplicity.max == 1

    def test_empty_table(self):
        """空表返回空列表。"""
        table = Table(headers=["名字", "重数", "类型"], rows=[])
        assert _parse_property_table(table) == []


class TestAssociationTableHeaderDriven:
    """关联端表：按表头关键字定位列。"""

    def test_ocr_native_order_multfrom_name_multto_type_desc(self):
        """OCR 真实列序：重数自 | 名字 | 重数到 | 类型 | 描述。"""
        table = Table(
            headers=["重数自", "名字", "重数到", "类型", "描述"],
            rows=[
                # row: [mult_from, name, mult_to, target_class, desc]
                ["0..*", "Terminal", "0..*", "Terminal", "关联到端点"],
                ["0..1", "BaseVoltage", "0..*", "BaseVoltage", "基准电压"],
            ],
        )
        assocs = _parse_association_table(table)
        assert len(assocs) == 2
        assert assocs[0].name == "Terminal"
        assert assocs[0].target.class_name == "Terminal"
        assert assocs[1].name == "BaseVoltage"
        assert assocs[1].target.class_name == "BaseVoltage"

    def test_fallback_when_mult_columns_garbled(self):
        """OCR 列名被噪声污染时仍能定位 name + target_class。"""
        table = Table(
            headers=["重数自", "$\\mathcal { ", "重数到", "类型", "描述"],
            rows=[
                ["0..*", "PSR", "0..*", "PowerSystemResource", "关联"],
            ],
        )
        assocs = _parse_association_table(table)
        assert len(assocs) == 1
        assert assocs[0].name == "PSR"
        assert assocs[0].target.class_name == "PowerSystemResource"


class TestInheritanceTableHeaderDriven:
    """继承表：从行内找 CamelCase 父类。"""

    def test_extracts_parent_class_name(self):
        """从父类表中提取 CamelCase 父类名。"""
        table = Table(
            headers=["父类"],
            rows=[["PowerSystemResource"]],
        )
        parents = _parse_inheritance_table(table)
        assert len(parents) == 1
        assert parents[0].class_name == "PowerSystemResource"

    def test_no_header_row(self):
        """没有"父类"表头时，扫描第一列找 CamelCase。"""
        table = Table(
            headers=["继承"],
            rows=[["PowerSystemResource"], ["IdentifiedObject"]],
        )
        parents = _parse_inheritance_table(table)
        assert len(parents) == 2
        assert parents[0].class_name == "PowerSystemResource"
        assert parents[1].class_name == "IdentifiedObject"


class TestOCRSpecificRobustness:
    """OCR 噪声行级测试。"""

    def test_property_row_with_latex_mult_garbage(self):
        """行内含 `$0 \ldots ^ { * }$` 应能解析为 0..*。"""
        table = Table(
            headers=["名字", "重数", "类型", "描述"],
            rows=[
                ["PSR", "$0 \\ldots ^ { * }$", "PowerSystemResource", "关联"],
            ],
        )
        attrs = _parse_property_table(table)
        assert len(attrs) == 1
        # multiplicity raw 保留噪声（multiplicity.py 的职责），min/max 清洗
        assert attrs[0].name == "PSR"
        assert attrs[0].data_type == "PowerSystemResource"
        # multiplicity.min 应被清洗为 0
        assert attrs[0].multiplicity.min == 0