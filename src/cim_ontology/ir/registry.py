"""类与命名空间注册表。

支持按名查找、模糊匹配（Levenshtein 距离）。"""
from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """计算 Levenshtein 编辑距离。"""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        current = [i + 1]
        for j, cb in enumerate(b):
            insertions = previous[j + 1] + 1
            deletions = current[j] + 1
            substitutions = previous[j] + (ca != cb)
            current.append(min(insertions, deletions, substitutions))
        previous = current
    return previous[-1]


class ClassRegistry:
    """已注册类的中央注册表。"""

    def __init__(self) -> None:
        self._classes: dict[str, str] = {}  # class_name -> package_name

    def add(self, package: str, class_name: str) -> None:
        """注册一个类。"""
        self._classes[class_name] = package

    def has(self, class_name: str) -> bool:
        """类是否已注册。"""
        return class_name in self._classes

    def get(self, class_name: str) -> str | None:
        """获取类所属包。"""
        return self._classes.get(class_name)

    def all_names(self) -> list[str]:
        """所有已注册类名。"""
        return list(self._classes.keys())

    def find_similar(self, name: str, threshold: int = 2) -> list[tuple[str, int]]:
        """查找与给定名相似的类（距离 ≤ threshold），按距离升序。

        返回: [(class_name, distance), ...]
        """
        results = []
        for registered in self._classes:
            d = levenshtein(name, registered)
            if d <= threshold:
                results.append((registered, d))
        results.sort(key=lambda x: x[1])
        return results


class NamespaceRegistry:
    """命名空间前缀注册表。"""

    # 已知命名空间映射（设计规范 §4.3）
    CANONICAL: dict[str, str] = {
        "cim": "http://iec.ch/TC57/2024/CIM-schema-cim17#",
        "eu": "http://iec.ch/TC57/NonStandard/UML#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "sh": "http://www.w3.org/ns/shacl#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }

    def __init__(self) -> None:
        self._aliases: dict[str, str] = dict(self.CANONICAL)

    def add_alias(self, alias: str, canonical_prefix: str) -> None:
        """注册别名（如 cin -> cim）。"""
        if canonical_prefix not in self.CANONICAL:
            raise ValueError(f"未知规范前缀: {canonical_prefix}")
        self._aliases[alias] = self.CANONICAL[canonical_prefix]

    def resolve(self, prefix: str) -> str | None:
        """解析前缀为完整 IRI 模板。"""
        return self._aliases.get(prefix)