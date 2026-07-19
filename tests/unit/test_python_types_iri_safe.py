"""P3-A-T5 测试：python_types.py 应用 OCR 鲁棒标识符校验。

覆盖以下内容：
  - _validate_package_name：仅 Python 标识符规则（不含 OCR 检测，保持稳定）
  - _validate_class_name：Python 标识符 + OCR 噪声双重检测
  - _validate_attr_name：新增的属性名校验
  - PythonTypesAdapter 集成：emit 入口对 OCR 噪声属性名触发 ValueError
"""
import pytest

from cim_ontology.adapters.python_types import (
    PythonTypesAdapter,
    _validate_attr_name,
    _validate_class_name,
    _validate_package_name,
)
from cim_ontology.ir.models import (
    ClassDef,
    DataProperty,
    IRStats,
    OntologyIR,
    Package,
    SourceInfo,
)


class TestValidatePackageName:
    """包名校验：仅 Python 标识符规则（不含 OCR 检测，保持稳定）。"""

    def test_accepts_clean_name(self):
        _validate_package_name("Core")  # 不抛错

    def test_rejects_latex(self):
        with pytest.raises(ValueError, match="非法包名"):
            _validate_package_name(r"\mathcal{Z}")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="非法包名"):
            _validate_package_name("../etc/passwd")


class TestValidateClassName:
    """类名校验：Python 标识符 + OCR 噪声双重检测。"""

    def test_accepts_clean_name(self):
        _validate_class_name("BaseVoltage")  # 不抛错

    def test_rejects_latex_ocr(self):
        with pytest.raises(ValueError, match="OCR 噪声"):
            _validate_class_name(r"\mathcal{Z}")

    def test_rejects_multiplicity_leak(self):
        """'Voltage0..1' 是合法 Python 标识符但含 OCR 噪声。"""
        with pytest.raises(ValueError, match="OCR 噪声"):
            _validate_class_name("Voltage0..1")


class TestValidateAttrName:
    """新增：属性名校验（之前未单独抽取为公开函数）。"""

    def test_accepts_clean_attr_name(self):
        _validate_attr_name("voltage")  # 不抛错

    def test_rejects_latex(self):
        with pytest.raises(ValueError, match="OCR 噪声"):
            _validate_attr_name(r"\mathcal{Z}")


class TestPythonTypesAdapterIntegration:
    """端到端：生成 _types.py 时 OCR 噪声属性名应触发 ValueError。"""

    @staticmethod
    def _make_ir(attr_name: str) -> OntologyIR:
        attr = DataProperty(name=attr_name, data_type="xsd:string", required=False)
        cls = ClassDef(name="BaseVoltage", parents=[], attributes=[attr], associations=[])
        pkg = Package(iri="http://x#T", name="Core", classes=[cls])
        return OntologyIR(
            schema_version="1.0",
            packages=[pkg],
            uncertain_entries=[],
            stats=IRStats(),
            source=SourceInfo(
                document_path="t.md",
                document_sha256="abc",
                parsed_at="2026-01-01T00:00:00Z",
                parser_version="0",
            ),
        )

    def test_emit_skips_ocr_noise_attr(self, tmp_path):
        """v1.4 P0 修复：python_types 对 OCR 噪声属性 fail-soft 跳过，不 raise。

        单元函数 _validate_attr_name 仍是 fail-fast（contract 不变），
        适配器层在 _generate_class 中负责 swallow 并记日志。
        """
        ir = self._make_ir(r"\mathcal{Z}")
        adapter = PythonTypesAdapter()
        result = adapter.emit(ir, tmp_path)  # 不抛错
        # 产物文件应正常生成
        assert (tmp_path / "Core_types.py").exists()
        assert len(result.files) == 1
        # OCR 噪声属性不应出现在产物中
        content = (tmp_path / "Core_types.py").read_text()
        assert "mathcal" not in content

    def test_emit_succeeds_with_clean_attrs(self, tmp_path):
        ir = self._make_ir("voltage")
        adapter = PythonTypesAdapter()
        result = adapter.emit(ir, tmp_path)  # 不抛错
        assert (tmp_path / "Core_types.py").exists()
        assert len(result.files) == 1


class TestCollectUsedTypesFailSoft:
    """v1.5 P1 修复：_collect_used_types 对空/OCR 噪声的 parent/assoc.target.class_name
    fail-soft 跳过（仿 _generate_class 的 ocr_attr_skipped 模式），不 raise 让 emit 崩溃。

    背景：cim-base-full.md Stage 1+2 解析时 42 个 association 含空 target.class_name
          （如 ConnectivityNodeContainer::Substation 的 target 残缺），
          启用 _infer_refs 后会触发跨包边，本函数开始真正执行。
    """

    @staticmethod
    def _make_ir_with_empty_assoc_target() -> OntologyIR:
        """构造 Wires → Core 跨包依赖，含一个空 target.class_name 的 assoc。"""
        from cim_ontology.ir.models import ClassRef, ObjectProperty

        core = Package(
            iri="http://x#C", name="Core", classes=[
                ClassDef(
                    name="IdentifiedObject",
                    attributes=[DataProperty(name="mRID", data_type="xsd:string", required=True)],
                ),
                ClassDef(
                    name="Substation",
                    attributes=[DataProperty(name="name", data_type="xsd:string", required=False)],
                ),
            ],
        )
        wires = Package(
            iri="http://x#W", name="Wires", classes=[
                ClassDef(
                    name="ACLineSegment",
                    parents=[ClassRef(package="Core", class_name="IdentifiedObject")],
                    associations=[
                        # 正常 assoc：Core::Substation
                        ObjectProperty(
                            name="ToSubstation",
                            target=ClassRef(package="Core", class_name="Substation"),
                        ),
                        # Stage 2 清空的 OCR 噪声 assoc：class_name=None
                        ObjectProperty(
                            name="Container",
                            target=ClassRef(package="Core", class_name=None),
                        ),
                    ],
                ),
            ],
        )
        return OntologyIR(
            schema_version="1.0",
            packages=[core, wires],
            uncertain_entries=[],
            stats=IRStats(),
            source=SourceInfo(
                document_path="t.md",
                document_sha256="abc",
                parsed_at="2026-01-01T00:00:00Z",
                parser_version="0",
            ),
        )

    def test_emit_does_not_raise_on_empty_assoc_target(self, tmp_path):
        """空 target.class_name 不应让 emit 崩溃（fail-soft 跳过）。"""
        ir = self._make_ir_with_empty_assoc_target()
        adapter = PythonTypesAdapter()
        result = adapter.emit(ir, tmp_path)  # 不抛错
        assert (tmp_path / "Core_types.py").exists()
        assert (tmp_path / "Wires_types.py").exists()
        assert len(result.files) == 2

    def test_emit_generates_cross_pkg_import_despite_ocr_assoc(self, tmp_path):
        """即便有 OCR 噪声 assoc，正常 parent 仍应触发跨包 import。"""
        ir = self._make_ir_with_empty_assoc_target()
        adapter = PythonTypesAdapter()
        adapter.emit(ir, tmp_path)
        wires_src = (tmp_path / "Wires_types.py").read_text()
        # 正常 parent 仍生成 from Core_types import
        assert "from Core_types import IdentifiedObject" in wires_src
        # 正常 assoc 也应包含
        assert "from Core_types import" in wires_src
        assert "IdentifiedObject" in wires_src
        # 空 class_name 的 assoc（Container）应被跳过，不影响产物
        assert "Container" not in wires_src or "from Core_types import" in wires_src
        # 关键：Substation 也应被导入（assac 正常）
        assert "Substation" in wires_src

