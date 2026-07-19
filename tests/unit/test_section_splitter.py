"""章节切分器测试。"""
from cim_ontology.cleaner.markdown_parser import parse_markdown
from cim_ontology.cleaner.section_splitter import (
    Section,
    split_into_sections,
)


def test_basic_split():
    md = (
        "## 6.1.1 Class A\n"
        "描述 A\n"
        "| attr | type |\n|---|---|\n| x | int |\n"
        "\n"
        "## 6.1.2 Class B\n"
        "描述 B\n"
    )
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)

    assert len(sections) == 2
    assert sections[0].heading == "6.1.1 Class A"
    assert sections[1].heading == "6.1.2 Class B"


def test_no_headings_single_section():
    md = "## 6.1.1 Only Section\n\n普通段落\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert len(sections) == 1


def test_section_path_extraction():
    md = "## 6.2.3 Class: Measurement (CIM)\n描述\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "6.2.3"
    assert sections[0].class_name == "Measurement"
    assert sections[0].stereotype == "CIM"


def test_section_without_class_prefix():
    md = "## 7 Package Overview\n文字\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "7"
    assert sections[0].class_name is None


# --- P1 修复测试：中文 H2 + 表格标题模式识别 ---

def test_chinese_h2_with_english_class_name():
    """P1: 中文 H2 含 (EnglishName) 括号模式应能提取 class_name。

    完整 GB/T 文档 H2 长这样：'## 6.7.10直流母线类(DCBusbar)'
    应提取 path='6.7.10', class_name='DCBusbar'。
    """
    md = "## 6.7.10直流母线类(DCBusbar)\n描述\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "6.7.10"
    assert sections[0].class_name == "DCBusbar"


def test_chinese_h2_appendix_path():
    """P1: 附录 H2 路径如 A.2.4.2.2 也应支持。"""
    md = "## A.2.4.2.2（欧洲)太阳能发电厂类(SolarPowerPlant)\n描述\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "A.2.4.2.2"
    assert sections[0].class_name == "SolarPowerPlant"


def test_section_class_boundary_via_table_title():
    """P1: '表XX Package::Class的属性' 段落应触发虚拟类边界。

    当某 section 中出现 '表8 Core::IdentifiedObject的属性' 时，
    应在该位置切分出新 section（class_name='IdentifiedObject'）。
    """
    md = (
        "## 5 Package: Core\n"
        "5.1 概述\n"
        "表8 Core::IdentifiedObject的属性\n"
        "| 属性 | 类型 | 基数 |\n|---|---|---|\n| mRID | string | 1..1 |\n"
    )
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    # 至少识别出 IdentifiedObject 类
    class_names = [s.class_name for s in sections if s.class_name]
    assert "IdentifiedObject" in class_names


def test_no_false_positive_on_plain_chinese():
    """P1: 不含括号的中文 H2 不应误识别为类（如'## 4.1 概述'）。"""
    md = "## 4.1 概述\n描述\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].class_name is None
    assert sections[0].path == "4.1"