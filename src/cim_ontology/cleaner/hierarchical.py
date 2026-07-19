"""层级推断：OCR 异常时 ## 标记可能丢失，此模块基于多种信号推断层级。"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionContext:
    """推断的章节上下文。"""

    depth: int           # 1-4
    confidence: float    # 0.0-1.0


def hierarchical_classify_section(
    heading: str,
    all_headings: list[str],
) -> SectionContext:
    """基于多种信号推断章节层级。

    信号优先级：
      1. 章节编号格式 (e.g. "6.1.2" → depth=3)，置信度 0.9
      2. Class: 关键字（无编号时），置信度 0.7，depth=3
      3. 默认 depth=2 + 警告，置信度 0.3
    """
    text = heading.strip()

    # 信号 1: 编号格式
    m = re.match(r"^(\d+(?:\.\d+){0,3})", text)
    if m:
        depth = m.group(1).count(".") + 1
        return SectionContext(depth=depth, confidence=0.9)

    # 信号 2: Class: 关键字
    if re.search(r"^Class\s*[:：]\s*\w+", text):
        return SectionContext(depth=3, confidence=0.7)

    # 默认
    return SectionContext(depth=2, confidence=0.3)
