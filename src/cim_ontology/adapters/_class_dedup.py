"""类去重辅助（v1.5 P1 修复）。

P3-B 防线：cim-base-full.md Stage 1+2 解析产生 304 个跨包重复 ClassDef，
加上 181 个 intra-pkg 重复（OCR 变体合并后剩余），导致 OWL 输出中同一
cim:<ClassName> IRI 在多包中重复 emit，rdfs:isDefinedBy 互相冲突。

策略：richest wins — 对每个 class name 组选最丰富的 ClassDef，
winner 留在原 Package 不动，其余 drop。
"""
from __future__ import annotations

import structlog

from cim_ontology.ir.models import ClassDef, Package

log = structlog.get_logger()


# Ranking 维度常量（仅文档用途；排序本身在 _classdef_rank_key 中）。
# 真实数据排序权重：attrs (主) > assocs (次) > parents (三) > has_desc (四) > first_occurrence (决胜)
RANK_DIMENSIONS: tuple[str, ...] = (
    "attribute_count",
    "association_count",
    "parent_count",
    "has_description",
    "first_occurrence",
)


def _classdef_rank_key(cls: ClassDef, position: int) -> tuple:
    """5-tuple ranking key (max wins)。

    顺序（降级优先级）：
      1. attribute_count   主要权重，更多 attrs = 更完整的定义
      2. association_count 次要，关联端保留语义
      3. parent_count      第三，继承信息
      4. has_description   第四，文档
      5. first_occurrence  决定性 tie-breaker（用 -position，越早越大）

    Args:
        cls: ClassDef 实例
        position: 全局位置（pkg_idx * 10000 + class_idx），越小越早出现
    """
    return (
        len(cls.attributes),
        len(cls.associations),
        len(cls.parents),
        int(bool(cls.description)),
        -position,
    )


def deduplicate_cross_package_classes(packages: list[Package]) -> list[Package]:
    """对每个 class name 组选择最丰富的 ClassDef，其余从所属 Package 中 drop。

    Args:
        packages: 经过 merge_fuzzy_duplicate_packages 之后的 Package 列表。
                  函数不修改入参；返回每个 pkg 的 model_copy(deep=True)。

    Returns:
        新 list[Package] —— 每个 pkg 内 classes 已按"richest wins"去重；
        同一类名最多出现在 1 个 pkg 内（保留最多 attrs 那个）。
        Package 数量和 name 保持不变。

    Strategy (richest wins, 5-tuple lex order):
      1. max attributes count
      2. max associations count
      3. max parents count
      4. has description
      5. first occurrence (deterministic tie-breaker)

    Examples:
        >>> pkgs = [
        ...     Package(iri="#Core", name="Core", classes=[
        ...         ClassDef(name="Foo", attributes=[DataProperty(name="a")]),
        ...     ]),
        ...     Package(iri="#Domain", name="Domain", classes=[
        ...         ClassDef(name="Foo"),  # empty shell
        ...     ]),
        ... ]
        >>> result = deduplicate_cross_package_classes(pkgs)
        >>> len(result)
        2
        >>> next(p for p in result if p.name == "Core").classes[0].attributes
        [DataProperty(name='a')]
        >>> next(p for p in result if p.name == "Domain").classes
        []
    """
    if not packages:
        return []

    # 全局扫描：name → [(pkg_idx, class_idx, ClassDef)]
    occurrences: dict[str, list[tuple[int, int, ClassDef]]] = {}
    for pkg_idx, pkg in enumerate(packages):
        for class_idx, cls in enumerate(pkg.classes):
            occurrences.setdefault(cls.name, []).append((pkg_idx, class_idx, cls))

    # 决定每个 name 的 winner（pkg_idx, ClassDef）
    winner_by_name: dict[str, tuple[int, ClassDef]] = {}
    for name, occs in occurrences.items():
        if len(occs) == 1:
            pkg_idx, _, cls = occs[0]
            winner_by_name[name] = (pkg_idx, cls)
            continue
        # 多处出现：选 rank 最高的（max tuple），ties 由 first_occurrence 决胜
        winner_pkg_idx, _, winner_cls = max(
            occs,
            key=lambda t: _classdef_rank_key(t[2], t[0] * 10000 + t[1]),
        )
        winner_by_name[name] = (winner_pkg_idx, winner_cls)

    # 重建 keep 集合：(pkg_idx, id(cls)) 表示要保留
    keep: set[tuple[int, int]] = set()
    for name, (pkg_idx, cls) in winner_by_name.items():
        keep.add((pkg_idx, id(cls)))

    # structlog 事件：started
    dup_groups = sum(1 for occs in occurrences.values() if len(occs) > 1)
    total_classes = sum(len(p.classes) for p in packages)
    log.info(
        "class_dedup_started",
        class_count=total_classes,
        package_count=len(packages),
        duplicate_groups=dup_groups,
    )

    # structlog 事件：per-group picked_winner (debug)
    dropped = 0
    for name, (winner_pkg_idx, winner_cls) in winner_by_name.items():
        occs = occurrences[name]
        if len(occs) == 1:
            continue
        losers = [
            (p, c)
            for p, _, c in occs
            if (p, id(c)) != (winner_pkg_idx, id(winner_cls))
        ]
        log.debug(
            "class_dedup_picked_winner",
            class_name=name,
            winner_pkg=packages[winner_pkg_idx].name,
            winner_attrs=len(winner_cls.attributes),
            loser_pkgs=[packages[p].name for p, _ in losers],
            loser_attrs_each=[len(c.attributes) for _, c in losers],
        )
        dropped += len(losers)

    # 重建 packages：每包保留 winner 在该包内的 ClassDef
    new_packages: list[Package] = []
    for pkg_idx, pkg in enumerate(packages):
        kept_classes = [cls for cls in pkg.classes if (pkg_idx, id(cls)) in keep]
        new_pkg = pkg.model_copy(deep=True)
        new_pkg.classes = kept_classes
        new_packages.append(new_pkg)

    # structlog 事件：completed
    log.info(
        "class_dedup_completed",
        dropped_count=dropped,
        kept_unique_classes=sum(len(p.classes) for p in new_packages),
        duplicate_groups_resolved=dup_groups,
    )
    return new_packages