# PSA Semantic Package Contract v0.1

> **Status**: Draft  
> **Version**: 0.1.0  
> **Producer**: grid-ontology  
> **Scope**: 定义 grid-ontology 中间表示（OntologyIR）如何映射为 PSA Semantic Package Specification 的物理目录与文件格式。  
> **Governed by**: `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md`

---

## 1. Purpose

本契约是 grid-ontology 作为 **PSA Semantic Model Producer** 的输出规范。它规定了：

1. 一个 PSA Semantic Package 必须包含哪些文件与目录；
2. `OntologyIR` 中的 `Package`、`ClassDef`、`Attribute`、`Association`、`Enumeration` 如何序列化为这些文件；
3. 各产物（OWL / SHACL / JSON-LD / JSON Schema / Python types）在 package 中的位置与命名约定；
4. 与下游消费者（SCR-Metadata、EASG Runtime、Agent Framework）的最小消费接口。

所有 grid-ontology 生成的 PSA Semantic Package **必须**满足本契约。

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **OntologyIR** | grid-ontology 的 frozen Pydantic 中间表示，见 `src/cim_ontology/ir/models.py`。 |
| **PSA Package** | 符合 PSA Engineering Baseline 的语义包，可被一个 Registry 加载并供 Runtime 消费。 |
| **Package ID** | 点分标识符，如 `power.equipment.transformer`，用于 Registry 索引。 |
| **Semantic Namespace** | 概念 IRI 的前缀，如 `https://grid-ontology.org/psa/v0.2/transformer`。 |
| **Primitive** | PSA 定义的 6 类原语：Entity、Attribute、Relation、Action、Rule、Evidence。 |
| **Artifact** | package 内可独立校验的物理文件：`.owl`、`.shacl`、`.jsonld`、`.yaml` 等。 |

---

## 3. Package Physical Layout

每个 PSA Package 输出到一个独立目录，目录名由 Package ID 的最后一个段决定，并附加版本号：

```text
packages/
└── transformer-0.1.0/
    ├── manifest.yaml
    ├── README.md
    ├── semantic-model/
    │   ├── entities.yaml
    │   ├── attributes.yaml
    │   ├── relations.yaml
    │   └── enumerations.yaml
    ├── ontology/
    │   └── transformer.owl
    ├── constraints/
    │   └── transformer.shacl
    ├── jsonld/
    │   └── transformer-context.jsonld
    ├── jsonschema/
    │   └── transformer.schema.json
    ├── python/
    │   └── transformer_types.py
    ├── examples/
    │   └── transformer-instance.jsonld
    ├── mappings/
    │   └── mapping-template.yaml
    └── tests/
        └── package-cts.yaml
```

### 3.1 Required vs Optional Files

| Path | Status | Description |
|------|--------|-------------|
| `manifest.yaml` | Required | Package 身份、版本、依赖、producer、PSA 兼容性声明。 |
| `README.md` | Required | 人类可读的包说明、用法、变更摘要。 |
| `semantic-model/entities.yaml` | Required | 实体（ClassDef → PSA Entity）清单。 |
| `semantic-model/attributes.yaml` | Required | 属性（Attribute → PSA Attribute）清单。 |
| `semantic-model/relations.yaml` | Required | 关系（Association → PSA Relation）清单。 |
| `semantic-model/enumerations.yaml` | Optional | 枚举类型清单；存在枚举时必填。 |
| `ontology/{package}.owl` | Required | OWL 2 本体文件。 |
| `constraints/{package}.shacl` | Required | SHACL shapes 文件。 |
| `jsonld/{package}-context.jsonld` | Required | JSON-LD context 文件。 |
| `jsonschema/{package}.schema.json` | Required | JSON Schema 文件。 |
| `python/{package}_types.py` | Required | Python dataclass / TypedDict 类型文件。 |
| `examples/{package}-instance.jsonld` | Required | 至少一个合法实例。 |
| `mappings/mapping-template.yaml` | Optional | 与外部系统（如 PMS）的映射锚点模板。 |
| `tests/package-cts.yaml` | Required | CTS（Conformance Test Suite）声明。 |

---

## 4. OntologyIR → Package Mapping Rules

### 4.1 Package Identity

`OntologyIR.packages[i]` 映射到 `manifest.yaml`：

```yaml
package:
  id: "power.equipment.transformer"          # 由 PSA primitive mapping registry 或包定义推导
  name: "Transformer Semantic Package"         # Package 显示名
  version: "0.1.0"                             # 语义版本
  producer: "grid-ontology"                    # 固定值
  source_ir: "https://grid-ontology.org/psa/v0.2/transformer"  # namespace
  compatibility:
    psa: ">=0.1"                               # PSA Engineering Baseline 版本
  status: "draft"                              # draft | release | deprecated
  maturity: "reference"                        # reference | stable | experimental
  generated_at: "2026-07-15T00:00:00Z"         # ISO 8601 UTC
  generator: "cim-ontology 1.7.0"              # 生成工具及版本
  dependencies: []                             # 依赖的其他 PSA Package ID 列表
```

**Mapping Rules**:

- `id`：优先取包定义中的 `package_id`；缺失时由 `Package.name` 按 kebab-case 转点分（如 `TransformerPackage` → `power.equipment.transformer` 需显式注册，不得自动推断）。
- `version`：取 `Package.version`；缺失时默认 `0.1.0`。
- `source_ir` / `namespace`：取 `Package.namespace`。
- `dependencies`：从 `ClassDef.parents` 跨包引用、以及 `Association` 的跨包 target 推导。

### 4.2 Entities (`ClassDef` → PSA Entity)

`semantic-model/entities.yaml`：

```yaml
entities:
  - id: "power.equipment.transformer.PowerTransformer"
    name: "PowerTransformer"
    display_name: "Power Transformer"
    primitive: "Entity"
    namespace: "https://grid-ontology.org/psa/v0.2/transformer"
    iri: "https://grid-ontology.org/psa/v0.2/transformer/PowerTransformer"
    description: "A transformer in the power grid, specialized from Equipment."
    parents:
      - iri: "https://grid-ontology.org/psa/v0.2/equipment/Transformer"
        package: "power.equipment"
    package_id: "power.equipment.transformer"
    source_refs: []        # 未来由 Provenance 模块填充
```

**Mapping Rules**:

- `id`： `{package_id}.{ClassDef.name}`。
- `iri`： `{namespace}/{ClassDef.name}`，使用 `_iri_safe.py` 中的 `safe_iri_segment()` 清洗。
- `primitive`：从 `psa_mapping.py` 的 registry 查询；未注册时默认 `Entity`。
- `parents`：仅列出跨包或本包内的直接父类；每个父类记录 `iri` 与 `package_id`。

### 4.3 Attributes (`Attribute` → PSA Attribute)

`semantic-model/attributes.yaml`：

```yaml
attributes:
  - id: "power.equipment.transformer.ratedCapacity"
    name: "ratedCapacity"
    display_name: "Rated Capacity"
    primitive: "Attribute"
    domain:
      entity_id: "power.equipment.transformer.PowerTransformer"
      iri: "https://grid-ontology.org/psa/v0.2/transformer/PowerTransformer"
    range:
      type: "Decimal"
      xsd: "xsd:double"
      unit: "MVA"
    required: false
    multiplicity: "0..1"
    description: "Rated apparent power in MVA."
```

**Mapping Rules**:

- `id`： `{package_id}.{Attribute.name}`。
- `domain`：属性所属 `ClassDef`。
- `range.type`：从 XSD 类型映射到 PSA 类型（见 §8.1）。
- `multiplicity`：属性默认 `0..1`；`required=True` 时仍记为 `1..1`，避免与关系多重性混淆。
- `unit`：从属性描述中的已知单位模式提取，或显式声明；无法提取时为空。

### 4.4 Relations (`Association` → PSA Relation)

`semantic-model/relations.yaml`：

```yaml
relations:
  - id: "power.equipment.transformer.hasTransformerEnd"
    name: "hasTransformerEnd"
    display_name: "Has Transformer End"
    primitive: "Relation"
    source:
      entity_id: "power.equipment.transformer.PowerTransformer"
      iri: "https://grid-ontology.org/psa/v0.2/transformer/PowerTransformer"
    target:
      entity_id: "power.equipment.transformer.TransformerEnd"
      iri: "https://grid-ontology.org/psa/v0.2/transformer/TransformerEnd"
    multiplicity: "1..*"
    inverse_name: "isTransformerEndOf"          # 可选，由命名约定生成
    description: "Transformer contains transformer ends."
```

**Mapping Rules**:

- `id`： `{package_id}.{Association.name}`。
- `source`：关联所在 `ClassDef`。
- `target`：由 `Association.target_package` + `Association.target_class` 解析。
- `multiplicity`：直接取 `Association.multiplicity`；缺失默认 `0..*`。
- `inverse_name`：可选，按 `is{Target}Of` 规则生成。

### 4.5 Enumerations

`semantic-model/enumerations.yaml`：

```yaml
enumerations:
  - id: "power.equipment.transformer.OperationStatus"
    name: "OperationStatus"
    package_id: "power.equipment.transformer"
    values:
      - value: "Running"
        label: "Running"
      - value: "OutOfService"
        label: "Out of Service"
      - value: "Maintenance"
        label: "Maintenance"
      - value: "Retired"
        label: "Retired"
    description: "Lifecycle operational state of a power transformer."
```

**Mapping Rules**:

- 仅当 `Package.enumerations` 非空时生成此文件。
- `id`： `{package_id}.{Enumeration.name}`。

---

## 5. Artifact Generation Rules

### 5.1 OWL (`ontology/{package}.owl`)

- 使用现有 `adapters/owl.py`，输入为 `OntologyIR` 中该 package 对应的子集。
- 输出格式：Turtle。
- IRI 策略： ontology header 使用 package namespace；类 IRI 见 §4.2。

### 5.2 SHACL (`constraints/{package}.shacl`)

- 使用现有 `adapters/shacl.py`。
- 每个 `ClassDef` 生成一个 `NodeShape`。
- 属性 `required=True` 时生成 `sh:minCount 1`。
- 关系 multiplicity 生成 `sh:minCount` / `sh:maxCount`（若可解析）。

### 5.3 JSON-LD Context (`jsonld/{package}-context.jsonld`)

- 使用现有 `adapters/jsonld_context.py`。
- 上下文 IRI 为 `{namespace}/context`。
- 包含所有实体、属性、关系、枚举的 term 定义。

### 5.4 JSON Schema (`jsonschema/{package}.schema.json`)

- 使用现有 `adapters/json_schema.py`。
- 顶层为 `definitions` / `$defs` 集合，每个 `ClassDef` 为一个 object schema。
- 枚举映射为 JSON Schema `enum`。

### 5.5 Python Types (`python/{package}_types.py`)

- 使用现有 `adapters/python_types.py`。
- 每个 `ClassDef` 生成一个 `frozen=True` 的 dataclass 或 TypedDict。
- 枚举生成 `enum.Enum` 子类或 `Literal[...]`。

---

## 6. Examples and Mappings

### 6.1 Example Instance

`examples/{package}-instance.jsonld` 必须是一个合法实例，至少包含：

```json
{
  "@context": "https://grid-ontology.org/psa/v0.2/transformer/context",
  "@type": "PowerTransformer",
  "id": "PT001",
  "ratedCapacity": 100,
  "voltageLevel": 220,
  "phaseCount": 3,
  "manufacturer": "SIEMENS",
  "operationStatus": "Running"
}
```

**规则**：

- 每个实体至少一个示例；优先覆盖 package 的“核心实体”。
- 示例必须能通 JSON Schema 校验。
- 示例中的 `@context` 应指向本 package 的 JSON-LD context IRI。

### 6.2 Mapping Template

`mappings/mapping-template.yaml` 提供 SCR-Metadata 的映射锚点：

```yaml
mapping_anchors:
  - semantic_id: "power.equipment.transformer.ratedCapacity"
    expected_mappings:
      - system: "PMS"
        object: "Equipment"
        field: "CAPACITY"
      - system: "EMS"
        object: "Transformer"
        field: "RATED_MVA"
```

**规则**：

- 每个属性至少一个示例映射。
- 示例系统应来自 PSA Ecosystem 已知消费者（PMS、EMS、DMS、OMS 等）。
- 不强制填写实际字段名；未确认时保留为空字符串并标注 `confidence: speculative`。

---

## 7. CTS Contract

`tests/package-cts.yaml` 声明本 package 必须通过的最小 CTS 集合：

```yaml
cts:
  package_id: "power.equipment.transformer"
  version: "0.1.0"
  cases:
    - id: "CTS-TP-001"
      name: "Package Metadata"
      check:
        - "manifest.yaml exists"
        - "manifest.yaml schema valid"
    - id: "CTS-TP-002"
      name: "Entity Completeness"
      check:
        - "PowerTransformer exists"
        - "TransformerEnd exists"
        - "Terminal exists"
    - id: "CTS-TP-003"
      name: "Relation Integrity"
      check:
        - "PowerTransformer hasTransformerEnd TransformerEnd"
    - id: "CTS-TP-004"
      name: "Artifact Generation"
      check:
        - "OWL file exists and parses"
        - "SHACL file exists and parses"
        - "JSON-LD context exists and parses"
        - "JSON Schema exists and validates example"
    - id: "CTS-TP-005"
      name: "Runtime Loading"
      check:
        - "Package loads into OntologyIR without error"
        - "All classes have IRI"
        - "All relations resolve target"
```

**规则**：

- 每个 package 的 CTS 必须覆盖：metadata、entity、relation、artifact、runtime 五类。
- `check` 项应为可自动验证的布尔断言。

---

## 8. Data Type Mapping

### 8.1 XSD → PSA Type

| XSD Type | PSA Type | JSON Schema Type | Python Type |
|----------|----------|------------------|-------------|
| `xsd:string` | String | `string` | `str` |
| `xsd:boolean` | Boolean | `boolean` | `bool` |
| `xsd:integer` | Integer | `integer` | `int` |
| `xsd:double` | Decimal | `number` | `float` |
| `xsd:decimal` | Decimal | `number` | `Decimal` |
| `xsd:dateTime` | DateTime | `string` (format date-time) | `datetime` |
| `xsd:anyURI` | IRI | `string` (format uri) | `str` |
| enum | Enum | `string` (enum) | `Literal[...]` / `Enum` |

### 8.2 Multiplicity Mapping

| Association.multiplicity | SHACL | JSON Schema | Semantic Meaning |
|----------------------------|-------|-------------|------------------|
| `0..1` | `sh:maxCount 1` | 单一值或 null | optional single |
| `1..1` | `sh:minCount 1; sh:maxCount 1` | 单一值 | required single |
| `0..*` | none | array | optional many |
| `1..*` | `sh:minCount 1` | non-empty array | required many |

---

## 9. Versioning and Compatibility

Package 版本遵循 `MAJOR.MINOR.PATCH`：

- **MAJOR**：Type C breaking semantic change（见 `AGENTS.md` Ontology Development Rules）。
- **MINOR**：Type A additive change 或 Type B compatible change。
- **PATCH**：文档修正、示例更新、非语义性 bug 修复。

跨版本 package 目录必须并列保留，命名包含版本号：`transformer-0.1.0/`、`transformer-0.2.0/`。

---

## 10. Validation Entry Points

grid-ontology 必须提供以下验证入口：

| Entry | Command | Responsibility |
|-------|---------|----------------|
| Structural validation | `python -m scripts.validate_psa_package --package packages/transformer-0.1.0` | 检查目录结构、manifest schema、文件存在性。 |
| Semantic validation | `pytest tests/psa/test_transformer_package.py` | 检查 IR 可加载、实体/属性/关系一致性。 |
| Artifact validation | `python -m scripts.validate_psa_artifacts --package packages/transformer-0.1.0` | 检查 OWL/SHACL/JSON-LD/JSON Schema 可解析且与 IR 一致。 |
| CTS validation | `pytest tests/psa/test_cts.py` | 运行 package-cts.yaml 中声明的用例。 |

---

## 11. Relationship to Other Documents

| Document | Role |
|----------|------|
| `docs/governance/Transformer Semantic Package v0.1.md` | 第一个 package 的领域规范。 |
| `docs/governance/psa-semantic-package-contract.md` | 本文件：所有 package 的物理与映射契约。 |
| `docs/governance/compatibility-analysis-template.md` | Type C 变更的兼容性分析模板。 |
| `docs/governance/cts-gap-register.md` | 记录 grid-ontology 当前 CTS 能力与 PSA 官方 CTS 的差距。 |
| `AGENTS.md` | 项目身份、PSA role、Ontology Development Rules。 |

---

## 12. Next Steps

1. 实现 `scripts/build_psa_package.py`：从 `build_reference_models.py` 输出的 IR 生成 `packages/transformer-0.1.0/`。
2. 实现 `scripts.validate_psa_package.py`、`scripts.validate_psa_artifacts.py`。
3. 在 `tests/psa/` 添加 CTS 自动化测试。
4. 创建 `docs/governance/cts-gap-register.md`。
