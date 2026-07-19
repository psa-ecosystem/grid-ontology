# Grid Ontology Project Charter

## Mission

`grid-ontology` exists to produce reusable power-domain semantic models and PSA-compatible semantic packages for the PSA ecosystem. It converts power-domain standards, models, documents, and business concepts into ontology artifacts that downstream Registry, Runtime, Agent, and Application consumers can consume through PSA-defined interfaces.

## PSA Role

- **PSA Role**: Semantic Asset Producer
- **Ecosystem Position**: Power Domain Ontology Asset Factory
- **Primary PSA Contract**: PSA Semantic Package Specification
- **Downstream Consumers**: Registry implementations, Runtime implementations (EASG), Agent adapters, and business applications

`grid-ontology` supplies domain semantics. It does not define PSA contracts.

## Scope

`grid-ontology` owns:

- Power-domain ontology assets;
- CIM-aligned class, property, and relation modeling;
- Domain concept mappings to PSA primitives;
- Ontology package export artifacts;
- Source and evidence references for generated semantic assets;
- Package-level validation fixtures for PSA compatibility.

## Non-Scope

`grid-ontology` does **not** own:

| Area | Owner |
|------|-------|
| PSA Core Semantic Model | PSA |
| PSA Semantic Package Specification | PSA |
| PSA Runtime Contract | PSA |
| Semantic Registry service | Registry implementation |
| Semantic Runtime behavior | Runtime implementation such as EASG |
| Metadata operations | SCR-Metadata |
| Agent execution | Agent Framework |
| Business application behavior | PowerGenius AI |

## Deliverables

- Ontology artifacts (OWL, SHACL, JSON-LD, JSON Schema, Python Types);
- Semantic profiles (e.g., equipment, topology, operation, maintenance);
- Mappings to PSA Core Semantic Model primitives;
- PSA-compatible Semantic Package export artifacts;
- Evidence and source references;
- Validation reports and compatibility findings.

The first PSA-facing deliverable is a **transformer-focused ontology package**.

## Dependencies

- **PSA Specifications**: PSA Core Semantic Model, PSA Semantic Package Specification, PSA Conformance Test Suite (CTS);
- **Standards**: GB/T 43259.301-2024 / IEC 61970-301:2020-derived CIM Markdown;
- **Build tools**: Python >=3.12, setuptools, pytest, ruff, mypy, pyright;
- **External consumers**: EASG (Runtime), Agent Framework, PowerGenius AI (Business App).

## Roadmap

| Window | Milestone |
|--------|-----------|
| Month 1 | Select the first ontology package scope and required PSA primitive mappings |
| Month 1-2 | Build or adapt the PSA Semantic Package export path |
| Month 2 | Run package validation and record CTS gaps |
| Month 2-3 | Prepare the next ontology profile based on package feedback |

---

**See also**:

- `charter/Project-Charter.md` — PSA Project Charter v0.1
- `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md` — Detailed PSA alignment constraints
- `project.yaml` — Machine-readable project identity
- `AGENTS.md` — Claude Code behavior constraints
