# Tooling Companion: cim-ontology-toolkit

> **Status**: Active
> **Last reviewed**: 2026-07-20
> **Maintainer**: grid-ontology team（仅 cross-reference 维护）；cim-ontology-toolkit 主仓独立维护

---

## 1. 关系（Relationship）

`grid-ontology` 主仓 **不依赖** cim-ontology-toolkit 运行。后者是 **Tooling Companion**——一个独立的 Claude Code 插件，为本仓库提供 IDE / Agent 侧辅助：

- 生成 PSA Semantic Package 时的语义复审提示
- OWL / SHACL / JSON-LD / JSON Schema 的差异/一致性检查
- 对照 grid-ontology `manifest.yaml` 的 CTS gap 查询
- Stage 1+2+3+4 端到端 pipeline 编排

它是 **支持工具**，不是运行时依赖。

---

## 2. 引用来源

由 **PSA Tooling Index** 在 PSA主仓 `docs/governance/tooling/README.md`（commit `55cef18`）登记并指向本仓库：

- **上游登记（PSA主仓 → cim-ontology-toolkit → grid-ontology）**：`psa-ecosystem/psa/docs/governance/tooling/README.md`
- **Tooling repo**：https://github.com/psa-ecosystem/cim-ontology-toolkit
- **Tooling role**：`Tooling Companion`（**不是** PSA contract participant；不承载 Runtime / Registry / Agent / Application 角色）

---

## 3. 安装 / 使用

参见 cim-ontology-toolkit 仓库的 README（https://github.com/psa-ecosystem/cim-ontology-toolkit）：

```bash
# 1. 准备 Claude Code plugin marketplace 入口
# 2. 安装 cim-ontology-toolkit（详见其仓库 README）
# 3. 在本仓库目录下启用 plugin：
cc --plugin-dir /Users/nexlume/AI-Workspace/cim-ontology-toolkit
```

启用后可使用 4 个 skill（`cim-validate` / `cim-ir-fix` / `cim-e2e` / `cim-package-info`）+ 2 个 agent（`cim-reviewer-agent` / `cim-explorer-agent`）+ 1 个 MCP server（`cim-rdflib` 6 tools）。

---

## 4. 适用版本

| grid-ontology 版本 | cim-ontology-toolkit 兼容版本 | 备注 |
|--------------------|------------------------------|------|
| v1.8.x             | >= 0.1.0                     | Bootstrap Phase 1，artifact 重建（语义不变）|
| v1.7.x             | >= 0.1.0                     | 当前 Level 2 baseline |
| v1.5.x             | >= 0.1.0                     | 历史兼容 |

> cim-ontology-toolkit 0.1.0 release（commit `7978e25`，2026-07-20）首次发布，与 grid-ontology v1.7.x PSA Level 2 基线对齐。v1.8.0 兼容该 toolkit（语义与 v1.7.0 完全一致）。

---

## 5. 不在范围（Not Responsible For）

cim-ontology-toolkit **不承担**以下职责：

- ❌ PSA contract 定义（Core Semantic Model / Package Spec / Registry Spec / Runtime Contract / Agent Contract）
- ❌ Runtime 实现（生产环境运行时属于 EASG Runtime）
- ❌ Registry 治理（PSA Registry 属于 PSA主仓）
- ❌ Agent orchestration（Agent Framework 职责）
- ❌ Business application behavior（PowerGenius AI 职责）

如未来 cim-ontology-toolkit 演化为上述任一角色，必须**重新注册到 PSA Project Registry** 并变更 charter。

---

## 6. 反馈 / 问题

请到 cim-ontology-toolkit 仓库（https://github.com/psa-ecosystem/cim-ontology-toolkit）提 Issue；与 grid-ontology 本体无关的工具问题**不应**在本仓提交。

与 grid-ontology PSA Semantic Package / IR 修复相关的 feedback 可以同时提到本仓 cross-reference 文档（本文件），作为双向反馈入口。

---

## 7. Sign-off

- **Cross-reference maintained by**: grid-ontology team
- **Reviewed by**: grid-ontology team
- **Effective from**: 2026-07-20
- **Next review**: 与 grid-ontology v1.8.0 release 同步