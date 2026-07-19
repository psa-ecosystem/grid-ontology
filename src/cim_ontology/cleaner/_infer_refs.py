"""跨包引用自动推断（v1.5 P1 修复）。

问题根因：cim-base-full.md Stage 1+2 解析后 `ir.cross_package_refs = []`（空），
但 ClassDef.parents/associations 实际有 375+ 个跨包引用（被依赖方 → 依赖方），
导致：
  - `build_package_dependency_graph` 返回无边的图
  - OWL 缺 `owl:imports` 声明（cim17_Wires.ttl 引用 cim:IdentifiedObject 但未 import Core）
  - Python Types 缺 `from Core_types import ...`（运行时会 ImportError）

修复：扫描所有 ClassDef.parents/associations，自动推断 (from_pkg, to_pkg, via_class)。
"""
from __future__ import annotations

import structlog

from cim_ontology.ir.models import CrossPackageRef, Package

log = structlog.get_logger()


def infer_cross_package_refs(packages: list[Package]) -> list[CrossPackageRef]:
    """扫描 ClassDef.parents/associations，自动推断跨包引用。

    Args:
        packages: 经过 merge_fuzzy_duplicate_packages + deduplicate_cross_package_classes
                  之后的 Package 列表（同 adapter emit 入口 dedup 序列）
        函数不修改入参；返回全新 list[CrossPackageRef]（按字典序排序，便于 diff 稳定）

    Returns:
        去重后的 list[CrossPackageRef]：(from_pkg, to_pkg, via_class, via_property) 四元组
        via_property 标识引用类型（parent 继承 / assoc.name 关联端）

    Examples:
        >>> from cim_ontology.ir.models import ClassDef, ClassRef, Package
        >>> pkgs = [
        ...     Package(iri="#Core", name="Core", classes=[
        ...         ClassDef(name="IdentifiedObject"),
        ...     ]),
        ...     Package(iri="#Wires", name="Wires", classes=[
        ...         ClassDef(name="ACLineSegment",
        ...                  parents=[ClassRef(package="Core", class_name="IdentifiedObject")]),
        ...     ]),
        ... ]
        >>> refs = infer_cross_package_refs(pkgs)
        >>> len(refs)
        1
        >>> refs[0].from_package
        'Wires'
        >>> refs[0].to_package
        'Core'
    """
    if not packages:
        return []

    # 1. 构造 class_to_pkg 索引（dedup 后唯一）
    class_to_pkg: dict[str, str] = {}
    for pkg in packages:
        for cls in pkg.classes:
            # 同一 class name 只可能出现在 1 个 pkg（dedup 后），后写覆盖前写是 idempotent
            class_to_pkg[cls.name] = pkg.name

    # 2. 扫描所有跨包引用
    # 用 set 去重 (from_pkg, to_pkg, via_class)；via_property 取最新扫描到的
    ref_keys: set[tuple[str, str, str]] = set()
    via_property_map: dict[tuple[str, str, str], str] = {}

    for pkg in packages:
        for cls in pkg.classes:
            # 继承引用
            for parent in cls.parents:
                target_name = parent.class_name
                if not target_name:
                    continue
                target_pkg = class_to_pkg.get(target_name)
                if target_pkg and target_pkg != pkg.name:
                    key = (pkg.name, target_pkg, target_name)
                    ref_keys.add(key)
                    via_property_map[key] = f"parent:{cls.name}"

            # 关联端引用
            for assoc in cls.associations:
                target_name = assoc.target.class_name
                if not target_name:
                    continue
                target_pkg = class_to_pkg.get(target_name)
                if target_pkg and target_pkg != pkg.name:
                    key = (pkg.name, target_pkg, target_name)
                    ref_keys.add(key)
                    via_property_map[key] = assoc.name

    # 3. 构造结果并排序（确保输出稳定，便于 snapshot/diff 测试）
    refs = [
        CrossPackageRef(
            from_package=from_p,
            to_package=to_p,
            via_class=via_c,
            via_property=via_property_map[(from_p, to_p, via_c)],
        )
        for from_p, to_p, via_c in sorted(ref_keys)
    ]

    # 4. structlog 事件
    log.info(
        "cross_package_refs_inferred",
        package_count=len(packages),
        class_count=len(class_to_pkg),
        ref_count=len(refs),
    )
    return refs