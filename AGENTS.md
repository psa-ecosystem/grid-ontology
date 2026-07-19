# AGENTS.md

## Project Identity

- **Project**: grid-ontology
- **PyPI Package**: `cim-ontology`
- **Repository**: `grid-ontology`

## PSA Role

This repository is part of the **PSA Ecosystem** (Power Semantic Architecture).

- **Role**: Semantic Model Producer
- **PSA Primitive Responsibility**: produce `Entity`, `Attribute`, `Relation`, `Action`, `Rule`, and `Evidence` assets as defined by PSA Core Semantic Model
- **Primary Contract**: PSA Semantic Package Specification

## Responsibilities

This repository is responsible for:

- Power-grid ontology modeling;
- Semantic concept definition (Class, Datatype Property, Object Property, Capability, Constraint);
- Semantic package production (OWL, SHACL, JSON-LD, JSON Schema, Python Types, PSA Semantic Package);
- Source traceability and evidence references for generated semantic assets;
- Package-level validation fixtures for PSA compatibility.

## Boundaries

This repository **MUST NOT**:

- Implement semantic runtime (resolver, validator, reasoner, query engine, registry);
- Implement agent orchestration or agent execution;
- Create business applications;
- Bypass PSA semantic contracts or define new PSA primitives;
- Own metadata operations (SCR-Metadata) or business application behavior (PowerGenius AI).

## PSA Alignment

This repository follows:

- PSA Engineering Baseline v0.1
- PSA Semantic Package Specification
- `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md`
- `charter/Project-Charter.md`

## Development Rules

Before modifying code:

1. Read `project.yaml`.
2. Read `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md`.
3. Check semantic ownership impact against PSA boundaries.
4. Update tests and documentation for any ontology, package format, or identifier change.

## Change Rules

Changes affecting the following **require** an ADR and compatibility analysis:

- Ontology concepts;
- Package format or manifest;
- Semantic identifiers (IRI, namespace, version);
- PSA primitive mappings;
- Cardinality or datatype mapping contracts.

## Ontology Development Rules

When modifying semantic models, classify the change first:

| Change Type | Definition | Required Action |
|-------------|------------|-----------------|
| **A. Additive change** | Add a new entity, attribute, relation, or rule without changing existing semantics | Normal development; add tests |
| **B. Compatible change** | Extend cardinality, add optional attribute, refine description without breaking consumers | Add tests; update docs |
| **C. Breaking semantic change** | Modify definition, delete concept, rename identifier, change cardinality from optional to required, change domain/range | ADR + compatibility analysis + migration note |

Breaking semantic changes **MUST NOT** be committed without:

1. An ADR under `docs/adr/` explaining the rationale and alternatives;
2. A compatibility analysis documenting downstream impact (Registry / Runtime / Agent / Apps);
3. A migration note for consumers of the previous ontology version.

### Simple Decision Tree

```text
新增实体/属性/关系？
  → Type A：正常开发，补测试

修改属性定义或关系语义？
  → Type C：需要 ADR + 兼容性分析

删除概念？
  → Type C：必须做影响分析
```

## Validation

Before commit:

```bash
psa-validator check .
```

If `psa-validator` is not available locally:

```bash
python tools/psa-validator check .
```

In addition, run the existing test suite:

```bash
python -m pytest tests/unit tests/integration tests/property -q
```

## Architecture Reminder

```text
Source AST (Markdown / PDF / Standards)
    ↓
OntologyIR (Compiler IR, frozen)
    ↓
Semantic Package / 5 Adapters
    ↓
Registry / Runtime (EASG) / Agent / Application consumption
```

`grid-ontology` owns the Compiler IR layer and adapters. It does **not** own the Semantic Runtime or Application layers.
