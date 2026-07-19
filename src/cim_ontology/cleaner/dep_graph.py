"""包依赖图与拓扑排序（设计规范 §6.2.1）。

用于：
  - OWL 按包拆分时正确添加 owl:imports
  - Python types 按拓扑序生成避免循环 import
"""
from __future__ import annotations

import networkx as nx
import structlog

from cim_ontology.ir.models import CrossPackageRef, OntologyIR

log = structlog.get_logger()


def build_package_dependency_graph(
    ir: OntologyIR,
    cross_package_refs: list[CrossPackageRef] | None = None,
) -> nx.DiGraph:
    """从 cross_package_refs 构建有向依赖图。

    Args:
        ir: OntologyIR（用于节点列表）
        cross_package_refs: 跨包引用列表（v1.5 P1：adapters 可传入推断的 refs）
                           默认 None → 使用 ir.cross_package_refs（向后兼容）

    节点: 包名
    边: to_package → from_package 表示 from_package 依赖 to_package
    （箭头方向指向依赖方，被依赖方在前，便于拓扑排序得到依赖优先序）
    """
    refs = cross_package_refs if cross_package_refs is not None else ir.cross_package_refs
    g = nx.DiGraph()
    for pkg in ir.packages:
        g.add_node(pkg.name)
    for ref in refs:
        # 箭头方向：被依赖方 → 依赖方，使拓扑排序结果中依赖在前
        g.add_edge(ref.to_package, ref.from_package)
    return g


def topological_sort(g: nx.DiGraph) -> list[str]:
    """Kahn 算法拓扑排序。

    循环依赖时回退到字典序（应避免循环，但降级方案必须可用）。
    """
    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        log.error("包依赖图中存在环，降级为字典序", error=str(e))
        return sorted(g.nodes, key=lambda n: n)