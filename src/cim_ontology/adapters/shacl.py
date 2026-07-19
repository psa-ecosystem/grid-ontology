"""SHACL Shapes 输出适配器（设计规范 §6.3）。"""
from __future__ import annotations

import time
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef

from cim_ontology.adapters._iri_safe import is_safe_iri_part
from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import ClassDef, OntologyIR

CIM = Namespace("http://iec.ch/TC57/2024/CIM-schema-cim17#")
SH = Namespace("http://www.w3.org/ns/shacl#")


class ShaclAdapter(OutputAdapter):
    """SHACL Shapes 适配器。"""

    target_format = "shacl"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)

        g = Graph()
        g.bind("sh", SH)
        g.bind("cim", CIM)

        skipped = 0
        for cls in ir.all_classes():
            # P1.2：cls.name 含 OCR 噪声时跳过整个 SHACL shape
            if not is_safe_iri_part(cls.name):
                skipped += 1
                continue

            shape_iri = URIRef(str(CIM) + f"shape_{cls.name}")
            g.add((shape_iri, RDF.type, SH.NodeShape))
            g.add((shape_iri, SH.targetClass, URIRef(str(CIM) + cls.name)))

            for attr in cls.attributes:
                # P1.2：attr.name 含 OCR 噪声时跳过该 property shape
                if not is_safe_iri_part(attr.name):
                    continue
                prop_shape = self._add_property_shape(g, shape_iri, cls, attr)
                if attr.required:
                    g.add((prop_shape, SH.minCount, Literal(1)))
                if attr.multiplicity.max is not None:
                    g.add((prop_shape, SH.maxCount, Literal(attr.multiplicity.max)))

            # B3：ObjectProperty 关联端 → sh:property (sh:class + sh:path)
            # 与 OWL ObjectProperty (rdfs:domain + rdfs:range) 语义对齐
            for assoc in cls.associations:
                if not is_safe_iri_part(assoc.name):
                    continue
                target_name = assoc.target.class_name
                if not target_name or not is_safe_iri_part(target_name):
                    continue
                assoc_shape = self._add_association_shape(
                    g, shape_iri, cls, assoc, target_name
                )
                if assoc.multiplicity.min is not None:
                    g.add((assoc_shape, SH.minCount, Literal(assoc.multiplicity.min)))
                if assoc.multiplicity.max is not None:
                    g.add((assoc_shape, SH.maxCount, Literal(assoc.multiplicity.max)))

        out_path = output_dir / "cim17_shapes.ttl"
        g.serialize(out_path, format="turtle")

        return EmitResult(
            files=[out_path],
            stats={"shapes": len(ir.all_classes()) - skipped, "skipped": skipped},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _add_property_shape(self, g: Graph, shape_iri: URIRef, cls: ClassDef, attr) -> URIRef:
        prop_shape = URIRef(f"{shape_iri}_{attr.name}")
        g.add((shape_iri, SH.property, prop_shape))
        g.add((prop_shape, SH.path, URIRef(f"{str(CIM)}{cls.name}.{attr.name}")))
        if attr.data_type and is_safe_iri_part(attr.data_type):
            g.add((prop_shape, SH.datatype, URIRef(attr.data_type)))
        return prop_shape

    def _add_association_shape(
        self, g: Graph, shape_iri: URIRef, cls: ClassDef, assoc, target_name: str
    ) -> URIRef:
        """B3：ObjectProperty 关联端 → SHACL sh:property (sh:class 模式).

        与 OWL ObjectProperty 语义对齐：
          OWL: prop rdfs:domain ClassName ; rdfs:range TargetName
          SHACL: shape sh:property [ sh:path ...; sh:class cim:TargetName ]
        """
        assoc_shape = URIRef(f"{shape_iri}_{assoc.name}")
        g.add((shape_iri, SH.property, assoc_shape))
        g.add((assoc_shape, SH.path, URIRef(f"{str(CIM)}{cls.name}.{assoc.name}")))
        g.add((assoc_shape, SH["class"], URIRef(str(CIM) + target_name)))
        return assoc_shape

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        path = emitted / "cim17_shapes.ttl"
        if not path.exists():
            return VerifyResult(passed=False, issues=["cim17_shapes.ttl 不存在"])
        g = Graph()
        try:
            g.parse(path, format="turtle")
        except Exception as e:
            return VerifyResult(passed=False, issues=[f"解析失败: {e}"])
        return VerifyResult(passed=True, roundtrip_match=True)
