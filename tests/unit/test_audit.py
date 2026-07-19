"""审计日志测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.audit import AuditLogger


@pytest.fixture
def audit_path(tmp_path):
    return tmp_path / "audit.jsonl"


class TestAuditLogger:
    def test_record_writes_jsonl(self, audit_path):
        logger = AuditLogger(path=audit_path)
        entry = UncertainEntry(
            case_id="x", source_table=1, package="P",
            raw_text="foo", rule_attempt={}, uncertainty_reason="class_name_typo",
        )
        logger.record(entry, raw_response='{"corrected":{}}', final_action="accepted")
        content = audit_path.read_text()
        record = json.loads(content.strip())
        assert record["case_id"] == "x"
        assert record["action"] == "accepted"
