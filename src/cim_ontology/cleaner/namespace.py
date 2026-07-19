"""命名空间清洗器：前缀 → 完整 IRI，支持 OCR 拼写自动纠正。"""
from __future__ import annotations

import re
from collections import Counter

from cim_ontology.ir.registry import NamespaceRegistry, levenshtein


class UnknownNamespace(KeyError):
    """未知命名空间前缀。"""

    def __init__(self, prefix: str) -> None:
        super().__init__(prefix)
        self.prefix = prefix


# 引用注册表的规范前缀
_CANONICAL_PREFIXES: list[str] = list(NamespaceRegistry.CANONICAL.keys())


def clean_namespace(prefix: str) -> str:
    """将命名空间前缀解析为完整 IRI 模板。

    prefix 示例: "cim:", "rdfs:"
    """
    ns = NamespaceRegistry()
    iri = ns.resolve(prefix.rstrip(":"))
    if iri is None:
        raise UnknownNamespace(prefix)
    return iri


def collect_namespace_aliases(content: str) -> dict[str, int]:
    """统计文档中出现的命名空间前缀及其频次。

    模式: \\b([a-z]+):[A-Z]\\w+
    """
    pattern = re.compile(r"\b([a-z]+):[A-Z]\w+")
    counter: Counter[str] = Counter()
    for m in pattern.finditer(content):
        counter[m.group(1)] += 1
    return dict(counter)


def auto_correct_namespaces(
    aliases: dict[str, int],
    max_distance: int = 2,
) -> dict[str, str]:
    """基于 Levenshtein 距离自动纠正命名空间前缀。

    返回: {alias: canonical_prefix}（仅包含需要纠正的项）
    """
    corrections: dict[str, str] = {}
    for alias in aliases:
        if alias in _CANONICAL_PREFIXES:
            continue
        # 找最近规范前缀
        closest = min(
            _CANONICAL_PREFIXES,
            key=lambda c: levenshtein(alias, c),
        )
        if levenshtein(alias, closest) <= max_distance:
            corrections[alias] = closest
    return corrections
