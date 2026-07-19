# CTS Gap Register v0.1

> **Status**: Draft  
> **Date**: 2026-07-15  
> **Scope**: 记录 grid-ontology 当前生成的 PSA Semantic Package 与 PSA Engineering Baseline 官方 CTS（Conformance Test Suite）之间的差距。  
> **Related**: `docs/governance/psa-semantic-package-contract.md`, `docs/governance/Transformer Semantic Package v0.1.md`

---

## 1. Overview

本文件是 PSA Engineering Baseline Level 2 的合规跟踪项。它列出 grid-ontology 已经实现的 CTS 能力、尚未实现的能力、以及需要 PSA Governance 明确定义的能力。

| Item | Status | Notes |
|------|--------|-------|
| CTS-TP-001 Package Metadata | ✅ Implemented | `manifest.yaml` 生成与 schema 校验通过单元测试。 |
| CTS-TP-002 Entity Completeness | ✅ Implemented | 实体存在性校验通过 `semantic-model/entities.yaml` 单元测试。 |
| CTS-TP-003 Relation Integrity | ✅ Implemented | 关系 source/target 一致性校验通过单元测试；builder 内置跨包引用存在性检查。 |
| CTS-TP-004 Artifact Generation | ✅ Implemented | 5 种 adapter 产物生成 + SHACL/JSON Schema 深度验证（正负用例）在 `tests/psa/`。 |
| CTS-TP-005 Runtime Loading | ⚠️ Partial | Package 可加载回 OntologyIR，但 EASG Runtime 真实加载未验证。 |

---

## 2. Gap Detail

### GAP-001：SHACL 验证未执行 ✅ Closed 2026-07-15

- **描述**：`constraints/{package}.shacl` 已生成，但当前没有调用 `pyshacl` 对示例实例进行验证。
- **解决**：`tests/psa/test_semantic_validation.py::TestSHACLValidation` 新增 4 个用例（1 正 3 负），验证示例实例符合 shapes，且缺失必填关系/必填属性/错误数据类型均被捕获。
- **附带修复**：发现原示例实例不满足 `hasTransformerEnd` 的 `sh:minCount 1`，已将示例改为 `@graph` 多节点链接结构。

### GAP-002：JSON Schema 验证未执行 ✅ Closed 2026-07-15

- **描述**：`jsonschema/{package}.schema.json` 已生成，但当前没有验证示例实例是否通过 JSON Schema。
- **解决**：`tests/psa/test_semantic_validation.py::TestJSONSchemaValidation` 新增 4 个用例（1 正 3 负）。
- **附带修复**：发现原 schema 与示例表面结构不一致（`type` vs `@type`、缺 `@context`/`@graph`），已重写 schema 使其描述 JSON-LD 表面文档。

### GAP-003：OWL 推理验证未执行 ✅ Closed 2026-07-17

- **描述**：`ontology/{package}.owl` 可解析，但未运行任何 OWL 推理（如 `rdflib` 或外部 reasoner）。
- **解决**：`tests/psa/test_owl_reasoning.py::TestRDFSReasoning` 新增 3 个用例，使用 `owlrl.DeductiveClosure(RDFS_Semantics)` 验证 `rdfs:subClassOf` 传递闭包。关键发现：PSA 包只 emit 自己的类，跨包 parent 通过 IRI 引用；真实 interop 场景需要消费者**先按 `manifest.dependencies` 拉依赖包、合并图、再做闭包**——这是测试中 `_merge_closure()` 模拟的工作流。PowerTransformer → Transformer → Equipment（Equipment 定义在 `power.grid.core`）3 级传递闭包已验证。
- **附带修复**：测试用 `_dependencies_of()` 显式读取 `manifest.dependencies`，保证 PSA interop 的核心契约（manifest → 拉依赖 → 合并 → 推理）被守护。

### GAP-004：跨包引用完整性未完全验证 ✅ Closed 2026-07-15

- **描述**：`manifest.yaml` 已推导 dependencies，但尚未验证所有跨包引用的 target IRI 真实存在。
- **解决**：`PSAPackageBuilder._validate_cross_refs()` 在 `build()` 入口检查所有 parent 与 association target 是否存在于 IR；存在悬空引用时抛 `ValueError`。测试见 `test_build_rejects_dangling_cross_ref`。

### GAP-005：EASG Runtime 消费未验证

- **描述**：CTS-TP-005 要求 package 能被 EASG Runtime 加载为 Semantic Context，但 EASG Runtime 当前未接入。
- **影响**：无法证明 package 对下游 Runtime 可用。
- **计划**：与 EASG 团队对接，提供 `transformer-0.1.0` package 进行文档级/接口级验证。
- **优先级**：P2

### GAP-006：PSA 官方 CTS 规范未发布

- **描述**：PSA Engineering Baseline v0.1 目前只定义了 5 个高层 CTS 用例，缺少详细的通过/失败标准和测试输入。
- **影响**：grid-ontology 的 CTS 实现只能基于当前文档自行解释。
- **计划**：等待 PSA Governance 发布官方 CTS Specification v0.1 后对齐。
- **优先级**：P2

### GAP-007：SCR-Metadata 映射未验证

- **描述**：`mappings/mapping-template.yaml` 已生成，但尚未与 SCR-Metadata 的实际字段映射进行对账。
- **影响**：映射锚点仍是模板，未经验证。
- **计划**：与 SCR-Metadata 团队对接，确认 PMS/EMS/DMS 等系统字段映射。
- **优先级**：P3

---

## 3. CTS Implementation Status

| CTS ID | Description | grid-ontology Implementation | Gap |
|--------|-------------|------------------------------|-----|
| CTS-TP-001 | Package Metadata | `manifest.yaml` + unit test | None |
| CTS-TP-002 | Entity Completeness | `entities.yaml` + unit test | None |
| CTS-TP-003 | Relation Integrity | `relations.yaml` + unit test + builder cross-ref check | None |
| CTS-TP-004 | Artifact Generation | 5 adapters emit + parse tests + SHACL/JSON Schema validation tests + OWL reasoning closure | None |
| CTS-TP-005 | Runtime Loading | Load back to OntologyIR | GAP-005 |

---

## 4. Action Items

| ID | Action | Owner | Target | Status |
|----|--------|-------|--------|--------|
| A1 | Implement SHACL validation test | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A2 | Implement JSON Schema validation test | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A3 | Add cross-reference existence check in builder | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A4 | Draft OWL reasoning smoke test | grid-ontology | 2026-07-29 | ✅ Done 2026-07-17 |
| A5 | Coordinate EASG Runtime loading PoC | PSA Ecosystem | 2026-08-15 | Open |
| A6 | Align with official PSA CTS v0.1 | grid-ontology | TBD | Open |

---

## 5. Sign-off

- **Maintainer**: grid-ontology team
- **Reviewers**: PSA Governance, EASG Runtime, SCR-Metadata
- **Next Review**: 2026-07-29
