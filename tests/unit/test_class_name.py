"""类名清洗器测试。"""
import pytest

from cim_ontology.cleaner.class_name import CleanedName, clean_class_name
from cim_ontology.ir.registry import ClassRegistry


class TestCleanClassName:
    def test_known_ocr_correction(self):
        reg = ClassRegistry()
        result = clean_class_name("Meastrement", reg)
        assert result.value == "Measurement"
        assert result.correction_applied is True

    def test_known_registered_passthrough(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        result = clean_class_name("IdentifiedObject", reg)
        assert result.value == "IdentifiedObject"
        assert result.correction_applied is False

    def test_typo_flagged_as_uncertain(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("Meastrement", reg)
        # 已在已知修正表
        assert result.uncertainty_reason is None

    def test_close_match_flagged_with_suggestions(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("Measurment", reg)  # 少一个 e
        # Levenshtein 距离 1，但不在已知修正表
        assert result.value == "Measurment"
        assert result.uncertainty_reason == "class_name_typo"
        assert "Measurement" in result.suggestions

    def test_completely_unknown(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("CompletelyNewClass", reg)
        assert result.uncertainty_reason == "class_unknown"


class TestAllOcrCorrections:
    """覆盖所有已知 OCR 错误（设计规范 §4.3）。"""

    @pytest.mark.parametrize("raw,expected", [
        ("Meastrement", "Measurement"),
        ("Rep0rtingGroup", "ReportingGroup"),
        ("AuxiliarEuiment", "AuxiliaryEquipment"),
        ("DiaramLaout", "DiagramLayout"),
    ])
    def test_known_correction(self, raw, expected):
        reg = ClassRegistry()
        result = clean_class_name(raw, reg)
        assert result.value == expected
        assert result.correction_applied is True