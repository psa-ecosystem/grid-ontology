"""CLI to build PSA Semantic Packages from grid-ontology reference models.

Usage:
    .venv/bin/python scripts/build_psa_package.py [--all] [--output packages]
    .venv/bin/python scripts/build_psa_package.py --package-id power.grid.core
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cim_ontology.psa import build_psa_package
from cim_ontology.reference_models.builder import build_reference_ontology


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PSA Semantic Package from OntologyIR")
    parser.add_argument(
        "--package-id",
        default="power.equipment.transformer",
        help="PSA package ID to emit (default: power.equipment.transformer)",
    )
    parser.add_argument(
        "--output",
        default="packages",
        help="Output directory for packages (default: packages)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Emit all PSA packages in the reference ontology",
    )
    args = parser.parse_args()

    ir = build_reference_ontology()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        for pkg in ir.packages:
            if not pkg.package_id:
                print(f"Skipping {pkg.name}: no package_id")  # noqa: T201
                continue
            pkg_dir = build_psa_package(ir, pkg.package_id, output_dir)
            print(f"Built PSA package: {pkg_dir}")  # noqa: T201
    else:
        pkg_dir = build_psa_package(ir, args.package_id, output_dir)
        print(f"Built PSA package: {pkg_dir}")  # noqa: T201


if __name__ == "__main__":
    main()
