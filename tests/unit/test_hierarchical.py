"""层级推断测试。"""
from cim_ontology.cleaner.hierarchical import (
    SectionContext,
    hierarchical_classify_section,
)


class TestHierarchicalClassify:
    def test_infer_depth_from_numbering(self):
        ctx = hierarchical_classify_section("6.1.2 Class: Foo", [])
        assert ctx.depth == 3
        assert ctx.confidence >= 0.8

    def test_top_level_number(self):
        ctx = hierarchical_classify_section("7 Package Overview", [])
        assert ctx.depth == 1

    def test_class_keyword_fallback(self):
        ctx = hierarchical_classify_section("Class: Foo", [])
        assert ctx.depth == 3  # 默认推断
        assert ctx.confidence < 0.8  # 置信度低

    def test_no_signal_returns_low_confidence(self):
        ctx = hierarchical_classify_section("Random Title", [])
        assert ctx.confidence < 0.5

    def test_full_depth_four_levels(self):
        ctx = hierarchical_classify_section("6.2.3.4 Subsection", [])
        assert ctx.depth == 4
