"""表格提取器：使用 BeautifulSoup 解析 HTML 表格，分类表格类型。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from cim_ontology.cleaner.markdown_parser import MarkdownToken, TokenType


@dataclass
class Table:
    """一个表格。"""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    kind: str = "unknown"  # property / association / enumeration / inheritance

    @property
    def first_header(self) -> str:
        return self.headers[0] if self.headers else ""


def extract_tables_from_section(tokens: list[MarkdownToken]) -> list[Table]:
    """从 section tokens 中提取所有表格。

    期望每个 TABLE token 的 content 为伪 markdown：
    ``"cell1|cell2|...\\ncell3|cell4|...\\n..."``，第一行为表头，其余为数据行。
    """
    tables: list[Table] = []

    for tok in tokens:
        if tok.type == TokenType.TABLE:
            html = "<table>" + _md_table_to_html(tok.content) + "</table>"
            soup = BeautifulSoup(html, "lxml")
            table = _parse_html_table(soup.find("table"))
            table.kind = _classify_table(table)
            tables.append(table)

    return tables


def _md_table_to_html(content: str) -> str:
    """将伪 markdown 表格内容转换为 HTML。

    适配 markdown_parser 输出的 ``"cell1|cell2|...\\n..."`` 格式。
    """
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    if not lines:
        return ""

    html_rows = []
    for i, line in enumerate(lines):
        # 跳过 separator 行（仅含 - : 字符）
        if re.match(r"^[\-:|]+$", line.replace("|", "")):
            continue
        cells = [c.strip() for c in line.split("|")]
        tag = "th" if i == 0 else "td"
        html_rows.append(
            "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
        )

    return "\n".join(html_rows)


def _parse_html_table(table_tag) -> Table:
    """从 BeautifulSoup table 标签解析 Table。"""
    result = Table()
    rows = table_tag.find_all("tr")
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [_normalize_cell(c.get_text()) for c in cells]
        if i == 0:
            result.headers = cell_texts
        else:
            result.rows.append(cell_texts)
    return result


def _normalize_cell(text: str) -> str:
    """规范化单元格文本。"""
    return " ".join(text.split())


def _classify_table(table: Table) -> str:
    """根据首列关键字分类表格。

    P1.2 扩展：识别 OCR 后的真实表头（"名字"/"名称"/"重数"/"类型"），
    不再仅依赖 "属性"/"property" 等原生 markdown 关键字。
    """
    headers_lower = [h.lower() for h in table.headers]
    first = headers_lower[0] if headers_lower else ""
    all_headers = " ".join(headers_lower)

    # 属性表：含 "属性" / "property" / "名字"/"名称" + ("类型" 或 "重数" 或 "类型")
    if "属性" in first or "property" in first or "attribute" in first:
        return "property"
    if first in ("名字", "名称", "name", "属性名", "字段"):
        return "property"
    if ("名字" in first or "名称" in first) and ("类型" in all_headers or "重数" in all_headers):
        return "property"

    # 关联端表：含 "关联端" / "association" / "重数自" / "[重数到]"
    if "关联端" in first or "association" in first or "关联" in first:
        return "association"
    if "重数自" in first or "重数到" in all_headers:
        return "association"
    # B3：SG-CIM LDM 4 列布局识别（重数 | 目标 | 类型 | 描述）。
    # 首列 = "重数"，通过 4 列 + "目标" 关键字（OCR 容忍"target"）识别。
    if len(table.headers) == 4 and ("重数" in first) and (
        "目标" in all_headers or "target" in all_headers
    ):
        return "association"

    # 字面量/枚举
    if "字面量" in first or "literal" in first or "枚举" in first:
        return "enumeration"

    # 继承/父类
    if "继承" in first or "父类" in first or "super" in first:
        return "inheritance"

    return "unknown"
