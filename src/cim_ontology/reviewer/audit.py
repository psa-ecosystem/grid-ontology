"""JSONL 审计日志（设计规范 §5.6）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cim_ontology.ir.models import UncertainEntry


class AuditLogger:
    """追加写 JSONL 审计日志。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        entry: UncertainEntry,
        raw_response: str,
        final_action: str,
        confidence: float | None = None,
    ) -> None:
        """记录一条 LLM 复审决策。"""
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": entry.case_id,
            "trigger": entry.uncertainty_reason,
            "raw": entry.raw_text,
            "rule_attempt": entry.rule_attempt,
            "llm_raw_response": raw_response[:500],  # 截断
            "action": final_action,
        }
        if confidence is not None:
            record["confidence"] = confidence
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
