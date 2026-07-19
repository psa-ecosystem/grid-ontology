"""B5 Stage 3: 多包 OWL 质量硬化单元测试。

覆盖：
  - 单元：_emit_order（Core 优先 / 无 Core / 单包稳定）
  - 单元：_partition_empty（纯空 / 全 B7 清空 / 混合 / name 全空白）
  - 端到端：emit（dedup 关闭 / 空包不写 / Core 第一 / 无 cycle 错误 / roundtrip）
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rdflib import Graph, OWL, RDF

from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.ir.models import (
    ClassDef,
    OntologyIR,
    Package,
    SourceInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pkg(name: str, cls_names: list[str]) -> Package:
    """构造一个 Package，含若干 ClassDef（按 cls_names 列表）。"""
    return Package(
        iri=f"http://test/{name}",
        name=name,
        classes=[ClassDef(name=n) for n in cls_names],
    )


def _make_ir(packages: list[Package]) -> OntologyIR:
    """构造最小可用的 IR fixture。"""
    return OntologyIR(
        packages=packages,
        uncertain_entries=[],
        cross_package_refs=[],
        source=SourceInfo(
            document_path="/test",
            document_sha256="x",
            parsed_at=datetime.now(timezone.utc),
            parser_version="0.2.0",
        ),
    )


# ---------------------------------------------------------------------------
# 单元：_emit_order（3 用例）
# ---------------------------------------------------------------------------


class TestEmitOrder:
    """_emit_order 应实现 Core 优先 + 其余 IR 原始顺序。"""

    def test_core_emitted_first(self):
        """Core 包无论位置都在第一位。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Zeta", ["Z"]),
            _make_pkg("Core", ["C"]),
            _make_pkg("Alpha", ["A"]),
        ]
        ordered = adapter._emit_order(packages)
        assert [p.name for p in ordered] == ["Core", "Zeta", "Alpha"]

    def test_no_core_preserves_ir_order(self):
        """无 Core 时按 IR 原始顺序。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Alpha", ["A"]),
            _make_pkg("Zeta", ["Z"]),
            _make_pkg("Beta", ["B"]),
        ]
        ordered = adapter._emit_order(packages)
        assert [p.name for p in ordered] == ["Alpha", "Zeta", "Beta"]

    def test_single_package_stable(self):
        """单包场景稳定返回（Core 或其他）。"""
        adapter = OwlTurtleAdapter()
        # 单 Core
        ordered = adapter._emit_order([_make_pkg("Core", ["C"])])
        assert [p.name for p in ordered] == ["Core"]
        # 单非 Core
        ordered = adapter._emit_order([_make_pkg("Only", ["O"])])
        assert [p.name for p in ordered] == ["Only"]


# ---------------------------------------------------------------------------
# 单元：_partition_empty（4 用例）
# ---------------------------------------------------------------------------


class TestPartitionEmpty:
    """_partition_empty 应正确分类非空包 vs 空包（含 B7 清空场景）。"""

    def test_pure_empty_package(self):
        """空包（classes=[]）归入空包列表。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["C"]),
            _make_pkg("Empty1", []),
        ]
        non_empty, empty_names = adapter._partition_empty(packages)
        assert [p.name for p in non_empty] == ["Core"]
        assert empty_names == ["Empty1"]

    def test_all_classes_cleared_by_b7(self):
        """所有 cls.name == ''（B7 清空后）→ 包归为空。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["C"]),
            _make_pkg("Cleared", ["", "", ""]),  # B7 清空场景
        ]
        non_empty, empty_names = adapter._partition_empty(packages)
        assert [p.name for p in non_empty] == ["Core"]
        assert empty_names == ["Cleared"]

    def test_mixed_packages(self):
        """混合：部分空、部分非空、部分 B7 清空。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["C"]),
            _make_pkg("Empty1", []),
            _make_pkg("RealPkg", ["R1", "R2"]),
            _make_pkg("Cleared", ["", "R1"]),  # 至少 1 个非空名 → 非空
            _make_pkg("AllCleared", ["", ""]),
        ]
        non_empty, empty_names = adapter._partition_empty(packages)
        assert {p.name for p in non_empty} == {"Core", "RealPkg", "Cleared"}
        assert set(empty_names) == {"Empty1", "AllCleared"}

    def test_whitespace_only_names_treated_as_empty(self):
        """所有 cls.name 为空白字符串 → 归为空包。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["C"]),
            _make_pkg("Whitespace", ["   ", "\t"]),
        ]
        non_empty, empty_names = adapter._partition_empty(packages)
        assert [p.name for p in non_empty] == ["Core"]
        assert empty_names == ["Whitespace"]


# ---------------------------------------------------------------------------
# 端到端：emit（5 用例）
# ---------------------------------------------------------------------------


class TestEmitEndToEnd:
    """B5 后 emit() 的契约：dedup 关闭、空包跳过、Core 优先、无 cycle 错误、roundtrip。"""

    def test_dedup_disabled_preserves_classes(self, tmp_path):
        """B5 后取消 dedup：同名类在不同包重复出现时仍各自 emit。"""
        adapter = OwlTurtleAdapter()
        # 两个包都含同名类 "IdentifiedObject"（模拟源 MD 重复）
        packages = [
            _make_pkg("Core", ["IdentifiedObject"]),
            _make_pkg("Wires", ["IdentifiedObject", "Conductor"]),
        ]
        ir = _make_ir(packages)
        result = adapter.emit(ir, tmp_path)

        # cim17_Core.ttl 应含 1 个 IdentifiedObject 定义
        core_g = Graph()
        core_g.parse(tmp_path / "cim17_Core.ttl", format="turtle")
        core_classes = set(core_g.subjects(RDF.type, OWL.Class))
        assert any("IdentifiedObject" in str(c) for c in core_classes)

        # cim17_Wires.ttl 也应含 1 个 IdentifiedObject 定义（不被 dedup 抽空）
        wires_g = Graph()
        wires_g.parse(tmp_path / "cim17_Wires.ttl", format="turtle")
        wires_classes = set(wires_g.subjects(RDF.type, OWL.Class))
        assert any("IdentifiedObject" in str(c) for c in wires_classes)
        assert any("Conductor" in str(c) for c in wires_classes)

        # cim17_full.ttl 应聚合所有（非空包）类
        # 注：RDF 按 subject IRI 去重；同名类仅出现 1 个 subject
        # 关键 B5 校验：IdentifiedObject + Conductor 都应在 full 中
        full_g = Graph()
        full_g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        full_classes = set(full_g.subjects(RDF.type, OWL.Class))
        assert any("IdentifiedObject" in str(c) for c in full_classes)
        assert any("Conductor" in str(c) for c in full_classes)

    def test_empty_packages_not_emitted(self, tmp_path):
        """空包（0 类 / B7 清空）不写 .ttl。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["Foo"]),
            _make_pkg("Empty1", []),
            _make_pkg("Empty2", ["", ""]),  # 全 B7 清空
        ]
        ir = _make_ir(packages)
        result = adapter.emit(ir, tmp_path)

        names = {f.name for f in result.files}
        assert "cim17_Core.ttl" in names
        assert "cim17_full.ttl" in names
        assert "cim17_Empty1.ttl" not in names
        assert "cim17_Empty2.ttl" not in names

    def test_core_emitted_first(self, tmp_path):
        """Core 永远在 emit 顺序的第一位。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Zeta", ["Z"]),
            _make_pkg("Core", ["C"]),
            _make_pkg("Alpha", ["A"]),
        ]
        ir = _make_ir(packages)
        result = adapter.emit(ir, tmp_path)

        # 过滤掉 full
        owl_files = [
            f for f in result.files
            if f.name.startswith("cim17_") and f.name != "cim17_full.ttl"
        ]
        assert owl_files[0].name == "cim17_Core.ttl"

    def test_no_cycle_error_in_logs(self, tmp_path, caplog):
        """B5 后 emit 不再触发 'Graph contains a cycle' 错误日志。"""
        adapter = OwlTurtleAdapter()
        # 构造循环：Core <-> Wires 互相引用
        packages = [
            Package(
                iri="http://x#Core", name="Core",
                classes=[ClassDef(
                    name="IdentifiedObject",
                    associations=[],
                )],
            ),
            Package(
                iri="http://x#Wires", name="Wires",
                classes=[ClassDef(
                    name="Conductor",
                    associations=[],
                )],
            ),
        ]
        ir = _make_ir(packages)
        # 添加循环 cross_package_refs
        from cim_ontology.ir.models import CrossPackageRef
        ir = ir.model_copy(update={
            "cross_package_refs": [
                CrossPackageRef(from_package="Core", to_package="Wires",
                                via_class="IdentifiedObject", via_property="x"),
                CrossPackageRef(from_package="Wires", to_package="Core",
                                via_class="Conductor", via_property="y"),
            ],
        })
        with caplog.at_level(logging.ERROR):
            adapter.emit(ir, tmp_path)
        assert "Graph contains a cycle" not in caplog.text

    def test_full_ttl_roundtrips_through_rdflib(self, tmp_path):
        """cim17_full.ttl 可被 rdflib 重新解析（标准 I/O 契约）。"""
        adapter = OwlTurtleAdapter()
        packages = [
            _make_pkg("Core", ["Foo", "Bar"]),
            _make_pkg("Wires", ["Conductor"]),
        ]
        ir = _make_ir(packages)
        adapter.emit(ir, tmp_path)

        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        # 至少存在 owl:Class
        classes = set(g.subjects(RDF.type, OWL.Class))
        assert len(classes) >= 3
