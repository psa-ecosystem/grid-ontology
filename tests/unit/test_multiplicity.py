"""多重性清洗器测试。"""
import pytest

from cim_ontology.cleaner.multiplicity import (
    UnparseableMultiplicity,
    clean_multiplicity,
)
from cim_ontology.ir.models import Multiplicity


class TestCleanMultiplicity:
    @pytest.mark.parametrize("raw,expected_min,expected_max,expected_raw", [
        ("0..1", 0, 1, "0..1"),
        (" 0..1 ", 0, 1, "0..1"),
        ("0..*", 0, None, "0..*"),
        ("many", 0, None, "0..*"),       # 语义归一
        ("0..n", 0, None, "0..*"),
        ("1..*", 1, None, "1..*"),
        ("1..1", 1, 1, "1..1"),
    ])
    def test_valid_multiplicity(self, raw, expected_min, expected_max, expected_raw):
        m = clean_multiplicity(raw)
        assert isinstance(m, Multiplicity)
        assert m.min == expected_min
        assert m.max == expected_max
        assert m.raw == expected_raw

    def test_strips_latex_noise(self):
        m = clean_multiplicity(" $0..1$ ")
        assert m.min == 0
        assert m.max == 1

    def test_unparseable_raises(self):
        with pytest.raises(UnparseableMultiplicity):
            clean_multiplicity("not-a-multiplicity")
