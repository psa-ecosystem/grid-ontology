"""属性测试：依赖图无循环。

不变量：任意 IR 生成的依赖图应能成功拓扑排序（即无循环依赖）。
如果存在循环，topological_sort 会在 networkx 阶段抛出 NetworkXUnfeasible，
但本工程降级为字典序返回，因此本测试专注于：
  1. topological_sort 不抛任何异常
  2. 排序结果包含所有包节点
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings

from cim_ontology.cleaner.dep_graph import (
    build_package_dependency_graph,
    topological_sort,
)
from tests.property._strategies import iris


@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
@given(iris)
def test_dependency_graph_is_acyclic(ir):
    """任意 IR 的依赖图应可拓扑排序（无不可处理的异常）。"""
    if not ir.packages:
        return  # 空 IR 无依赖图

    graph = build_package_dependency_graph(ir)
    # 不变量：topological_sort 不抛错
    try:
        ordered = topological_sort(graph)
    except Exception as e:  # pragma: no cover - 不变量违反
        raise AssertionError(f"依赖图拓扑排序失败：{e}") from e

    # 不变量：排序后的节点数 == 包数（无丢失）
    expected_count = len(ir.packages)
    assert len(ordered) == expected_count, (
        f"拓扑排序丢失节点：{len(ordered)} != {expected_count}"
    )


@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
@given(iris)
def test_topological_sort_preserves_all_packages(ir):
    """拓扑排序结果应包含 IR 中所有包名（无丢失、无重复）。"""
    if not ir.packages:
        return

    graph = build_package_dependency_graph(ir)
    ordered = topological_sort(graph)

    package_names = {p.name for p in ir.packages}
    ordered_set = set(ordered)

    # 不变量：节点数一致（去重后）
    assert len(ordered) == len(ordered_set), (
        f"拓扑排序结果有重复节点：{ordered}"
    )
    assert ordered_set == package_names, (
        f"拓扑排序结果与包名集合不一致："
        f"missing={package_names - ordered_set}, extra={ordered_set - package_names}"
    )
