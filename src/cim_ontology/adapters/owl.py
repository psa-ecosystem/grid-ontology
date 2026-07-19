"""OWL/RDF Turtle 输出适配器（设计规范 §6.2）。

特点：
  - 按包拆分（避免单文件过大）
  - 跨包依赖通过 owl:imports 声明
  - 包生成顺序经拓扑排序
"""
from __future__ import annotations

import re
from pathlib import Path

import structlog
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef, XSD

from cim_ontology.adapters._iri_safe import contains_ocr_noise, is_valid_python_identifier
from cim_ontology.adapters._pkg_dedup import merge_fuzzy_duplicate_packages
from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.cleaner._infer_refs import infer_cross_package_refs
from cim_ontology.cleaner.dep_graph import build_package_dependency_graph
from cim_ontology.ir.models import ClassDef, OntologyIR, Package

log = structlog.get_logger()


CIM = Namespace("http://iec.ch/TC57/2024/CIM-schema-cim17#")


class OwlTurtleAdapter(OutputAdapter):
    """OWL/RDF Turtle 输出适配器。"""

    target_format = "owl"

    def _emit_order(self, packages: list[Package]) -> list[Package]:
        """Core 包优先 + 其余按 IR 原始顺序（稳定排序）。

        替代 topological_sort：B5 取消拓扑排序，依赖 OWL 原生 import 循环处理。
        Core 优先确保 foundation 包先 emit，便于下游 SPARQL 工具从 Core 起解析。
        """
        by_name = {p.name: p for p in packages}
        core = [by_name.pop("Core")] if "Core" in by_name else []
        return core + list(by_name.values())

    def _partition_empty(
        self, packages: list[Package]
    ) -> tuple[list[Package], list[str]]:
        """分类非空包 vs 空包，发出警告日志。

        空包定义：
          - 0 个 class
          - 所有 class.name 为空字符串或纯空白（B7 清空后残留）

        Returns:
            (non_empty, empty_names)
        """
        non_empty: list[Package] = []
        empty_names: list[str] = []
        for pkg in packages:
            # 至少一个非空类名（去空白后）才算非空包
            if any(cls.name and cls.name.strip() for cls in pkg.classes):
                non_empty.append(pkg)
            else:
                empty_names.append(pkg.name)
                log.warning(
                    "b5_empty_pkg_skipped",
                    pkg=pkg.name,
                    class_count=len(pkg.classes),
                )
        return non_empty, empty_names

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = _now_ms()

        # v1.2.1 P3-B 防线：合并同名 Package 避免 dict 静默覆盖导致 ClassDef 丢失
        packages = merge_fuzzy_duplicate_packages(ir.packages)
        # v1.5 P1：跨包去重（304 个 ClassDef 在 >1 包中重复出现）
        # B5: 取消 deduplicate_cross_package_classes 调用——
        #      原语义：把同名类合并到 Core（463/992 被吃，47% 丢包）
        #      新语义：按原包保留所有类（OWL 多 ontology 共存语义）

        # v1.5 P1：自动推断跨包引用（IR.cross_package_refs 默认空，需从 ClassDef 推断）
        # B5: 仅对非空包推断（空包不入依赖图）
        # Step 1: 计算 emit 顺序（Core 优先 + 其余 IR 顺序）
        ordered_all = self._emit_order(packages)
        # Step 2: 空包分类（非空 + 空名列表）
        non_empty, empty_names = self._partition_empty(ordered_all)

        # 跨包依赖收集（保留用于 owl:imports 声明，不再 topo 排序）
        cross_refs = infer_cross_package_refs(non_empty)
        dep_graph = build_package_dependency_graph(ir, cross_package_refs=cross_refs)

        full_g = Graph()
        full_g.bind("cim", CIM)
        full_g.bind("rdf", RDF)
        full_g.bind("rdfs", RDFS)
        full_g.bind("owl", OWL)
        full_g.bind("xsd", XSD)

        # Ontology 头
        onto_iri = URIRef(str(CIM).rstrip("#"))
        full_g.add((onto_iri, RDF.type, OWL.Ontology))
        full_g.add((onto_iri, OWL.versionInfo, Literal("cim17")))
        full_g.add((onto_iri, RDFS.comment, Literal(
            "GB/T 43259.301-2024 IDT IEC 61970-301:2020", lang="en"
        )))

        files_written: list[Path] = []

        # B5: for pkg in non_empty（而非 ordered_packages）
        for pkg in non_empty:
            pkg_g = self._build_package_graph(pkg)
            # 添加 owl:imports（B 应 import 它所依赖的包，即 predecessor）
            for dep in dep_graph.predecessors(pkg.name):
                try:
                    dep_iri = URIRef(f"{str(CIM).rstrip('#')}_{dep}")
                    pkg_iri = URIRef(f"{str(CIM).rstrip('#')}_{pkg.name}")
                except KeyError:
                    log.debug("b5_owl_import_skipped", pkg=pkg.name, dep=dep)
                    continue
                pkg_g.add((pkg_iri, OWL.imports, dep_iri))
                full_g.add((pkg_iri, OWL.imports, dep_iri))

            out_path = output_dir / f"cim17_{pkg.name}.ttl"
            pkg_g.serialize(out_path, format="turtle")
            files_written.append(out_path)

            # 累加到全量
            for triple in pkg_g:
                full_g.add(triple)

        full_path = output_dir / "cim17_full.ttl"
        full_g.serialize(full_path, format="turtle")
        files_written.append(full_path)

        log.info(
            "b5_emit_completed",
            packages_emitted=len(non_empty),
            packages_skipped=len(empty_names),
        )

        return EmitResult(
            files=files_written,
            stats={
                "packages": len(non_empty),
                "classes": len(ir.all_classes()),
                "skipped_packages": len(empty_names),
                "total_files": len(files_written),
            },
            duration_ms=_now_ms() - start,
        )

    def _build_package_graph(self, pkg: Package) -> Graph:
        """构造单个包的 RDF 图。

        P1.2 增强：每个 ClassDef 生成完整 RDFS/OWL 元数据（不只是 rdf:type）：
          - rdfs:label（必需）
          - rdfs:isDefinedBy（关联包）
          - rdfs:comment（可选，类描述）
          - rdfs:subClassOf（继承）
          - 每个 DataProperty：rdfs:label + rdfs:domain + rdfs:range
          - 每个 ObjectProperty：rdfs:label + rdfs:domain + rdfs:range
        """
        g = Graph()
        g.bind("cim", CIM)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # 包级 isDefinedBy IRI
        pkg_iri = URIRef(f"{str(CIM).rstrip('#')}_{pkg.name}")

        for cls in pkg.classes:
            cls_iri = URIRef(str(CIM) + cls.name)
            # 类型 + 标签 + 所属包 + 描述
            g.add((cls_iri, RDF.type, OWL.Class))
            g.add((cls_iri, RDFS.label, Literal(cls.name, lang="en")))
            g.add((cls_iri, RDFS.isDefinedBy, pkg_iri))
            if cls.description:
                g.add((cls_iri, RDFS.comment, Literal(cls.description, lang="zh")))
            if cls.stereotype:
                g.add((cls_iri, URIRef(str(RDFS) + "comment"),
                       Literal(f"stereotype: {cls.stereotype}", lang="en")))

            # 继承
            for parent in cls.parents:
                parent_name = parent.class_name
                if not parent_name:
                    continue
                parent_iri = URIRef(str(CIM) + parent_name)
                g.add((cls_iri, RDFS.subClassOf, parent_iri))

            # DataProperty 元数据
            for attr in cls.attributes:
                prop_iri = _safe_property_iri(cls.name, attr.name)
                if prop_iri is None:
                    continue  # OCR 噪声过深，跳过该属性
                g.add((prop_iri, RDF.type, OWL.DatatypeProperty))
                g.add((prop_iri, RDFS.label, Literal(attr.name[:64], lang="en")))
                g.add((prop_iri, RDFS.domain, cls_iri))
                # P1.2 鲁棒性：data_type 可能是 OCR 噪声（如 "0..1"），
                # 容错回退到 XSD.string 而非序列化失败
                range_iri = _safe_xsd_range(attr.data_type)
                g.add((prop_iri, RDFS.range, range_iri))
                if attr.required:
                    g.add((prop_iri, RDFS.comment, Literal("required (min >= 1)", lang="en")))

            # ObjectProperty 元数据（关联端）
            for assoc in cls.associations:
                prop_iri = _safe_property_iri(cls.name, assoc.name)
                if prop_iri is None:
                    continue  # OCR 噪声过深，跳过该关联端
                g.add((prop_iri, RDF.type, OWL.ObjectProperty))
                g.add((prop_iri, RDFS.label, Literal(assoc.name[:64], lang="en")))
                g.add((prop_iri, RDFS.domain, cls_iri))
                # P1.2 鲁棒性：target 也可能含 OCR 噪声
                target_name = assoc.target.class_name
                if target_name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", target_name):
                    target_iri = URIRef(str(CIM) + target_name)
                    g.add((prop_iri, RDFS.range, target_iri))

        return g

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        """验证生成的 OWL 可被重新解析。"""
        full = emitted / "cim17_full.ttl"
        if not full.exists():
            return VerifyResult(passed=False, issues=["cim17_full.ttl 不存在"])

        g = Graph()
        try:
            g.parse(full, format="turtle")
        except Exception as e:
            return VerifyResult(passed=False, issues=[f"解析失败: {e}"])

        return VerifyResult(
            passed=True,
            roundtrip_match=True,
        )


def _now_ms() -> int:
    import time
    return int(time.monotonic() * 1000)


def _safe_xsd_range(data_type: str | None) -> URIRef:
    """将 OCR 后的 data_type 安全转换为 XSD range URI。

    容错规则：
      - None → XSD.string
      - 以 http(s):// 开头 → 直接 URIRef
      - 含非法 URI 字符（如 "0..1" 中的 ".."） → XSD.string 回退
      - 否则（"string"/"float"/"int"/"boolean" 等）→ XSD.{type}
    """
    if not data_type:
        return XSD.string
    if data_type.startswith("http://") or data_type.startswith("https://"):
        try:
            return URIRef(data_type)
        except Exception:
            return XSD.string
    # XSD 内置类型白名单（其他视为 OCR 噪声）
    safe_types = {
        "string": XSD.string, "str": XSD.string,
        "float": XSD.float, "double": XSD.double,
        "int": XSD.integer, "integer": XSD.integer, "long": XSD.long,
        "boolean": XSD.boolean, "bool": XSD.boolean,
        "date": XSD.date, "datetime": XSD.dateTime,
        "decimal": XSD.decimal,
    }
    return safe_types.get(data_type.lower(), XSD.string)


def _safe_property_iri(cls_name: str, attr_name: str | None) -> URIRef | None:
    """将 OCR 后的属性名安全转换为 DatatypeProperty/ObjectProperty IRI。

    容错规则：
      - None / 空字符串 → None（跳过）
      - 含 OCR 噪声 → None（跳过）— 复用 _iri_safe.contains_ocr_noise
      - 非合法 Python 标识符字符 → None（跳过）— 复用 _iri_safe.is_valid_python_identifier
      - 长度 > 64 → 截断
      - 正常驼峰命名 → <cim>:<ClassName>.<attr_name>

    返回 None 表示该属性 OCR 噪声过深，应跳过 metadata 生成（不抛错）。
    """
    if not attr_name:
        return None
    name = attr_name.strip()
    if not name:
        return None
    if contains_ocr_noise(name):
        return None
    if not is_valid_python_identifier(name):
        return None
    if len(name) > 64:
        name = name[:64]
    return URIRef(f"{str(CIM)}{cls_name}.{name}")