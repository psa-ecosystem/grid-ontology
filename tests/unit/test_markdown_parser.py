"""Markdown 解析器单元测试。"""
from cim_ontology.cleaner.markdown_parser import (
    MarkdownToken,
    TokenType,
    parse_markdown,
)


class TestParseMarkdown:
    def test_extracts_h2_heading(self):
        md = "## 6.1.2 Class: IdentifiedObject\n"
        tokens = parse_markdown(md)
        h2 = [t for t in tokens if t.type == TokenType.HEADING and t.level == 2]
        assert len(h2) == 1
        assert "IdentifiedObject" in h2[0].content

    def test_extracts_table(self):
        md = "| 列1 | 列2 |\n|---|---|\n| A | B |\n"
        tokens = parse_markdown(md)
        tables = [t for t in tokens if t.type == TokenType.TABLE]
        assert len(tables) >= 1
        assert "A" in tables[0].content
        assert "B" in tables[0].content

    def test_empty_input(self):
        tokens = parse_markdown("")
        assert tokens == []

    def test_mixed_content(self):
        md = (
            "# 标题\n\n"
            "## 6.1.2 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 |\n|---|---|\n| name | string |\n"
        )
        tokens = parse_markdown(md)
        types = {t.type for t in tokens}
        assert TokenType.HEADING in types
        assert TokenType.TABLE in types

    def test_extracts_html_block_table(self):
        """P1: 嵌入的 <table> HTML 块应被转为 TABLE token。

        完整 GB/T 文档 OCR 后的属性表是 raw HTML 形式（如 <table><tr><td>），
        markdown-it 产生 html_block 类型 token，markdown_parser 需识别并转为 TABLE。
        """
        md = (
            "## 类\n\n"
            "<table><tr><td>属性1</td><td>类型1</td></tr>"
            "<tr><td>name</td><td>string</td></tr></table>\n"
        )
        tokens = parse_markdown(md)
        tables = [t for t in tokens if t.type == TokenType.TABLE]
        assert len(tables) == 1
        # TABLE content 应包含单元格的文本
        assert "属性1" in tables[0].content or "name" in tables[0].content

    def test_html_block_preserves_sibling_markdown_table(self):
        """P1: HTML 表格转换不应破坏原生 markdown 表格解析。"""
        md = (
            "| 列1 | 列2 |\n|---|---|\n| A | B |\n\n"
            "<table><tr><td>X</td></tr></table>\n"
        )
        tokens = parse_markdown(md)
        tables = [t for t in tokens if t.type == TokenType.TABLE]
        assert len(tables) == 2