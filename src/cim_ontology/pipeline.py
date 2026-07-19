"""Pipeline 编排器：串联 4 阶段（设计规范 §2.1）。

Markdown → IR-JSON → LLM 复审 → 多格式输出 → 验证
"""
from __future__ import annotations

from pathlib import Path

import structlog

from cim_ontology.adapters import ADAPTERS, get_adapter
from cim_ontology.audit.errors import PipelineError, Severity
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir
from cim_ontology.ir.models import OntologyIR
from cim_ontology.reviewer.providers import LLMProvider, MockProvider
from cim_ontology.reviewer.reviewer import LLMReviewer

log = structlog.get_logger()


def build(
    md_path: Path,
    output_dir: Path,
    formats: list[str] | None = None,
    llm_provider: LLMProvider | None = None,
    use_llm: bool = False,
) -> dict:
    """执行完整 4 阶段流水线。

    Args:
        md_path: 输入 Markdown 文件
        output_dir: 输出根目录
        formats: 输出格式列表（默认 owl + shacl + jsonld-context）
        llm_provider: LLM Provider（None = Mock）
        use_llm: 是否启用 LLM 复审

    Returns:
        dict 含 "ir"、"stats"、各 adapter 的 emit 结果
    """
    formats = formats or ["owl", "shacl", "jsonld-context"]
    for fmt in formats:
        if fmt not in ADAPTERS:
            raise ValueError(
                f"Unknown format: {fmt!r}. Available: {list(ADAPTERS.keys())}"
            )

    # Stage 1: 规则清洗
    log.info("stage_start", stage="ingest", input=str(md_path))
    try:
        ir = clean_markdown_to_ir(md_path)
    except FileNotFoundError:
        raise PipelineError(
            severity=Severity.FATAL,
            stage="ingest",
            message=f"输入文件不存在: {md_path}",
        )
    log.info("stage_end", stage="ingest",
             classes=ir.stats.class_count, packages=ir.stats.package_count)

    # Stage 2: LLM 复审（可选）
    if use_llm and ir.uncertain_entries:
        provider = llm_provider or MockProvider(fixtures_dir=Path("tests/fixtures/llm"))
        reviewer = LLMReviewer(provider=provider)
        log.info("stage_start", stage="review", uncertain=len(ir.uncertain_entries))
        ir = reviewer.review(ir)
        log.info("stage_end", stage="review",
                 remaining_uncertain=len(ir.uncertain_entries))

    # Stage 3 + 4: 输出 + 验证
    results: dict = {"ir": ir, "stats": {}, "emits": {}}
    for fmt in formats:
        adapter = get_adapter(fmt)
        log.info("stage_start", stage="emit", format=fmt)
        try:
            emit_result = adapter.emit(ir, output_dir / fmt)
            results["emits"][fmt] = emit_result
            results["stats"].update(emit_result.stats)
            log.info("stage_end", stage="emit", format=fmt,
                     files=len(emit_result.files))
        except Exception as e:
            log.error("emit_failed", format=fmt, error=str(e))
            raise PipelineError(
                severity=Severity.ERROR,
                stage="emit",
                message=f"格式 {fmt} 生成失败: {e}",
            )

    return results
