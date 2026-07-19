# Compatibility Analysis Template

## Change Overview

- **Change ID**: [PR / ADR number]
- **Author**: 
- **Date**: 
- **Affected Ontology Package**: [e.g., GridCore, GridEquipment, TransformerPackage]
- **Change Type**: [A. Additive / B. Compatible / C. Breaking semantic]

## What is changing?

Describe the ontology change in plain language.

## PSA Primitive Impact

| Concept | PSA Primitive | Impact |
|---------|---------------|--------|
| [Class/Attribute/Relation] | Entity / Attribute / Relation | None / Low / Medium / High |

## Downstream Consumer Impact

| Consumer | Impact | Migration Required | Notes |
|----------|--------|-------------------|-------|
| Semantic Registry | None / Low / Medium / High | Yes / No | |
| Runtime (EASG) | None / Low / Medium / High | Yes / No | |
| Agent Framework | None / Low / Medium / High | Yes / No | |
| PowerGenius AI | None / Low / Medium / High | Yes / No | |

## Breaking Change Checklist

- [ ] IRI or namespace changed
- [ ] Class/Attribute/Relation removed
- [ ] Cardinality strengthened (optional → required)
- [ ] Domain or range changed
- [ ] Semantic definition narrowed or redefined

## Migration Note

If this is a breaking change, describe how consumers should migrate.

## Evidence

- ADR: [link]
- Tests: [link]
- CTS Gap Register entry: [link]
