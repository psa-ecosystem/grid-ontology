# grid-ontology Project Charter v0.1

Status: Project-Local Seed Draft

Date: 2026-07-14

Target location: `grid-ontology/charter/Project-Charter.md`

Source basis: PSA Project Registry; PSA Project Charter Template v0.1; grid-ontology architecture report; GPT-generated governance draft.

## 1. Purpose

`grid-ontology` exists to produce reusable power-domain ontology assets for the PSA ecosystem.

It converts power-domain standards, models, documents, and business concepts into ontology artifacts and PSA-compatible Semantic Package inputs.

## 2. Strategic Position

| Item | Definition |
|---|---|
| PSA role | Semantic Asset Producer |
| Ecosystem position | Power Domain Ontology Asset Factory |
| Primary PSA contract | PSA Semantic Package Specification |
| Primary downstream users | PSA package validation, Registry implementations, Runtime implementations, Agent adapters, and business applications |

`grid-ontology` supplies domain semantics. It does not define PSA contracts.

## 3. Scope

`grid-ontology` owns:

- power-domain ontology assets;
- CIM-aligned class, property, and relation modeling;
- domain concept mappings to PSA primitives;
- ontology package export artifacts;
- source and evidence references for generated semantic assets;
- package-level validation fixtures for PSA compatibility.

## 4. Non-Responsibilities

`grid-ontology` does not own:

| Area | Owner |
|---|---|
| PSA Core Semantic Model | PSA |
| PSA Semantic Package Specification | PSA |
| PSA Runtime Contract | PSA |
| Semantic Registry service | Registry implementation |
| Semantic Runtime behavior | Runtime implementation such as EASG |
| Metadata operations | SCR-Metadata |
| Agent execution | Agent Framework |
| Business application behavior | PowerGenius AI |

## 5. PSA Relationship

The PSA-facing integration path is:

```text
grid-ontology
-> ontology assets
-> PSA-compatible Semantic Package
-> CTS validation
-> Registry / Runtime / Agent / Application consumption
```

Domain concepts must map to the six PSA primitives instead of becoming new PSA primitives:

| grid-ontology concept | PSA primitive |
|---|---|
| Class | Entity |
| Datatype Property | Attribute |
| Object Property | Relation |
| Capability | Action |
| Constraint or Rule | Rule |
| Justification or Source | Evidence |

## 6. Outputs

`grid-ontology` produces:

- ontology artifacts;
- semantic profiles, such as equipment, topology, operation, and maintenance profiles;
- mappings to PSA Core Semantic Model primitives;
- Semantic Package export artifacts;
- evidence and source references;
- validation reports and compatibility findings.

The first PSA-facing deliverable should be a transformer-focused ontology package.

## 7. Repository Structure

Recommended local layout:

```text
grid-ontology/
├── charter/
│   └── Project-Charter.md
├── ontology/
├── profiles/
├── mappings/
├── packages/
├── examples/
├── tests/
└── docs/
```

The project repository may adapt this structure, but the local charter should remain under `charter/`.

## 8. Engineering Principles

- Preserve source traceability for ontology assets.
- Keep domain ontology modeling separate from Runtime behavior.
- Export PSA-compatible packages through the PSA Semantic Package Specification.
- Treat CTS failures as compatibility feedback, not as permission to redefine PSA contracts.
- Keep generated artifacts reproducible and reviewable.

## 9. Roadmap

| Window | Milestone |
|---|---|
| Month 1 | Select the first ontology package scope and required PSA primitive mappings |
| Month 1-2 | Build or adapt the PSA Semantic Package export path |
| Month 2 | Run package validation and record CTS gaps |
| Month 2-3 | Prepare the next ontology profile based on package feedback |

## 10. Success Criteria

`grid-ontology` succeeds in the PSA v0.1/v0.2 phase if:

- one ontology asset is exported as a PSA-compatible Semantic Package;
- mappings to PSA primitives are explicit;
- source and evidence references are preserved;
- CTS gaps are documented without redefining PSA contracts;
- downstream Registry or Runtime work can consume the package through PSA-defined interfaces.

## 11. Governance Rules

| Rule | Requirement |
|---|---|
| GRID-001 | Domain concepts must map to PSA primitives instead of becoming new PSA primitives |
| GRID-002 | Ontology package exports must preserve source and evidence references |
| GRID-003 | Runtime behavior must not be encoded as ontology asset ownership |
| GRID-004 | Package compatibility changes that affect PSA contracts must be routed through PSA ADR, specification, or CTS updates |
| GRID-005 | Project roadmap, implementation details, and release cadence are maintained in the `grid-ontology` repository |

## 12. Evidence Baseline

The current PSA report describes `grid-ontology` as an offline ontology generator for power-domain CIM assets. It extracts classes, attributes, and associations from GB/T 43259.301-2024 / IEC 61970-301:2020-derived Markdown and emits OWL, SHACL, JSON-LD, JSON Schema, and Python Types artifacts.

The same report separates the immutable IR and adapter pipeline from a Semantic Runtime.

Source: `docs/report/grid-ontology-project-report.md`.
