"""OWL reasoning smoke test for PSA Semantic Packages (GAP-003).

Proves the generated OWL ontology is not just well-formed Turtle, but
that RDFS/OWL semantics actually fire on it — specifically, the
transitive closure of ``rdfs:subClassOf`` must propagate multi-hop
inheritance (PowerTransformer → Transformer → Equipment).

This is the kind of guarantee that SHACL/JSON Schema cannot give
(SHACL sees only the asserted graph), yet PSA interop depends on it
when downstream tools compute ``instanceOf`` or run SHACL against
shapes declared on parent classes.

PSA packages are independent units: each emits only its own classes,
with cross-package parents referenced by IRI (not inlined). Real
interop follows the workflow ``manifest.dependencies → fetch →
merge graphs → reason``. This test exercises exactly that flow.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from owlrl import DeductiveClosure, RDFS_Semantics
from rdflib import RDFS, Graph, URIRef

from cim_ontology.psa import build_psa_package
from cim_ontology.reference_models.builder import build_reference_ontology

NS_CORE = "https://grid-ontology.org/psa/v0.2/core/"
NS_EQUIPMENT = "https://grid-ontology.org/psa/v0.2/equipment/"
NS_TRANSFORMER = "https://grid-ontology.org/psa/v0.2/transformer/"


@pytest.fixture(scope="module")
def all_psa_pkgs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scoped root dir containing all reference PSA packages built."""
    ir = build_reference_ontology()
    out = tmp_path_factory.mktemp("psa_reasoning")
    for pkg in ir.packages:
        if pkg.package_id:
            build_psa_package(ir, pkg.package_id, out)
    return out


def _merge_closure(root: Path, pkg_ids: list[str]) -> Graph:
    """Parse OWL for each package and apply RDFS deductive closure to the union."""
    g = Graph()
    for pkg_id in pkg_ids:
        slug = pkg_id.split(".")[-1]
        owl = root / f"{slug}-0.1.0" / "ontology" / f"{slug}.owl"
        g.parse(str(owl), format="turtle")
    DeductiveClosure(RDFS_Semantics).expand(g)
    return g


def _dependencies_of(root: Path, pkg_id: str) -> list[str]:
    """Read manifest.dependencies for a built package (simulates consumer fetch)."""
    slug = pkg_id.split(".")[-1]
    manifest = yaml.safe_load(
        (root / f"{slug}-0.1.0" / "manifest.yaml").read_text()
    )
    return list(manifest["package"]["dependencies"])


class TestRDFSReasoning:
    """GAP-003: rdfs:subClassOf transitive closure must hold across packages."""

    def test_power_transformer_is_a_transformer(self, all_psa_pkgs: Path) -> None:
        """Single-package closure: PowerTransformer -> Transformer is asserted."""
        g = _merge_closure(all_psa_pkgs, ["power.equipment.transformer"])
        pt = URIRef(f"{NS_TRANSFORMER}PowerTransformer")
        transformer = URIRef(f"{NS_EQUIPMENT}Transformer")
        assert (pt, RDFS.subClassOf, transformer) in g

    def test_power_transformer_is_a_equipment_after_dependency_merge(
        self, all_psa_pkgs: Path,
    ) -> None:
        """GAP-003 core: merge with manifest.dependencies, then close.

        Consumer workflow: read manifest → fetch power.equipment →
        merge → reason. PowerTransformer must be inferred as
        rdfs:subClassOf Equipment via Transformer (multi-hop).
        """
        deps = _dependencies_of(all_psa_pkgs, "power.equipment.transformer")
        assert "power.equipment" in deps, (
            "manifest.dependencies must declare power.equipment for PSA interop"
        )
        g = _merge_closure(
            all_psa_pkgs,
            ["power.equipment.transformer", "power.equipment", "power.grid.core"],
        )
        pt = URIRef(f"{NS_TRANSFORMER}PowerTransformer")
        equipment = URIRef(f"{NS_CORE}Equipment")
        assert (pt, RDFS.subClassOf, equipment) in g, (
            "RDFS closure failed across packages: PowerTransformer must be "
            "inferred as rdfs:subClassOf Equipment via Transformer (multi-hop)"
        )

    def test_transformer_is_a_equipment(self, all_psa_pkgs: Path) -> None:
        """Sanity: Equipment parent is asserted by equipment.owl + core.owl merge."""
        g = _merge_closure(all_psa_pkgs, ["power.equipment", "power.grid.core"])
        transformer = URIRef(f"{NS_EQUIPMENT}Transformer")
        equipment = URIRef(f"{NS_CORE}Equipment")
        assert (transformer, RDFS.subClassOf, equipment) in g
