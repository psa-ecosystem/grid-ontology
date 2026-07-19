"""多重性清洗器：处理 OCR 变体、LaTeX 噪声、语义归一。"""
from __future__ import annotations

import re

from cim_ontology.ir.models import Multiplicity


class UnparseableMultiplicity(ValueError):
    """无法解析的多重性字符串。"""

    def __init__(self, raw: str) -> None:
        super().__init__(f"无法解析的多重性: {raw!r}")
        self.raw = raw


# 已知别名 → 规范格式
_ALIASES: dict[str, str] = {
    "many": "0..*",
    "n": "0..*",
    "*": "0..*",
    "0..n": "0..*",
    "1..n": "1..*",
}

# 标准 N..M 格式
_PATTERN = re.compile(r"^(\d+)\.\.(\d+|\*)$")


def clean_multiplicity(raw: str) -> Multiplicity:
    """清洗多重性字符串，返回 Multiplicity 或抛出 UnparseableMultiplicity。

    处理：
      - 前后空白
      - LaTeX 标记（$...$、\\mathcal{Z} 等）
      - 语义别名（many → 0..*）
      - N..M 标准格式
    """
    # 1. 去除 LaTeX 噪声
    text = raw.strip()
    text = text.replace("$", "")
    text = re.sub(r"\\mathcal\{[A-Z]+\}", "", text)
    text = text.strip()

    # 2. 别名归一
    text = _ALIASES.get(text, text)

    # 3. 解析 N..M
    m = _PATTERN.match(text)
    if not m:
        raise UnparseableMultiplicity(raw)

    min_str, max_str = m.groups()
    min_val = int(min_str)
    max_val: int | None = None if max_str == "*" else int(max_str)

    return Multiplicity(min=min_val, max=max_val, raw=text)
