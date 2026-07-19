"""P3-A 公共 IRI 安全模块单元测试。"""
import pytest

from cim_ontology.adapters._iri_safe import (
    is_safe_iri_part,        # 字符白名单校验（来自 shacl.py）
    is_valid_python_identifier,  # Python 标识符校验
    contains_ocr_noise,      # OCR 噪声检测（来自 owl.py）
    safe_attr_slug,          # 清洗为安全属性名（去噪 → slug）
)


class TestIsSafeIriPart:
    """字符白名单校验：仅允许 ASCII 字母/数字/_/.-"""

    def test_accepts_ascii_identifier(self):
        assert is_safe_iri_part("Voltage") is True

    def test_rejects_spaces(self):
        assert is_safe_iri_part("name with space") is False

    def test_rejects_latex_artifacts(self):
        assert is_safe_iri_part(r"\mathcal{Z}") is False

    def test_rejects_empty(self):
        assert is_safe_iri_part("") is False
        assert is_safe_iri_part(None) is False


class TestIsValidPythonIdentifier:
    """Python 标识符严格校验。"""

    def test_accepts_camel_case(self):
        assert is_valid_python_identifier("BaseVoltage") is True

    def test_rejects_starts_with_digit(self):
        assert is_valid_python_identifier("1Voltage") is False

    def test_rejects_hyphen(self):
        assert is_valid_python_identifier("base-voltage") is False

    def test_rejects_latex(self):
        assert is_valid_python_identifier(r"\mathcal{Z}") is False


class TestContainsOcrNoise:
    """OCR 噪声模式识别。"""

    def test_detects_multiplicity_leak(self):
        assert contains_ocr_noise("Voltage0..1") is True

    def test_detects_latex_mathcal(self):
        assert contains_ocr_noise(r"value \mathcal{Z}") is True

    def test_detects_math_symbols(self):
        assert contains_ocr_noise(r"value \in Set") is True
        assert contains_ocr_noise(r"value \cup Set") is True

    def test_accepts_clean_name(self):
        assert contains_ocr_noise("Voltage") is False


class TestSafeAttrSlug:
    """综合清洗：OCR 噪声 → 替代占位符；非法字符 → 下划线。"""

    def test_clean_name_passes_through(self):
        assert safe_attr_slug("Voltage") == "Voltage"

    def test_ocr_noise_replaced_with_placeholder(self):
        assert safe_attr_slug(r"\mathcal{Z}") == "ocr_noise_attr"

    def test_illegal_chars_replaced_with_underscore(self):
        assert safe_attr_slug("name-with-dashes") == "name_with_dashes"

    def test_combined_noise(self):
        # 先 OCR 噪声检测，命中即返回占位符
        assert safe_attr_slug(r"value \in S") == "ocr_noise_attr"

    def test_empty_returns_placeholder(self):
        assert safe_attr_slug("") == "ocr_noise_attr"
        assert safe_attr_slug(None) == "ocr_noise_attr"
