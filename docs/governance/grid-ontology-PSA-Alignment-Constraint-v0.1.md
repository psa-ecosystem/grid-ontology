# grid-ontology PSA Alignment Constraint v0.1

> **作用域**：本文件约束 Claude Code 在 `grid-ontology` 仓库中的所有后续开发行为。
> **状态**：PSA Engineering Baseline Level 1（Repository Ready）接入文档。
> **依据**：`charter/Project-Charter.md`（PSA Project Charter v0.1）。

---

## 1. PSA 生态身份

| 属性 | 定义 |
|------|------|
| 项目 ID | `grid-ontology` |
| PSA 角色 | **Semantic Asset Producer** |
| 生态定位 | Power Domain Ontology Asset Factory |
| 主契约 | PSA Semantic Package Specification |
| 下游消费者 | Registry / Runtime（EASG）/ Agent Adapters / Business Applications |

`grid-ontology` 只供应**领域语义资产**，不定义 PSA 核心契约。

---

## 2. 职责边界（Responsibilities）

本仓库负责：

- 电网领域本体资产建模；
- CIM 对齐的类、属性、关联建模；
- 领域概念到 PSA primitives 的映射；
- 本体包导出产物（OWL / SHACL / JSON-LD / JSON Schema / Python Types / PSA Semantic Package）；
- 生成语义资产的 source 与 evidence 引用；
- PSA 兼容性的包级验证 fixture。

---

## 3. 非职责边界（Non-Responsibilities）

本仓库**禁止**负责：

| 领域 | 正确拥有者 |
|------|-----------|
| PSA Core Semantic Model | PSA |
| PSA Semantic Package Specification | PSA |
| PSA Runtime Contract | PSA |
| Semantic Registry service | Registry implementation |
| Semantic Runtime behavior | Runtime implementation such as EASG |
| Metadata operations | SCR-Metadata |
| Agent execution | Agent Framework |
| Business application behavior | PowerGenius AI |

---

## 4. PSA Primitive 映射契约

所有 grid-ontology 概念必须映射到 PSA primitives，**不得**创造新的 PSA primitives：

| grid-ontology concept | PSA primitive |
|-----------------------|---------------|
| Class | Entity |
| Datatype Property | Attribute |
| Object Property | Relation |
| Capability | Action |
| Constraint or Rule | Rule |
| Justification or Source | Evidence |

---

## 5. 治理规则（GRID-001 至 GRID-005）

| 规则 | 要求 |
|------|------|
| **GRID-001** | Domain concepts must map to PSA primitives instead of becoming new PSA primitives |
| **GRID-002** | Ontology package exports must preserve source and evidence references |
| **GRID-003** | Runtime behavior must not be encoded as ontology asset ownership |
| **GRID-004** | Package compatibility changes that affect PSA contracts must be routed through PSA ADR, specification, or CTS updates |
| **GRID-005** | Project roadmap, implementation details, and release cadence are maintained in the `grid-ontology` repository |

---

## 6. 工程原则

- **Preserve source traceability**：每个语义资产必须保留 source 和 evidence 引用。
- **Separate ontology from Runtime**：领域本体建模与 Runtime 行为严格分离。
- **PSA-compatible export**：通过 PSA Semantic Package Specification 导出兼容包。
- **CTS failures are feedback**：CTS 失败是兼容性反馈，不是重新定义 PSA 契约的许可。
- **Reproducible & reviewable**：产物必须可重现、可审查。

---

## 7. Claude Code 开发约束

### 7.1 每次修改前必须读取

1. `project.yaml` — 确认项目身份与 PSA 角色；
2. `AGENTS.md` — 确认行为约束；
3. `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md` — 确认本约束；
4. `charter/Project-Charter.md` — 确认 PSA 边界。

### 7.2 变更影响检查

在修改任何以下元素前，必须评估对 PSA 契约的影响：

- 本体概念（Class / Attribute / Relation / Rule / Action）
- 包格式（Package format / manifest / checksum）
- 语义标识符（IRI / namespace / version）
- PSA primitive 映射

### 7.3 需要 ADR + 兼容性分析的变更

以下变更**必须**配套 ADR 和兼容性分析：

- 新增/删除/重命名 ontology 概念；
- 修改 package format；
- 修改 IRI 或 namespace；
- 修改 cardinality / datatype mapping；
- 影响其他 PSA 项目消费的接口或输出。

### 7.4 禁止事项

- 禁止实现 Semantic Runtime（如 resolver / validator / reasoner / query engine）作为 ontology 资产；
- 禁止实现 Agent Orchestration 或 Business Application 行为；
- 禁止绕过 PSA Semantic Package Specification 私自定义输出契约；
- 禁止在本仓库内创建新的 PSA primitive。

---

## 8. 验证要求

- 每次提交前运行：`psa-validator check .`（或 `python tools/psa-validator check .`）；
- 每次影响 ontology 概念、package format、semantic identifiers 的变更必须更新测试与文档；
- 新增 adapter 或 exporter 时必须新增对应的 roundtrip property 测试（延续现有 Hypothesis 不变量守护）。

---

## 9. 成熟度路径

| 阶段 | 目标 | 关键产出 |
|------|------|----------|
| **Level 1** | Repository Ready | AGENTS.md / project.yaml / Charter / Governance Constraint |
| **Level 2** | PSA Aligned | Contract / Tests / Documentation |
| **Level 3** | PSA Native | CTS / Integration Test / Release Process |

当前状态：**Level 2 (PSA Aligned)**。

> 详见 ADR-0001（`docs/adr/ADR-0001-psa-level-means-current-certification.md`）与
> `psa-baseline-compliance-report-v0.2.md`（Level 2 ✅ PASS，2026-07-17）。
