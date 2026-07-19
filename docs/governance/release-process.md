# Release Process

> **Status**: Draft  
> **Date**: 2026-07-17  
> **Scope**: grid-ontology 库 + PSA Semantic Package 的发布流程。  
> **Related**: `CHANGELOG.md` · `docs/governance/psa-semantic-package-contract.md` · `docs/governance/cts-gap-register.md`

---

## 1. 目标

定义一个**可重复、低回归风险**的发布流程，覆盖两类产物：

| 产物 | 形态 | 消费者 |
|------|------|--------|
| **grid-ontology 库**（PyPI `cim-ontology`） | `pip install` 可装的 Python 包 | 内部 IR/Adapters 用户、PSA 工程团队 |
| **PSA Semantic Packages** | 目录式 PSA 包（`manifest.yaml` + 14 文件） | PSA Ecosystem、EASG Runtime、下游厂商 |

两套产物共享版本节奏，但**发布动作独立**：库发布不强制伴随包发布；包版本由 PSA 治理（SemVer）单独控制。

---

## 2. 版本策略

### 2.1 grid-ontology 库

采用 **Semantic Versioning 2.0.0**（与 `CHANGELOG.md` 一致）：

| 位 | 触发条件 |
|----|---------|
| **MAJOR** | 任何破坏性变更（IR 模型字段删除/语义变更、Adapter 输出格式变更、CLI 子命令改名） |
| **MINOR** | 新增公开 API、新增 adapter、新增 Stage、新增 PSA Semantic Package 包 |
| **PATCH** | bug 修复、文档更新、内部重构、性能优化、依赖升级（不破坏 API） |

历史 tag：`v1.0.0` → `v1.7.0`（见 `git tag --sort=-v:refname`）。

### 2.2 PSA Semantic Package 版本

包内 `manifest.yaml` 的 `package.version` 字段独立管理：

| 位 | 触发条件 |
|----|---------|
| **MAJOR** | 实体/关系语义破坏（删除类、改 parent、IRI 不可逆改写） |
| **MINOR** | 新增类/属性/关系、新增枚举值（向后兼容） |
| **PATCH** | 文档修正、example 优化、SHACL 形状细化（语义不变） |

包目录名约定：`<slug>-<version>`（如 `transformer-0.1.0`），与 `manifest.package.version` 一致。

---

## 3. 预发布检查清单（Library）

每次打 tag 前**必须**全部通过：

| ID | 检查 | 命令 | 阻塞？ |
|----|------|------|--------|
| C1 | ruff lint | `ruff check src tests scripts` | ✅ 阻塞 |
| C2 | mypy 类型 | `mypy src` | ⚠️ 仅新错误阻塞 |
| C3 | 单元 + 集成 + 属性 + PSA 测试 | `pytest tests/unit tests/integration tests/property tests/psa -v` | ✅ 阻塞（0 fail） |
| C4 | pytest property profile = `ci` | 默认即 `ci`（`tests/property/conftest.py`） | 信息 |
| C5 | CHANGELOG 更新 | 手工编辑 `CHANGELOG.md` | ✅ 阻塞 |
| C6 | CTS gap register 同步 | 关闭的 GAP 移到 ✅ | ⚠️ 涉及 CTS 时阻塞 |
| C7 | 未提交残留 | `git status` 干净 | ✅ 阻塞 |
| C8 | main 分支是 HEAD | `git rev-parse --abbrev-ref HEAD` = `main` | ✅ 阻塞 |

> **P2 注意**：`e2e` 测试（`tests/e2e/test_deepseek_real_e2e.py`）走三重 skipif（无 API key / CI 环境 / 未设 `E2E_DEEPSEEK_REAL=1`），不在 release gate 内。

---

## 4. 预发布检查清单（PSA Semantic Package）

包发布前**必须**全部通过：

| ID | 检查 | 工具 | 阻塞？ |
|----|------|------|--------|
| P1 | `manifest.yaml` schema 合法 | `tests/psa/test_semantic_validation.py`（隐含） | ✅ |
| P2 | 14 个必需文件齐全 | `test_required_files_exist` | ✅ |
| P3 | OWL / SHACL / JSON-LD / JSON Schema 可解析 | `test_owl_parses` / `test_shacl_parses` / `test_jsonld_context_valid` / `test_jsonschema_valid` | ✅ |
| P4 | **SHACL 示例通过** | `TestSHACLValidation.test_example_conforms_to_shapes` | ✅ |
| P5 | **JSON Schema 示例通过** | `TestJSONSchemaValidation.test_example_validates_against_schema` | ✅ |
| P6 | **跨包引用完整** | `test_build_rejects_dangling_cross_ref` | ✅ |
| P7 | **OWL 推理闭包成立** | `tests/psa/test_owl_reasoning.py`（多包合并 + RDFS closure） | ✅ |
| P8 | CTS 声明覆盖（5 个 CTS-TP-* 全部存在） | `TestCTSDeclarationCoverage` | ✅ |
| P9 | `package-cts.yaml` 与实现一致 | 手工 review | ⚠️ |
| P10 | `manifest.version` 与目录名一致 | 手工 review | ✅ |

---

## 5. 发布步骤（Library）

```bash
# 0. 准备：本地 main 是 HEAD
git checkout main
git pull --rebase origin main

# 1. 跑全量门禁
ruff check src tests scripts
mypy src
pytest tests/unit tests/integration tests/property tests/psa -v

# 2. 更新 CHANGELOG.md：在 [Unreleased] 段写本次变更，按 Added/Changed/Fixed/Test/Security 五段

# 3. 提交
git add CHANGELOG.md
git commit -m "docs(changelog): prepare vX.Y.Z"

# 4. 打 tag
git tag -a vX.Y.Z -m "vX.Y.Z — <一句话描述>"

# 5. 推送（需人工授权）
git push origin main
git push origin vX.Y.Z

# 6. PyPI 发布（手动或 CI 触发）
#    .github/workflows/release.yml（post-MVP）
```

### 5.1 commit 规范

每个 P0/P1 任务**独立 commit**，不批量。格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

- `type`: `feat` / `fix` / `test` / `refactor` / `docs` / `chore`
- `scope`: `ir` / `cleaner` / `adapters` / `reviewer` / `psa` / `cli` / `docs`
- 关联 issue / gap：`Refs GAP-003` / `Closes GAP-005`

### 5.2 CHANGELOG 五段

按 [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/)：

- **Added**：新功能、新 API、新 adapter
- **Changed**：行为变更（非破坏）、依赖升级
- **Fixed**：bug 修复
- **Test**：新增/修改测试（无生产代码变更）
- **Security**：安全相关修复

每段只列**用户可见的变更**，跳过内部重构。

---

## 6. 发布步骤（PSA Semantic Package）

```bash
# 1. 构建
python scripts/build_psa_package.py --all --output packages/

# 2. 跑包级测试（用刚构建的 output_dir）
pytest tests/psa -v

# 3. 人工 review manifest.yaml + package-cts.yaml

# 4. 提交（包含新生成的 packages/<slug>-<version>/）
git add packages/<slug>-<version>/
git commit -m "feat(psa): release <slug> v<version>"

# 5. （可选）上传到 PSA Package Catalog
#    与 PSA Governance 协调，post-MVP 接入自动 catalog
```

> **重要**：包目录**进 git**（已约定），因为下游 EASG / 第三方可能通过 git tag 直接 fetch；PyPI 仅发布 Python 库本身。

---

## 7. 发布后

| 动作 | 负责人 | 时机 |
|------|--------|------|
| GitHub Release 写 changelog 摘要 | maintainer | tag 推送后 24h 内 |
| PSA Catalog 登记新包 | maintainer + PSA Governance | 同上 |
| 内部 Slack `#psa-ecosystem` 通告 | maintainer | 同上 |
| 下游 EASG / SCR-Metadata 团队通知 | maintainer | 同上 |
| `cts-gap-register.md` 下一次 review 推进未关闭项 | maintainer | tag + 7d |

---

## 8. Hotfix 流程

发现紧急 bug 已发布版本（影响下游消费者）：

1. 从受影响 tag `git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z`
2. 最小修复（**不改无关代码**——minimal change engineer）
3. 跑全量门禁
4. 更新 CHANGELOG 单独段：`## [X.Y.Z+1] - YYYY-MM-DD — Hotfix`
5. PR → main → tag → push
6. 通知 +1d 内到位

不允许跨 MAJOR 边界的 hotfix：1.6.x hotfix 不能修 1.7.x 的回归——后者必须发 1.7.1。

---

## 9. 不在范围（post-MVP）

- 自动化 PyPI 发布（`.github/workflows/release.yml`）
- 自动化 PSA Catalog 上传
- 自动化 GitHub Release 生成（release-drafter）
- 签名 tag / Sigstore 验证
- SemVer 兼容性 CI（`pysemver`、`griffe`）

这些与本流程解耦，独立迭代。

---

## 10. Sign-off

- **Maintainer**: grid-ontology team
- **Reviewers**: PSA Governance
- **Effective from**: 2026-07-17（与 grid-ontology v1.7.0 同时生效）
- **Next review**: 2026-10-17（季度 review），或新增 P0 GAP 时即时更新