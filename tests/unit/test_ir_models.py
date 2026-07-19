"""IR-JSON Pydantic 模型单元测试。"""
import pytest
from pydantic import ValidationError

from cim_ontology.ir.models import (
    CrossPackageRef,
    Enumeration,
    IRStats,
    Multiplicity,
    PrimitiveType,
    SourceInfo,
)


class TestMultiplicity:
    def test_zero_one(self):
        m = Multiplicity(min=0, max=1, raw="0..1")
        assert m.is_many is False

    def test_one_one(self):
        m = Multiplicity(min=1, max=1, raw="1..1")
        assert m.is_many is False

    def test_zero_many(self):
        m = Multiplicity(min=0, max=None, raw="0..*")
        assert m.is_many is True

    def test_one_many(self):
        m = Multiplicity(min=1, max=None, raw="1..*")
        assert m.is_many is True

    def test_serialization_roundtrip(self):
        m = Multiplicity(min=0, max=None, raw="0..*")
        data = m.model_dump()
        restored = Multiplicity(**data)
        assert restored == m


class TestEnumeration:
    def test_basic(self):
        e = Enumeration(name="PhaseCode", values=["A", "B", "C"], description="相序")
        assert e.name == "PhaseCode"
        assert "A" in e.values


class TestIRStats:
    def test_basic(self):
        s = IRStats(
            package_count=27,
            class_count=234,
            attribute_count=1500,
            association_count=800,
            enumeration_count=15,
            uncertain_count=20,
        )
        assert s.package_count == 27


class TestSourceInfo:
    def test_basic(self):
        si = SourceInfo(
            document_path="docs/cim-base-full.md",
            document_sha256="abc123",
            parsed_at="2026-06-22T10:00:00Z",
            parser_version="0.1.0",
        )
        assert si.document_sha256 == "abc123"