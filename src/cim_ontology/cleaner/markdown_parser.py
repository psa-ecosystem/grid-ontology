"""Markdown 解析器：使用 markdown-it-py 提取 token 序列。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from markdown_it import MarkdownIt


class TokenType(str, Enum):
    """Token 类型。"""

    HEADING = "heading"
    TABLE = "table"
    PARAGRAPH = "paragraph"
    CODE = "code"
    OTHER = "other"


@dataclass
class MarkdownToken:
    """单个 Markdown 元素。"""

    type: TokenType
    level: int = 0
    content: str = ""
    children: list[MarkdownToken] = field(default_factory=list)


def parse_markdown(content: str) -> list[MarkdownToken]:
    """解析 Markdown 为 token 列表。

    仅提取对本体抽取有用的 token：标题、表格、段落、代码块。
    表格内嵌套容器 token（thead/tbody/tr/th/td）显式忽略。
    表格 inline content 保留为伪 markdown：`cell1|cell2|...` 每行用 `\\n` 分隔，
    第二行为分隔行 `---`（用于 task 6 table_extractor 重建行列结构）。

    P1 修复：识别 markdown-it 输出的 `html_block` token 中嵌入的 `<table>...</table>`，
    将其转为标准伪 markdown 表格格式，作为 TABLE token 追加。这是为了支持 OCR 后的
    GB/T 标准文档（其属性表是 raw HTML 形式，非原生 markdown 表格）。
    """
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    raw_tokens = md.parse(content)

    results: list[MarkdownToken] = []
    in_table = False
    in_tr = False  # 当前是否在 <tr> 内（用于在 cells 间插入 `|`）

    for tok in raw_tokens:
        ttype = tok.type

        if ttype == "heading_open":
            level = int(tok.tag[1])
            results.append(MarkdownToken(type=TokenType.HEADING, level=level))
        elif ttype == "heading_close":
            pass

        elif ttype == "table_open":
            results.append(MarkdownToken(type=TokenType.TABLE))
            in_table = True
        elif ttype == "table_close":
            in_table = False

        elif ttype == "tr_open":
            in_tr = True
            # 在每个新 tr 开始时，先换行（除非是第一个 tr）
            if in_table and results and results[-1].type == TokenType.TABLE:
                existing = results[-1].content
                if existing:
                    results[-1].content = existing + "\n"
        elif ttype == "tr_close":
            in_tr = False

        elif ttype == "inline":
            if in_table and in_tr and results and results[-1].type == TokenType.TABLE:
                existing = results[-1].content
                addition = _clean_inline(tok.content)
                if not existing or existing.endswith("\n"):
                    results[-1].content = (existing or "") + addition
                else:
                    results[-1].content = existing + "|" + addition
            elif results and results[-1].type == TokenType.HEADING:
                results[-1].content = _clean_inline(tok.content)
            elif results and results[-1].type == TokenType.PARAGRAPH:
                # P1: 将 inline 内容填入 PARAGRAPH（支持表标题边界检测）
                if results[-1].content:
                    results[-1].content += "\n" + _clean_inline(tok.content)
                else:
                    results[-1].content = _clean_inline(tok.content)

        elif ttype == "paragraph_open":
            results.append(MarkdownToken(type=TokenType.PARAGRAPH))
        elif ttype == "paragraph_close":
            pass

        elif ttype in ("code_block_open", "fence"):
            results.append(MarkdownToken(type=TokenType.CODE, content=tok.content))

        elif ttype == "html_block":
            # P1: 提取嵌入的 <table>...</table>，转为伪 markdown 表格格式
            pseudo = _html_table_to_pseudo(tok.content)
            if pseudo:
                results.append(MarkdownToken(type=TokenType.TABLE, content=pseudo))

        # 其他 token（thead/tbody/th/td 容器）忽略

    return results


def _clean_inline(content: str) -> str:
    """清理 inline 文本，去除多余空白。"""
    return " ".join(content.split())


# P1: 简单的 HTML <table> → 伪 markdown 表格转换（不依赖 BeautifulSoup，零依赖扩展）
_HTML_TABLE_RE = re.compile(
    r"<table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL
)
_HTML_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HTML_TD_RE = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _html_table_to_pseudo(html: str) -> str:
    """将 HTML <table> 转为伪 markdown 表格 `cell1|cell2\\n...` 格式。

    返回空字符串表示未包含 <table>。仅支持简单表格（无嵌套 table）。
    """
    table_match = _HTML_TABLE_RE.search(html)
    if not table_match:
        return ""

    rows: list[str] = []
    for tr_match in _HTML_TR_RE.finditer(table_match.group(1)):
        cells: list[str] = []
        for td_match in _HTML_TD_RE.finditer(tr_match.group(1)):
            cell_text = _HTML_TAG_RE.sub("", td_match.group(1))
            cells.append(_clean_inline(cell_text))
        if cells:
            rows.append("|".join(cells))

    return "\n".join(rows)