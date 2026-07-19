"""JSON-LD Context 输出适配器（设计规范 §6.4）。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from cim_ontology.adapters._class_dedup import deduplicate_cross_package_classes
from cim_ontology.adapters._iri_safe import contains_ocr_noise, normalize_xsd_type
from cim_ontology.adapters._pkg_dedup import merge_fuzzy_duplicate_packages
from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import OntologyIR

CIM_IRI = "http://iec.ch/TC57/2024/CIM-schema-cim17#"


class JsonLdContextAdapter(OutputAdapter):
    """JSON-LD Context 适配器（语义层）。"""

    target_format = "jsonld-context"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        # v1.2.1 P3-B 防线：合并同名 Package 避免同名输出文件互相覆盖
        # v1.5 P1：跨包去重（304 个 ClassDef 在 >1 包中重复出现）
        packages = merge_fuzzy_duplicate_packages(ir.packages)
        packages = deduplicate_cross_package_classes(packages)
        for pkg in packages:
            ctx: dict = {
                "@context": {
                    "@vocab": CIM_IRI,
                    "cim": CIM_IRI,
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#",
                }
            }
            # 为每个属性添加 @context 映射
            # B4：添加 @type xsd 注解（复用 normalize_xsd_type）
            # 跳过 B7 清空的噪声属性（attr.name == ""）
            # 防御性二次检查：未走 B7 clean 路径的噪声（LaTeX/纯 CJK）也跳过，
            # 避免 B7 行为变化时 B4 产出脏映射（与 _classify_attr_noise 语义一致，
            # 但不复用 cleaner 模块以避免 B7→B4 反向依赖）。
            for cls in pkg.classes:
                for attr in cls.attributes:
                    if not attr.name or attr.name.strip() == "":
                        continue  # B7 清空的噪声属性
                    if contains_ocr_noise(attr.name):
                        continue  # 防御性：LaTeX/多重性泄露
                    if not any(ord(c) < 128 for c in attr.name):
                        continue  # 防御性：纯 CJK 字符
                    xsd_type = normalize_xsd_type(attr.data_type) or "xsd:string"
                    ctx["@context"][attr.name] = {
                        "@id": f"cim:{cls.name}.{attr.name}",
                        "@type": xsd_type,
                    }
                # B3：ObjectProperty 关联端 → JSON-LD @id 映射（语义化链接）
                # 关联指向另一资源（target.class_name），需用 @id 标记
                for assoc in cls.associations:
                    target = assoc.target.class_name
                    if not target or not target[0].isupper():
                        continue  # 跳过 OCR 截断残留
                    ctx["@context"][assoc.name] = {
                        "@id": f"cim:{cls.name}.{assoc.name}",
                        "@type": "@id",
                    }
            # 为每个类添加 @id 映射（v1.8.0 F2b）：保证无属性/关联的抽象类
            # （如 Base、Class1）也能在 Stage 4 probe 中被识别。
            # 顺序：必须**最后** emit，使类映射在键冲突时**无条件覆盖**同名的属性/关联映射
            # （如 ACLineSegment.Clamp 关联会占位 Clamp 键 → 类映射覆盖后变 cim:Clamp）。
            # 副作用：与类名同名的关联会丢失其 @id 信息，但该类的其他属性/关联映射
            # 仍存在，probe 仍可通过 ``cim:OtherClass.*`` 前缀找到 OtherClass。
            for cls in pkg.classes:
                if not cls.name:
                    continue
                if contains_ocr_noise(cls.name):
                    continue
                ctx["@context"][cls.name] = {
                    "@id": f"cim:{cls.name}",
                    "@type": "@id",
                }

            out_path = output_dir / f"{pkg.name}_context.jsonld"
            out_path.write_text(json.dumps(ctx, indent=2, ensure_ascii=False))
            files.append(out_path)

        return EmitResult(
            files=files,
            stats={"contexts": len(files)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        for pkg in ir.packages:
            path = emitted / f"{pkg.name}_context.jsonld"
            if not path.exists():
                issues.append(f"{pkg.name}_context.jsonld 不存在")
                continue
            try:
                data = json.loads(path.read_text())
                if "@context" not in data:
                    issues.append(f"{pkg.name} 缺少 @context")
            except Exception as e:
                issues.append(f"{pkg.name} JSON 解析失败: {e}")
        return VerifyResult(
            passed=len(issues) == 0,
            issues=issues,
            roundtrip_match=len(issues) == 0,
        )
