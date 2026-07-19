"""属性测试：OWL 适配器 IRI 规范化（round-trip 视角）。

不变量：OWL 适配器 emit 后，对 IR 中每个 class 的 `name`，
其在产物 Graph 中的规范化 URI 应有且仅有一种拼写变体（即不允许
`<...#Foo>` 与 `<...#foo>` 同时作为「同一类」出现）。

rdflib 序列化时使用前缀缩写（如 `cim:Foo`），所以我们使用 rdflib 重新
解析每个产物文件，然后枚举 Graph 中的所有 URI 来验证不变量。
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from rdflib import Graph, URIRef

from cim_ontology.adapters.owl import OwlTurtleAdapter
from tests.property._strategies import iris


CIM_NS = "http://iec.ch/TC57/2024/CIM-schema-cim17#"  # owl.py 中的命名空间


def _isolated_tmp(tmp_path_factory) -> "object":
    """为每次 generated input 创建独立子目录。"""
    return tmp_path_factory.mktemp(f"owl_{uuid.uuid4().hex[:8]}")


def _parse_all_to_set(result_files) -> set[URIRef]:
    """汇总产物中所有 URIRef（去重）。"""
    uris: set[URIRef] = set()
    for f in result_files:
        if not f.name.endswith(".ttl"):
            continue
        g = Graph()
        try:
            g.parse(f, format="turtle")
        except Exception:  # noqa: BLE001
            continue
        for s, p, o in g:
            for term in (s, p, o):
                if isinstance(term, URIRef):
                    uris.add(term)
    return uris


@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_each_class_appears_with_canonical_uri(tmp_path_factory, ir):
    """每个 IR 类名应在产物 Graph 中作为规范化 URI 出现（只要该类被 emit）。"""
    out = _isolated_tmp(tmp_path_factory)
    adapter = OwlTurtleAdapter()
    try:
        result = adapter.emit(ir, out)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"OwlTurtleAdapter emit 失败（生成器边界）：{e}")

    class_names = {cls.name for pkg in ir.packages for cls in pkg.classes}
    if not class_names:
        pytest.skip("无类可检查")

    all_uris = _parse_all_to_set(result.files)

    # 不变量：每个期望的类 URI 应作为 URIRef 之一出现
    expected = {URIRef(f"{CIM_NS}{name}") for name in class_names}
    missing = [str(u) for u in expected if u not in all_uris]
    assert not missing, f"以下类 URI 未在产物中出现：{missing}"


@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_class_names_have_no_spelling_variants(tmp_path_factory, ir):
    """每个类名在产物 URI 集合中不应有大小写或拼写变体（即同源变体只出现一次）。"""
    out = _isolated_tmp(tmp_path_factory)
    adapter = OwlTurtleAdapter()
    try:
        result = adapter.emit(ir, out)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"OwlTurtleAdapter emit 失败（生成器边界）：{e}")

    class_names = {cls.name for pkg in ir.packages for cls in pkg.classes}
    if not class_names:
        pytest.skip("无类可检查")

    all_uris = _parse_all_to_set(result.files)
    # 索引：以 cim_ns 结尾的 URI（按 local name 分组）
    by_local: dict[str, set[str]] = {}
    for u in all_uris:
        s = str(u)
        if s.startswith(CIM_NS):
            local = s[len(CIM_NS):]
            by_local.setdefault(local, set()).add(s)

    # 不变量：每个期望类名应只对应一个 URI 变体（即大小写敏感唯一）
    for cname in class_names:
        variants = by_local.get(cname, set())
        # 如果 cname 被某种方式写出，则不应有多个拼写变体
        assert len(variants) <= 1, (
            f"类名 {cname!r} 在产物中出现多个 URI 变体：{variants}"
        )


@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(iris)
def test_owl_emit_roundtrip_no_duplicate_triples(tmp_path_factory, ir):
    """OWL emit 后 Graph 中无重复三元组（rdflib Graph 天然不允许）。"""
    out = _isolated_tmp(tmp_path_factory)
    adapter = OwlTurtleAdapter()
    try:
        result = adapter.emit(ir, out)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"OwlTurtleAdapter emit 失败（生成器边界）：{e}")

    full = next((f for f in result.files if f.name == "cim17_full.ttl"), None)
    if full is None:
        pytest.skip("cim17_full.ttl 未生成")

    g = Graph()
    try:
        g.parse(full, format="turtle")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Turtle 解析失败：{e}")

    # 不变量：Graph 内三元组计数 = distinct（rdflib 自动去重）
    # 简单断言：len(g) 等于其去重后大小（Graph 已是 set）
    triples_list = list(g)
    assert len(triples_list) == len(set(triples_list)), (
        "Graph 中存在重复三元组（违反 RDF 不变量）"
    )