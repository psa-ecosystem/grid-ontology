"""CLI 入口测试（使用 typer.testing.CliRunner）。"""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cim_ontology.cli import app


@pytest.fixture
def runner():
    return CliRunner()


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


class TestBuildCommand:
    def test_build_help(self, runner):
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.stdout
        assert "--output" in result.stdout

    def test_build_runs(self, runner, sample_md, tmp_path):
        out = tmp_path / "build"
        result = runner.invoke(app, [
            "build",
            "--input", str(sample_md),
            "--output", str(out),
            "--format", "owl",
        ])
        assert result.exit_code == 0
        assert (out / "owl" / "cim17_full.ttl").exists()
