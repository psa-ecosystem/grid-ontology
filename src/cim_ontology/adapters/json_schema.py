"""JSON Schema 输出适配器（结构验证层）。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from cim_ontology.adapters._class_dedup import deduplicate_cross_package_classes
from cim_ontology.adapters._iri_safe import is_table_separator, normalize_xsd_type, safe_attr_slug
from cim_ontology.adapters._pkg_dedup import merge_fuzzy_duplicate_packages
from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import OntologyIR

# XSD → JSON Schema 类型映射（覆盖 SG-CIM LDM 132 种 data_type 变体）
XSD_TO_JSON_SCHEMA = {
    "xsd:string": {"type": "string"},
    "xsd:integer": {"type": "integer"},
    "xsd:long": {"type": "integer"},
    "xsd:float": {"type": "number"},
    "xsd:double": {"type": "number"},
    "xsd:decimal": {"type": "number"},
    "xsd:boolean": {"type": "boolean"},
    "xsd:date": {"type": "string", "format": "date"},
    "xsd:time": {"type": "string", "format": "time"},
    "xsd:dateTime": {"type": "string", "format": "date-time"},
    "xsd:duration": {"type": "string", "format": "duration"},
    "xsd:anyURI": {"type": "string", "format": "uri"},
    "xsd:base64Binary": {"type": "string", "contentEncoding": "base64"},
}


class JsonSchemaAdapter(OutputAdapter):
    """JSON Schema 适配器（按包生成）。"""

    target_format = "json-schema"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        # v1.2.1 P3-B 防线：合并同名 Package 避免同名输出文件互相覆盖
        # v1.5 P1：跨包去重（304 个 ClassDef 在 >1 包中重复出现）
        packages = merge_fuzzy_duplicate_packages(ir.packages)
        packages = deduplicate_cross_package_classes(packages)
        for pkg in packages:
            schema = self._build_schema(pkg)
            out = output_dir / f"{pkg.name}_schema.json"
            out.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
            files.append(out)

        return EmitResult(
            files=files,
            stats={"schemas": len(files)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _build_schema(self, pkg) -> dict:
        schema: dict = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"CIM {pkg.name}",
            "type": "object",
            "properties": {},
        }
        for cls in pkg.classes:
            cls_schema = self._build_class_schema(cls)
            schema["properties"][cls.name] = cls_schema
        return schema

    def _build_class_schema(self, cls) -> dict:
        properties: dict = {}
        required: list[str] = []
        for attr in cls.attributes:
            # 跳过分隔符行泄露（"|---|---|" → name="---"）
            if is_table_separator(attr.name):
                continue
            slug = safe_attr_slug(attr.name)
            # 规范化 data_type（"String"/"Int"/"DateTime"/"xsd:string" → 统一 xsd:foo）
            xsd_type = normalize_xsd_type(attr.data_type)
            properties[slug] = XSD_TO_JSON_SCHEMA.get(
                xsd_type, {"type": "string"}  # 自定义枚举 → string fallback
            )
            if attr.description and isinstance(properties[slug], dict):
                properties[slug]["description"] = attr.description
            if attr.required:
                required.append(slug)
        # B3：ObjectProperty 关联端 → $ref 引用目标类 schema
        for assoc in cls.associations:
            if is_table_separator(assoc.name):
                continue
            slug = safe_attr_slug(assoc.name)
            target_name = assoc.target.class_name
            if not target_name or not target_name[0].isupper():
                continue  # 跳过 OCR 截断残留（不以大写字母开头的 target）
            properties[slug] = {"$ref": f"#/properties/{target_name}"}
        result = {"type": "object", "properties": properties}
        if required:
            result["required"] = required
        return result

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        for pkg in ir.packages:
            p = emitted / f"{pkg.name}_schema.json"
            if not p.exists():
                issues.append(f"{p.name} 不存在")
        return VerifyResult(passed=len(issues) == 0, issues=issues)
