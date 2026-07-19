"""Build PSA-aligned grid ontology reference models and emit adapter artifacts.

Usage:
    .venv/bin/python scripts/build_reference_models.py --output build/reference
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cim_ontology.reference_models.builder import build_reference_ontology


def main() -> None:
    parser = argparse.ArgumentParser(description="Build grid-ontology reference models")
    parser.add_argument("--output", default="build/reference", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    ir = build_reference_ontology()

    # Serialize IR as JSON for inspection.
    ir_path = output_dir / "reference_ir.json"
    ir_path.write_text(ir.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote IR: {ir_path}")

    # Emit a simple manifest.
    manifest = {
        "schema_version": ir.schema_version,
        "package_count": ir.stats.package_count,
        "class_count": ir.stats.class_count,
        "attribute_count": ir.stats.attribute_count,
        "association_count": ir.stats.association_count,
        "packages": [pkg.name for pkg in ir.packages],
        "classes": [c.name for c in ir.all_classes()],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")

    print(f"\nReference ontology built: {ir.stats.class_count} classes across {ir.stats.package_count} packages")


if __name__ == "__main__":
    main()
