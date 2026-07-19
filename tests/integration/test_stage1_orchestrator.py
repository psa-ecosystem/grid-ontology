"""Stage 1 编排器集成测试。"""
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir


class TestCleanMarkdownToIR:
    def test_extracts_core_package(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
            "| mRID | string | 1..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        assert len(ir.packages) >= 1
        assert ir.stats.class_count >= 1
        assert ir.stats.package_count >= 1

    def test_extracts_attributes(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
            "| mRID | string | 1..1 |\n"
            "| name | string | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("IdentifiedObject")
        assert cls is not None
        attr_names = [a.name for a in cls.attributes]
        assert "mRID" in attr_names
        assert "name" in attr_names

    def test_extracts_associations(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.3 Class: Measurement\n\n"
            "| 关联端 | 目标类 | 基数 |\n|---|---|---|\n"
            "| PowerSystemResource | PowerSystemResource | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("Measurement")
        assert cls is not None
        assert len(cls.associations) >= 1
        assert cls.associations[0].target.class_name == "PowerSystemResource"

    def test_extracts_inheritance(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.2 Class: PowerSystemResource\n\n"
            "| 继承 | 父类 |\n|---|---|\n| 父类 | IdentifiedObject |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("PowerSystemResource")
        assert cls is not None
        parent_names = [p.class_name for p in cls.parents]
        assert "IdentifiedObject" in parent_names

    def test_source_sha256(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("## 5.1.1 Class: A\n", encoding="utf-8")
        ir = clean_markdown_to_ir(md)
        assert ir.source is not None
        assert len(ir.source.document_sha256) == 64

    def test_ocr_corrections_applied(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: Meastrement\n\n"  # OCR 错字
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| measurementType | string | 1..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        # 自动修正为 Measurement
        assert ir.get_class("Measurement") is not None

    # --- P1.1 测试：multi-package 输出 ---

    def test_multi_package_from_table_titles(self, tmp_path):
        """P1.1: 表标题 '表XX Pkg::Class的属性' 应让 ClassDef 归属正确 Package。

        修复前：所有类都归到 _DEFAULT_PACKAGE = 'Core'（硬编码）。
        修复后：根据表标题的 Package 字段分组到不同 Package。
        """
        md = tmp_path / "test.md"
        md.write_text(
            "## 5 Package: Core\n"
            "5.1 概述\n"
            "表8 Core::IdentifiedObject的属性\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| mRID | string | 1..1 |\n"
            "\n"
            "表9 Core::Measurement的属性\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| type | string | 1..1 |\n"
            "\n"
            "## 6 Package: Wires\n"
            "6.1 概述\n"
            "表22 Wires::Conductor的属性\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| length | float | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        # P1.1: 应有 2 个 Package（Core + Wires），而不是全部归到 Core
        package_names = sorted(p.name for p in ir.packages)
        assert "Core" in package_names
        assert "Wires" in package_names
        # IdentifiedObject 应在 Core 包
        core_pkg = ir.get_package("Core")
        assert core_pkg is not None
        core_class_names = [c.name for c in core_pkg.classes]
        assert "IdentifiedObject" in core_class_names
        assert "Measurement" in core_class_names
        # Conductor 应在 Wires 包
        wires_pkg = ir.get_package("Wires")
        assert wires_pkg is not None
        wires_class_names = [c.name for c in wires_pkg.classes]
        assert "Conductor" in wires_class_names

    def test_ir_stats_package_count(self, tmp_path):
        """P1.1: IRStats.package_count 应反映实际包数（不再是硬编码 1）。"""
        md = tmp_path / "test.md"
        md.write_text(
            "## 5 Package: Core\n"
            "表8 Core::IdentifiedObject的属性\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| mRID | string | 1..1 |\n"
            "\n"
            "## 6 Package: Wires\n"
            "表22 Wires::Conductor的属性\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| length | float | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        assert ir.stats.package_count == 2
        assert ir.stats.class_count == 2