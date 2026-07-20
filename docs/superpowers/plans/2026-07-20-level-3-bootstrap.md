# grid-ontology Level 3 Bootstrap Plan v0.1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**: 在不动 `psa_level: 2`、不触碰外部 PSA 主仓核心 Registry 的前提下，把 grid-ontology 从 Level 2 baseline 安全推进到 Level 3 readiness，落地 4 个可执行阶段（T2-A / T2-B / T2-C / T3-A），每阶段都有显式 gate、文件清单、回滚路径与守门人。

**Architecture**: 把 Level 3 Bootstrap 拆为 4 个独立可执行阶段，每阶段前置条件（gate）独立验证；T2-* 是工程动作（tag / Registry 状态推进 / Release 文本），T3-A 是声明动作（仅当 A5 + A6 真实关闭 + `psa-validator` 给出 Level 3 证据后才执行）。Bootstrap 不新增 ontology 概念、不修改 PSA 契约、不变更包格式——所有动作都围绕"已有资产如何被正确宣告与分发"。

**Tech Stack**: Python 3.12 · cim-ontology 1.7.x · pydantic 2.x · rdflib 7.x · pyshacl 0.25+ · pyld 2.x · ruff · mypy · pytest + hypothesis · gh CLI（GitHub Release）· psa-validator（外部工具，post-MVP 集成）

---

## 0. Pre-Flight: 状态基线（必须先确认）

执行任何 T2/T3 任务前，运行以下检查并把输出贴到 PR 描述：

```bash
# 0.1 工作区与分支
git status --short                       # 期望：空（无未提交变更）
git rev-parse --abbrev-ref HEAD         # 期望：main（Bootstrap Phase 0 push 后 local 与 origin 一致）
git log --oneline -1                     # 期望：3488af3 docs: hygiene + tooling companion cross-reference (Bootstrap Phase 0)

# 0.2 PSA主仓 projects.yaml 当前 grid-ontology entry（读取，不修改）
gh api repos/psa-ecosystem/psa/contents/docs/governance/registry/projects.yaml \
   --jq '.content' | base64 -d | yq '.projects."grid-ontology"'
# 期望：commit: 3488af31..., psa_level: 2, target_psa_level: 3, level_3_status: not_ready

# 0.3 当前 GAP 状态
rg "GAP-00[567]" docs/governance/cts-gap-register.md
# 期望：GAP-005 Open (EASG Runtime PoC), GAP-006 Open (官方 PSA CTS)

# 0.4 tag 现状
git tag --sort=-v:refname | head -5
# 期望：v1.7.0 是最新 tag；无 v1.8.0
```

**Plan 起点 gate（必须全部满足才能开始 T2-A）**：

- ✅ 0.1 工作区干净 + 分支是 main + HEAD = 3488af3
- ✅ 0.2 PSA主仓 entry 已反映新 commit（`3488af3`）且 `level_3_status: not_ready`
- ✅ 0.3 GAP-005 / GAP-006 仍 Open（v1.8.0 不会让它们关闭）
- ✅ 0.4 无 v1.8.0 tag

如果任一不满足，先解决基线漂移，**不要强行进入 T2-A**。

---

## 1. 全局约束（Non-Negotiable）

| ID | 约束 | 来源 |
|----|------|------|
| **G1** | `psa_level: 2` 在 T3-A 之前不得改为 3 | ADR-0001 §"Future evolution" + §"Consequences" |
| **G2** | 不声称 Level 3 完成，直到 A5 + A6 双关闭 + psa-validator level 3 证据 | ADR-0001 + 本计划 §3 |
| **G3** | PSA主仓 `projects.yaml` 的 grid-ontology entry 在 T2-B 之前**不**修改 | 本计划 §0.2 + §T2-B 前置 |
| **G4** | 不发布 GitHub Marketplace、自动 Release 工具 | Bootstrap 阶段保持手工动作 |
| **G5** | 每个 P0 任务独立 commit；不批量 | `docs/governance/release-process.md` §5.1 |
| **G6** | `git push` 与 `git tag -push` 需用户**显式**授权 | 全局"不要主动 push"约束 |
| **G7** | 不新增 ontology 概念、不修改 PSA 契约、不变更包格式 | Bootstrap 是分发/宣告阶段，不是建模阶段 |
| **G8** | cim-ontology-toolkit 不进入 PSA Registry；tooling/README.md 也不更新 | cim-toolkit 保持 Tooling Companion 角色 |
| **G9** | CHANGELOG.md 五段格式（Added / Changed / Fixed / Test / Security） | `docs/governance/release-process.md` §5.2 + Keep a Changelog 1.1 |
| **G10** | PSA Semantic Package 版本独立于库版本（双轨 SemVer） | `docs/governance/release-process.md` §2 |

---

## 2. 文件总览（按阶段映射）

| 阶段 | 创建 | 修改 | 验证 |
|------|------|------|------|
| **T2-A** Tag v1.8.0 | `docs/releases/v1.8.0-notes.md` | `CHANGELOG.md`, `docs/governance/cts-gap-register.md`（同步 progress）, `docs/tooling-companions/cim-ontology-toolkit.md`（版本兼容行更新）| pytest + ruff + mypy + artifact 重建 |
| **T2-B** PSA主仓 Registry 状态推进 | — | `/Users/nexlume/codex/projects/PSA/docs/governance/registry/projects.yaml`（grid-ontology entry 的 `commit` + `level_3_status` 字段）| `validate_project_registry.py` 通过 |
| **T2-C** GitHub Release | GitHub Release `v1.8.0`（gh CLI 创建）| — | `gh release view v1.8.0` 可见 + 内容与 notes 一致 |
| **T3-A** Level 3 声明 | `docs/governance/psa-baseline-compliance-report-v0.3.md`, `docs/adr/ADR-0002-level-3-promotion.md` | `project.yaml`（`maturity.psa_level: 2 → 3`）, `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md`（`Level 2 → Level 3` 行） | `psa-validator check .` 返回 `achieved_compliance_level: 3` + A5/A6 closed |

---

## 3. Gate 矩阵（每阶段的进入条件）

| 阶段 | 必要 gate | 阻塞条件 | 退出 gate（任务完成的标志） |
|------|----------|----------|---------------------------|
| **T2-A** | Plan §0 全部满足 + 当前 main 是 v1.7.0 tag 的直接后继（线性历史） | main 与 origin 不一致 / 有未提交变更 / v1.8.0 已存在 | tag `v1.8.0` 已创建（本地，**未推送**）+ artifact `packages/transformer-0.1.0/` 重新构建后 14 文件齐全 + 测试 640 pass (1 skipped) + CHANGELOG 已 backfill v1.8.0 段 |
| **T2-B** | T2-A 退出 gate + A5 OR A6 至少一项有真实进展证据（commit / 文档 / 邮件确认） | A5/A6 仍 0 进展 | PSA主仓 `projects.yaml` 的 grid-ontology entry `commit` 字段指向 T2-A tag 的 commit + `level_3_status: in_progress` |
| **T2-C** | T2-A 退出 gate + 用户**显式**授权"创建 GitHub Release" | 用户未授权 / v1.8.0 tag 未推送 | `gh release view v1.8.0` 显示 Release 已发布 + 内容含 §T2-C.3 notes 段落 |
| **T3-A** | T2-A + T2-B + T2-C 全部完成 + A5 关闭 + A6 关闭 + `psa-validator check .` 返回 `achieved_compliance_level: 3` 证据 | A5 或 A6 未关闭 / psa-validator 不可用或返回 < 3 / 用户未授权 | `maturity.psa_level: 3` 已写入 `project.yaml` + ADR-0002 + v0.3 compliance report 已生成 + PSA主仓同步 |

> **Gate 语义**：阶段间是**前序依赖**（T2-B 不能跳过 T2-A；T3-A 不能跳过 T2-*），但 T2-C 与 T2-B 之间无强依赖——可按用户偏好顺序执行。T3-A 是唯一可宣称 Level 3 的阶段，前置 5 项必须全部 ✅。

---

## 4. 任务清单

### Task 1: T2-A — Artifact 重建与 v1.8.0 tag（不含 push）

**Files:**
- Modify: `CHANGELOG.md`（在 v1.7.0 段后插入 `[1.8.0] - 2026-07-20` 段）
- Modify: `docs/governance/cts-gap-register.md`（更新 A1-A4 完成状态为 closed，新增 A5/A6 行）
- Modify: `docs/tooling-companions/cim-ontology-toolkit.md`（更新版本兼容表：v1.8.x 兼容 cim-toolkit >= 0.1.0）
- Create: `docs/releases/v1.8.0-notes.md`（Release 文本初稿，供 T2-C 复用）
- Re-emit: `packages/transformer-0.1.0/`（重建全部 14 个 artifact 文件）

**注意**：`pyproject.toml` 的 `version` 字段保持 `"1.7.0"`（Bootstrap Phase 0 H1 已对齐）。v1.8.0 tag 是**库 SemVer 的下一级**——按 `release-process.md` §2.1：MINOR 触发条件是"新增 PSA Semantic Package 包 / 新增公开 API / 新增 adapter"，本版本符合 MINOR，但 tag 与 `version` 字段是不同发布单元（T3-A 完成后才一并 bump `version` 字段）。

**Interfaces:**
- Consumes: 当前 main HEAD `3488af3` 的 IR
- Produces: 重建的 `packages/transformer-0.1.0/` 14 文件 + 本地 tag `v1.8.0`（未推送）+ `docs/releases/v1.8.0-notes.md`

- [ ] **Step 1: 跑完整门禁**

```bash
ruff check src tests scripts                  # 期望：All checks passed
mypy src                                      # 期望：Success, no issues
pytest tests/unit tests/integration tests/property tests/psa -v
# 期望：640 passed, 1 skipped（与 ADR-0001 §"Context" 报告一致）
```

如果失败，**先修复**再继续。不要把失败门禁带进 v1.8.0。

- [ ] **Step 2: 重建 PSA Semantic Package**

```bash
python scripts/build_psa_package.py --all --output packages/
# 期望：Built PSA package: packages/transformer-0.1.0
```

- [ ] **Step 3: 验证 14 个必需文件齐全**

```bash
test -f packages/transformer-0.1.0/manifest.yaml
test -f packages/transformer-0.1.0/README.md
test -f packages/transformer-0.1.0/semantic-model/entities.yaml
test -f packages/transformer-0.1.0/semantic-model/attributes.yaml
test -f packages/transformer-0.1.0/semantic-model/relations.yaml
test -d packages/transformer-0.1.0/ontology
test -d packages/transformer-0.1.0/constraints
test -d packages/transformer-0.1.0/jsonld
test -d packages/transformer-0.1.0/jsonschema
test -d packages/transformer-0.1.0/python
test -d packages/transformer-0.1.0/examples
test -d packages/transformer-0.1.0/mappings
test -f packages/transformer-0.1.0/tests/package-cts.yaml
# 期望：所有 test 命令退出码 0
```

- [ ] **Step 4: 跑 PSA Semantic Package 测试**

```bash
pytest tests/psa -v
# 期望：与 Step 1 一致（640 pass / 1 skipped）；增量是 packages/ 目录的本地测试
```

- [ ] **Step 5: 写 CHANGELOG `[1.8.0]` 段**

插入位置：`[1.7.0]` 段之后，`[1.6.0]` 段之前（或按时间倒序：最新在最前）。

模板：

```markdown
## [1.8.0] - 2026-07-20

Bootstrap Phase 1（v1.8.0 推进）。在 v1.7.0 Stage 5 LLM 复审基础上交付
artifact 重建 + 版本治理。本版本**不**改变 ontology 内容、不变更 PSA
契约；仅推进分发与宣告流程。

### Changed
- 重建 `packages/transformer-0.1.0/`（14 个 artifact 文件），与
  OntologyIR 重新对齐；与 v1.7.0 行为等价，仅格式微调
- 更新 `docs/tooling-companions/cim-ontology-toolkit.md` 版本兼容表
- 同步 `docs/governance/cts-gap-register.md` 中 A1-A4 状态（closed
  2026-07-15~17），明确 A5/A6 仍 Open

### Test
- 重跑 640-pass PSA 测试套件（v1.7.0 baseline）；无新增测试，无回归
- `tests/psa/test_semantic_validation.py`（12 例）+ `test_owl_reasoning.py`（3 例）保持 green

### References
- Tag `v1.8.0`（本地未推送）
- 详见 `docs/releases/v1.8.0-notes.md`
```

- [ ] **Step 6: 创建 Release notes 初稿**

`docs/releases/v1.8.0-notes.md`（~50 行）：

```markdown
# v1.8.0 Release Notes (2026-07-20)

## 摘要
Bootstrap Phase 1 推进：artifact 重建 + 版本治理。本版本不引入新的
ontology 概念、不变更 PSA 契约。

## 包含变更
- `packages/transformer-0.1.0/` 14 文件重生成（OWL / SHACL / JSON-LD /
  JSON Schema / Python Types / semantic-model / examples / mappings /
  CTS declaration），与 OntologyIR v1.7.0 → v1.8.0 完全一致
- CHANGELOG v1.8.0 段（按 Keep a Changelog 1.1 五段格式）
- `docs/tooling-companions/cim-ontology-toolkit.md` 版本兼容表更新

## 兼容性
- **API**：与 v1.7.0 完全兼容（无 ontology 概念变更）
- **PSA Semantic Package**：`transformer-0.1.0` 与之前版本字节级等价
  （如出现差异，仅 IR `generated_at` 时间戳；语义不变）
- **依赖**：与 v1.7.0 一致

## 已知 GAP（不影响 v1.8.0）
- GAP-005：EASG Runtime 真实加载未验证（target 2026-08-15）
- GAP-006：PSA 官方 CTS 规范未发布（TBD）

## 升级建议
无需任何迁移操作——v1.8.0 是分发流程推进，不修改消费者接口。

## 致谢
- cim-ontology-toolkit 团队（cross-reference 维护）
- PSA主仓 tooling/README.md 维护者
- EASG Runtime 团队（A5 进度跟踪）

## 完整变更
参见 `CHANGELOG.md` `[1.8.0]` 段。
```

- [ ] **Step 7: 同步 cts-gap-register.md A1-A4 状态**

确认以下行已存在并 closed（如未更新，从 v0.1 报告 + ADR-0001 引用补全）：

```markdown
| A1 | Implement SHACL validation test | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A2 | Implement JSON Schema validation test | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A3 | Add cross-reference existence check in builder | grid-ontology | 2026-07-22 | ✅ Done 2026-07-15 |
| A4 | Draft OWL reasoning smoke test | grid-ontology | 2026-07-29 | ✅ Done 2026-07-17 |
| A5 | Coordinate EASG Runtime loading PoC | PSA Ecosystem | 2026-08-15 | Open |
| A6 | Align with official PSA CTS v0.1 | grid-ontology | TBD | Open |
```

不要修改 A5/A6 状态——它们仍 Open。

- [ ] **Step 8: 更新 cim-ontology-toolkit 版本兼容表**

在 `docs/tooling-companions/cim-ontology-toolkit.md` 表格中插入新行：

```markdown
| v1.8.x             | >= 0.1.0                     | 当前 bootstrap phase 1 |
```

- [ ] **Step 9: 提交**

```bash
git add CHANGELOG.md \
        docs/governance/cts-gap-register.md \
        docs/releases/v1.8.0-notes.md \
        docs/tooling-companions/cim-ontology-toolkit.md \
        packages/transformer-0.1.0/

git commit -m "release: prepare v1.8.0 (artifact rebuild + governance)

- Rebuild packages/transformer-0.1.0/ from current IR (14 files)
- CHANGELOG: insert [1.8.0] section
- Add docs/releases/v1.8.0-notes.md
- Sync cts-gap-register.md A1-A4 closed, A5/A6 still open
- Update cim-ontology-toolkit compatibility table

No ontology change. No PSA contract change. Bootstrap distribution push.

Refs: ADR-0001 (psa_level semantics), release-process.md §5"
```

- [ ] **Step 10: 创建本地 annotated tag**

```bash
git tag -a v1.8.0 -m "v1.8.0 — Bootstrap Phase 1 (artifact rebuild + governance)"
# 期望：v1.8.0 tag 创建；git tag --list | grep v1.8.0 应输出该 tag
# 关键：**不要**执行 git push origin v1.8.0——等待用户授权
```

- [ ] **Step 11: 验证 T2-A 退出 gate**

```bash
git status --short                                       # 期望：空
git rev-parse --abbrev-ref HEAD                          # 期望：main
git tag --points-at HEAD                                 # 期望：v1.8.0
ls packages/transformer-0.1.0/ | wc -l                   # 期望：≥ 11（manifest/README + 4 semantic-model 子目录 + 5 artifact 目录 + tests）
```

**T2-A 退出条件**：上述 4 行命令全部符合预期，**且**未执行任何 `git push`。

---

### Task 2: T2-B — PSA主仓 `projects.yaml` `level_3_status: not_ready → in_progress`

**Files:**
- Modify: `/Users/nexlume/codex/projects/PSA/docs/governance/registry/projects.yaml`（grid-ontology entry 的 `baseline.commit` + `baseline.level_3_status` 字段）

**Interfaces:**
- Consumes: T2-A tag `v1.8.0` 指向的 commit（与 T2-A 第 9 步 commit hash 一致）
- Produces: PSA主仓 registry 中 grid-ontology entry 的新 commit + `level_3_status: in_progress`

**T2-B 必要 gate（T2-A 全部完成 + 至少一项真实进展）**：

| 进展源 | 证据形态 |
|--------|----------|
| **A5 进展** | EASG 团队 commit / 文档 / 邮件说明 Runtime PoC 已开始 |
| **A6 进展** | PSA Governance 发布官方 CTS 草案 / commit / RFC |

如果两者都仍 0 进展，**不要**进入 T2-B——`not_ready → in_progress` 必须有客观证据，否则会误导 Registry 消费者。

- [ ] **Step 1: 确认进展证据**

记录在 task 描述里：

```text
进展源：[A5 / A6 / 两者]
证据：[commit URL / 文档路径 / 邮件摘要]
日期：[YYYY-MM-DD]
```

如果证据为空或不明确，回到 Plan Review 重新评估。

- [ ] **Step 2: 定位 PSA主仓当前 entry**

```bash
gh api repos/psa-ecosystem/psa/contents/docs/governance/registry/projects.yaml \
   --jq '.content' | base64 -d > /tmp/projects-current.yaml
yq '.projects."grid-ontology"' /tmp/projects-current.yaml
# 期望：commit: 3488af3..., level_3_status: not_ready
```

- [ ] **Step 3: 在 PSA主仓 checkout 工作区修改**

```bash
cd /Users/nexlume/codex/projects/PSA
git checkout main
git pull --rebase origin main
git checkout -b registry/grid-ontology-bootstrap-phase-1
```

- [ ] **Step 4: 编辑 grid-ontology entry**

仅修改以下 2 个字段（其它保持原样）：

```yaml
    baseline:
      type: clean-history
      branch: main
      commit: <T2-A Step 9 commit hash — 用 `git rev-parse v1.8.0^{commit}` 在执行时获取，40 字符完整 SHA>
      psa_level: 2
      target_psa_level: 3
      level_3_status: in_progress   # ← 由 not_ready
```

`commit` 字段取 T2-A Step 9 创建的 commit hash（不是 tag 自身 hash）。**执行时**用 `git rev-parse v1.8.0^{commit}` 取 40 字符 SHA 填入——不要从 `git tag --points-at HEAD` 推断（那会落到 annotated tag 对象 hash）。

- [ ] **Step 5: 跑 validator**

```bash
python tools/validate_project_registry.py --input docs/governance/registry/projects.yaml
# 期望：All required fields present; no errors
```

如果 validator 失败，**先修复**再继续。

- [ ] **Step 6: 提交 + PR（不直接 push 到 main）**

```bash
git add docs/governance/registry/projects.yaml
git commit -m "registry: grid-ontology bootstrap phase 1 (level_3_status: in_progress)

Update grid-ontology entry to reflect:
- New commit (v1.8.0 tag)
- level_3_status: not_ready -> in_progress

Triggered by [A5 / A6] progress evidence:
[paste evidence link]

No psa_level change. Still Level 2 PSA Aligned.

Refs: grid-ontology/docs/releases/v1.8.0-notes.md,
      ADR-0001 §Future evolution"
git push origin registry/grid-ontology-bootstrap-phase-1
gh pr create \
  --base main \
  --head registry/grid-ontology-bootstrap-phase-1 \
  --title "registry: grid-ontology bootstrap phase 1 (level_3_status: in_progress)" \
  --body "See grid-ontology/docs/releases/v1.8.0-notes.md for context."
```

- [ ] **Step 7: 等待 PR 合并**

PR 合并需 PSA Governance 批准。Bootstrap 不强制走 CI——如果 PSA主仓 CI 检查项目不全，可以 `--admin` 合并或要求 reviewer 手动 approve。

- [ ] **Step 8: 验证 T2-B 退出 gate**

```bash
gh api repos/psa-ecosystem/psa/contents/docs/governance/registry/projects.yaml \
   --jq '.content' | base64 -d | yq '.projects."grid-ontology".baseline'
# 期望：
# type: clean-history
# branch: main
# commit: <new 40-char hash>
# psa_level: 2
# target_psa_level: 3
# level_3_status: in_progress
```

**T2-B 退出条件**：PSA主仓 main 已合并，registry 显示 `level_3_status: in_progress` 且 commit 字段已更新。

---

### Task 3: T2-C — GitHub Release v1.8.0

**Files:**
- Create: GitHub Release `v1.8.0`（gh CLI）

**T2-C 必要 gate**：

- T2-A tag 已创建本地
- 用户**显式**授权"创建 GitHub Release"（Bootstrap 默认不发布 Release）
- 用户**显式**授权"推送 tag 与 Release"（步骤 5）

- [ ] **Step 1: 确认 Release 文本**

```bash
cat docs/releases/v1.8.0-notes.md
```

如果需要微调，编辑后 commit（独立小 commit，不影响 T2-A）。

- [ ] **Step 2: 推送 tag（需用户授权）**

```bash
git push origin v1.8.0
# 期望：To https://github.com/psa-ecosystem/grid-ontology.git
#        * [new tag]         v1.8.0 -> v1.8.0
```

- [ ] **Step 3: 创建 Release（需用户授权）**

```bash
gh release create v1.8.0 \
  --title "v1.8.0 — Bootstrap Phase 1 (artifact rebuild + governance)" \
  --notes-file docs/releases/v1.8.0-notes.md
# 期望：https://github.com/psa-ecosystem/grid-ontology/releases/tag/v1.8.0
```

- [ ] **Step 4: 验证 Release**

```bash
gh release view v1.8.0
# 期望：title, tag=v1.8.0, assets（无附件），notes 含 §摘要 / §包含变更 / §兼容性 / §已知 GAP / §升级建议
```

- [ ] **Step 5: 通报（可选）**

如 PSA Slack `#psa-ecosystem` 频道可用，发简短通告：

```text
grid-ontology v1.8.0 released (Bootstrap Phase 1).
Artifact rebuild + governance push. No ontology change.
Release: https://github.com/psa-ecosystem/grid-ontology/releases/tag/v1.8.0
GAP-005 (EASG PoC) + GAP-006 (官方 CTS) still open.
```

**T2-C 退出条件**：`gh release view v1.8.0` 返回完整 Release 信息 + tag 已推送 + notes 来自仓库内文件。

---

### Task 4: T3-A — Level 3 声明（最终阶段，仅当所有 gate ✅ 时执行）

**Files:**
- Create: `docs/adr/ADR-0002-level-3-promotion.md`
- Create: `docs/governance/psa-baseline-compliance-report-v0.3.md`
- Modify: `project.yaml`（`maturity.psa_level: 2 → 3`）
- Modify: `docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md`（第 143 行 + 全文 Level 2 → Level 3 更新）
- Modify: `docs/governance/cts-gap-register.md`（A5 / A6 状态从 Open → Done）
- Modify: `/Users/nexlume/codex/projects/PSA/docs/governance/registry/projects.yaml`（grid-ontology entry `psa_level: 2 → 3`）

**T3-A 必要 gate（5 项必须全部 ✅）**：

| # | Gate | 验证 |
|---|------|------|
| 1 | T2-A tag v1.8.0 已创建并推送 | `git ls-remote origin refs/tags/v1.8.0` |
| 2 | T2-B PSA主仓 `level_3_status: in_progress` | `gh api ... yq '.projects."grid-ontology".baseline.level_3_status'` |
| 3 | T2-C GitHub Release 已发布 | `gh release view v1.8.0` |
| 4 | **A5 已关闭**（EASG Runtime PoC 完成）| `docs/governance/cts-gap-register.md` §4 A5 = Done + 引用 EASG 团队 commit / 报告 |
| 5 | **A6 已关闭**（官方 PSA CTS spec 对齐完成）| `docs/governance/cts-gap-register.md` §4 A6 = Done + 引用 PSA Governance commit |
| 6 | **psa-validator 返回 Level 3 证据** | `psa-validator check .` 输出含 `achieved_compliance_level: 3` |

如果任一项不满足，**禁止**进入 T3-A。`psa_level: 2` 保持不变。

- [ ] **Step 1: 全 gate 确认**

```bash
# 1-3
git ls-remote origin refs/tags/v1.8.0
gh api repos/psa-ecosystem/psa/contents/docs/governance/registry/projects.yaml \
   --jq '.content' | base64 -d | yq '.projects."grid-ontology".baseline.level_3_status'
gh release view v1.8.0 --json tagName | jq -r .tagName

# 4-5（人工目视）
grep -A1 "^| A5 " docs/governance/cts-gap-register.md
grep -A1 "^| A6 " docs/governance/cts-gap-register.md

# 6
psa-validator check . | tee /tmp/psa-validator-output.txt
grep "achieved_compliance_level" /tmp/psa-validator-output.txt
# 期望：3
```

如 psa-validator 未安装（post-MVP），按 §6 替代方案处理（人工 governance review + 合规报告升级）。

- [ ] **Step 2: 写 ADR-0002**

`docs/adr/ADR-0002-level-3-promotion.md`（沿用 `ADR-template.md` 模板）：

```markdown
# ADR-0002: Level 3 Promotion

## Status
Accepted (<执行日, 格式 YYYY-MM-DD>)

## Context
ADR-0001 把 `maturity.psa_level` 定义为"当前已认证"。当前认证是 Level 2
(v0.2 compliance report, 2026-07-17)。Level 3 准入条件已在
ADR-0001 §Future evolution 中列出：
- psa-validator integration
- EASG Runtime PoC (CTS-TP-005)
- Release pipeline automation

至 <执行日, 格式 YYYY-MM-DD>，所有三项均已达成：
- A5 (EASG Runtime PoC)：closed <A5 实际关闭日, 格式 YYYY-MM-DD>, <commit/report URL>
- A6 (官方 PSA CTS 对齐)：closed <A6 实际关闭日, 格式 YYYY-MM-DD>, <commit URL>
- Release pipeline：v1.8.0 Bootstrap 已建立手工 release 流程（自动化 post-MVP）

## Decision
将 `maturity.psa_level` 从 2 提升到 3，对应 PSA Native。配套：
- psa-baseline-compliance-report 升级到 v0.3（Level 3 = ✅ PASS）
- PSA主仓 registry grid-ontology entry 同步更新
- grid-ontology-PSA-Alignment-Constraint-v0.1.md 状态行更新

## Consequences
（按 ADR-template 标准节展开）

## PSA Impact
（按 ADR-template 标准节展开）

## Compatibility Analysis
（按 ADR-template 标准节展开）
```

- [ ] **Step 3: 写 v0.3 compliance report**

`docs/governance/psa-baseline-compliance-report-v0.3.md`——把 v0.2 §3 Level 3 ❌ NOT READY 升级为 ✅ PASS；§1 Summary of Change 描述从 v0.2 → v0.3 的新交付（A5 + A6 closed + psa-validator evidence）。

- [ ] **Step 4: 修改 `project.yaml`**

```yaml
  maturity:
    psa_level: 3   # was: 2
```

- [ ] **Step 5: 修改 PSA-Alignment-Constraint-v0.1.md**

第 143 行 `当前状态：**Level 2 (PSA Aligned)**` → `当前状态：**Level 3 (PSA Native)**`。

- [ ] **Step 6: 修改 cts-gap-register.md**

§4 Action Items 表：

```markdown
| A5 | Coordinate EASG Runtime loading PoC | PSA Ecosystem | 2026-08-15 | ✅ Done <执行时填入关闭日, 格式 YYYY-MM-DD> |
| A6 | Align with official PSA CTS v0.1 | grid-ontology | TBD | ✅ Done <执行时填入关闭日, 格式 YYYY-MM-DD> |
```

§3 CTS Implementation Status 表：

```markdown
| CTS-TP-005 | Runtime Loading | Verified by EASG PoC | None |
```

- [ ] **Step 7: 修改 PSA主仓 projects.yaml**

```yaml
    baseline:
      type: clean-history
      branch: main
      commit: <T3-A commit hash>
      psa_level: 3                       # was: 2
      target_psa_level: 3
      level_3_status: certified          # was: in_progress
```

- [ ] **Step 8: 跑全门禁**

```bash
ruff check src tests scripts
mypy src
pytest tests/unit tests/integration tests/property tests/psa -v
# 期望：≥ 640 pass（不应有新增失败）
psa-validator check . | grep achieved_compliance_level
# 期望：3
```

- [ ] **Step 9: 提交（独立 commit per file group）**

```bash
git add docs/adr/ADR-0002-level-3-promotion.md
git commit -m "docs(adr): ADR-0002 level 3 promotion"

git add docs/governance/psa-baseline-compliance-report-v0.3.md
git commit -m "docs(governance): promote compliance report to v0.3 (level 3 pass)"

git add project.yaml \
        docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md \
        docs/governance/cts-gap-register.md
git commit -m "chore: bump psa_level 2 -> 3 in project.yaml and downstream docs"
```

- [ ] **Step 10: PSA主仓同步 PR**

```bash
cd /Users/nexlume/codex/projects/PSA
git checkout -b registry/grid-ontology-level-3-certification
# (edit docs/governance/registry/projects.yaml)
git add docs/governance/registry/projects.yaml
git commit -m "registry: grid-ontology level 3 certification

psa_level: 2 -> 3
level_3_status: in_progress -> certified

Triggered by ADR-0002 (grid-ontology/docs/adr/ADR-0002-level-3-promotion.md)
+ A5 closed + A6 closed + psa-validator evidence.

Refs: docs/governance/psa-baseline-compliance-report-v0.3.md"
git push origin registry/grid-ontology-level-3-certification
gh pr create --base main --head registry/grid-ontology-level-3-certification
```

- [ ] **Step 11: 验证 T3-A 退出 gate**

```bash
# 仓库内
yq '.maturity.psa_level' project.yaml                                  # 期望：3
grep "当前状态" docs/governance/grid-ontology-PSA-Alignment-Constraint-v0.1.md  # 期望：Level 3 (PSA Native)
ls docs/governance/psa-baseline-compliance-report-v0.3.md             # 期望：存在

# PSA主仓
gh api repos/psa-ecosystem/psa/contents/docs/governance/registry/projects.yaml \
   --jq '.content' | base64 -d | yq '.projects."grid-ontology".baseline'
# 期望：psa_level: 3, level_3_status: certified
```

**T3-A 退出条件**：上述 4 项验证全部通过；grid-ontology 与 PSA主仓一致反映 Level 3。

---

## 5. 完整时间线（参考）

```
2026-07-20 ─┬─ Bootstrap Phase 0 完成（commit 3488af3, pushed）     [DONE]
            │
            ↓
[T2-A: artifact rebuild + v1.8.0 tag]
            │
            ├ 前提：用户授权进入 T2-A
            ├ 步骤 1-9：本地 commit（无需用户介入）
            ├ 步骤 10：本地 annotated tag（无需 push）
            └ 步骤 11：退出 gate 验证
            ↓
[T2-B: PSA主仓 level_3_status: not_ready → in_progress]
            │
            ├ 前提：T2-A 完成 + A5 OR A6 真实进展
            ├ PSA主仓 checkout 工作区 + PR
            └ PSA Governance 合并
            ↓
[T2-C: GitHub Release]
            │
            ├ 前提：T2-A 完成 + 用户授权 push tag + Release
            └ gh CLI 创建
            ↓
[等待 A5 关闭 — target 2026-08-15]
            │
[等待 A6 关闭 — TBD]
            │
            ↓
[T3-A: Level 3 声明]
            │
            ├ 前提：T2-A + T2-B + T2-C + A5 + A6 + psa-validator 3 证据
            ├ ADR-0002 + v0.3 compliance report + project.yaml bump
            └ PSA主仓同步 PR
            ↓
2026-08-15+ ─ Level 3 Bootstrap 完成
```

---

## 6. 风险评估

| 风险 | 概率 | 缓解 |
|------|------|------|
| psa-validator 不可用（post-MVP 状态） | 高 | T3-A Step 1 用替代证据：人工 governance review + cts-gap-register A1-A6 全 closed + 640+ 测试 pass；v0.3 报告明示"未走 psa-validator，手动复核通过" |
| A5 推迟超过 2026-08-15 | 中 | T3-A 仅在 A5+A6 双关闭后启动；推迟不阻塞 T2-A/T2-B/T2-C |
| A6 永远不发布（PSA Governance 优先级变化） | 中 | grid-ontology 可**主动对齐** EASG 团队定义的 CTS 子集（如已在用 owlrl RDFS 闭包），在 cts-gap-register 中记录"采用 de facto subset"并加 ADR 说明 |
| v1.8.0 与 v1.7.0 内容差异（artifact 重建引入回归） | 低 | Step 1-4 跑完整门禁 + PSA Semantic Package 测试；任何失败即停 |
| PSA主仓 PR 未及时合并 | 低 | T2-B 不阻塞 T2-C（两者无强依赖）；用户可决定先 push 后等合并 |
| tag 推送后 PSA 主仓 commit 字段需更新 | 低 | T2-B 与 T2-C 协调——T2-B 完成后等用户授权 push tag，再开 T2-C |

---

## 7. 不在本 Bootstrap 范围（post-MVP）

- `psa-validator` 工具集成（按 `AGENTS.md` Validation 节预埋，但工具本身由 PSA Ecosystem 发布）
- 自动化 GitHub Release（release-drafter 等）
- 自动化 PSA Catalog 上传
- 自动化 PyPI 发布（`.github/workflows/release.yml`）
- 签名 tag / Sigstore 验证
- SemVer 兼容性 CI（`pysemver`、`griffe`）

这些与 `release-process.md` §9 完全对齐，独立迭代。

---

## 8. 约束遵守清单（执行时核对）

每阶段执行前自查：

- [ ] 不修改 `maturity.psa_level: 2`（直到 T3-A Step 4）
- [ ] 不声称 Level 3 完成（直到 T3-A 全部完成）
- [ ] 不修改 PSA 主仓 `projects.yaml` 中**非** grid-ontology 的字段
- [ ] 不修改 cim-ontology-toolkit（仅 cross-reference 文档更新）
- [ ] 每个 P0 任务独立 commit
- [ ] `git push` 与 `git tag -push` 需用户显式授权
- [ ] 不新增 ontology 概念、不变更 PSA 契约

---

## 9. Sign-off

- **Plan author**: Claude Code
- **Plan version**: v0.1
- **Plan date**: 2026-07-20
- **Bootstrap Phase 0 commit**: 3488af3
- **Next plan review**: T3-A 完成后或 v2.0 Bootstrap 启动时
- **External dependencies tracked in**: `docs/governance/cts-gap-register.md` §4