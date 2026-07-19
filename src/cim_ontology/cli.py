"""CLI 入口（设计规范 §6.7）。"""
from __future__ import annotations

from pathlib import Path

import typer

from cim_ontology.pipeline import build as run_pipeline

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="GB/T 43259.301-2024 CIM 本体提取与生成器",
)


@app.callback()
def _main() -> None:
    """主入口（占位 callback，强制 typer 创建 Group 模式）。"""


@app.command(name="build")
def build_cmd(  # noqa: A002  # 'input'/'format' 是 CLI 标志名（brief verbatim）
    input: Path = typer.Option(  # noqa: A002, B008
        ..., "--input", "-i", help="输入 Markdown 文件"
    ),
    output: Path = typer.Option(  # noqa: B008
        Path("./build"), "--output", "-o", help="输出目录"
    ),
    format: list[str] = typer.Option(  # noqa: A002, B008
        ["owl", "shacl", "jsonld-context"],
        "--format",
        "-f",
        help="输出格式（可重复）",
    ),
    use_llm: bool = typer.Option(False, "--llm", help="启用 LLM 复审"),
) -> None:
    """从 Markdown 标准文档构建本体。"""
    result = run_pipeline(input, output, formats=format, use_llm=use_llm)
    typer.echo(f"✓ 构建完成: {result['stats']}")


if __name__ == "__main__":
    app()
