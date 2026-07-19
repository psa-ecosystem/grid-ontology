"""表格提取器测试。"""
from cim_ontology.cleaner.markdown_parser import parse_markdown
from cim_ontology.cleaner.table_extractor import Table, extract_tables_from_section


def test_simple_table():
    md = (
        "| 属性 | 类型 | 基数 |\n"
        "|---|---|---|\n"
        "| name | string | 0..1 |\n"
        "| mRID | string | 1..1 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert len(tables) == 1
    t = tables[0]
    assert t.headers == ["属性", "类型", "基数"]
    assert t.rows == [["name", "string", "0..1"], ["mRID", "string", "1..1"]]


def test_table_classification_property():
    md = (
        "| 属性 | 类型 |\n|---|---|\n"
        "| name | string |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "property"


def test_table_classification_association():
    md = (
        "| 关联端 | 目标类 | 基数 |\n|---|---|---|\n"
        "| PowerSystemResource | PowerSystemResource | 0..1 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "association"


def test_table_classification_enumeration():
    md = (
        "| 字面量 | 说明 |\n|---|---|\n"
        "| A | A 相 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "enumeration"


def test_empty_cells_stripped():
    md = "| a | b |\n|---|---|\n| 1 |  2  |\n"
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].rows[0] == ["1", "2"]