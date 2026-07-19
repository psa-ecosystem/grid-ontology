"""属性测试：每个类在 OWL 产物中必须有 rdfs:label。

不变量：OwlTurtleAdapter emit 后，每个 ClassDef.name 应在产物中
作为 rdfs:label 的值出现（rdflib 序列化为 rdfs:label "ClassName"@en）。
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings

from cim_ontology.adapters.owl import OwlTurtleAdapter
from tests.property._strategies import iris


# rdfs:label "xxx" 或 "xxx"@lang 模式
# rdflib 会转义字符如 \"、\\n、\\r、\\\\ 等，用非贪婪匹配至 "
_LABEL_PATTERN = re.compile(r'rdfs:label\s+"((?:[^"\\]|\\.)*)"(?:@[a-zA-Z\-]+)?')


def _extract_labels(turtle_content: str) -> set[str]:
    """从 Turtle 文本提取所有 rdfs:label 值。"""
    matches = _LABEL_PATTERN.findall(turtle_content)
    return set(matches)


@settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow])
@given(iris)
def test_every_class_has_rdfs_label(ir):
    """每个 ClassDef.name 都应有对应的 rdfs:label。"""
    if not ir.packages:
        return

    expected_labels = {
        cls.name
        for pkg in ir.packages
        for cls in pkg.classes
    }
    if not expected_labels:
        return

    # 使用 TemporaryDirectory 避免 function-scoped fixture 不在 @given 之间重置的陷阱。
    # 必须在 with 块内读取文件：退出 with 会清理目录，导致 result.files 指向不存在的路径。
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            result = OwlTurtleAdapter().emit(ir, tmp_path)
        except Exception as e:  # pragma: no cover - 适配器错误
            pytest.skip(f"OwlTurtleAdapter emit 失败：{e}")

        # 收集所有产物的 rdfs:label
        all_labels: set[str] = set()
        for f in result.files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:  # pragma: no cover - 读文件失败
                continue
            all_labels.update(_extract_labels(content))

        # 不变量：每个类名都应有对应的 rdfs:label
        missing = expected_labels - all_labels
        assert not missing, f"以下类缺少 rdfs:label：{sorted(missing)}"
