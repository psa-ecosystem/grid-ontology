"""B7 Stage 2: 属性名 OCR 修复单元测试。

覆盖：
  - _classify_attr_noise: 4 类噪声模式识别
  - resolve_attr_names: 完整 Stage 2 流程
  - 与 B6 resolve_association_targets 协同（互不干扰）
"""
from datetime import datetime, timezone

import pytest

from cim_ontology.cleaner.orchestrator import (
    _classify_attr_noise,
    resolve_attr_names,
)
from cim_ontology.ir.models import (
    ClassDef,
    DataProperty,
    Multiplicity,
    OntologyIR,
    Package,
    SourceInfo,
)


# ---------------------------------------------------------------------------
# _classify_attr_noise: 4 类噪声模式识别
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,kind", [
    # LaTeX 残骸（含 $ 或 \\）
    ("$\\mathcal { Z } \\mathcal { \\ Z }$", "latex"),
    ("$\\mathrm { m R I D }$", "latex"),
    ("$\\mathrm { p h a s e }$", "latex"),
    # 纯 CJK
    ("名字", "cjk"),
    ("类", "cjk"),
    ("描述", "cjk"),
    # Markdown 分隔符
    ("---", "separator"),
    (":---:", "separator"),
    # 混合标点（描述列泄露）
    ("name：foo", "mixed_punct"),
    ("test（1）", "mixed_punct"),
    # 合法 CamelCase（应保留 → None）
    ("aliasName", None),
    ("mRID", None),
    ("sequenceNumber", None),
    ("networkAnalysisEnabled", None),
])
def test_classify_attr_noise(name, kind):
    assert _classify_attr_noise(name) is kind


# ---------------------------------------------------------------------------
# resolve_attr_names: Stage 2 端到端
# ---------------------------------------------------------------------------


def _make_ir_for_attrs(classes: list[ClassDef]) -> OntologyIR:
    """单包 IR 用于 B7 端到端测试。"""
    return OntologyIR(
        packages=[Package(
            iri="http://test/TestPkg",
            name="TestPkg",
            classes=classes,
        )],
        uncertain_entries=[],
        source=SourceInfo(
            document_path="/test",
            document_sha256="x",
            parsed_at=datetime.now(timezone.utc),
            parser_version="0.2.0",
        ),
    )


def _cls_with_attrs(name: str, attr_names: list[str]) -> ClassDef:
    """构造带属性的 ClassDef。"""
    return ClassDef(
        name=name,
        attributes=[
            DataProperty(
                name=n,
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            )
            for n in attr_names
        ],
    )


class TestResolveAttrNames:
    """Stage 2 完整流程：4 类噪声清空 + 合法属性保留。"""

    def test_latex_attr_cleared(self):
        """LaTeX 残骸 → attr.name = '' + 计数 +1。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", ["$\\mathcal { Z }$"]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["latex"] == 1
        assert stats["total_cleaned"] == 1
        assert ir.packages[0].classes[0].attributes[0].name == ""

    def test_cjk_attr_cleared(self):
        """纯 CJK → attr.name = '' + cjk 计数 +1。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", ["名字", "类"]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["cjk"] == 2
        assert ir.packages[0].classes[0].attributes[1].name == ""

    def test_separator_attr_cleared(self):
        """Markdown 分隔符 → attr.name = '' + separator 计数 +1。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", ["---", ":---:"]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["separator"] == 2

    def test_mixed_punct_attr_cleared(self):
        """混合标点 → attr.name = '' + mixed_punct 计数 +1。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", ["name：foo", "test（1）"]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["mixed_punct"] == 2

    def test_valid_attrs_kept(self):
        """合法 CamelCase 不动 + kept 计数累加。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", ["aliasName", "mRID", "sequenceNumber"]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["kept"] == 3
        assert stats["total_cleaned"] == 0
        attrs = ir.packages[0].classes[0].attributes
        assert attrs[0].name == "aliasName"
        assert attrs[1].name == "mRID"
        assert attrs[2].name == "sequenceNumber"

    def test_mixed_noise_and_valid(self):
        """混合场景：噪声清空 + 合法保留，列表长度不变。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", [
                "$\\mathcal { Z }$",  # latex
                "名字",                # cjk
                "aliasName",           # valid
                "---",                 # separator
            ]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["latex"] == 1
        assert stats["cjk"] == 1
        assert stats["separator"] == 1
        assert stats["kept"] == 1
        assert stats["total_cleaned"] == 3
        attrs = ir.packages[0].classes[0].attributes
        assert len(attrs) == 4
        assert attrs[0].name == ""
        assert attrs[1].name == ""
        assert attrs[2].name == "aliasName"
        assert attrs[3].name == ""

    def test_empty_name_attr_kept(self):
        """name 已为空字符串 → 视为合法，kept +1。"""
        ir = _make_ir_for_attrs([
            _cls_with_attrs("ClassA", [""]),
        ])
        stats = resolve_attr_names(ir)
        assert stats["kept"] == 1
        assert stats["total_cleaned"] == 0


# ---------------------------------------------------------------------------
# 与 B6 resolve_association_targets 协同：互不干扰
# ---------------------------------------------------------------------------


def test_b6_b7_independent_counting():
    """B6 修复 target + B7 修复 attr.name 应独立计数。"""
    from cim_ontology.cleaner.orchestrator import resolve_association_targets
    from cim_ontology.ir.models import (
        ClassDef, ClassRef, Multiplicity, ObjectProperty,
        DataProperty,
    )

    # 构造 IR：ClassA 含一个噪声 attr + 一个含噪声 target 的 assoc
    cls_a = ClassDef(
        name="ClassA",
        attributes=[
            DataProperty(
                name="$\\mathcal { Z }$",  # B7 噪声
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            ),
            DataProperty(
                name="aliasName",  # 合法
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            ),
        ],
        associations=[
            ObjectProperty(
                name="rel1",
                target=ClassRef(package="TestPkg", class_name="---"),  # B6 噪声
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            ),
        ],
    )
    cls_b = ClassDef(name="ClassB")  # 已知类名（用于 B6 fuzzy 不命中）

    ir = _make_ir_for_attrs([cls_a, cls_b])

    # 顺序：先 B6 后 B7（与 clean_markdown_to_ir 一致）
    b6_stats = resolve_association_targets(ir)
    b7_stats = resolve_attr_names(ir)

    # B6 计数：1 noise_dropped（target="---"）
    assert b6_stats["noise_dropped"] == 1
    # B7 计数：1 latex（attr="$\\mathcal{Z}$"），1 kept（aliasName）
    assert b7_stats["latex"] == 1
    assert b7_stats["kept"] == 1
    # 互不干扰：B6 不动 attr.name，B7 不动 target.class_name
    assert ir.packages[0].classes[0].attributes[0].name == ""
    assert ir.packages[0].classes[0].associations[0].target.class_name is None


def test_b7_does_not_touch_associations():
    """B7 不应修改任何 association 字段。"""
    from cim_ontology.ir.models import ClassRef, ObjectProperty

    cls_a = ClassDef(
        name="ClassA",
        attributes=[DataProperty(name="名字", multiplicity=Multiplicity(min=0, max=1, raw="0..1"))],
        associations=[
            ObjectProperty(
                name="rel1",
                target=ClassRef(package="TestPkg", class_name="ClassB"),
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            ),
        ],
    )
    cls_b = ClassDef(name="ClassB")
    ir = _make_ir_for_attrs([cls_a, cls_b])

    # 仅跑 B7（不跑 B6），association 应保持原样
    resolve_attr_names(ir)

    assoc = ir.packages[0].classes[0].associations[0]
    assert assoc.name == "rel1"
    assert assoc.target.class_name == "ClassB"


def test_b6_does_not_touch_attributes():
    """B6 不应修改任何 attribute 字段。"""
    from cim_ontology.cleaner.orchestrator import resolve_association_targets
    from cim_ontology.ir.models import ClassRef, ObjectProperty

    cls_a = ClassDef(
        name="ClassA",
        attributes=[DataProperty(name="aliasName", multiplicity=Multiplicity(min=0, max=1, raw="0..1"))],
        associations=[
            ObjectProperty(
                name="rel1",
                target=ClassRef(package="TestPkg", class_name="---"),
                multiplicity=Multiplicity(min=0, max=1, raw="0..1"),
            ),
        ],
    )
    ir = _make_ir_for_attrs([cls_a])

    # 仅跑 B6（不跑 B7），attribute 应保持原样
    resolve_association_targets(ir)

    attr = ir.packages[0].classes[0].attributes[0]
    assert attr.name == "aliasName"  # B6 不动 attr.name


def test_b7_idempotent():
    """重复运行 B7 不会重复计数（空字符串视为合法）。"""
    ir = _make_ir_for_attrs([
        _cls_with_attrs("ClassA", ["名字", "$\\mathcal { Z }$"]),
    ])
    stats1 = resolve_attr_names(ir)
    stats2 = resolve_attr_names(ir)
    # 第一次：2 cleaned
    assert stats1["total_cleaned"] == 2
    # 第二次：0 cleaned（已空字符串被 kept）
    assert stats2["total_cleaned"] == 0
    assert stats2["kept"] == 2
