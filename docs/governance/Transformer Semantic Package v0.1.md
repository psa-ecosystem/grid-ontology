# **Transformer Semantic Package v0.1**

## **Power Semantic Architecture**

## **Reference Semantic Package Specification**

**Status:** Draft
 **Version:** v0.1
 **Package ID:** `power.equipment.transformer`
 **Producer:** `grid-ontology`
 **PSA Compatibility:** PSA Engineering Baseline v0.1
 **Semantic Domain:** Power Equipment / Transformer
 **Package Type:** Reference Semantic Package

------

# **1. Purpose**

## **1.1 Purpose**

This document defines the first PSA-compatible reference semantic package for power transformer equipment.

The purpose is to demonstrate the complete semantic asset lifecycle:

```text
Semantic Model Definition

        ↓

Ontology Compilation

        ↓

Semantic Package

        ↓

Registry Publication

        ↓

Semantic Runtime Consumption

        ↓

Agent/Application Capability
```

------

# **1.2 Position in PSA Ecosystem**

Transformer Semantic Package is produced by:

```text
grid-ontology

Semantic Model Producer
```

Consumed by:

```text
SCR-Metadata

Semantic Mapping Provider


EASG

Semantic Runtime Provider


Agent Framework

Agent Capability Provider
```

------

# **1.3 Scope**

This package covers:

- Power Transformer semantic concepts;
- Transformer components;
- Transformer relationships;
- Transformer attributes;
- Transformer operational semantics.

------

# **1.4 Non-Scope**

This package does not define:

- physical database structures;
- PMS table mappings;
- runtime execution logic;
- AI agent behavior;
- business applications.

------

# **2. Package Identity**

## **2.1 Package Manifest**

```yaml
package:

  id:

    power.equipment.transformer


  name:

    Transformer Semantic Package


  version:

    0.1.0


  producer:

    grid-ontology


  domain:

    power-equipment


  compatibility:

    psa:

      >=0.1


  status:

    draft


  maturity:

    reference
```

------

# **3. Package Structure**

Standard package layout:

```text
transformer-package/

├── manifest.yaml

├── semantic-model/

│
├── entities.yaml

│
├── attributes.yaml

│
└── relations.yaml


├── ontology/

│
├── transformer.owl


├── constraints/

│
└── transformer.shacl


├── examples/

│
└── transformer-instance.jsonld


├── mappings/

│
└── mapping-template.yaml


├── tests/

│
├── package-cts.yaml


└── README.md
```

------

# **4. Semantic Model**

## **4.1 Core Entity**

## **PowerTransformer**

Definition:

An electrical equipment entity that transforms voltage levels and transfers electrical energy between circuits.

Identifier:

```text
power.equipment.transformer.PowerTransformer
```

Type:

```text
Entity
```

------

# **4.2 Transformer Components**

## **TransformerEnd**

Definition:

A terminal component representing one electrical connection end of a transformer.

Identifier:

```text
power.equipment.transformer.TransformerEnd
```

------

## **Terminal**

Definition:

A connection point used for electrical connectivity.

Identifier:

```text
power.equipment.transformer.Terminal
```

------

# **4.3 Entity Hierarchy**

```text
Equipment
    ↑
PowerTransformer
    |
    +── hasTransformerEnd ──► TransformerEnd
                                  |
                                  +── terminal ──► Terminal
                                                       |
                                                       +── connectedTo ──► Terminal
```

**Note**: `TransformerEnd` and `Terminal` are not subclasses of `PowerTransformer`.
They are related through `ObjectProperty` associations (composition / connection),
not `rdfs:subClassOf` inheritance.

------

# **5. Attributes Model**

## **5.1 PowerTransformer Attributes**

| **Attribute**   | **Type** | **Unit** | **Description**            |
| --------------- | -------- | -------- | -------------------------- |
| ratedCapacity   | Decimal  | MVA      | Rated transformer capacity |
| voltageLevel    | String   | -        | Voltage level              |
| phaseCount      | Integer  | -        | Number of phases           |
| manufacturer    | String   | -        | Manufacturer               |
| operationStatus | Enum     | -        | Current operation state    |

------

Example:

```yaml
attribute:

 id:

  power.equipment.transformer.ratedCapacity


domain:

 PowerTransformer


type:

 Decimal


unit:

 MVA
```

------

# **6. Relationship Model**

## **6.1 installedIn**

Meaning:

Transformer belongs to a substation.

```yaml
relation:

 id:

  installedIn


source:

 PowerTransformer


target:

 Substation
```

------

## **6.2 hasTransformerEnd**

Meaning:

Transformer contains transformer ends.

```yaml
relation:

 id:

  hasTransformerEnd


source:

 PowerTransformer


target:

 TransformerEnd
```

------

## **6.3 connectedTo**

Meaning:

Terminal participates in electrical connectivity.

```yaml
relation:

 id:

  connectedTo


source:

 Terminal


target:

 Terminal
```

------

# **7. PSA Primitive Mapping**

Transformer Package maps domain concepts to PSA primitives.

## **7.1 Entity**

```yaml
primitive:

 Entity


mapping:

 PowerTransformer
```

------

## **7.2 Attribute**

```yaml
primitive:

 Attribute


mapping:

 ratedCapacity
```

------

## **7.3 Relation**

```yaml
primitive:

 Relation


mapping:

 installedIn
```

------

## **7.4 Action**

Future extension:

```yaml
primitive:

 Action


candidate:

 inspectTransformer
```

------

## **7.5 Rule**

Example:

```yaml
primitive:

 Rule


id:

 transformer.overload.rule


description:

 Transformer overload condition detection
```

------

## **7.6 Evidence**

Example:

```yaml
primitive:

 Evidence


source:

 TransformerMonitoringRecord
```

------

# **8. Ontology Representation**

The package SHALL support:

## **OWL Representation**

Purpose:

- ontology exchange;
- reasoning support.

------

## **SHACL Representation**

Purpose:

- semantic validation;
- constraint checking.

------

## **JSON-LD Representation**

Purpose:

- instance exchange;
- API integration.

------

# **9. Example Instance**

Example:

```json
{
 "@context":

 "https://grid-ontology.org/psa/v0.2/",


 "@type":

 "PowerTransformer",


 "id":

 "PT001",


 "ratedCapacity":

 100,


 "voltageLevel":

 "220kV",


 "operationStatus":

 "Running"

}
```

------

# **10. Semantic Mapping Contract**

Transformer Package provides mapping anchors for SCR-Metadata.

Example:

```yaml
mapping_anchor:

 semantic:

  power.equipment.transformer.ratedCapacity


 expected_mapping:

  system:

   PMS


  object:

   Equipment


  field:

   CAPACITY
```

------

# **11. Runtime Consumption Contract**

EASG Runtime SHALL be able to:

## **Load Package**

```text
Registry

 ↓

Transformer Package

 ↓

Semantic Context
```

------

## **Resolve Entity**

Example:

Query:

```
Find transformer PT001
```

Runtime resolves:

```text
PowerTransformer

        +

Attributes

        +

Relations
```

------

# **12. Agent Capability Contract**

Agent Framework may consume:

```yaml
capability:

 id:

  transformer.analysis


semantic_context:

  power.equipment.transformer


runtime:

  EASG
```

------

Example:

```text
User:

分析主变 PT001 状态


Agent:

↓

Semantic Context


↓

EASG Runtime


↓

Transformer Package


↓

Result
```

------

# **13. Package Validation**

## **13.1 Structural Validation**

Check:

- manifest exists;
- required directories exist;
- identifiers unique.

------

## **13.2 Semantic Validation**

Check:

- entity definitions;
- relation consistency;
- attribute domains.

------

## **13.3 Compatibility Validation**

Check:

- PSA version;
- primitive mapping;
- runtime compatibility.

------

# **14. CTS Specification**

## **Transformer Package CTS v0.1**

测试范围：

------

## **CTS-TP-001 Package Metadata**

验证：

```text
manifest.yaml

exists

valid
```

------

## **CTS-TP-002 Entity Completeness**

验证：

必须存在：

```text
PowerTransformer

TransformerEnd

Terminal
```

------

## **CTS-TP-003 Relation Integrity**

验证：

```text
PowerTransformer

hasTransformerEnd

TransformerEnd
```

------

## **CTS-TP-004 Artifact Generation**

验证：

生成：

```text
OWL

SHACL

JSON-LD
```

------

## **CTS-TP-005 Runtime Loading**

验证：

```text
Package

↓

EASG

↓

Semantic Context
```

------

# **15. Version Strategy**

Package Version:

```text
MAJOR.MINOR.PATCH
```

Example:

```text
0.1.0
```

------

## **Breaking Change**

包括：

- 删除 Entity；
- 修改 Entity Meaning；
- 修改 Relation Semantics。

要求：

- ADR；
- Migration Note。

------

# **16. Namespace Strategy**

Current Development Namespace:

```text
https://grid-ontology.org/psa/v0.2/
```

Status:

Temporary Development Namespace.

正式 namespace 需要 PSA Governance 后续分配。

------

# **17. Repository Location**

建议：

在 grid-ontology:

```text
packages/

└── transformer/
```

或者：

```text
src/cim_ontology/packages/transformer/
```

由项目实际结构决定。

------

# **18. Release Criteria**

Transformer Semantic Package v0.1 发布条件：

## **Semantic**

✓ Entity Model Complete
 ✓ Primitive Mapping Complete
 ✓ Namespace Defined

------

## **Engineering**

✓ OntologyIR Generated
 ✓ Exporters Passed
 ✓ Unit Tests Passed

------

## **PSA Integration**

✓ Package Manifest Valid
 ✓ CTS Passed
 ✓ Registry Compatible

------

# **19. Current Implementation Mapping**

对应 grid-ontology 当前实现：

| **Package Component** | **Implementation**         |
| --------------------- | -------------------------- |
| Core Domain Model     | `core.py`                  |
| Equipment Model       | `equipment.py`             |
| Transformer Package   | `transformer_package.py`   |
| Compiler IR           | `builder.py`               |
| Primitive Mapping     | `psa_mapping.py`           |
| Validation            | `test_reference_models.py` |

------

# **20. Next Evolution Path**

```text
Transformer Semantic Package v0.1

        ↓

SCR-Metadata Mapping Package

        ↓

EASG Runtime Package Loading

        ↓

Agent Capability:

Transformer Intelligence Assistant

        ↓

PowerGenius AI Scenario
```

------

## **最终定位**

`Transformer Semantic Package v0.1` 不只是一个设备模型。

它是 PSA 第一个：

**从 Semantic Model → Package → Mapping → Runtime → Agent 的端到端验证资产。**

下一步建议不要继续扩展 Transformer 模型，而是围绕它建立三个配套规范：

1. **《PSA Semantic Package Contract v0.1》**（放 PSA 主仓，作为标准）
2. **《Transformer Semantic Package CTS Specification v0.1》**
3. **《SCR-Metadata Transformer Mapping Specification v0.1》**

这样 Transformer 才能成为 PSA 第一个完整 Vertical Slice。