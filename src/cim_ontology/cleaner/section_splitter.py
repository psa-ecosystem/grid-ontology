"""章节切分器：将 token 流按 ## 标题分组为 Section。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from cim_ontology.cleaner.markdown_parser import MarkdownToken, TokenType


@dataclass
class Section:
    """一个章节（通常对应一个 CIM 类）。"""

    path: str                       # "6.2.3"
    heading: str                    # "6.2.3 Class: Measurement (CIM)"
    class_name: str | None = None   # "Measurement"
    stereotype: str | None = None   # "CIM"
    package: str | None = None      # P1.1: 从表标题 "表XX Pkg::Class" 提取的包名
    tokens: list[MarkdownToken] = field(default_factory=list)


# 章节标题解析：
#   "6.1.2 Class: IdentifiedObject"
#   "6.1.2 Class: Measurement (CIM)"
#   "6.2.3 Class Measurement"  ← 容错（无冒号）
#   "7 Package Overview"      ← 无 Class 前缀，仅路径
# P1 扩展：
#   "6.7.10直流母线类(DCBusbar)"  ← 中文 H2 含 (EnglishName)
#   "A.2.4.2.2（欧洲)SolarPowerPlant 类"  ← 附录路径 + 中文括号
_HEADING_RE_WITH_CLASS = re.compile(
    r"^(?P<path>\d+(?:\.\d+){0,3})\s+Class(?:\s*[:：])?\s+(?P<name>\w+)(?:\s+\((?P<stereo>\w+)\))?"
)
_PATH_RE = re.compile(r"^(?P<path>\d+(?:\.\d+){0,3})\b")
# P1: 中英文混合 H2 + 括号英文类名（如 '6.7.10直流母线类(DCBusbar)'）
# 支持半角 ( ) 和中文全角 （ ）；括号内可含中文（如 'A.2.4.2.2（欧洲)SolarPowerPlant'）
# 路径模式：可选 A. 前缀（附录）+ 数字（.数字）{0,4}层
_PATH_RE_LETTER = re.compile(
    r"^(?P<path>(?:[A-Z]\.)?\d+(?:\.\d+){0,4})"
)
# P1: 抽取括号内 ASCII 类名（支持嵌套括号：取最后一个 ASCII 名）
_PAREN_ASCII_NAME_RE = re.compile(
    r"[\(（]([A-Za-z][A-Za-z0-9_]+)[\)）]"
)
# P1: 单段落内多个边界处理（支持换行或空格分隔）
# (?<![A-Za-z]) 确保 '表' 不是更大英文单词的一部分
_TABLE_TITLE_SPLIT_RE = re.compile(
    r"(?<![A-Za-z])表\s*\d+\s+(?P<pkg>[A-Z][A-Za-z0-9]*)::(?P<cls>[A-Z][A-Za-z0-9]+)\s*的属性"
)


def split_into_sections(tokens: list[MarkdownToken]) -> list[Section]:
    """按 H2 标题切分章节，并支持 P1 类边界检测。

    P1 扩展：在 H2 内部，如果出现 "表XX Package::Class的属性" 段落，
    在该位置切分出新的虚拟 section（class_name=Class, heading=表标题）。
    这样可以从 OCR 文档的 '## 6.7 直流' + 多个 '表N Package::Class的属性'
    结构中正确切出多个类 section。
    """
    sections: list[Section] = []
    current: Section | None = None

    for tok in tokens:
        if tok.type == TokenType.HEADING and tok.level == 2:
            heading = tok.content
            section = _parse_heading(heading)
            current = section
            sections.append(section)
        elif current is not None and tok.type == TokenType.PARAGRAPH:
            # P1: 在当前 section 内检测 "表XX Package::Class的属性" 边界
            # （含单段落多边界：markdown-it 合并无空行相邻段落）
            boundaries = _extract_table_boundaries(tok.content)
            if boundaries:
                # 段落内有边界：第一个边界之前的文本留在当前 section，
                # 后续每个边界切分出新 section
                first_boundary_pos = boundaries[0][0]
                pre_text = tok.content[:first_boundary_pos].strip()
                if pre_text:
                    current.tokens.append(
                        MarkdownToken(type=TokenType.PARAGRAPH, content=pre_text)
                    )
                for i, (pos, boundary) in enumerate(boundaries):
                    new_section = Section(
                        path=current.path,
                        heading=boundary["heading"],
                        class_name=boundary["class_name"],
                        stereotype=current.stereotype,
                        package=boundary["package"],  # P1.1: 传递包名
                    )
                    sections.append(new_section)
                    current = new_section
                    # 边界标记后的剩余文本（如下一个边界前的内容）也保留
                    next_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(tok.content)
                    tail = tok.content[pos + len(boundary["raw"]):next_pos].strip()
                    if tail:
                        current.tokens.append(
                            MarkdownToken(type=TokenType.PARAGRAPH, content=tail)
                        )
                continue
            current.tokens.append(tok)
        elif current is not None:
            current.tokens.append(tok)

    if not sections and tokens:
        # 没有 H2 标题 → 整个文档作为一节
        sections.append(Section(path="0", heading=""))

    return sections


def _extract_table_boundaries(paragraph_text: str) -> list[tuple[int, dict]]:
    """返回段落中所有 '表XX Package::Class的属性' 边界及其位置。"""
    results: list[tuple[int, dict]] = []
    for m in _TABLE_TITLE_SPLIT_RE.finditer(paragraph_text):
        results.append((m.start(), {
            "class_name": m.group("cls"),
            "package": m.group("pkg"),
            "heading": m.group(0).strip(),
            "raw": m.group(0),
        }))
    return results


def _parse_heading(heading: str) -> Section:
    """从 H2 标题文本解析 Section。"""
    section = Section(path="", heading=heading)
    stripped = heading.strip()
    m = _HEADING_RE_WITH_CLASS.match(stripped)
    if m:
        section.path = m.group("path")
        section.class_name = m.group("name")
        section.stereotype = m.group("stereo")
        return section
    # P1: 中英文混合 H2：先提取路径，再从括号中找 ASCII 类名（取最后一个）
    p = _PATH_RE_LETTER.match(stripped)
    if p:
        section.path = p.group("path")
        rest = stripped[p.end():]
        names = _PAREN_ASCII_NAME_RE.findall(rest)
        if names:
            section.class_name = names[-1]
            return section
        # 仅有路径，无类名
        return section
    elif (p := _PATH_RE.match(stripped)):
        section.path = p.group("path")
    return section