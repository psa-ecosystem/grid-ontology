"""Pipeline 编排器集成测试。"""
from pathlib import Path

import pytest

from cim_ontology.pipeline import build


@pytest.fixture
def sample_md(tmp_path):
    md = tmp_path / "test.md"
    md.write_text(
        "## 5.1.1 Class: IdentifiedObject\n\n"
        "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
        "| mRID | string | 1..1 |\n",
        encoding="utf-8",
    )
    return md


class TestBuild:
    def test_builds_all_three_formats(self, sample_md, tmp_path):
        out = tmp_path / "build"
        result = build(sample_md, out, formats=["owl", "shacl", "jsonld-context"])
        assert (out / "owl").exists()
        assert (out / "shacl").exists()
        assert (out / "jsonld-context").exists()
        assert result["stats"]["classes"] >= 1

    def test_invalid_format_raises(self, sample_md, tmp_path):
        out = tmp_path / "build"
        with pytest.raises(ValueError, match="Unknown format"):
            build(sample_md, out, formats=["invalid_format_xyz"])

    def test_skips_missing_format_gracefully(self, sample_md, tmp_path):
        out = tmp_path / "build"
        # 仅请求 OWL，其他应跳过
        result = build(sample_md, out, formats=["owl"])
        assert (out / "owl").exists()
        assert not (out / "shacl").exists()
