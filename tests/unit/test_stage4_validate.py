"""Stage 4: 跨适配器一致性验证单元测试。

覆盖：
  - dataclass 契约（Sample / ProbeResult / Inconsistency / ConsistencyMatrix）
  - 分层抽样（_stratified_sample）
  - 5 个 probe 函数（_probe_owl / _probe_shacl / _probe_json_schema / _probe_jsonld / _probe_python_types）
  - Markdown 渲染（_render_markdown）
  - 端到端（main 函数）
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# dataclass 契约（4 用例）
# ---------------------------------------------------------------------------


class TestDataclasses:
    """Stage 4 dataclass 契约。"""

    def test_sample_is_frozen_and_has_iri(self):
        from scripts.stage4_validate import Sample
        s = Sample(pkg_name="Core", class_name="Foo", class_iri="http://x#Foo")
        assert s.pkg_name == "Core"
        assert s.class_name == "Foo"
        assert s.class_iri == "http://x#Foo"
        # frozen: 应不允许修改
        with pytest.raises(Exception):
            s.class_name = "Bar"  # type: ignore

    def test_probe_result_found_and_error(self):
        from scripts.stage4_validate import ProbeResult
        # found=True, no error
        r1 = ProbeResult(found=True, error=None)
        assert r1.found is True
        assert r1.error is None
        # found=False, with error
        r2 = ProbeResult(found=False, error="FILE_MISSING")
        assert r2.found is False
        assert r2.error == "FILE_MISSING"

    def test_inconsistency_holds_sample_and_missing(self):
        from scripts.stage4_validate import Inconsistency, Sample
        s = Sample("Core", "Foo", "http://x#Foo")
        inc = Inconsistency(sample=s, missing_adapters=["JSON Schema", "Python Types"])
        assert inc.sample == s
        assert inc.missing_adapters == ["JSON Schema", "Python Types"]

    def test_consistency_matrix_aggregates(self):
        from scripts.stage4_validate import (
            ConsistencyMatrix, Inconsistency, ProbeResult, Sample,
        )
        s = Sample("Core", "Foo", "http://x#Foo")
        matrix = ConsistencyMatrix(
            samples=[s],
            results={"http://x#Foo": {
                "OWL": ProbeResult(found=True),
                "SHACL": ProbeResult(found=True),
                "JSON Schema": ProbeResult(found=False, error="FILE_MISSING"),
                "JSON-LD": ProbeResult(found=True),
                "Python Types": ProbeResult(found=True),
            }},
            inconsistencies=[Inconsistency(sample=s, missing_adapters=["JSON Schema"])],
            samples_per_pkg={"Core": 1},
            adapters=["OWL", "SHACL", "JSON Schema", "JSON-LD", "Python Types"],
            seed=42,
            generated_at="2026-07-09T00:00:00Z",
        )
        assert len(matrix.samples) == 1
        assert len(matrix.inconsistencies) == 1
        assert matrix.samples_per_pkg == {"Core": 1}
        assert matrix.seed == 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pkg(name: str, cls_names: list[str]):
    from cim_ontology.ir.models import ClassDef, Package
    return Package(
        iri=f"http://test/{name}",
        name=name,
        classes=[ClassDef(name=n) for n in cls_names],
    )


def _make_ir(packages):
    from cim_ontology.ir.models import OntologyIR, SourceInfo
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
# 分层抽样（3 用例）
# ---------------------------------------------------------------------------


class TestSampling:
    """_stratified_sample 应实现：分层 + 每包 ≤ samples_per_pkg + seed 稳定 + 不足取全部。"""

    def test_stratified_sample_per_pkg_count(self):
        from scripts.stage4_validate import _stratified_sample
        ir = _make_ir([
            _make_pkg("Core", [f"C{i}" for i in range(50)]),
            _make_pkg("Wires", [f"W{i}" for i in range(30)]),
        ])
        samples = _stratified_sample(ir, samples_per_pkg=25, seed=42)
        # 验证：Core 抽 25，Wires 抽 25（30 ≥ 25）
        core_samples = [s for s in samples if s.pkg_name == "Core"]
        wires_samples = [s for s in samples if s.pkg_name == "Wires"]
        assert len(core_samples) == 25
        assert len(wires_samples) == 25
        assert len(samples) == 50

    def test_stratified_sample_seed_deterministic(self):
        from scripts.stage4_validate import _stratified_sample
        ir = _make_ir([_make_pkg("Core", [f"C{i}" for i in range(50)])])
        s1 = _stratified_sample(ir, samples_per_pkg=10, seed=42)
        s2 = _stratified_sample(ir, samples_per_pkg=10, seed=42)
        # 同 seed → 同结果
        assert [s.class_name for s in s1] == [s.class_name for s in s2]
        # 不同 seed → 不同结果（至少一个 class_name 不同）
        s3 = _stratified_sample(ir, samples_per_pkg=10, seed=99)
        assert [s.class_name for s in s1] != [s.class_name for s in s3]

    def test_stratified_sample_insufficient_takes_all(self):
        from scripts.stage4_validate import _stratified_sample
        # Core 仅 5 类，请求抽 25 → 取全部 5
        ir = _make_ir([_make_pkg("Core", ["A", "B", "C", "D", "E"])])
        samples = _stratified_sample(ir, samples_per_pkg=25, seed=42)
        assert len(samples) == 5
        assert {s.class_name for s in samples} == {"A", "B", "C", "D", "E"}


# ---------------------------------------------------------------------------
# 5 个 Probe 函数（10 用例）
# ---------------------------------------------------------------------------


class TestProbeOwl:
    """_probe_owl: rdflib 解析 cim17_full.ttl，检查 owl:Class subject 集合。"""

    def test_probe_owl_finds_class(self, tmp_path):
        from rdflib import Graph, URIRef, OWL, RDF
        from scripts.stage4_validate import _probe_owl, CIM, Sample
        (tmp_path / "owl").mkdir()
        g = Graph()
        g.add((URIRef(str(CIM) + "Foo"), RDF.type, OWL.Class))
        g.serialize(tmp_path / "owl" / "cim17_full.ttl", format="turtle")
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_owl(sample, tmp_path)
        assert result.found is True
        assert result.error is None

    def test_probe_owl_marks_missing(self, tmp_path):
        from rdflib import Graph, URIRef, OWL, RDF
        from scripts.stage4_validate import _probe_owl, CIM, Sample
        (tmp_path / "owl").mkdir()
        g = Graph()
        g.add((URIRef(str(CIM) + "Bar"), RDF.type, OWL.Class))
        g.serialize(tmp_path / "owl" / "cim17_full.ttl", format="turtle")
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_owl(sample, tmp_path)
        assert result.found is False
        assert result.error is None


class TestProbeShacl:
    """_probe_shacl: rdflib 解析 cim17_shapes.ttl，检查 sh:targetClass 集合。"""

    def test_probe_shacl_finds_class(self, tmp_path):
        from rdflib import Graph, URIRef
        from scripts.stage4_validate import _probe_shacl, CIM, SHACL, Sample
        (tmp_path / "shacl").mkdir()
        g = Graph()
        g.add((URIRef("http://x/shape1"), SHACL.targetClass, URIRef(str(CIM) + "Foo")))
        g.serialize(tmp_path / "shacl" / "cim17_shapes.ttl", format="turtle")
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_shacl(sample, tmp_path)
        assert result.found is True
        assert result.error is None

    def test_probe_shacl_marks_missing(self, tmp_path):
        from rdflib import Graph, URIRef
        from scripts.stage4_validate import _probe_shacl, CIM, SHACL, Sample
        (tmp_path / "shacl").mkdir()
        g = Graph()
        g.add((URIRef("http://x/shape1"), SHACL.targetClass, URIRef(str(CIM) + "Bar")))
        g.serialize(tmp_path / "shacl" / "cim17_shapes.ttl", format="turtle")
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_shacl(sample, tmp_path)
        assert result.found is False
        assert result.error is None


class TestProbeJsonSchema:
    """_probe_json_schema: 扫描 *.json，检查 properties/<class_iri> 或 definitions/<class_iri>。"""

    def test_probe_json_schema_finds_class(self, tmp_path):
        from scripts.stage4_validate import _probe_json_schema, CIM, Sample
        (tmp_path / "json-schema").mkdir()
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": {
                "Foo": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        }
        (tmp_path / "json-schema" / "Core_schema.json").write_text(json.dumps(schema))
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_json_schema(sample, tmp_path)
        assert result.found is True
        assert result.error is None

    def test_probe_json_schema_marks_missing(self, tmp_path):
        from scripts.stage4_validate import _probe_json_schema, CIM, Sample
        (tmp_path / "json-schema").mkdir()
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": {
                "Bar": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        }
        (tmp_path / "json-schema" / "Core_schema.json").write_text(json.dumps(schema))
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_json_schema(sample, tmp_path)
        assert result.found is False


class TestProbeJsonLd:
    """_probe_jsonld: 扫描 *_context.jsonld，检查 @id 含 class_name。"""

    def test_probe_jsonld_finds_class(self, tmp_path):
        from scripts.stage4_validate import _probe_jsonld, CIM, Sample
        (tmp_path / "jsonld-context").mkdir()
        ctx = {
            "@context": {
                "Foo": {"@id": "cim:Core.Foo", "@type": "xsd:string"},
            }
        }
        (tmp_path / "jsonld-context" / "Core_context.jsonld").write_text(json.dumps(ctx))
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_jsonld(sample, tmp_path)
        assert result.found is True
        assert result.error is None

    def test_probe_jsonld_marks_missing(self, tmp_path):
        from scripts.stage4_validate import _probe_jsonld, CIM, Sample
        (tmp_path / "jsonld-context").mkdir()
        ctx = {
            "@context": {
                "Bar": {"@id": "cim:Core.Bar", "@type": "xsd:string"},
            }
        }
        (tmp_path / "jsonld-context" / "Core_context.jsonld").write_text(json.dumps(ctx))
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_jsonld(sample, tmp_path)
        assert result.found is False


class TestProbePythonTypes:
    """_probe_python_types: 解析 *.py AST，检查 ClassDef 节点名匹配。"""

    def test_probe_python_types_finds_class(self, tmp_path):
        from scripts.stage4_validate import _probe_python_types, CIM, Sample
        (tmp_path / "python-types").mkdir()
        code = '''\
class Foo:
    """Foo class."""

    name: str = ""
'''
        (tmp_path / "python-types" / "Core_types.py").write_text(code)
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_python_types(sample, tmp_path)
        assert result.found is True
        assert result.error is None

    def test_probe_python_types_marks_missing(self, tmp_path):
        from scripts.stage4_validate import _probe_python_types, CIM, Sample
        (tmp_path / "python-types").mkdir()
        code = '''\
class Bar:
    """Bar class."""

    name: str = ""
'''
        (tmp_path / "python-types" / "Core_types.py").write_text(code)
        sample = Sample("Core", "Foo", str(CIM) + "Foo")
        result = _probe_python_types(sample, tmp_path)
        assert result.found is False


# ---------------------------------------------------------------------------
# Markdown 渲染（2 用例）
# ---------------------------------------------------------------------------


class TestReportRendering:
    """_render_markdown 应输出 4 节结构 Markdown 报告。"""

    def test_render_markdown_contains_sections(self):
        from scripts.stage4_validate import (
            ADAPTERS, ConsistencyMatrix, _render_markdown,
        )
        matrix = ConsistencyMatrix(
            samples=[],
            results={},
            inconsistencies=[],
            samples_per_pkg={},
            adapters=ADAPTERS,
            seed=42,
            generated_at="2026-07-09T00:00:00Z",
        )
        md = _render_markdown(matrix)
        # 验证 4 节标题都存在
        assert "# Stage 4: 跨适配器一致性验证报告" in md
        assert "## 1. 抽样策略" in md
        assert "## 2. 一致性矩阵" in md
        assert "## 3. 不一致点" in md
        assert "## 4. 结论" in md

    def test_render_markdown_lists_inconsistencies(self):
        from scripts.stage4_validate import (
            ADAPTERS, ConsistencyMatrix, Inconsistency, _render_markdown, Sample,
        )
        s = Sample("Core", "Foo", "http://x#Foo")
        inc = Inconsistency(sample=s, missing_adapters=["JSON Schema"])
        matrix = ConsistencyMatrix(
            samples=[s],
            results={},
            inconsistencies=[inc],
            samples_per_pkg={"Core": 1},
            adapters=ADAPTERS,
            seed=42,
            generated_at="2026-07-09T00:00:00Z",
        )
        md = _render_markdown(matrix)
        # 验证不一致点表含 Foo + JSON Schema
        assert "Foo" in md
        assert "JSON Schema" in md
        assert "Core" in md


# ---------------------------------------------------------------------------
# 端到端（1 用例）
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """端到端：构造 IR + 模拟 5 adapter 产物 → 报告生成。"""

    def test_end_to_end_produces_report(self, tmp_path):
        """完整 main 流程：IR + build_dir → 报告生成（sys.argv 简化方案）。"""
        # 构造 IR
        ir = _make_ir([_make_pkg("Core", ["Foo", "Bar"])])
        ir_path = tmp_path / "ir_after.json"
        ir_path.write_text(ir.model_dump_json())

        # 构造 build_dir（5 个 adapter 子目录，每个含 Foo 不含 Bar）
        build_dir = tmp_path / "build"
        # OWL
        (build_dir / "owl").mkdir(parents=True)
        from rdflib import Graph, URIRef, OWL as OWL_NS, RDF
        from scripts.stage4_validate import CIM, SHACL

        g = Graph()
        g.add((URIRef(str(CIM) + "Foo"), RDF.type, OWL_NS.Class))
        g.serialize(build_dir / "owl" / "cim17_full.ttl", format="turtle")
        # SHACL
        (build_dir / "shacl").mkdir()
        g2 = Graph()
        g2.add((URIRef("http://x/shape1"), SHACL.targetClass, URIRef(str(CIM) + "Foo")))
        g2.serialize(build_dir / "shacl" / "cim17_shapes.ttl", format="turtle")
        # JSON Schema
        (build_dir / "json-schema").mkdir()
        schema = {"definitions": {"Foo": {"type": "object"}}}
        (build_dir / "json-schema" / "Core_schema.json").write_text(json.dumps(schema))
        # JSON-LD
        (build_dir / "jsonld-context").mkdir()
        ctx = {"@context": {"Foo": {"@id": "cim:Core.Foo"}}}
        (build_dir / "jsonld-context" / "Core_context.jsonld").write_text(json.dumps(ctx))
        # Python Types
        (build_dir / "python-types").mkdir()
        (build_dir / "python-types" / "Core_types.py").write_text("class Foo:\n    pass\n")

        # 通过 sys.argv 调用 _cli
        out_path = tmp_path / "report.md"
        import sys
        from scripts.stage4_validate import _cli

        old_argv = sys.argv
        try:
            sys.argv = [
                "stage4_validate",
                "--ir", str(ir_path),
                "--build", str(build_dir),
                "--out", str(out_path),
            ]
            _cli()
        finally:
            sys.argv = old_argv

        # 验证
        assert out_path.exists()
        content = out_path.read_text()
        assert "Foo" in content
        assert "Bar" in content


# ---------------------------------------------------------------------------
# Stage 5: 语义一致性 dataclass 契约（3 用例）
# ---------------------------------------------------------------------------


class TestClassSemantics:
    """Stage 5 dataclass 契约。"""

    def test_attr_and_assoc_semantics_frozen(self):
        from scripts.stage4_validate import AssocSemantics, AttrSemantics
        a = AttrSemantics(name="length", data_type="xsd:float", multiplicity="1")
        assert a.name == "length"
        assert a.data_type == "xsd:float"
        assert a.multiplicity == "1"
        with pytest.raises(Exception):
            a.name = "x"  # type: ignore  # frozen
        b = AssocSemantics(name="terminal", target_class="Terminal", multiplicity="0..*")
        assert b.target_class == "Terminal"
        assert b.multiplicity == "0..*"

    def test_class_semantics_holds_attrs_assocs_error(self):
        from scripts.stage4_validate import AttrSemantics, ClassSemantics
        sem = ClassSemantics(
            class_iri="http://x#Foo",
            adapter="OWL",
            attrs=(AttrSemantics("voltage", "xsd:float", "0..1"),),
            assocs=(),
            error=None,
        )
        assert sem.class_iri == "http://x#Foo"
        assert sem.adapter == "OWL"
        assert len(sem.attrs) == 1
        assert sem.attrs[0].name == "voltage"
        assert sem.error is None
        # error 占位（FILE_MISSING / PARSE_ERROR / CLASS_NOT_FOUND）
        err = ClassSemantics(
            class_iri="http://x#Bar", adapter="JSON-LD",
            attrs=(), assocs=(), error="CLASS_NOT_FOUND",
        )
        assert err.error == "CLASS_NOT_FOUND"

    def test_semantic_mismatch_fields(self):
        from scripts.stage4_validate import SemanticMismatch
        m = SemanticMismatch(
            class_iri="http://x#Foo",
            missing_attrs={"Python Types": ["voltage"]},
            missing_assocs={"JSON-LD": ["terminal"]},
            multiplicity_mismatch=["OWL:length 0..1 vs SHACL 1"],
            llm_notes="Python Types 缺 voltage",
            confidence=0.88,
        )
        assert m.class_iri == "http://x#Foo"
        assert m.missing_attrs == {"Python Types": ["voltage"]}
        assert m.missing_assocs == {"JSON-LD": ["terminal"]}
        assert m.multiplicity_mismatch == ["OWL:length 0..1 vs SHACL 1"]
        assert m.confidence == 0.88


# ---------------------------------------------------------------------------
# Stage 5: 5 adapter 语义抽取（10 用例）
# ---------------------------------------------------------------------------


class TestExtractOwl:
    """_extract_owl_semantics: rdflib 解析 cim17_full.ttl，抽取 DatatypeProperty + ObjectProperty。"""

    def test_extract_owl_finds_attrs_and_assocs(self, tmp_path):
        from rdflib import Graph, Namespace, OWL, RDF, RDFS, XSD, URIRef
        from scripts.stage4_validate import _extract_owl_semantics, CIM
        (tmp_path / "owl").mkdir()
        g = Graph()
        # DatatypeProperty: ACLineSegment.length (domain=ACLineSegment, range=xsd:float)
        length_prop = URIRef(str(CIM) + "ACLineSegment.length")
        g.add((length_prop, RDF.type, OWL.DatatypeProperty))
        g.add((length_prop, RDFS.domain, URIRef(str(CIM) + "ACLineSegment")))
        g.add((length_prop, RDFS.range, XSD.float))
        # ObjectProperty: ACLineSegment.Terminal (domain=ACLineSegment, range=Terminal)
        term_prop = URIRef(str(CIM) + "ACLineSegment.Terminal")
        g.add((term_prop, RDF.type, OWL.ObjectProperty))
        g.add((term_prop, RDFS.domain, URIRef(str(CIM) + "ACLineSegment")))
        g.add((term_prop, RDFS.range, URIRef(str(CIM) + "Terminal")))
        g.serialize(tmp_path / "owl" / "cim17_full.ttl", format="turtle")
        sem = _extract_owl_semantics(str(CIM) + "ACLineSegment", tmp_path)
        assert sem.error is None
        assert sem.adapter == "OWL"
        attr_names = {a.name for a in sem.attrs}
        assoc_names = {a.name for a in sem.assocs}
        assert "ACLineSegment.length" in attr_names or "length" in attr_names
        assert "Terminal" in assoc_names or any("Terminal" in a.target_class for a in sem.assocs)

    def test_extract_owl_class_not_found(self, tmp_path):
        from rdflib import Graph
        from scripts.stage4_validate import _extract_owl_semantics, CIM
        (tmp_path / "owl").mkdir()
        g = Graph()
        g.serialize(tmp_path / "owl" / "cim17_full.ttl", format="turtle")
        sem = _extract_owl_semantics(str(CIM) + "NonExistent", tmp_path)
        # 类存在但无属性 → attrs=()/assocs=()，error=None（非 CLASS_NOT_FOUND，因 OWL 属性是全局的）
        assert sem.error is None
        assert sem.attrs == ()
        assert sem.assocs == ()


class TestExtractShacl:
    """_extract_shacl_semantics: rdflib 解析 cim17_shapes.ttl，抽取 sh:property。"""

    def test_extract_shacl_finds_attrs_and_assocs(self, tmp_path):
        from rdflib import Graph, Namespace, URIRef, XSD, Literal
        from scripts.stage4_validate import _extract_shacl_semantics, CIM, SHACL
        (tmp_path / "shacl").mkdir()
        g = Graph()
        shape = URIRef("http://x/ACLineSegmentShape")
        g.add((shape, SHACL.targetClass, URIRef(str(CIM) + "ACLineSegment")))
        # attr property: sh:path=cim:length, sh:datatype=xsd:float, sh:minCount=1
        length_prop = URIRef("http://x/lengthProp")
        g.add((shape, SHACL.property, length_prop))
        g.add((length_prop, SHACL.path, URIRef(str(CIM) + "length")))
        g.add((length_prop, SHACL.datatype, XSD.float))
        g.add((length_prop, SHACL.minCount, Literal(1)))
        # assoc property: sh:path=cim:Terminal, sh:class=cim:Terminal, sh:maxCount=unbounded
        term_prop = URIRef("http://x/termProp")
        g.add((shape, SHACL.property, term_prop))
        g.add((term_prop, SHACL.path, URIRef(str(CIM) + "Terminal")))
        g.add((term_prop, SHACL["class"], URIRef(str(CIM) + "Terminal")))
        g.serialize(tmp_path / "shacl" / "cim17_shapes.ttl", format="turtle")
        sem = _extract_shacl_semantics(str(CIM) + "ACLineSegment", tmp_path)
        assert sem.error is None
        assert sem.adapter == "SHACL"
        assert len(sem.attrs) >= 1
        assert len(sem.assocs) >= 1

    def test_extract_shacl_class_not_found(self, tmp_path):
        from rdflib import Graph
        from scripts.stage4_validate import _extract_shacl_semantics, CIM
        (tmp_path / "shacl").mkdir()
        g = Graph()
        g.serialize(tmp_path / "shacl" / "cim17_shapes.ttl", format="turtle")
        sem = _extract_shacl_semantics(str(CIM) + "NonExistent", tmp_path)
        assert sem.error == "CLASS_NOT_FOUND"


class TestExtractJsonSchema:
    """_extract_json_schema_semantics: 扫描 *_schema.json，区分标量属性与 object/array 关联。"""

    def test_extract_json_schema_finds_attrs_and_assocs(self, tmp_path):
        from scripts.stage4_validate import _extract_json_schema_semantics, CIM
        (tmp_path / "json-schema").mkdir()
        schema = {
            "definitions": {
                "ACLineSegment": {
                    "type": "object",
                    "properties": {
                        "length": {"type": "number"},
                        "Terminal": {"type": "object", "$ref": "#/definitions/Terminal"},
                    },
                    "required": ["length"],
                }
            }
        }
        (tmp_path / "json-schema" / "Core_schema.json").write_text(json.dumps(schema))
        sem = _extract_json_schema_semantics("ACLineSegment", tmp_path)
        assert sem.error is None
        assert sem.adapter == "JSON Schema"
        attr_names = {a.name for a in sem.attrs}
        assoc_names = {a.name for a in sem.assocs}
        assert "length" in attr_names
        assert "Terminal" in assoc_names

    def test_extract_json_schema_class_not_found(self, tmp_path):
        from scripts.stage4_validate import _extract_json_schema_semantics
        (tmp_path / "json-schema").mkdir()
        schema = {"definitions": {"Other": {"type": "object"}}}
        (tmp_path / "json-schema" / "Core_schema.json").write_text(json.dumps(schema))
        sem = _extract_json_schema_semantics("NonExistent", tmp_path)
        assert sem.error == "CLASS_NOT_FOUND"


class TestExtractJsonLd:
    """_extract_jsonld_semantics: 扫描 *_context.jsonld，@context 通常只含术语映射（语义稀疏）。"""

    def test_extract_jsonld_sparse_returns_class_not_found(self, tmp_path):
        from scripts.stage4_validate import _extract_jsonld_semantics
        (tmp_path / "jsonld-context").mkdir()
        # @context 仅含术语映射，不含属性结构
        ctx = {"@context": {"ACLineSegment": {"@id": "cim:ACLineSegment"}}}
        (tmp_path / "jsonld-context" / "Core_context.jsonld").write_text(json.dumps(ctx))
        sem = _extract_jsonld_semantics("ACLineSegment", tmp_path)
        # JSON-LD 不导出属性结构 → CLASS_NOT_FOUND（诚实标注）
        assert sem.error == "CLASS_NOT_FOUND"
        assert sem.attrs == ()
        assert sem.assocs == ()

    def test_extract_jsonld_file_missing(self, tmp_path):
        from scripts.stage4_validate import _extract_jsonld_semantics
        # 不创建 jsonld-context 目录
        sem = _extract_jsonld_semantics("ACLineSegment", tmp_path)
        assert sem.error == "FILE_MISSING"


class TestExtractPythonTypes:
    """_extract_python_types_semantics: ast.parse *_types.py，区分标量注解与 list[OtherClass] 关联。"""

    def test_extract_python_types_finds_attrs_and_assocs(self, tmp_path):
        from scripts.stage4_validate import _extract_python_types_semantics
        (tmp_path / "python-types").mkdir()
        code = '''\
class ACLineSegment:
    """ACLineSegment class."""

    length: float = 0.0
    terminals: list["Terminal"] = None
'''
        (tmp_path / "python-types" / "Core_types.py").write_text(code)
        sem = _extract_python_types_semantics("ACLineSegment", tmp_path)
        assert sem.error is None
        assert sem.adapter == "Python Types"
        attr_names = {a.name for a in sem.attrs}
        assoc_names = {a.name for a in sem.assocs}
        assert "length" in attr_names
        assert "terminals" in assoc_names

    def test_extract_python_types_class_not_found(self, tmp_path):
        from scripts.stage4_validate import _extract_python_types_semantics
        (tmp_path / "python-types").mkdir()
        (tmp_path / "python-types" / "Core_types.py").write_text("class Other:\n    pass\n")
        sem = _extract_python_types_semantics("NonExistent", tmp_path)
        assert sem.error == "CLASS_NOT_FOUND"


# ---------------------------------------------------------------------------
# Stage 5: prompt 构造 + response 解析（5 用例）
# ---------------------------------------------------------------------------


class TestSemanticPrompt:
    """_build_semantic_prompt: 构造 ReviewPrompt（system=CIM 17 专家，user=IR+5 adapter 摘要）。"""

    def test_prompt_contains_ir_and_semantics(self):
        from scripts.stage4_validate import (
            AttrSemantics, ClassSemantics, _build_semantic_prompt,
        )
        sem = {
            "OWL": ClassSemantics("http://x#Foo", "OWL", (AttrSemantics("voltage", "xsd:float", "0..1"),), (), None),
            "SHACL": ClassSemantics("http://x#Foo", "SHACL", (), (), "CLASS_NOT_FOUND"),
        }
        prompt = _build_semantic_prompt("Foo", None, sem)
        assert "CIM" in prompt.system or "本体" in prompt.system
        assert "Foo" in prompt.user
        assert "voltage" in prompt.user
        assert "CLASS_NOT_FOUND" in prompt.user
        assert prompt.raw_text == "Foo"

    def test_prompt_handles_missing_ir_class(self):
        from scripts.stage4_validate import _build_semantic_prompt
        prompt = _build_semantic_prompt("Foo", None, {})
        # IR 类定义缺失 → user 仍构造（含占位）
        assert "Foo" in prompt.user


class TestSemanticResponse:
    """_parse_semantic_response: 三层熔断（JSON / 业务校验 / 通过）。"""

    def test_parse_consistent_response(self):
        from scripts.stage4_validate import _parse_semantic_response
        raw = json.dumps({
            "class_iri": "http://x#Foo", "consistent": True,
            "missing_attrs": {}, "missing_assocs": {}, "multiplicity_mismatch": [],
            "notes": "ok", "confidence": 0.95,
        })
        result = _parse_semantic_response(raw, "http://x#Foo")
        assert result is not None
        assert result.class_iri == "http://x#Foo"
        assert result.missing_attrs == {}
        assert result.confidence == 0.95

    def test_parse_missing_attrs_response(self):
        from scripts.stage4_validate import _parse_semantic_response
        raw = json.dumps({
            "class_iri": "http://x#Bar", "consistent": False,
            "missing_attrs": {"Python Types": ["voltage"]},
            "missing_assocs": {}, "multiplicity_mismatch": [],
            "notes": "缺 voltage", "confidence": 0.88,
        })
        result = _parse_semantic_response(raw, "http://x#Bar")
        assert result is not None
        assert result.missing_attrs == {"Python Types": ["voltage"]}

    def test_parse_rejects_low_confidence(self):
        from scripts.stage4_validate import _parse_semantic_response
        # confidence < 0.5 → fallback
        raw = json.dumps({
            "class_iri": "http://x#Bar", "consistent": False,
            "missing_attrs": {"Python Types": ["voltage"]},
            "missing_assocs": {}, "multiplicity_mismatch": [],
            "notes": "不确定", "confidence": 0.3,
        })
        result = _parse_semantic_response(raw, "http://x#Bar")
        assert result is None
        # 损坏 JSON → fallback
        assert _parse_semantic_response("{not json", "http://x#Bar") is None
        # 缺 missing_attrs 字段 → fallback
        assert _parse_semantic_response(json.dumps({"confidence": 0.9}), "http://x#Bar") is None


# ---------------------------------------------------------------------------
# Stage 5: §6 语义一致性渲染（2 用例）
# ---------------------------------------------------------------------------


class TestSemanticRendering:
    """_render_semantic_section: 渲染 §6 Markdown（缺失属性表 + 缺失关联表 + 多重性冲突表）。"""

    def test_render_semantic_section_contains_tables(self):
        from scripts.stage4_validate import SemanticMismatch, _render_semantic_section
        mismatches = [
            SemanticMismatch(
                class_iri="http://x#Foo",
                missing_attrs={"Python Types": ["voltage"]},
                missing_assocs={},
                multiplicity_mismatch=[],
                llm_notes="Python Types 缺 voltage",
                confidence=0.88,
            )
        ]
        md = _render_semantic_section(mismatches, total=1)
        assert "## 6. 语义一致性复审" in md
        assert "缺失属性" in md
        assert "Foo" in md
        assert "Python Types" in md
        assert "voltage" in md

    def test_render_semantic_section_handles_empty(self):
        from scripts.stage4_validate import _render_semantic_section
        md = _render_semantic_section([], total=5)
        assert "## 6. 语义一致性复审" in md
        assert "5/5" in md or "100" in md  # 全部一致


# ---------------------------------------------------------------------------
# Stage 5: 端到端（2 用例）
# ---------------------------------------------------------------------------


class TestSemanticE2E:
    """端到端：--semantic-review 渲染 §6 语义一致性段。"""

    def test_e2e_semantic_review_renders_section(self, tmp_path):
        import sys
        from scripts.stage4_validate import _cli
        # 构造 IR（Foo 含 voltage 属性 + Terminal 关联）
        from cim_ontology.ir.models import ClassDef, Package, OntologyIR, SourceInfo
        from datetime import datetime, timezone
        ir = OntologyIR(
            packages=[Package(
                iri="http://test/Core", name="Core",
                classes=[ClassDef(name="Foo", attributes=[], associations=[])],
            )],
            uncertain_entries=[], cross_package_refs=[],
            source=SourceInfo(
                document_path="/test", document_sha256="x",
                parsed_at=datetime.now(timezone.utc), parser_version="0.2.0",
            ),
        )
        ir_path = tmp_path / "ir_after.json"
        ir_path.write_text(ir.model_dump_json())

        # 构造 build_dir（5 adapter 子目录，每个含 Foo）
        build_dir = tmp_path / "build"
        (build_dir / "owl").mkdir(parents=True)
        from rdflib import Graph, URIRef, OWL as OWL_NS, RDF
        from scripts.stage4_validate import CIM, SHACL
        g = Graph()
        g.add((URIRef(str(CIM) + "Foo"), RDF.type, OWL_NS.Class))
        g.serialize(build_dir / "owl" / "cim17_full.ttl", format="turtle")
        (build_dir / "shacl").mkdir()
        g2 = Graph()
        g2.add((URIRef("http://x/shape1"), SHACL.targetClass, URIRef(str(CIM) + "Foo")))
        g2.serialize(build_dir / "shacl" / "cim17_shapes.ttl", format="turtle")
        (build_dir / "json-schema").mkdir()
        (build_dir / "json-schema" / "Core_schema.json").write_text(json.dumps({"definitions": {"Foo": {"type": "object"}}}))
        (build_dir / "jsonld-context").mkdir()
        (build_dir / "jsonld-context" / "Core_context.jsonld").write_text(json.dumps({"@context": {"Foo": {"@id": "cim:Foo"}}}))
        (build_dir / "python-types").mkdir()
        (build_dir / "python-types" / "Core_types.py").write_text("class Foo:\n    pass\n")

        # 通过 sys.argv 调用 _cli --semantic-review
        out_path = tmp_path / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = [
                "stage4_validate",
                "--ir", str(ir_path),
                "--build", str(build_dir),
                "--out", str(out_path),
                "--semantic-review",
                "--provider-fixtures", "tests/fixtures/llm",
            ]
            _cli()
        finally:
            sys.argv = old_argv

        assert out_path.exists()
        content = out_path.read_text()
        assert "## 6. 语义一致性复审" in content

    def test_e2e_without_semantic_review_no_section(self, tmp_path):
        import sys
        from scripts.stage4_validate import _cli
        # 最小 IR
        from cim_ontology.ir.models import Package, OntologyIR, SourceInfo
        from datetime import datetime, timezone
        ir = OntologyIR(
            packages=[Package(iri="http://test/Core", name="Core", classes=[])],
            uncertain_entries=[], cross_package_refs=[],
            source=SourceInfo(
                document_path="/test", document_sha256="x",
                parsed_at=datetime.now(timezone.utc), parser_version="0.2.0",
            ),
        )
        ir_path = tmp_path / "ir.json"
        ir_path.write_text(ir.model_dump_json())
        build_dir = tmp_path / "build"
        for d in ("owl", "shacl", "json-schema", "jsonld-context", "python-types"):
            (build_dir / d).mkdir(parents=True)
        from rdflib import Graph
        Graph().serialize(build_dir / "owl" / "cim17_full.ttl", format="turtle")
        Graph().serialize(build_dir / "shacl" / "cim17_shapes.ttl", format="turtle")
        (build_dir / "json-schema" / "Core_schema.json").write_text("{}")
        (build_dir / "jsonld-context" / "Core_context.jsonld").write_text("{}")
        (build_dir / "python-types" / "Core_types.py").write_text("")
        out_path = tmp_path / "report.md"
        old_argv = sys.argv
        try:
            sys.argv = ["stage4_validate", "--ir", str(ir_path), "--build", str(build_dir), "--out", str(out_path)]
            _cli()
        finally:
            sys.argv = old_argv
        content = out_path.read_text()
        # 不传 --semantic-review → §6 不渲染（向后兼容）
        assert "## 6. 语义一致性复审" not in content
