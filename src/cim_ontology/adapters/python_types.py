"""Python Types 输出适配器（设计规范 §6.4 + §6.4.1）。

按拓扑序生成每个包的 _types.py 文件，自动注入跨包 import。
"""
from __future__ import annotations

import time
from pathlib import Path

import structlog

from cim_ontology.adapters._class_dedup import deduplicate_cross_package_classes
from cim_ontology.adapters._iri_safe import (
    contains_ocr_noise,
    is_table_separator,
    is_valid_python_identifier,
    normalize_xsd_type,
)
from cim_ontology.adapters._pkg_dedup import merge_fuzzy_duplicate_packages
from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.cleaner._infer_refs import infer_cross_package_refs
from cim_ontology.cleaner.dep_graph import build_package_dependency_graph, topological_sort
from cim_ontology.ir.models import OntologyIR, Package

log = structlog.get_logger()


def _validate_package_name(name: str) -> None:
    """strict 校验包名仅含合法 Python 标识符字符。

    注意：包名不检测 OCR 噪声（保持稳定，避免破坏跨包 import）。

    Raises:
        ValueError: 包名不合法。
    """
    if not is_valid_python_identifier(name):
        raise ValueError(
            f"非法包名: {name!r}（必须匹配 ^[A-Za-z_][A-Za-z0-9_]*$）"
        )


def _validate_class_name(name: str) -> None:
    """strict 校验类名：Python 标识符 + 无 OCR 噪声。

    Raises:
        ValueError: 类名不合法或含 OCR 噪声。
    """
    # 先检测 OCR 噪声：LaTeX 残骸（如 \\mathcal{Z}）虽然不是合法 Python
    # 标识符，但属于语义噪声，应当以 OCR 噪声错误形式报告（更具诊断价值）。
    if contains_ocr_noise(name):
        raise ValueError(
            f"类名含 OCR 噪声: {name!r}（如 LaTeX 残骸/多重性泄露/数学符号）"
        )
    if not is_valid_python_identifier(name):
        raise ValueError(
            f"非法类名: {name!r}（必须匹配 ^[A-Za-z_][A-Za-z0-9_]*$）"
        )


def _validate_attr_name(name: str) -> None:
    """strict 校验属性名：Python 标识符 + 无 OCR 噪声。

    Raises:
        ValueError: 属性名不合法或含 OCR 噪声。
    """
    # 先检测 OCR 噪声：LaTeX 残骸（如 \\mathcal{Z}）虽然不是合法 Python
    # 标识符，但属于语义噪声，应当以 OCR 噪声错误形式报告（更具诊断价值）。
    if contains_ocr_noise(name):
        raise ValueError(
            f"属性名含 OCR 噪声: {name!r}（如 LaTeX 残骸/多重性泄露/数学符号）"
        )
    if not is_valid_python_identifier(name):
        raise ValueError(
            f"非法属性名: {name!r}（必须匹配 ^[A-Za-z_][A-Za-z0-9_]*$）"
        )


class PythonTypesAdapter(OutputAdapter):
    """生成 Python dataclass 类型文件。"""

    target_format = "python-types"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        # I2: 在所有 IO 之前校验每个包名，防止路径遍历。
        for pkg in ir.packages:
            _validate_package_name(pkg.name)

        # v1.2.1 P3-B 防线：合并同名 Package 避免 dict 静默覆盖导致 ClassDef 丢失
        packages = merge_fuzzy_duplicate_packages(ir.packages)
        # v1.5 P1：跨包去重（304 个 ClassDef 在 >1 包中重复出现）
        packages = deduplicate_cross_package_classes(packages)

        # v1.5 P1：自动推断跨包引用（IR.cross_package_refs 默认空，需从 ClassDef 推断）
        cross_refs = infer_cross_package_refs(packages)

        dep_graph = build_package_dependency_graph(ir, cross_package_refs=cross_refs)
        ordered_names = topological_sort(dep_graph)
        packages_by_name = {p.name: p for p in packages}
        ordered = [packages_by_name[n] for n in ordered_names if n in packages_by_name]

        resolved_output = output_dir.resolve()
        for pkg in ordered:
            src = self._generate_package_source(pkg, ir, dep_graph)
            out = (output_dir / f"{pkg.name}_types.py").resolve()
            # I2: 防御路径遍历，确保输出文件仍在 output_dir 之内。
            if not out.is_relative_to(resolved_output):
                raise ValueError(
                    f"路径遍历尝试: pkg.name={pkg.name!r}，"
                    f"解析后={out}，output_dir={resolved_output}"
                )
            out.write_text(src)
            files.append(out)

        return EmitResult(
            files=files,
            stats={"packages": len(ordered)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _generate_package_source(
        self,
        pkg: Package,
        ir: OntologyIR,
        dep_graph,
    ) -> str:
        """生成单个包的 Python 源码。"""
        # _validate_package_name 已在 emit() 入口统一校验；此处冗余防御。
        _validate_package_name(pkg.name)
        lines: list[str] = [
            f"# Auto-generated from CIM {pkg.name} package",
            "from __future__ import annotations",
            "from dataclasses import dataclass",
            "from typing import ClassVar, Optional",
            "",
        ]

        # 注入跨包 import
        # dep_graph 边方向: 被依赖方 → 依赖方（to_package → from_package）
        # 所以本包依赖的"被依赖方"是 predecessors，不是 successors
        for dep in dep_graph.predecessors(pkg.name):
            dep_pkg = next((p for p in ir.packages if p.name == dep), None)
            if dep_pkg is None:
                continue
            # I3: dep_pkg.name 同源已通过 emit() 校验；这里仍然校验一次。
            _validate_package_name(dep_pkg.name)
            used_types = self._collect_used_types(pkg, dep_pkg)
            if used_types:
                lines.insert(5, f"from {dep_pkg.name}_types import {', '.join(sorted(used_types))}")

        # 生成类
        for cls in pkg.classes:
            lines.extend(self._generate_class(cls))
            lines.append("")

        return "\n".join(lines)

    def _collect_used_types(self, pkg: Package, dep_pkg: Package) -> set[str]:
        """收集本包对依赖包类型的引用。

        I5: parent/assoc.target.class_name OCR 噪声/空字符串 fail-soft 跳过。
        原因：cim-base-full.md Stage 1+2 解析时 42 个 association 含空 target.class_name
              （如 ConnectivityNodeContainer::Substation 的 target 残缺），这在 _infer_refs
              启用跨包引用推断后才暴露（之前 dedup 后的图无跨包边，本函数不执行）。
              若 raise 会让 emit 崩溃；跳过并记日志，由 Stage 1/2 在上游清洗。
        """
        used: set[str] = set()
        dep_class_names = {c.name for c in dep_pkg.classes}

        for cls in pkg.classes:
            # I1: 类名校验（已由 emit() 入口校验一次，这里复用）。
            _validate_class_name(cls.name)
            # 继承引用
            for parent in cls.parents:
                parent_name = parent.class_name
                if not parent_name:
                    continue
                try:
                    _validate_class_name(parent_name)
                except ValueError as e:
                    log.warning(
                        "python_types_ocr_parent_skipped",
                        cls=cls.name,
                        parent=parent_name,
                        reason=str(e),
                    )
                    continue
                if parent_name in dep_class_names:
                    used.add(parent_name)
            # 关联目标引用
            for assoc in cls.associations:
                target_name = assoc.target.class_name
                if not target_name:
                    continue
                try:
                    _validate_class_name(target_name)
                except ValueError as e:
                    log.warning(
                        "python_types_ocr_assoc_target_skipped",
                        cls=cls.name,
                        assoc=assoc.name,
                        target=target_name,
                        reason=str(e),
                    )
                    continue
                if target_name in dep_class_names:
                    used.add(target_name)
        return used

    def _generate_class(self, cls) -> list[str]:
        """生成单个类的 dataclass 定义。"""
        # I1: 类名严格校验（fail-fast）。
        _validate_class_name(cls.name)
        # I4: 属性名校验，OCR 噪声属性 fail-soft 跳过（仿 OWL _safe_property_iri）。
        # 原因：cim-base-full.md 含 LaTeX 残骸等字符级噪声（rule_attempt.value），
        #       这些属性若 raise 会让整个 emit 崩溃，违背"不污染产物"原则。
        #       跳过并记日志，由 Stage 1/2 在上游清洗。
        # B2: 跳过分隔符行泄露（"|---|---|" → name="---"）。
        valid_attrs: list = []
        for attr in cls.attributes:
            if is_table_separator(attr.name):
                continue
            try:
                _validate_attr_name(attr.name)
            except ValueError as e:
                log.warning(
                    "python_types_ocr_attr_skipped",
                    cls=cls.name,
                    attr=attr.name,
                    reason=str(e),
                )
                continue
            valid_attrs.append(attr)
        lines = ["@dataclass"]
        lines.append(f"class {cls.name}:")
        # C1: 用 ClassVar[str] 标注，让 rdf_type 成为类属性而非实例字段，
        # 避免有默认值的字段排在无默认值 required 字段之前导致 TypeError。
        lines.append(f'    rdf_type: ClassVar[str] = "cim:{cls.name}"')

        for attr in valid_attrs:
            # B2: 规范化 data_type（"String"/"Int"/"DateTime" → "xsd:string"/"xsd:integer"/"xsd:dateTime"）
            xsd_type = normalize_xsd_type(attr.data_type)
            type_hint = self._json_schema_type(xsd_type)
            if attr.required:
                lines.append(f"    {attr.name}: {type_hint}")
            else:
                lines.append(f"    {attr.name}: Optional[{type_hint}] = None")

        # B3：ObjectProperty 关联端 → 前向引用目标 dataclass
        # 用字符串注解避免循环 import（"from __future__ import annotations" 已启用）
        for assoc in cls.associations:
            if is_table_separator(assoc.name):
                continue
            try:
                _validate_attr_name(assoc.name)
            except ValueError as e:
                log.warning(
                    "python_types_ocr_assoc_skipped",
                    cls=cls.name,
                    assoc=assoc.name,
                    reason=str(e),
                )
                continue
            target = assoc.target.class_name
            if not target or not is_valid_python_identifier(target):
                continue  # 跳过 OCR 截断残留
            lines.append(f"    {assoc.name}: Optional['{target}'] = None")

        if not valid_attrs:
            lines.append("    pass")

        return lines

    def _json_schema_type(self, xsd_type: str) -> str:
        """映射 xsd:foo → Python 类型 hint（覆盖 SG-CIM LDM 132 种 data_type 变体）。"""
        mapping = {
            "xsd:string": "str",
            "xsd:integer": "int",
            "xsd:long": "int",
            "xsd:float": "float",
            "xsd:double": "float",
            "xsd:decimal": "float",
            "xsd:boolean": "bool",
            "xsd:date": "str",
            "xsd:time": "str",
            "xsd:dateTime": "str",
            "xsd:duration": "str",
            "xsd:anyURI": "str",
            "xsd:base64Binary": "str",
        }
        return mapping.get(xsd_type, "str")  # 自定义枚举 → str fallback

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        # I2 防御：verify 入口同样校验包名。
        for pkg in ir.packages:
            _validate_package_name(pkg.name)
            p = emitted / f"{pkg.name}_types.py"
            if not p.exists():
                issues.append(f"{p.name} 不存在")
        return VerifyResult(passed=len(issues) == 0, issues=issues)
