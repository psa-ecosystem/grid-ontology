"""ClassRegistry 单元测试。"""
import pytest

from cim_ontology.ir.registry import ClassRegistry


class TestClassRegistry:
    def test_add_and_get(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        assert reg.get("IdentifiedObject") == "Core"
        assert reg.has("IdentifiedObject")

    def test_get_unknown_returns_none(self):
        reg = ClassRegistry()
        assert reg.get("Unknown") is None
        assert not reg.has("Unknown")

    def test_find_similar_finds_close_match(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        reg.add("Wires", "ReportingGroup")
        similar = reg.find_similar("Meastrement", threshold=2)
        names = [name for name, _ in similar]
        assert "Measurement" in names

    def test_find_similar_returns_empty_when_no_match(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        similar = reg.find_similar("CompletelyDifferent", threshold=1)
        assert similar == []

    def test_all_names(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        reg.add("Wires", "Line")
        names = reg.all_names()
        assert "IdentifiedObject" in names
        assert "Line" in names
        assert len(names) == 2