# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — PSA Level 2 完成

本段为 PSA Level 2（PSA Aligned）闭合的累积变更。下次打 tag 时按
Keep a Changelog 惯例折叠到具体版本号段下。

### Added

- **PSA Semantic Package 输出**：`src/cim_ontology/psa/` + `scripts/build_psa_package.py` — 从 OntologyIR 生成 14 文件 PSA package（manifest / entities / attributes / relations / enumerations / OWL / SHACL / JSON-LD context / JSON Schema / Python types / example / mappings / CTS / README）。
- **PSA-specific 测试**：`tests/psa/test_semantic_validation.py`（12 用例：SHACL 正负、JSON Schema 正负、CTS 声明覆盖）+ `tests/psa/test_owl_reasoning.py`（3 用例：跨包 RDFS subClassOf 传递闭包）。
- **跨包引用完整性检查**：`PSAPackageBuilder._validate_cross_refs()` 在 `build()` 入口检查所有 parent 与 association target 是否存在于 IR，悬空引用时抛 `ValueError`。
- **PSA package metadata 字段**：`Package` 模型新增 `package_id` / `version` 字段，`reference_models/_common.py::make_package` 透传。
- **治理文档**：PSA Semantic Package Contract、ADR Template + ADR-0001（psa_level=current）、Compatibility Analysis Template、CTS Gap Register、Release Process、PSA Baseline Compliance Report v0.2。

### Fixed

- **PSA example 不符合自身 SHACL**：`hasTransformerEnd` (`sh:minCount 1`) 与原单节点示例矛盾。改为 `@graph` 多节点链接结构，正向通过 pyshacl 验证（test_example_conforms_to_shapes）。
- **JSON Schema 描述与示例表面不一致**：schema 描述 `type`/`id` 但示例用 `@type`/`@context`。schema 重写为 JSON-LD 表面文档（`@context` + `@graph` + 每个 $def 用 `@type: const`）。

### Changed

- **governance/psa-baseline-compliance-report** 从 v0.1（Level 2 ⚠️ PARTIAL）升 v0.2（Level 2 ✅ PASS）；`maturity.psa_level: 2` 保持不变但语义现在由 ADR-0001 明确定义为"当前已认证"。
- **CI 测试入口**：`pytest tests/unit tests/integration tests/property tests/psa`（`.github/workflows/test.yml`）。
- **dependencies**：`pyyaml>=6.0`、`jsonschema>=4.20`、`owlrl`（隐含 rdflib 已有）。

### Test

- 全量套件 **640 passed**（1 skipped）。新增 PSA-specific 12 用例 + 3 OWL 推理用例。handoff 阶段曾报告 741 passing；T0 复验时部分未跟踪测试文件已不在当前工作区，当前 tracked suite 为 640 passed。

### References

- ADR-0001: `docs/adr/ADR-0001-psa-level-means-current-certification.md`
- GAP-001/002/003/004: Closed（详见 `cts-gap-register.md`）
- Roadmap: `docs/governance/level-2-roadmap.md` 全部 6 项 ✅

## [1.7.0] - 2026-07-11

Stage 5 跨适配器语义一致性 LLM 复审。在 v1.6.0 诊断 CLI 基础上加入
LLM 语义仲裁，固化 5 adapter 一致性的不可达边界。

### Added

- **Stage 5 LLM review**：`scripts/stage4_validate.py --semantic-review --use-real-llm` 跨 5 adapter 产物做语义层面 LLM 复审
- **LLM 三层熔断**：JSON 解析 → 业务校验 → 降级到上一步结果

### References

- Tag `v1.7.0`, commit `5b0b82a`
- 详见 `docs/governance/release-process.md` §3 预发布清单

## [1.6.0] - 2026-07-10

Stage 4 跨适配器一致性诊断 CLI。在 v1.5.0 跨包引用修复基础上提供
5 adapter 产物（OWL / SHACL / JSON-LD / JSON Schema / Python Types）一致性诊断。

### Added

- **Stage 4 validate CLI**：`python -m scripts.stage4_validate` 跨 adapter 比对 IRI/类名/属性集合
- **Tests**：`tests/unit/test_stage4_validate.py` 866 LOC 覆盖

## [1.5.0] - 2026-07-01

Stage 3 跨适配器一致性硬化收尾 + 跨包引用语义修复。在 v1.3.0 observability 基础上
闭合 4 项 E2E 验证暴露的根因问题，OWL / Python Types 跨包产物完整对齐。

### Added

- **跨包引用自动推断（v1.5 P1 修复）**：新增 `infer_cross_package_refs()` 模块
  （`src/cim_ontology/cleaner/_infer_refs.py`），扫描 `ClassDef.parents/associations`
  重建 `(from_pkg, to_pkg, via_class)` 三元组。背景：cim-base-full.md Stage 1+2 解析后
  `ir.cross_package_refs = []`（空），但 ClassDef 实际有 375+ 个跨包引用，导致：
  - OWL 缺 `owl:imports` 声明（双向 import 缺失）
  - Python Types 缺 `from Core_types import ...`（运行 ImportError）
  - 启用后 OWL `owl:imports` 数 = **20**，Python 跨包 import 边 = **20**
- **Class 跨包去重（v1.5 P1 修复）**：新增 `deduplicate_cross_package_classes()`
  模块（`src/cim_ontology/adapters/_class_dedup.py`），richest-wins 5-tuple 排序：
  `(attrs, assocs, parents, has_desc, -position)`。背景：cim-base-full.md Stage 1+2 解析
  产生 **304 个跨包重复 ClassDef** + **181 个 intra-pkg 重复**，导致 OWL 输出中
  同一 `cim:<ClassName>` IRI 在多包重复 emit，`rdfs:isDefinedBy` 互相冲突。
  - 同一函数天然清理 intra-pkg + cross-pkg 重复（YAGNI）
  - Winner 留在原 Package 不搬运（语义上保持 ClassDef 在其原始归属包更准确）
  - structlog 事件：`class_dedup_started` / `class_dedup_picked_winner` / `class_dedup_completed`
- **Fail-soft 收集（v1.5 P1 修复）**：`PythonTypesAdapter._collect_used_types()`
  对空/OCR 噪声的 `parent.class_name` / `assoc.target.class_name` 跳过并记日志
  （`python_types_ocr_parent_skipped` / `python_types_ocr_assoc_target_skipped`），
  不再让 emit 崩溃。背景：cim-base-full.md 解析时 42 个 association 含空 target.class_name
  （如 `ConnectivityNodeContainer::Substation` 的 target 残缺），启用 `_infer_refs`
  后跨包边开始真正执行。

### Changed

- **OCR 鲁棒标识符校验扩展（v1.4 配套）**：`_validate_attr_name` 公开为模块级函数，
  与 `_validate_class_name` 一致应用 OCR 噪声检测（LaTeX 残骸 / multiplicity leak）。
  - 单元函数 fail-fast（contract 不变），适配器层 `_generate_class` 仍 swallow + 记日志
  - 新增 `test_python_types_iri_safe.py::TestCollectUsedTypesFailSoft`（2 测试）
- **结构化日志新增事件**：
  - `cross_package_refs_inferred`：跨包引用推断结果汇总
  - `class_dedup_started/completed/picked_winner`：去重过程追踪
  - `python_types_ocr_parent_skipped` / `python_types_ocr_assoc_target_skipped`：fail-soft 跳过
- **Stage 2 OCR 样本扩样（v1.5 P2 任务）**：fixture 从 14 → 50 个 OCR 噪声样本
  （`tests/fixtures/ocr_noise_samples.json`），新增覆盖：
  - `case_error`（2 样本）：`basevoltage` → `BaseVoltage`、`BASEVOLTAGE` → `BaseVoltage`
  - `namespace_pollution`（3 样本）：`cim:PowerTransformer` → `PowerTransformer`、
    `rdf:type` → `type`、`cim:IdentifiedObject` → `IdentifiedObject`
  - `clean_name`（10+ 样本）：canonical baseline 基线（`Breaker` / `PowerTransformerEnd` /
    `PhaseTapChanger` / `ApparentPower` / `SvVoltage` 等）
  - `multiplicity_leak` 扩到 21 样本，覆盖 `0..1` / `1..*` / `0..*` / `0..n` / `1..1` /
    `1..n` / `*..1` / `1..2` 八种 CIM 多重性记法
  - `typo` 扩到 7 样本：homoglyph（`Identified0bject`）/ 大小写错误（`ACLineSEGment`）/
    缺字母（`ConuctingEquipment`）等

### Fixed

- **OWL `rdfs:isDefinedBy` 互相冲突（v1.5 P1 副作用）**：304 个跨包重复 ClassDef 在
  4 个 adapter 中去重后，每个 class 在 OWL 输出中只 emit 一次，IRI 唯一性恢复。
- **OWL 文件名 OCR 副作用修复（v1.4 副作用）**：合并重名 Package 后包文件名稳定，
  不再因 OCR 变体产生重复文件名。
- **Stage 2 reviewer e2e 鲁棒性提升（v1.5 P2）**：50 个 OCR 样本参数化测试覆盖
  完整性 / 类别分布 / reviewer 处理 / 批处理 / acceptance rate / 已知类名校验 6 个维度。

### Test

- **新增**：
  - `tests/unit/test_class_dedup.py`：**17 测试** 覆盖 rank key 排序、winner 不搬运、
    intra-pkg 同步清理、不修改入参、真实 CIM 样本
  - `tests/unit/test_infer_refs.py`：**13 测试** 覆盖基础场景、跨包 parent 引用、
    跨包 assoc 引用、去重排序、真实 CIM 样本、不修改入参
  - `tests/unit/test_p2d_stage2_ocr_samples.py`：**68 测试** 覆盖 fixture 完整性、
    类别分布、reviewer 50 样本处理、批处理、acceptance rate、已知类名校验
  - `tests/unit/test_orchestrator_section_header_filter.py`（v1.4）：section header
    false-positive 修复配套测试
  - `tests/unit/test_python_types_iri_safe.py` 扩展：+2 测试（`TestCollectUsedTypesFailSoft`）
- **总测试**：418 → **486 passed**（+68），4 skipped，0 failed（19.43s）

### Documentation

- **`docs/cim-e2e-validation-report.md` v1.5 闭环**：§4 七大问题清单 6/7 已闭合
  （#7 abstract 基类识别为 P3 候选），新增 §8.5（Class 跨包去重）、§8.6
  （cross_package_refs 自动推断）两节详细修复记录。

## [1.3.0] - 2026-06-30

Observability 强化：在 v1.2.2 基础上引入可观测性基础设施，
让 Reviewer 全链路（单条/批处理）的运行时行为可度量、可分析。

### Added

- **`Metrics` 模块**（`src/cim_ontology/observability/metrics.py`）：
  - 三种原语：`Counter`（单调递增）/ `Histogram`（值分布）/ `Gauge`（瞬时值）
  - 可选 `labels`（dict）支持维度切分（如 `path=single|batch`、`outcome=success|failure`）
  - 线程安全（`threading.Lock` 守护并发写入）
  - `snapshot()` 返回 JSON 友好 dict，便于嵌入审计报告
  - 无外部依赖（避免 `prometheus_client` 等重型库）
- **Reviewer metrics 埋点（6 类指标）**：
  - `reviewer.calls{outcome,path}`：LLM 调用计数
  - `reviewer.cache{result,path}`：cache 命中/未命中/失败
  - `reviewer.fallbacks{reason,path}`：三层 fallback 分类统计
  - `reviewer.corrections{applied,path}`：修订是否实际应用
  - `reviewer.latency{path,outcome}`：LLM 调用耗时（Histogram）
  - `reviewer.batch.size{path}`：批处理规模（Gauge）
- **OCP 注入点**：`LLMReviewer` 接受可选 `metrics` 参数，
  未传则内部创建默认实例（向后兼容）。

### Changed

- **结构化日志增强**：所有 Reviewer log 事件统一追加 `path=single|batch` 维度，
  与 metrics labels 对齐便于日志/指标交叉查询（`grep reviewer.*path=batch` 一致）。

### Test

- **Metrics 单元测试**：11 个测试覆盖 inc/observe/gauge/snapshot/reset/线程安全
- **Reviewer 集成测试**：8 个测试覆盖路径埋点/fallback/cache hit/默认实例创建
- **总测试**：311 → **330 passed**（+19），4 skipped，0 failed

## [1.2.2] - 2026-06-30

多样性扩样 + 批处理响应截断修复。在 v1.1.0 基础上增强 Reviewer 鲁棒性测试覆盖。

### Changed

- **OCR 样本扩样（8 → 14）**：新增 6 个 multiplicity_leak 样本
  （`noise_sample_9` ~ `noise_sample_14`），覆盖 CIM 多重性语法变体：
  - `0..1`（可选）— 既有 sample_3
  - `1..*`（必需-多）— sample_9 `Current1..*`
  - `0..*`（可选-多）— sample_10 `Frequency0..*`
  - `0..n`（UML `n` 记法）— sample_11 `Breaker0..n`
  - `1..1`（恰好 1）— sample_12 `ACLineSegment1..1`
  - `0..1`（可选-单）— sample_13 `Substation0..1`
  - `1..n`（UML `n` 记法）— sample_14 `GeneratingUnit1..n`

### Fixed

- **批处理 JSON 响应截断**：`DeepSeekProvider.max_tokens` 默认值从 `2048` 提升到 `4096`，
  新增 `DEFAULT_MAX_TOKENS` 类属性与构造器参数（OCP 可覆盖）。14 样本批量响应约
  2500 字符，旧 2048 tokens 在 JSON 中段截断导致 `json.loads` 失败、全批 fallback。
  - 实测：8 样本无需提升仍能完成；14 样本必须 ≥ 4096 才能完整输出。
  - ClaudeProvider 维持 2048 不变（不同响应体长度特性）。
- **单元测试同步**：`test_deepseek_call_uses_correct_max_tokens` 断言更新到 `4096`。

### Test

- **单元**：311 passed, 4 skipped, 0 failed（20.13s）
- **真实 API e2e**：3 passed（single + all 14 + batch）
  - batch: 16.06s vs 25s 阈值（线性扩样未触发性能退化）
  - 13/14 修订成功（sample_2 LaTeX 残骸正确保持 uncertain）

## [1.1.0] - 2026-06-30

首个正式功能发布。在 1.0.0 脚手架之上完成 Stage 2 LLM Reviewer 全链路生产化强化
（P2-B / P2-C）和 Stage 3 / Stage 4 跨适配器一致性硬化（P3-A / P3-B）。

### Added

- **LLM Reviewer 批处理优化（v1.2 内部里程碑）**：单次 API 调用处理 N 条 uncertain 条目，
  节省 ~81% 网络 RTT（实测：8 样本 59.85s → 11.10s，8 次调用 → 1 次调用）。
  新增 `build_batch_review_prompt()` 与 `review_batch()`，错误隔离保证单条失败不影响其他条目。
- **known_classes 扩充（v1.1.1 内部里程碑）**：引入 CIM 17 标准 ~208 核心类清单
  （`tests/fixtures/cim_known_classes.txt`），覆盖 Domain / Core / Wires / Generation /
  LoadModel / Outage / Protection / Measurements / Controls / SCADA /
  OperationalLimits / Equivalents / Asset / Customers / Metering / Location 16 个包，
  修复 sample_3 multiplicity_leak 失败（Voltage0..1 → Voltage）。
- **DeepSeek V4 Provider**：通过 OpenAI 兼容 API 接入（base_url `https://api.deepseek.com`），
  支持所有 4 个 Reviewer 适配器。
- **BaseProvider 抽象类**：统一 retry / timeout 骨架（`DEFAULT_MAX_RETRIES=3`、
  `DEFAULT_TIMEOUT_S=60`），为未来 Provider（Claude / Ollama / Qwen）提供一致基线。
- **LLMCache**：SQLite 持久化缓存层，per-case_id 粒度，避免重复 LLM 请求。
- **三级回退机制**：JSON 解析失败 → 业务校验失败 → 保留规则结果（设计规范 §5.5）。
- **IRI 跨适配器安全工具**（P3-A）：`is_safe_iri_part`、`is_valid_python_identifier`、
  `contains_ocr_noise`、`safe_attr_slug`，被 owl / python_types / json_schema / jsonld_context
  四个适配器共享。
- **属性测试**（P3-B）：hypothesis invariants（IRI 唯一性、类名守恒、零循环 import），
  暴露并修复了 dict override 引发的 silent data loss。
- **E2E 真实 API 测试**（P2-C）：8 个 OCR 噪声样本（基础命名错误 / multiplicity_leak /
  LaTeX 残骸 / 拼写错误），执行 `test_batch_review_e2e` 验证批处理性能。

### Changed

- Reviewer Prompt 模板增强：明确 CIM 17 上下文（~992 类，27 包），指导 LLM 通过
  上下文推断非清单类名（避免 token 爆炸）。
- 批处理 Prompt（`prompts.py:_BATCH_USER_TEMPLATE`）：单 prompt 容纳 N 条 entry，
  强制输出 JSON 数组（按 case_id 索引），错误隔离。
- Reviewer 实际应用 LLM 修订到 `ClassDef.name`（修复 no-op bug，之前仅丢弃 LLM 结果）。
- 适配器重构：共享 IRI 安全工具模块（`_pkg_dedup.py`），跨 4 适配器 OCP 一致性。
- 测试套件：311 passed, 4 skipped, 0 failed（覆盖率 ≥ 85%）。

### Fixed

- **P3-B IRI Collision**：4 个适配器（OWL / Python Types / JSON Schema / JSON-LD Context）
  通过 `merge_duplicate_packages()` 合并重名 Package，修复 Hypothesis 属性测试
  falsifying example（两个 `Package(name='A00')` 加 `ClassDef(A00)` / `ClassDef(A01)`
  时旧代码用 dict 覆盖导致 `A01` 静默丢失）。
- **Sample 3 multiplicity_leak**：Voltage0..1 → Voltage（v1.1.1 known_classes 扩充后通过）。
- **Sample 2 LaTeX 误判**：从 known_classes 移除 Integer / Boolean / Float / String
  数据类型（DataProperty 的 data_type 而非 ClassDef），避免 LLM 把 LaTeX 残骸
  误判为 Integer。

### Security

- **F1 CI/CD TRUST**：e2e 测试三重 skipif 守卫
  （`DEEPSEEK_API_KEY` 已设置 + `CI != true` + `E2E_DEEPSEEK_REAL=1`），
  避免 CI secrets 泄露误触发。
- **F2 SENSITIVE-TO-OBSERVABILITY**：error 消息截断到 200 字符，
  防止 API Key / endpoint 泄露到日志。
- **F3 RESOURCE-BOUND PLACEMENT**：单样本 60s 熔断阈值，
  避免慢响应导致 API 成本失控（BaseProvider 重试上限 ~187s 含退避）。
- **API Key 安全**：所有真实 API 调用通过 inline `export` 注入环境变量，
  Key 永不入库；`.gitignore` 排除 `docs/deepseek_e2e_results.json`
  （含 API 元数据的运行时产物）。

## [1.0.0] - 2026-06-22

初始化发布。22 节设计规范、34 任务实施计划、Stage 1-4 完整 Pipeline 脚手架。

### Added

- **设计规范**（`docs/superpowers/specs/2026-06-22-grid-ontology-design.md`）：
  22 节，2 022 行，覆盖 Pipeline-Stage 架构、IR 模型、Reviewer 设计、6 个适配器、验证策略。
- **实施计划**（`docs/superpowers/plans/2026-06-22-grid-ontology.md`）：
  34 任务，5 245 行，5 阶段交付（M1 脚手架 / M2 Stage 1 / M3 Stage 2 / M4 Stage 3 / M5 Pipeline）。
- **Pydantic v2 IR 模型**（`src/cim_ontology/ir/models.py`）：
  Package / ClassDef / AttributeDef / AssociationDef / Multiplicity / UncertainEntry。
- **ClassRegistry**：跨包类引用索引（`src/cim_ontology/ir/registry.py`）。
- **Markdown 解析器**：markdown-it-py + 章节分割 + 表格抽取（`src/cim_ontology/cleaner/`）。
- **Stage 3 适配器骨架**：OWL/RDF Turtle / SHACL / JSON-LD Context / JSON Schema / Python Types
  共 5 个基础 emit 实现。
- **测试金字塔**：unit / integration / property / e2e 四层脚手架（`tests/`）。

[Unreleased]: https://example.com/cim-ontology/compare/v1.5.0...HEAD
[1.5.0]: https://example.com/cim-ontology/releases/tag/v1.5.0
[1.3.0]: https://example.com/cim-ontology/releases/tag/v1.3.0
[1.2.2]: https://example.com/cim-ontology/releases/tag/v1.2.2
[1.1.0]: https://example.com/cim-ontology/releases/tag/v1.1.0
[1.0.0]: https://example.com/cim-ontology/releases/tag/v1.0.0
