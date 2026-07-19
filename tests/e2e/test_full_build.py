"""端到端测试：完整 9243 行文档构建。

Task 30 + P1 — 验证 full fixture 跨全部输出格式的端到端构建。

P1 全量修复后状态（2026-06-23）：
- classes: 0 → 992 ✅ (P1 修复中文 H2 + 表格标题识别 + html_block 解析)
- packages: 1 → 27 ✅ (P1.1 修复 section.package 透传到 ClassDef，多包分组)
- OWL triples: 0 → 26045 ✅ (P1.2 元数据 + P1.3 列序修复)
- ObjectProperty: 0 → 2672 ✅ (P1.3 表头驱动列映射 + OCR 列序兜底)

已知残留限制：
- rdfs:subClassOf = 0：OCR 文档中继承关系以叙述文字或"描述"列表达
  （"PowerSystemResource 继承自 IdentifiedObject"），不在结构化表格中。
  解决需要 Stage 2 LLM 抽取或 paragraph text regex，超出 P1 范围。
"""
import time
from pathlib import Path

import pytest
from rdflib import Graph

from cim_ontology.pipeline import build


FIXTURE_PATH = Path("tests/fixtures/large/full.md")


@pytest.mark.skipif(
    not FIXTURE_PATH.exists(),
    reason="完整文档 fixture 不存在（参见 Task 29）",
)
class TestFullDocumentBuild:
    def test_full_builds_all_formats(self, tmp_path):
        out = tmp_path / "build"
        start = time.monotonic()
        result = build(
            FIXTURE_PATH,
            out,
            formats=["owl", "shacl", "jsonld-context"],
        )
        elapsed = time.monotonic() - start
        # 5 分钟超时
        assert elapsed < 300, f"耗时 {elapsed:.0f}s 超过 5 分钟"

        # 所有格式目录存在
        assert (out / "owl").exists()
        assert (out / "shacl").exists()
        assert (out / "jsonld-context").exists()

        # P1 修复后已通过：至少抽取 27 个包或 100 个类
        assert result["stats"].get("packages", 0) >= 27 or result["stats"]["classes"] > 100

    def test_owl_full_ttl_parseable(self, tmp_path):
        """P1.2：完整 OWL 输出可解析且三元组数 ≥ 5000。

        P1.2 之前为 xfail（P1.2 修复后 528 → 15411 triples，超 5000 阈值，正式通过）。
        """
        out = tmp_path / "build"
        build(FIXTURE_PATH, out, formats=["owl"])
        full = out / "owl" / "cim17_full.ttl"
        g = Graph()
        g.parse(full, format="turtle")
        # P1.2 阈值：5000 triples
        assert len(g) > 5000, f"仅 {len(g)} triples，远低于 P1.2 阈值 5000"

    def test_owl_object_properties_emitted(self, tmp_path):
        """P1.3：OWL 应为关联端生成 ObjectProperty 三元组。

        P1.3 之前为 0（orchestrator 硬编码 [name, type, mult] 列序与 OCR 实际
        [mult_from, name, mult_to, type, desc] 不匹配，导致关联被错误解析）。
        """
        from rdflib import RDF, OWL
        out = tmp_path / "build"
        build(FIXTURE_PATH, out, formats=["owl"])
        full = out / "owl" / "cim17_full.ttl"
        g = Graph()
        g.parse(full, format="turtle")
        n_op = len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
        assert n_op > 1000, f"仅 {n_op} ObjectProperty，远低于 P1.3 阈值 1000"

    def test_owl_subclass_of_emitted(self, tmp_path):
        """P2-A：OWL 应为类生成 subClassOf 三元组（继承关系）。

        P2-A 之前为 0（继承信息在 OCR 表格描述列中，之前未被抽取）。
        """
        from rdflib import RDFS
        out = tmp_path / "build"
        build(FIXTURE_PATH, out, formats=["owl"])
        full = out / "owl" / "cim17_full.ttl"
        g = Graph()
        g.parse(full, format="turtle")
        n_sub = len(list(g.triples((None, RDFS.subClassOf, None))))
        assert n_sub > 500, f"仅 {n_sub} subClassOf，远低于 P2-A 阈值 500"
