"""命名空间清洗器测试。"""
import pytest

from cim_ontology.cleaner.namespace import (
    UnknownNamespace,
    auto_correct_namespaces,
    clean_namespace,
    collect_namespace_aliases,
)


class TestCleanNamespace:
    def test_known_prefix_cim(self):
        assert clean_namespace("cim:") == "http://iec.ch/TC57/2024/CIM-schema-cim17#"

    def test_known_prefix_rdfs(self):
        assert clean_namespace("rdfs:") == "http://www.w3.org/2000/01/rdf-schema#"

    def test_unknown_raises(self):
        with pytest.raises(UnknownNamespace):
            clean_namespace("unknown:")


class TestCollectNamespaceAliases:
    def test_collects_unique_prefixes(self):
        content = "cim:Foo cim:Bar rdfs:Label"
        aliases = collect_namespace_aliases(content)
        assert aliases["cim"] == 2
        assert aliases["rdfs"] == 1


class TestAutoCorrect:
    def test_corrects_close_misspellings(self):
        # cin: → cim:（距离 1）
        aliases = {"cin": 5, "cim": 10, "rdfts": 2}
        corrections = auto_correct_namespaces(aliases)
        assert corrections.get("cin") == "cim"
        assert corrections.get("rdfts") == "rdfs"
        # 已正确的不纠正
        assert "cim" not in corrections
