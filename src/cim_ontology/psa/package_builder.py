"""PSA Semantic Package builder.

Consumes a grid-ontology OntologyIR and emits a PSA-compatible package
directory per docs/governance/psa-semantic-package-contract.md.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

from cim_ontology.ir.models import ClassDef, DataProperty, ObjectProperty, OntologyIR, Package


class PackageNotFoundError(ValueError):
    """Raised when the requested package_id is not present in OntologyIR."""


class PSAPackageBuilder:
    """Build a PSA Semantic Package from a single OntologyIR package."""

    def __init__(self, ir: OntologyIR, package_id: str) -> None:
        self.ir = ir
        self.package = self._find_package(package_id)
        self.pkg_id = package_id
        self.pkg_name = self.package.package_id or self._slug_from_name(self.package.name)
        self.version = self.package.version or "0.1.0"
        self.ns = Namespace(self.package.iri.rstrip("/") + "/")
        self.slug = self._slug_from_name(package_id.split(".")[-1])
        self.output_dir: Path | None = None

    def _find_package(self, package_id: str) -> Package:
        for pkg in self.ir.packages:
            if pkg.package_id == package_id:
                return pkg
        raise PackageNotFoundError(f"Package {package_id!r} not found in OntologyIR")

    @staticmethod
    def _slug_from_name(name: str) -> str:
        return "".join([c if c.isalnum() else "-" for c in name]).lower().strip("-")

    @staticmethod
    def _safe_iri_local(name: str | None) -> str:
        if not name:
            return "_"
        # Keep ASCII alphanumeric, underscore, hyphen; replace others with underscore.
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    @staticmethod
    def _xsd_to_psa_type(data_type: str | None) -> str:
        mapping = {
            "xsd:string": "String",
            "xsd:boolean": "Boolean",
            "xsd:integer": "Integer",
            "xsd:int": "Integer",
            "xsd:double": "Decimal",
            "xsd:decimal": "Decimal",
            "xsd:date": "Date",
            "xsd:dateTime": "DateTime",
            "xsd:anyURI": "IRI",
        }
        return mapping.get(data_type or "", "String")

    @staticmethod
    def _xsd_to_json_schema_type(data_type: str | None) -> dict[str, Any]:
        mapping: dict[str, dict[str, Any]] = {
            "xsd:string": {"type": "string"},
            "xsd:boolean": {"type": "boolean"},
            "xsd:integer": {"type": "integer"},
            "xsd:int": {"type": "integer"},
            "xsd:double": {"type": "number"},
            "xsd:decimal": {"type": "number"},
            "xsd:date": {"type": "string", "format": "date"},
            "xsd:dateTime": {"type": "string", "format": "date-time"},
            "xsd:anyURI": {"type": "string", "format": "uri"},
        }
        return mapping.get(data_type or "", {"type": "string"})

    @staticmethod
    def _multiplicity_to_str(multiplicity: Any) -> str:
        if multiplicity is None:
            return "0..1"
        if hasattr(multiplicity, "raw"):
            return multiplicity.raw
        return str(multiplicity)

    def _entity_id(self, cls: ClassDef) -> str:
        return f"{self.pkg_id}.{cls.name}"

    def _attribute_id(self, cls: ClassDef, attr: DataProperty) -> str:
        return f"{self.pkg_id}.{attr.name}"

    def _relation_id(self, cls: ClassDef, assoc: ObjectProperty) -> str:
        return f"{self.pkg_id}.{assoc.name}"

    def _class_iri(self, cls: ClassDef) -> str:
        return str(self.ns[cls.name])

    def _target_iri(self, assoc: ObjectProperty) -> str:
        target = assoc.target
        if target.iri:
            return target.iri
        resolved = self._resolve_class_iri(target.package, target.class_name)
        if resolved:
            return resolved
        return f"{self.package.iri.rstrip('/')}/{self._safe_iri_local(target.class_name)}"

    def _resolve_package_iri(self, package_name: str) -> str:
        for pkg in self.ir.packages:
            if pkg.name == package_name:
                return pkg.iri.rstrip("/")
        return self.package.iri.rstrip("/")

    def _resolve_class_iri(self, package_name: str, class_name: str | None) -> str | None:
        if not class_name:
            return None
        return f"{self._resolve_package_iri(package_name)}/{class_name}"

    def _resolve_target_entity_id(self, assoc: ObjectProperty) -> str | None:
        target = assoc.target
        for pkg in self.ir.packages:
            if pkg.name == target.package and pkg.package_id and target.class_name:
                return f"{pkg.package_id}.{target.class_name}"
        return None

    def _validate_cross_refs(self) -> list[str]:
        """Verify every parent and association target resolves to a class in the IR.

        Returns a list of human-readable issues; empty when all references
        resolve. Covers CTS gap GAP-004 (cross-reference integrity).
        """
        known = {(pkg.name, c.name) for pkg in self.ir.packages for c in pkg.classes}
        issues: list[str] = []
        for cls in self.package.classes:
            for parent in cls.parents:
                if parent.class_name and (parent.package, parent.class_name) not in known:
                    issues.append(
                        f"{cls.name}: parent {parent.package}::{parent.class_name} not found in IR"
                    )
            for assoc in cls.associations:
                target = assoc.target
                if target.class_name and (target.package, target.class_name) not in known:
                    issues.append(
                        f"{cls.name}.{assoc.name}: target {target.package}::{target.class_name}"
                        " not found in IR"
                    )
        return issues

    def build(self, output_dir: Path) -> Path:
        """Emit the complete PSA package and return the package directory."""
        ref_issues = self._validate_cross_refs()
        if ref_issues:
            raise ValueError(
                "Unresolved cross-package references:\n" + "\n".join(f"  - {i}" for i in ref_issues)
            )

        pkg_dir = output_dir / f"{self.slug}-{self.version}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = pkg_dir

        (pkg_dir / "semantic-model").mkdir(exist_ok=True)
        (pkg_dir / "ontology").mkdir(exist_ok=True)
        (pkg_dir / "constraints").mkdir(exist_ok=True)
        (pkg_dir / "jsonld").mkdir(exist_ok=True)
        (pkg_dir / "jsonschema").mkdir(exist_ok=True)
        (pkg_dir / "python").mkdir(exist_ok=True)
        (pkg_dir / "examples").mkdir(exist_ok=True)
        (pkg_dir / "mappings").mkdir(exist_ok=True)
        (pkg_dir / "tests").mkdir(exist_ok=True)

        self._write_manifest()
        self._write_readme()
        self._write_entities()
        self._write_attributes()
        self._write_relations()
        self._write_enumerations()
        self._write_owl()
        self._write_shacl()
        self._write_jsonld_context()
        self._write_jsonschema()
        self._write_python_types()
        self._write_example()
        self._write_mapping_template()
        self._write_cts()

        return pkg_dir

    # ------------------------------------------------------------------ YAML

    def _artifact_path(self, subdir: str, filename_suffix: str) -> Path:
        """Return ``output_dir/subdir/<pkg-slug><suffix>`` for a generated artifact."""
        assert self.output_dir is not None
        return self.output_dir / subdir / f"{self.slug}{filename_suffix}"

    def _dump_yaml(self, data: Any, path: Path) -> None:
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    def _dump_semantic_model(self, data: Any, filename: str) -> None:
        """Dump a semantic-model YAML artifact (entities/attributes/relations/enumerations)."""
        assert self.output_dir is not None
        self._dump_yaml(data, self.output_dir / "semantic-model" / filename)

    def _write_manifest(self) -> None:
        assert self.output_dir is not None
        manifest = {
            "package": {
                "id": self.pkg_id,
                "name": self.package.name,
                "version": self.version,
                "producer": "grid-ontology",
                "source_ir": self.package.iri,
                "compatibility": {"psa": ">=0.1"},
                "status": "draft",
                "maturity": "reference",
                "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "generator": "cim-ontology 1.7.0",
                "dependencies": self._collect_dependencies(),
            }
        }
        self._dump_yaml(manifest, self.output_dir / "manifest.yaml")

    def _dependency_id(self, package_name: str) -> str | None:
        """Return the PSA package_id for an IR package name, excluding this package."""
        for pkg in self.ir.packages:
            if pkg.name == package_name and pkg.package_id and pkg.package_id != self.pkg_id:
                return pkg.package_id
        return None

    def _collect_dependencies(self) -> list[str]:
        deps: set[str] = set()
        for cls in self.package.classes:
            for parent in cls.parents:
                if dep := self._dependency_id(parent.package):
                    deps.add(dep)
            for assoc in cls.associations:
                if dep := self._dependency_id(assoc.target.package):
                    deps.add(dep)
        return sorted(deps)

    def _write_readme(self) -> None:
        assert self.output_dir is not None
        lines = [
            f"# {self.package.name}",
            "",
            f"**Package ID**: `{self.pkg_id}`  ",
            f"**Version**: `{self.version}`  ",
            f"**Namespace**: `{self.package.iri}`  ",
            "",
            "## Overview",
            "",
            self.package.description
            or "PSA-compatible semantic package generated by grid-ontology.",
            "",
            "## Contents",
            "",
            "- `semantic-model/` — entities, attributes, relations, enumerations",
            "- `ontology/` — OWL 2 ontology",
            "- `constraints/` — SHACL shapes",
            "- `jsonld/` — JSON-LD context",
            "- `jsonschema/` — JSON Schema definitions",
            "- `python/` — Python dataclasses",
            "- `examples/` — instance examples",
            "- `mappings/` — external system mapping template",
            "- `tests/` — CTS declaration",
            "",
        ]
        (self.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_entities(self) -> None:
        assert self.output_dir is not None
        entities = []
        for cls in self.package.classes:
            parents = []
            for parent in cls.parents:
                if parent.class_name:
                    parent_iri = parent.iri or self._resolve_class_iri(
                        parent.package, parent.class_name
                    )
                    if parent_iri:
                        parents.append({"iri": parent_iri, "package": parent.package})
            entities.append({
                "id": self._entity_id(cls),
                "name": cls.name,
                "display_name": cls.name,
                "primitive": "Entity",
                "namespace": str(self.ns),
                "iri": self._class_iri(cls),
                "description": cls.description,
                "parents": parents,
                "package_id": self.pkg_id,
                "source_refs": [],
            })
        self._dump_semantic_model({"entities": entities}, "entities.yaml")

    def _write_attributes(self) -> None:
        assert self.output_dir is not None
        attributes = []
        for cls in self.package.classes:
            for attr in cls.attributes:
                attributes.append({
                    "id": self._attribute_id(cls, attr),
                    "name": attr.name,
                    "display_name": attr.name,
                    "primitive": "Attribute",
                    "domain": {
                        "entity_id": self._entity_id(cls),
                        "iri": self._class_iri(cls),
                    },
                    "range": {
                        "type": self._xsd_to_psa_type(attr.data_type),
                        "xsd": attr.data_type or "xsd:string",
                        "unit": None,
                    },
                    "required": attr.required,
                    "multiplicity": self._multiplicity_to_str(attr.multiplicity),
                    "description": attr.description,
                })
        self._dump_semantic_model({"attributes": attributes}, "attributes.yaml")

    def _write_relations(self) -> None:
        assert self.output_dir is not None
        relations = []
        for cls in self.package.classes:
            for assoc in cls.associations:
                target_id = self._resolve_target_entity_id(assoc)
                relations.append({
                    "id": self._relation_id(cls, assoc),
                    "name": assoc.name,
                    "display_name": assoc.name,
                    "primitive": "Relation",
                    "source": {
                        "entity_id": self._entity_id(cls),
                        "iri": self._class_iri(cls),
                    },
                    "target": {
                        "entity_id": target_id,
                        "iri": self._target_iri(assoc),
                    },
                    "multiplicity": self._multiplicity_to_str(assoc.multiplicity),
                    "inverse_name": assoc.inverse_name,
                    "description": assoc.description,
                })
        self._dump_semantic_model({"relations": relations}, "relations.yaml")

    def _write_enumerations(self) -> None:
        assert self.output_dir is not None
        if not self.package.enumerations:
            return
        enums = []
        for enum in self.package.enumerations:
            enums.append({
                "id": f"{self.pkg_id}.{enum.name}",
                "name": enum.name,
                "package_id": self.pkg_id,
                "values": [{"value": v, "label": v} for v in enum.values],
                "description": enum.description,
            })
        self._dump_semantic_model({"enumerations": enums}, "enumerations.yaml")

    # ------------------------------------------------------------------ OWL

    def _write_owl(self) -> None:
        assert self.output_dir is not None
        g = Graph()
        g.bind("psa", self.ns)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        onto_iri = URIRef(str(self.ns).rstrip("/"))
        g.add((onto_iri, RDF.type, OWL.Ontology))
        g.add((onto_iri, OWL.versionInfo, Literal(self.version)))
        g.add((onto_iri, RDFS.label, Literal(self.package.name, lang="en")))

        for cls in self.package.classes:
            cls_iri = URIRef(self._class_iri(cls))
            g.add((cls_iri, RDF.type, OWL.Class))
            g.add((cls_iri, RDFS.label, Literal(cls.name, lang="en")))
            if cls.description:
                g.add((cls_iri, RDFS.comment, Literal(cls.description, lang="zh")))
            for parent in cls.parents:
                if parent.class_name:
                    parent_iri_str = parent.iri or self._resolve_class_iri(
                        parent.package, parent.class_name
                    )
                    fallback_iri = f"{self.package.iri.rstrip('/')}/{parent.class_name}"
                    parent_iri = URIRef(parent_iri_str or fallback_iri)
                    g.add((cls_iri, RDFS.subClassOf, parent_iri))

            for attr in cls.attributes:
                prop_iri = URIRef(f"{self.ns}{cls.name}.{attr.name}")
                g.add((prop_iri, RDF.type, OWL.DatatypeProperty))
                g.add((prop_iri, RDFS.label, Literal(attr.name, lang="en")))
                g.add((prop_iri, RDFS.domain, cls_iri))
                range_iri = self._xsd_to_owl_range(attr.data_type)
                g.add((prop_iri, RDFS.range, range_iri))

            for assoc in cls.associations:
                prop_iri = URIRef(f"{self.ns}{cls.name}.{assoc.name}")
                g.add((prop_iri, RDF.type, OWL.ObjectProperty))
                g.add((prop_iri, RDFS.label, Literal(assoc.name, lang="en")))
                g.add((prop_iri, RDFS.domain, cls_iri))
                g.add((prop_iri, RDFS.range, URIRef(self._target_iri(assoc))))

        out_path = self._artifact_path("ontology", ".owl")
        g.serialize(out_path, format="turtle")

    @staticmethod
    def _xsd_to_owl_range(data_type: str | None) -> URIRef:
        mapping = {
            "xsd:string": XSD.string,
            "xsd:boolean": XSD.boolean,
            "xsd:integer": XSD.integer,
            "xsd:int": XSD.integer,
            "xsd:double": XSD.double,
            "xsd:decimal": XSD.decimal,
            "xsd:date": XSD.date,
            "xsd:dateTime": XSD.dateTime,
            "xsd:anyURI": XSD.anyURI,
        }
        return mapping.get(data_type or "", XSD.string)

    # ------------------------------------------------------------------ SHACL

    def _write_shacl(self) -> None:
        assert self.output_dir is not None
        g = Graph()
        sh = Namespace("http://www.w3.org/ns/shacl#")
        g.bind("sh", sh)
        g.bind("psa", self.ns)

        for cls in self.package.classes:
            shape_iri = URIRef(f"{self.ns}{cls.name}Shape")
            cls_iri = URIRef(self._class_iri(cls))
            g.add((shape_iri, RDF.type, sh.NodeShape))
            g.add((shape_iri, sh.targetClass, cls_iri))
            g.add((shape_iri, RDFS.label, Literal(f"{cls.name} shape", lang="en")))

            for attr in cls.attributes:
                prop_shape = URIRef(f"{self.ns}{cls.name}.{attr.name}Shape")
                g.add((shape_iri, sh.property, prop_shape))
                g.add((prop_shape, RDF.type, sh.PropertyShape))
                g.add((prop_shape, sh.path, URIRef(f"{self.ns}{cls.name}.{attr.name}")))
                g.add((prop_shape, sh.datatype, self._xsd_to_owl_range(attr.data_type)))
                if attr.required:
                    g.add((prop_shape, sh.minCount, Literal(1)))
                mult = attr.multiplicity
                if mult is not None:
                    if mult.max is not None and mult.max <= 1:
                        g.add((prop_shape, sh.maxCount, Literal(1)))

            for assoc in cls.associations:
                prop_shape = URIRef(f"{self.ns}{cls.name}.{assoc.name}Shape")
                g.add((shape_iri, sh.property, prop_shape))
                g.add((prop_shape, RDF.type, sh.PropertyShape))
                g.add((prop_shape, sh.path, URIRef(f"{self.ns}{cls.name}.{assoc.name}")))
                g.add((prop_shape, sh.class_, URIRef(self._target_iri(assoc))))
                mult = assoc.multiplicity
                if mult is not None:
                    if mult.min is not None:
                        g.add((prop_shape, sh.minCount, Literal(mult.min)))
                    if mult.max is not None:
                        g.add((prop_shape, sh.maxCount, Literal(mult.max)))

        out_path = self._artifact_path("constraints", ".shacl")
        g.serialize(out_path, format="turtle")

    # ------------------------------------------------------------------ JSON-LD

    def _write_jsonld_context(self) -> None:
        assert self.output_dir is not None
        context: dict[str, Any] = {
            "@vocab": str(self.ns),
            "id": "@id",
            "type": "@type",
        }
        for cls in self.package.classes:
            context[cls.name] = {"@id": self._class_iri(cls), "@type": "@id"}
            for attr in cls.attributes:
                context[attr.name] = {"@id": f"{self.ns}{cls.name}.{attr.name}"}
            for assoc in cls.associations:
                context[assoc.name] = {"@id": f"{self.ns}{cls.name}.{assoc.name}", "@type": "@id"}
        for enum in self.package.enumerations:
            context[enum.name] = {"@id": f"{self.ns}{enum.name}", "@type": "@id"}

        out_path = self._artifact_path("jsonld", "-context.jsonld")
        out_path.write_text(
            json.dumps({"@context": context}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ JSON Schema

    def _write_jsonschema(self) -> None:
        """Emit JSON Schema describing the JSON-LD surface document.

        The schema validates the *surface* JSON document form used by the
        package's own examples: a root object holding ``@context`` and a
        ``@graph`` array whose nodes are typed per class. Each node carries
        ``@type`` / ``id`` plus attribute and relation terms.
        """
        assert self.output_dir is not None
        defs: dict[str, Any] = {}
        class_names: list[str] = []
        for cls in self.package.classes:
            class_names.append(cls.name)
            props: dict[str, Any] = {}
            required = ["@type", "id"]
            for attr in cls.attributes:
                props[attr.name] = self._xsd_to_json_schema_type(attr.data_type)
                if attr.required:
                    required.append(attr.name)
            for assoc in cls.associations:
                mult = assoc.multiplicity
                if mult is not None and (mult.max is None or mult.max > 1):
                    props[assoc.name] = {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                else:
                    props[assoc.name] = {"type": "string"}
            defs[cls.name] = {
                "type": "object",
                "properties": {
                    "@type": {"const": cls.name},
                    "id": {"type": "string"},
                    **props,
                },
                "required": required,
                "additionalProperties": False,
            }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"{self.ns}schema",
            "title": self.package.name,
            "type": "object",
            "properties": {
                "@context": {"type": ["string", "object"]},
                "@graph": {
                    "type": "array",
                    "items": {"anyOf": [{"$ref": f"#/$defs/{n}"} for n in class_names]},
                },
            },
            "required": ["@graph"],
            "$defs": defs,
        }
        out_path = self._artifact_path("jsonschema", ".schema.json")
        out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------ Python

    def _write_python_types(self) -> None:
        assert self.output_dir is not None
        lines = [
            '"""Python types for PSA package."""',
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass",
            "from typing import Optional",
            "",
            "",
        ]
        for cls in self.package.classes:
            lines.append("@dataclass(frozen=True)")
            lines.append(f"class {cls.name}:")
            lines.append(f'    """{cls.description or ""}"""')
            lines.append('    id: str')
            for attr in cls.attributes:
                py_type = self._xsd_to_python_type(attr.data_type)
                default = " = None" if not attr.required else ""
                lines.append(f"    {attr.name}: {py_type}{default}")
            for assoc in cls.associations:
                mult = assoc.multiplicity
                if mult is not None and (mult.max is None or mult.max > 1):
                    lines.append(f"    {assoc.name}: list[str] = None")
                else:
                    lines.append(f"    {assoc.name}: Optional[str] = None")
            lines.append("")

        for enum in self.package.enumerations:
            lines.append("from enum import Enum")
            lines.append("")
            lines.append(f"class {enum.name}(Enum):")
            lines.append(f'    """{enum.description or ""}"""')
            for value in enum.values:
                lines.append(f'    {value} = "{value}"')
            lines.append("")

        out_path = self._artifact_path("python", "_types.py")
        out_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _xsd_to_python_type(data_type: str | None) -> str:
        mapping = {
            "xsd:string": "str",
            "xsd:boolean": "bool",
            "xsd:integer": "int",
            "xsd:int": "int",
            "xsd:double": "float",
            "xsd:decimal": "float",
            "xsd:date": "str",
            "xsd:dateTime": "str",
            "xsd:anyURI": "str",
        }
        return mapping.get(data_type or "", "str")

    # ------------------------------------------------------------------ Examples / Mappings / CTS

    def _write_example(self) -> None:
        """Emit a JSON-LD example graph.

        The example contains one node per class in the package and links
        in-package associations by node id so that the document conforms to
        the package's own SHACL shapes (required relations are populated)
        and JSON Schema. Out-of-package targets and many-valued optional
        associations are omitted to keep the example acyclic and minimal.
        """
        assert self.output_dir is not None
        if not self.package.classes:
            return
        in_pkg = {c.name for c in self.package.classes}
        nodes: dict[str, dict[str, Any]] = {}
        for cls in self.package.classes:
            node: dict[str, Any] = {"@type": cls.name, "id": f"{cls.name}001"}
            for attr in cls.attributes:
                node[attr.name] = self._example_value(attr)
            nodes[cls.name] = node

        for cls in self.package.classes:
            node = nodes[cls.name]
            for assoc in cls.associations:
                target_name = assoc.target.class_name
                if target_name not in in_pkg:
                    continue
                mult = assoc.multiplicity
                min_count = mult.min if mult is not None else 0
                max_count = mult.max if mult is not None else None
                is_many = max_count is None or (max_count is not None and max_count > 1)
                # Required links must be present (SHACL minCount); optional
                # single-valued links are demonstrated for realism.
                target_id = nodes[target_name]["id"]
                if min_count >= 1:
                    node[assoc.name] = [target_id] if is_many else target_id
                elif max_count == 1:
                    node[assoc.name] = target_id

        example = {
            "@context": f"{self.ns}context",
            "@graph": list(nodes.values()),
        }
        out_path = self._artifact_path("examples", "-instance.jsonld")
        out_path.write_text(json.dumps(example, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _example_value(attr: DataProperty) -> Any:
        dt = attr.data_type
        if dt == "xsd:string":
            return attr.name
        if dt in ("xsd:integer", "xsd:int"):
            return 1
        if dt in ("xsd:double", "xsd:decimal"):
            return 1.0
        if dt == "xsd:boolean":
            return True
        return ""

    def _write_mapping_template(self) -> None:
        assert self.output_dir is not None
        anchors = []
        for cls in self.package.classes:
            for attr in cls.attributes:
                anchors.append({
                    "semantic_id": self._attribute_id(cls, attr),
                    "expected_mappings": [
                        {"system": "PMS", "object": cls.name, "field": ""},
                    ],
                })
        out = self.output_dir / "mappings" / "mapping-template.yaml"
        self._dump_yaml({"mapping_anchors": anchors}, out)

    def _write_cts(self) -> None:
        assert self.output_dir is not None
        checks = {
            "CTS-TP-001": {
                "name": "Package Metadata",
                "check": ["manifest.yaml exists", "manifest.yaml schema valid"],
            },
            "CTS-TP-002": {
                "name": "Entity Completeness",
                "check": [f"{cls.name} exists" for cls in self.package.classes],
            },
            "CTS-TP-003": {
                "name": "Relation Integrity",
                "check": [
                    f"{cls.name} {assoc.name} {assoc.target.class_name}"
                    for cls in self.package.classes
                    for assoc in cls.associations
                ],
            },
            "CTS-TP-004": {
                "name": "Artifact Generation",
                "check": [
                    "OWL file exists and parses",
                    "SHACL file exists and parses",
                    "JSON-LD context exists and parses",
                    "JSON Schema exists and validates example",
                ],
            },
            "CTS-TP-005": {
                "name": "Runtime Loading",
                "check": [
                    "Package loads into OntologyIR without error",
                    "All classes have IRI",
                    "All relations resolve target",
                ],
            },
        }
        cts = {
            "cts": {
                "package_id": self.pkg_id,
                "version": self.version,
                "cases": [
                    {"id": case_id, "name": meta["name"], "check": meta["check"]}
                    for case_id, meta in checks.items()
                ],
            }
        }
        self._dump_yaml(cts, self.output_dir / "tests" / "package-cts.yaml")


def build_psa_package(ir: OntologyIR, package_id: str, output_dir: Path) -> Path:
    """Convenience entry point: build a single PSA package."""
    builder = PSAPackageBuilder(ir, package_id)
    return builder.build(output_dir)
