# Grid Ontology Level 2 Roadmap

> **目标**：从 PSA Engineering Baseline Level 1（Repository Ready）推进到 Level 2（PSA Aligned）。
> **状态**：✅ **Level 2 已达成**（2026-07-17，详见 `psa-baseline-compliance-report-v0.2.md` 与 ADR-0001）。
> **当前阶段**：等待 EASG Runtime / 官方 PSA CTS 等外部依赖以推进 Level 3。
> **原时间范围**：2026 Q3–Q4（按计划完成）。

---

## Level 2 完成标准

| 维度 | Level 2 要求 | 当前状态 |
|------|-------------|----------|
| **Contract** | 明确定义 grid-ontology 输出与 PSA Semantic Package Specification 的映射契约 | ✅ 已创建 `psa-semantic-package-contract.md` |
| **Tests** | 覆盖 PSA primitive 映射、package format、compatibility 的测试 | ✅ 新增 `tests/unit/test_psa_package_builder.py`（16 用例） |
| **Documentation** | ADR、兼容性分析、CTS gap register、release process | ✅ 全部就位（ADR-0001、compatibility-analysis-template、cts-gap-register、release-process） |

---

## 三阶段路线

### Phase 1：Core Domain Model

**目标**：建立电网核心语义参考模型，作为后续专业域模型的基础。

**覆盖概念**：

```text
Power Grid Core Ontology
├── Asset
├── Equipment
├── Location
├── Organization
├── Work
├── Event
└── Measurement
```

**关键任务**：

| ID | 任务 | 优先级 |
|----|------|--------|
| C1 | 定义 Core Domain 类的 IRI 与 namespace 策略 | P0 |
| C2 | 建立 `Asset` / `Equipment` / `Location` 的继承与关联 | P0 |
| C3 | 定义核心属性体系（name, identifier, status, category） | P0 |
| C4 | 为每个核心类添加 SourceRef 与 Evidence 引用 | P1 |
| C5 | 生成 5 adapter 产物并验证一致性 | P1 |

**退出条件**：

- Core Domain Model 在 OntologyIR 中完整表达；
- 5 adapter 输出一致；
- 所有核心类至少 1 个 SourceRef。

---

### Phase 2：Equipment Ontology

**目标**：建立电网设备领域模型，重点覆盖变压器、开关、线路、保护装置、表计。

**覆盖概念**：

```text
Equipment Ontology
├── Transformer
├── Breaker
├── Line
├── Cable
├── ProtectionDevice
└── Meter
```

**关键任务**：

| ID | 任务 | 优先级 |
|----|------|--------|
| E1 | 定义 `Transformer` 及其关键属性（ratedCapacity, voltageLevel, manufacturer, operatingStatus, installedIn） | P0 |
| E2 | 定义 `Breaker` / `Line` / `Cable` / `ProtectionDevice` / `Meter` 的核心属性与关联 | P0 |
| E3 | 建立 Equipment 与 Core Domain（Asset / Equipment / Location）的继承关系 | P0 |
| E4 | 定义设备状态模型与测量点关联 | P1 |
| E5 | 补全 Equipment 域的负面测试与属性不变量 | P1 |

**退出条件**：

- Equipment Ontology 覆盖 6 类核心设备；
- 每个设备类有明确的 PSA primitive 映射；
- 通过 L1-L3 分层校验。

---

### Phase 3：Transformer Semantic Package

**目标**：产出 PSA Ecosystem 的第一个电网语义包——Transformer Semantic Package v0.1。

**包内容**：

```text
Transformer Semantic Package v0.1
├── Transformer
│   ├── ratedCapacity
│   ├── voltageLevel
│   ├── manufacturer
│   ├── operatingStatus
│   └── installedIn
├── TransformerEnd
├── PowerTransformer
└── Terminal
```

**关键任务**：

| ID | 任务 | 优先级 | 状态 |
|----|------|--------|------|
| P1 | 定义 PSA Semantic Package 输出格式（manifest + artifacts + evidence） | P0 | ✅ 已完成 |
| P2 | 实现 `Transformer` 子集的 PSA package export | P0 | ✅ 已完成 |
| P3 | 建立 package-level validation fixtures | P0 | ⚠️ 部分完成（单元测试已覆盖结构/解析，深度语义校验待补充） |
| P4 | 记录 CTS gaps（与 PSA CTS 的差距） | P1 | ✅ 已完成 |
| P5 | 编写 Transformer Package 使用示例 | P1 | ✅ 已自动生成 |

**退出条件**：

- 可生成一个 PSA-compatible Transformer Semantic Package；
- package 通过 grid-ontology 内部 validation；
- CTS gaps 已记录；
- 下游 EASG Runtime 可消费该 package（至少文档级验证）。

---

## Level 2 必需产物清单

| 产物 | 位置 | 说明 |
|------|------|------|
| PSA Semantic Package Contract | `docs/governance/psa-semantic-package-contract.md` | ✅ 明确输出映射契约 |
| ADR 目录 | `docs/adr/` | 已创建，需补充具体 ADR |
| Compatibility Analysis Template | `docs/governance/compatibility-analysis-template.md` | ✅ 用于 Type C 变更 |
| PSA Primitive Mapping Tests | `tests/unit/test_reference_models.py` | ✅ 验证 Entity primitive 映射 |
| CTS Gap Register | `docs/governance/cts-gap-register.md` | ✅ 记录与 PSA CTS 的差距 |
| Release Process | `docs/governance/release-process.md` | ✅ PSA-compliant 发布流程（库 SemVer + 包版本双轨） |

---

## 与 BUILDER_V2_PLAN 的关系

本 Roadmap 聚焦 PSA 对齐（Level 2），与 `docs/BUILDER_V2_PLAN.md` 的业务阶段互补：

- `BUILDER_V2_PLAN.md` §2 阶段 1（IR + Provenance）→ 为 Core Domain Model 提供 SourceRef 基础；
- `BUILDER_V2_PLAN.md` §2 阶段 2（Validator）→ 为 Equipment Ontology 提供 L1-L3 校验；
- `BUILDER_V2_PLAN.md` §2 阶段 3（Exporter Contract）→ 为 Transformer Semantic Package 提供统一输出契约；
- `BUILDER_V2_PLAN.md` §2 阶段 4（Release Package）→ 为 PSA Semantic Package 发布提供打包能力。

---

## 下一步动作

1. ~~实现 SHACL / JSON Schema 深度验证测试~~ ✅ 2026-07-15 完成（`tests/psa/test_semantic_validation.py`，9 用例）；
2. ~~在 package builder 中增加跨包引用存在性检查~~ ✅ 2026-07-15 完成（`_validate_cross_refs()`）；
3. ~~实现 OWL 推理 smoke test（GAP-003，验证 `rdfs:subClassOf` 传递闭包）~~ ✅ 2026-07-17 完成（`tests/psa/test_owl_reasoning.py`，3 用例，验证 PowerTransformer → Transformer → Equipment 3 级闭包 + `manifest.dependencies` 工作流）；
4. ~~创建 `docs/governance/release-process.md`~~ ✅ 2026-07-17 完成（覆盖 SemVer 库版本 + PSA 包版本、双套预发布清单、hotfix 流程、post-MVP 排除项）；
5. 与 EASG Runtime 对接 CTS-TP-005 真实加载验证；
6. ~~澄清 `project.yaml` 中 `psa_level: 2` 是指目标认证还是当前认证~~ ✅ 2026-07-17 完成（**ADR-0001** 决策为"当前已认证"，`project.yaml` 保持 `2`；合规报告 v0.1 → **v0.2**，Level 2 升级为 ✅ PASS）。
