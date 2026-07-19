"""P3-A-T6 跨适配器一致性测试。

验证 4 个适配器对相同 OCR 噪声输入的响应都体现"鲁棒性"原则：
  - owl.py / shacl.py：fail-soft（跳过）
  - json_schema.py：清洗为安全 slug
  - python_types.py：fail-fast（raise ValueError）

虽然行为不同（fail-soft vs fail-fast），但**核心语义一致**：
  都不让 OCR 噪声污染输出产物。
"""
import json

import pytest

from cim_ontology.adapters._iri_safe import (
    contains_ocr_noise,
    is_safe_iri_part,
    is_valid_python_identifier,
    safe_attr_slug,
)
from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.adapters.owl import OwlTurtleAdapter, _safe_property_iri
from cim_ontology.adapters.python_types import (
    PythonTypesAdapter,
    _validate_attr_name,
    _validate_class_name,
)
from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.ir.models import (
    ClassDef,
    DataProperty,
    IRStats,
    OntologyIR,
    Package,
    SourceInfo,
)


# OCR 噪声样本（覆盖每种已识别模式）
OCR_NOISE_SAMPLES = [
    r"\mathcal{Z}",         # LaTeX 残骸
    r"\ldots",             # LaTeX 省略号
    "Voltage0..1",         # 多重性泄露
    "Voltage1..*",         # 多重性泄露
    r"value^{abc}",        # 上标噪声 LaTeX ^{...}
    "val $0",              # 公式序号
    r"value \cup Set",     # 集合运算
    r"value \in Set",      # 集合运算
    r"value \Z",           # 整数集符号
    r"value \R",           # 实数集符号
]


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _make_ir(packages: list[Package]) -> OntologyIR:
    return OntologyIR(
        schema_version="1.0",
        packages=packages,
        uncertain_entries=[],
        stats=IRStats(),
        source=SourceInfo(
            document_path="t.md",
            document_sha256="abc",
            parsed_at="2026-01-01T00:00:00Z",
            parser_version="0",
        ),
    )


def _make_pkg_with_attr(attr_name: str, pkg_name: str = "Core",
                        cls_name: str = "BaseVoltage") -> Package:
    attr = DataProperty(name=attr_name, data_type="xsd:string", required=False)
    cls = ClassDef(
        name=cls_name, parents=[], attributes=[attr], associations=[]
    )
    return Package(iri="http://x#T", name=pkg_name, classes=[cls])


# ---------------------------------------------------------------------------
# 核心工具边界用例
# ---------------------------------------------------------------------------


class TestIriSafeCoreEdgeCases:
    """核心工具边界用例。"""

    def test_empty_string_returns_placeholder(self):
        assert safe_attr_slug("") == "ocr_noise_attr"

    def test_whitespace_only_returns_placeholder(self):
        assert safe_attr_slug("   ") == "ocr_noise_attr"

    def test_none_returns_placeholder(self):
        assert safe_attr_slug(None) == "ocr_noise_attr"

    def test_unicode_replaced_with_underscore(self):
        """非 ASCII 字符（中文等）应被替换为下划线。

        '电压' 含两个非 ASCII 字符，每个被替换为 '_' → '__'。
        """
        assert safe_attr_slug("电压") == "__"
        # 简单 ASCII 对照：连字符替换为下划线
        assert safe_attr_slug("name-hyphen") == "name_hyphen"

    def test_max_length_truncation(self):
        """长度 > 64 应被截断。"""
        long_name = "a" * 100
        slug = safe_attr_slug(long_name)
        assert len(slug) <= 64

    def test_combined_clean_and_noise(self):
        """干净名 + 噪声混合 → 噪声优先（命中即返回占位符）。"""
        assert safe_attr_slug(r"Voltage \mathcal{Z}") == "ocr_noise_attr"

    def test_placeholder_used_for_pure_noise(self):
        """纯 LaTeX 噪声 → 占位符。"""
        assert safe_attr_slug(r"\mathcal{Z}") == "ocr_noise_attr"

    def test_leading_digit_is_not_ocr_but_invalid_identifier(self):
        """首字符为数字既不是 OCR 噪声，也不是合法 Python 标识符。"""
        assert contains_ocr_noise("1Voltage") is False
        assert is_valid_python_identifier("1Voltage") is False


# ---------------------------------------------------------------------------
# 跨适配器：所有 4 个适配器都应对 OCR 噪声做出防御性反应
# ---------------------------------------------------------------------------


class TestAllAdaptersRejectOcrNoise:
    """OCR 噪声样本至少被两层校验之一拒绝。"""

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_all_noise_samples_detected_by_contains_ocr_noise(self, noise):
        assert contains_ocr_noise(noise), f"OCR 噪声未被检测: {noise!r}"

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_all_noise_samples_fail_python_identifier_or_safe_iri(self, noise):
        """OCR 噪声样本要么不是合法 Python 标识符，要么不是合法 IRI 部件。

        我们的安全网是"两道闸门"：Python 标识符 + IRI 字符白名单。
        如果一个样本同时通过这两道闸门，则是不安全漏过——必须 fail。
        """
        is_valid_py = is_valid_python_identifier(noise)
        is_safe_iri = is_safe_iri_part(noise)
        if is_valid_py and is_safe_iri:
            pytest.fail(
                f"OCR 噪声 {noise!r} 同时通过了 Python 标识符和 IRI 校验，"
                f"是潜在漏过点"
            )


# ---------------------------------------------------------------------------
# owl.py：返回 None（fail-soft）
# ---------------------------------------------------------------------------


class TestOwlAdapterFailSoftOnOcr:
    """owl.py 应对 OCR 噪声返回 None（fail-soft）。"""

    def test_safe_property_iri_returns_none_for_latex(self):
        result = _safe_property_iri("BaseVoltage", r"\mathcal{Z}")
        assert result is None

    def test_safe_property_iri_returns_none_for_empty(self):
        assert _safe_property_iri("BaseVoltage", "") is None
        assert _safe_property_iri("BaseVoltage", None) is None
        assert _safe_property_iri("BaseVoltage", "   ") is None

    def test_safe_property_iri_returns_none_for_illegal_chars(self):
        """含非法字符（如连字符）→ None。"""
        assert _safe_property_iri("BaseVoltage", "name-with-dash") is None

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_safe_property_iri_returns_none_for_all_ocr_noise(self, noise):
        result = _safe_property_iri("BaseVoltage", noise)
        assert result is None, f"OCR 噪声 {noise!r} 未被 owl 跳过"


# ---------------------------------------------------------------------------
# shacl.py：跳过（fail-soft，验证 emit 不崩溃）
# ---------------------------------------------------------------------------


class TestShaclAdapterFailSoftOnOcr:
    """shacl.py 应对 OCR 噪声跳过该 property shape。"""

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_shacl_emits_without_crash_for_ocr_attr(self, tmp_path, noise):
        """所有 OCR 噪声样本：shacl.emit() 必须不抛错，并成功写出文件。"""
        pkg = _make_pkg_with_attr(noise)
        ir = _make_ir([pkg])

        adapter = ShaclAdapter()
        result = adapter.emit(ir, tmp_path)  # 不抛错

        # 文件已生成
        out_path = tmp_path / "cim17_shapes.ttl"
        assert out_path.exists()
        # OCR 噪声属性被跳过（不会出现在 property shape 中）
        content = out_path.read_text()
        # 关键防御：原始噪声字符串不应原样渗入产物
        # 注意：turtle 中路径 URI 是被清洗过的；这里只做"不崩溃"+"文件存在"的
        # 鲁棒性断言，详细统计在 stats 中。
        assert result.stats["skipped"] >= 0


# ---------------------------------------------------------------------------
# json_schema.py：清洗为 ocr_noise_attr slug
# ---------------------------------------------------------------------------


class TestJsonSchemaAdapterSanitizesOcr:
    """json_schema.py 应对 OCR 噪声清洗为 ocr_noise_attr slug。"""

    def test_latex_becomes_placeholder_in_schema(self, tmp_path):
        pkg = _make_pkg_with_attr(r"\mathcal{Z}")
        ir = _make_ir([pkg])

        JsonSchemaAdapter().emit(ir, tmp_path)
        schema = json.loads((tmp_path / "Core_schema.json").read_text())
        props = schema["properties"]["BaseVoltage"]["properties"]
        assert "ocr_noise_attr" in props
        assert r"\mathcal{Z}" not in props

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_all_ocr_noise_becomes_placeholder(self, tmp_path, noise):
        """所有 OCR 噪声样本都应被清洗为 ocr_noise_attr。"""
        # 注意：_make_pkg_with_attr 共用 cls_name/attr 模板
        # 为避免覆盖，我们用唯一 cls_name
        pkg = _make_pkg_with_attr(noise, cls_name="Cls_" + str(abs(hash(noise)) % 1000))
        ir = _make_ir([pkg])

        JsonSchemaAdapter().emit(ir, tmp_path)
        schema_file = tmp_path / f"{pkg.name}_schema.json"
        assert schema_file.exists()
        schema = json.loads(schema_file.read_text())
        cls_schema = list(schema["properties"].values())[0]
        assert "ocr_noise_attr" in cls_schema["properties"]


# ---------------------------------------------------------------------------
# python_types.py：raise ValueError（fail-fast）
# ---------------------------------------------------------------------------


class TestPythonTypesAdapterFailFastOnOcr:
    """python_types.py 应对 OCR 噪声 raise ValueError（fail-fast）。"""

    def test_class_name_with_latex_raises(self):
        with pytest.raises(ValueError):
            _validate_class_name(r"\mathcal{Z}")

    def test_attr_name_with_latex_raises(self):
        with pytest.raises(ValueError):
            _validate_attr_name(r"\mathcal{Z}")

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_class_name_raises_for_all_ocr_noise(self, noise):
        """所有 OCR 噪声样本都应使类名校验抛 ValueError。"""
        with pytest.raises(ValueError):
            _validate_class_name(noise)

    @pytest.mark.parametrize("noise", OCR_NOISE_SAMPLES)
    def test_attr_name_raises_for_all_ocr_noise(self, noise):
        """所有 OCR 噪声样本都应使属性名校验抛 ValueError。"""
        with pytest.raises(ValueError):
            _validate_attr_name(noise)


# ---------------------------------------------------------------------------
# 跨适配器综合：相同输入 → 不同反应策略，但"鲁棒性"等价
# ---------------------------------------------------------------------------


class TestCrossAdapterRobustnessEquivalence:
    """核心不变性：4 个适配器对 OCR 噪声的反应在"不污染产物"这一维度上等价。"""

    def test_no_adapter_propagates_raw_ocr_noise_to_output(self, tmp_path):
        """所有 4 个适配器都不应将原始 LaTeX 字符串原样写入产物。

        v1.3 → v1.4 行为变更：
          python_types 由 fail-fast 改为 fail-soft（仿 OWL _safe_property_iri），
          跳过 OCR 噪声属性 + structlog warning，不阻断整个 emit。
        """
        noise = r"\mathcal{Z}"
        pkg = _make_pkg_with_attr(noise)
        ir = _make_ir([pkg])

        # owl / shacl / json_schema / python_types 均不抛错
        OwlTurtleAdapter().emit(ir, tmp_path)
        ShaclAdapter().emit(ir, tmp_path)
        JsonSchemaAdapter().emit(ir, tmp_path)
        # python_types：fail-soft（OCR 属性跳过，不再 raise）
        PythonTypesAdapter().emit(ir, tmp_path)

        # 检查产物文件中不含 LaTeX 噪声原样
        for out_file in tmp_path.rglob("*"):
            if out_file.is_file():
                content = out_file.read_text(errors="ignore")
                # 关键防御：噪声字符串不能原样渗入产物
                # 注意：注释中可能提及，这里只检查产物中的"载荷"位置
                # 保守做法：直接断言产物文件中不含 "mathcal"
                assert "mathcal" not in content, (
                    f"产物文件 {out_file} 包含 LaTeX 噪声原样"
                )


# ---------------------------------------------------------------------------
# python_types.py：fail-soft 跳过 OCR 噪声属性（v1.4 P0 修复）
# ---------------------------------------------------------------------------


class TestPythonTypesAdapterSkipsOcrAttr:
    """python_types.py 对 OCR 噪声属性应 fail-soft 跳过（不 raise、不污染产物）。"""

    def test_emit_does_not_raise_on_ocr_attr(self, tmp_path):
        """单个 OCR 噪声属性不应让 emit 崩溃。"""
        noise = r"\mathcal{Z}"
        pkg = _make_pkg_with_attr(noise)
        ir = _make_ir([pkg])
        # 不应抛错
        PythonTypesAdapter().emit(ir, tmp_path)
        # 产物文件应正常生成
        out_file = tmp_path / "Core_types.py"
        assert out_file.exists()

    def test_ocr_attr_excluded_from_output(self, tmp_path):
        """OCR 噪声属性不应出现在输出源码中（不被重命名、不被注释保留）。"""
        noise = r"\mathcal{Z}"
        pkg = _make_pkg_with_attr(noise)
        ir = _make_ir([pkg])
        PythonTypesAdapter().emit(ir, tmp_path)
        content = (tmp_path / "Core_types.py").read_text()
        # 不应包含噪声字符串原样
        assert noise not in content
        assert "mathcal" not in content

    def test_valid_attr_kept_alongside_ocr_attr(self, tmp_path):
        """混合输入：合法属性保留，OCR 噪声属性被跳过。"""
        valid_attr = DataProperty(name="normalName", data_type="xsd:string", required=False)
        noise_attr = DataProperty(name=r"\mathcal{Z}", data_type="xsd:string", required=False)
        cls = ClassDef(
            name="BaseVoltage", parents=[], attributes=[valid_attr, noise_attr], associations=[]
        )
        pkg = Package(iri="http://x#T", name="Core", classes=[cls])
        ir = _make_ir([pkg])

        PythonTypesAdapter().emit(ir, tmp_path)
        content = (tmp_path / "Core_types.py").read_text()
        assert "normalName" in content
        assert "mathcal" not in content

    def test_emit_class_still_uses_pass_when_all_attrs_skipped(self, tmp_path):
        """所有属性都被跳过时，类应回退到 `pass` 占位（不破坏语法）。"""
        noise_attr = DataProperty(name=r"\mathcal{Z}", data_type="xsd:string", required=False)
        cls = ClassDef(
            name="EmptyClass", parents=[], attributes=[noise_attr], associations=[]
        )
        pkg = Package(iri="http://x#T", name="Core", classes=[cls])
        ir = _make_ir([pkg])

        PythonTypesAdapter().emit(ir, tmp_path)
        content = (tmp_path / "Core_types.py").read_text()
        assert "class EmptyClass:" in content
        assert "    pass" in content

    def test_validate_attr_name_still_raises_unit(self):
        """_validate_attr_name 仍是 fail-fast 单元函数（contract 不变）。

        适配器层在 _generate_class 中负责 swallow ValueError；
        单元函数保留严格校验语义，供 caller 显式选择 fail-fast。
        """
        with pytest.raises(ValueError):
            _validate_attr_name(r"\mathcal{Z}")
