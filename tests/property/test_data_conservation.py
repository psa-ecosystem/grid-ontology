"""属性测试：端到端数据守恒。

不变量：经过 4 个适配器（OWL/SHACL/JSON Schema/Python Types）emit 后，
IR 中所有类的名称、包名称应至少在一个产物文件中出现（不可静默丢失）。
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings

from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.adapters.python_types import PythonTypesAdapter
from cim_ontology.adapters.shacl import ShaclAdapter
from tests.property._strategies import iris


def _isolated_tmp(tmp_path_factory) -> "object":
    """为每次 generated input 创建独立子目录。"""
    return tmp_path_factory.mktemp(f"dc_{uuid.uuid4().hex[:8]}")


def _all_content(result_files) -> str:
    """汇总产物中所有文件的文本内容。"""
    parts: list[str] = []
    for f in result_files:
        try:
            parts.append(f.read_text())
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(parts)


def _run_all_adapters(ir, out_dir) -> str:
    """运行 4 个适配器并汇总所有产物内容。"""
    all_text = ""
    for adapter_cls in (
        OwlTurtleAdapter,
        ShaclAdapter,
        JsonSchemaAdapter,
        PythonTypesAdapter,
    ):
        try:
            result = adapter_cls().emit(ir, out_dir)
        except Exception:  # noqa: BLE001 - 部分适配器可能对随机 IR 失败
            continue
        all_text += _all_content(result.files) + "\n"
    return all_text


@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_all_classes_appear_in_some_output(tmp_path_factory, ir):
    """所有 ClassDef.name 应至少出现在一个适配器的产物中（数据守恒）。"""
    if not ir.packages:
        pytest.skip("空 IR")

    expected_class_names = {
        cls.name for pkg in ir.packages for cls in pkg.classes
    }
    if not expected_class_names:
        pytest.skip("无类可检查")

    out = _isolated_tmp(tmp_path_factory)
    all_content = _run_all_adapters(ir, out)

    # 不变量：每个类名应至少在一个产物中出现
    missing = [n for n in expected_class_names if n not in all_content]
    assert not missing, f"以下类名未出现在任何产物中：{missing}"


@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_package_count_preserved(tmp_path_factory, ir):
    """包名称应在产物中保留（每个包名至少出现一次）。"""
    if not ir.packages:
        pytest.skip("空 IR")

    expected_pkg_names = {pkg.name for pkg in ir.packages}

    out = _isolated_tmp(tmp_path_factory)
    all_content = _run_all_adapters(ir, out)

    # 不变量：每个包名应至少出现一次
    missing_pkgs = [p for p in expected_pkg_names if p not in all_content]
    assert not missing_pkgs, f"以下包名未出现在产物中：{missing_pkgs}"


@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_attribute_names_appear_in_some_output(tmp_path_factory, ir):
    """所有 DataProperty.name 应至少在一个适配器的产物中出现。"""
    expected_attr_names = {
        attr.name
        for pkg in ir.packages
        for cls in pkg.classes
        for attr in cls.attributes
    }
    if not expected_attr_names:
        pytest.skip("无属性可检查")

    out = _isolated_tmp(tmp_path_factory)
    all_content = _run_all_adapters(ir, out)

    missing = [n for n in expected_attr_names if n not in all_content]
    assert not missing, f"以下属性名未出现在任何产物中：{missing}"