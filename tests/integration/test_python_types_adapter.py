"""Python Types 适配器测试。"""
import pytest

from cim_ontology.adapters.python_types import PythonTypesAdapter
from cim_ontology.ir.models import (
    ClassDef, ClassRef, CrossPackageRef, DataProperty, Multiplicity, OntologyIR, Package,
)


@pytest.fixture
def ir_two_packages():
    pkg_a = Package(iri="http://x#A", name="A",
                    classes=[ClassDef(name="IdentifiedObject", attributes=[
                        DataProperty(name="mRID", data_type="xsd:string",
                                     multiplicity=Multiplicity(min=1, max=1, raw="1..1"), required=True),
                    ])])
    pkg_b = Package(iri="http://x#B", name="B",
                    classes=[ClassDef(name="Specific", parents=[
                        ClassRef(package="A", class_name="IdentifiedObject"),
                    ])])
    return OntologyIR(
        packages=[pkg_a, pkg_b],
        cross_package_refs=[
            CrossPackageRef(from_package="B", to_package="A",
                            via_class="Specific", via_property="parents"),
        ],
    )


class TestPythonTypesAdapter:
    def test_emits_types_per_package(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        assert (tmp_path / "A_types.py").exists()
        assert (tmp_path / "B_types.py").exists()

    def test_b_imports_from_a(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        b_src = (tmp_path / "B_types.py").read_text()
        assert "from A_types import" in b_src
        assert "IdentifiedObject" in b_src

    def test_a_has_no_external_imports(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        a_src = (tmp_path / "A_types.py").read_text()
        assert "from B_types" not in a_src


class TestPythonTypesAdapterImportSafety:
    """Task 25 fix: 验证生成文件可被 Python 解释器 import（C1 修复）。"""

    def test_generated_dataclass_is_importable(self, ir_two_packages, tmp_path):
        """C1 修复：required 字段与 ClassVar 字段共存时 dataclass 可被 import。"""
        import importlib.util
        import sys
        PythonTypesAdapter().emit(ir_two_packages, tmp_path)
        # 修复后 import 不能抛 TypeError
        # Python 3.13+ dataclass 要求模块必须注册到 sys.modules 才能 exec_module
        spec = importlib.util.spec_from_file_location(
            "A_types_fixed", tmp_path / "A_types.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["A_types_fixed"] = mod
        try:
            spec.loader.exec_module(mod)  # 不应抛 TypeError
        finally:
            sys.modules.pop("A_types_fixed", None)
        # rdf_type 是 ClassVar（类属性），不是实例字段
        assert mod.IdentifiedObject.rdf_type == "cim:IdentifiedObject"

    def test_rejects_invalid_package_name(self, tmp_path):
        """I2 修复：包名含路径分隔符或非法字符 → ValueError。"""
        from cim_ontology.ir.models import OntologyIR
        bad = Package(iri="http://x#X", name="../../etc/passwd")
        ir = OntologyIR(packages=[bad])
        adapter = PythonTypesAdapter()
        with pytest.raises(ValueError, match="非法包名"):
            adapter.emit(ir, tmp_path)

    def test_rejects_non_identifier_class_name(self, tmp_path):
        """I1 修复：类名含 Unicode 标点或关键字 → ValueError。"""
        bad_cls = ClassDef(name="Foo; import os")
        pkg = Package(iri="http://x#A", name="A", classes=[bad_cls])
        ir = OntologyIR(packages=[pkg])
        adapter = PythonTypesAdapter()
        with pytest.raises(ValueError, match="非法类名"):
            adapter.emit(ir, tmp_path)