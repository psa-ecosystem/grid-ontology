# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目定位

`cim-ontology` (PyPI) / `grid-ontology` (仓库) — 从 GB/T 43259.301-2024（IDT IEC 61970-301:2020）CIM 国标 PDF 抽取本体定义，生成 OWL / SHACL / JSON-LD / JSON Schema / Python Types 五种格式的离线产物。当前版本 v1.7.0（2026-07-11），处于 Pilot 阶段。

---

## 常用命令

### 安装与构建

```bash
pip install -e ".[dev]"                                       # 安装（含 dev 依赖）
cim-ontology build --input docs/GBT43259301—2024/cim-base-full.md --output ./build
cim-ontology build --input X.md --output ./build --format owl --format shacl --llm
```

默认 `--format` 列表：`["owl", "shacl", "jsonld-context"]`，可多值。

### 测试

```bash
pytest tests/unit                                              # 全部单元测试
pytest tests/unit/test_xxx.py::TestClass::test_method          # 单个测试
pytest tests/property                                          # hypothesis 属性测试
pytest tests/integration                                       # 跨 stage 集成
pytest tests/e2e -v                                            # 真实 API e2e（三重 skipif）
pytest --cov=cim_ontology --cov-report=term                    # 带覆盖率
```

CI 跑的是 `tests/unit tests/integration tests/property`（`.github/workflows/test.yml`），e2e 单独跑。

### Lint / Type

```bash
ruff check src tests                                          # ruff lint（pyproject 已配 line-length=100）
mypy src                                                      # mypy 严格类型
pyright                                                       # pyright（pyrightconfig.json: Python 3.14）
```

### 其他

```bash
python -m scripts.stage4_validate --help                       # Stage 4 跨适配器一致性诊断
python -m scripts.stage4_validate --input X.md --semantic-review --use-real-llm  # Stage 5 语义复审
```

---

## 架构核心（必读）

### 4-Stage Pipeline

```
Markdown → IR (Pydantic frozen) → LLM Reviewer → 5 Adapters → 文件输出
   ↑               ↑                    ↑              ↑
cleaner/         ir/               reviewer/      adapters/
```

单一中间表示：`OntologyIR`（`src/cim_ontology/ir/models.py`）。所有 stage 共享同一份 IR 实例。

### IR 不可变性约束（最重要的一条）

`OntologyIR` 及所有内部模型都是 `frozen=True` Pydantic BaseModel。**任何想"修改 IR"的代码都是错的**——正确做法是 `model_copy(update=...)` 返回新实例。`pipeline.build()` 返回 dict，不持有可变 IR。

### Stage 边界（不可越界）

| Stage | 模块 | 输入 | 输出 | 责任 |
|-------|------|------|------|------|
| 1 | `cleaner/` | Markdown 字符串 | `OntologyIR` | 规则清洗（95% 确定工作）+ 不确定性标记 |
| 2 | `reviewer/` | `OntologyIR.uncertain_entries` | 修订后的 `OntologyIR` | LLM 仲裁 5–10% 真不确定条目 |
| 3 | `adapters/` | `OntologyIR` | 文件 (`*.ttl` / `*.json` / `*.py`) | 多格式只读 emit |

Stage 2 默认 `MockProvider`，要真 LLM 必须显式 `--llm` 或传 `llm_provider=...`。

### LLM Reviewer 三层熔断

```
JSON 解析失败 → 业务校验失败（confidence<0.5 / 缺字段） → 保留规则结果
```

任何一层失败都不能让 emit 崩溃；fallback 必须降级到上一步结果并写 structlog 事件。

### OCR 鲁棒性是核心需求（不是补丁）

CIM 国标源文档是扫描件 OCR，**所有代码必须假设命名空间/类名/属性名带噪声**：

- `adapters/_iri_safe.py` — IRI 字符白名单 + OCR 噪声检测 + safe_attr_slug
- `adapters/_pkg_dedup.py` — 跨包 Package 精确名合并（v1.1 P3-A）
- `adapters/_class_dedup.py` — 跨包 ClassDef richest-wins 去重（v1.5 P1）
- `cleaner/_infer_refs.py` — 跨包引用自动推断（v1.5 P1）

`safe_attr_slug()` 返回的 slug **不保证**是合法 Python 标识符——调用方需再用 `is_valid_python_identifier()` 校验。

### Hypothesis 属性测试守护不变量

`tests/property/` 4 件套（116+138+65+61 LOC）守护：
- IRI 唯一性
- 类名守恒（IR → Owl → IR' 名字不变）
- 无循环 import
- 标签完整性

新加适配器时**必须**新增对应的 roundtrip property 测试。

---

## 安全护栏（必须遵守）

### API Key 三重保护

1. **永不入库**：所有真实 API 调用通过 `export DEEPSEEK_API_KEY=...` 注入，Key 不进任何文件
2. **三重 skipif 守护 e2e**（`tests/e2e/test_deepseek_real_e2e.py`）：
   ```python
   @pytest.mark.skipif(not os.environ.get("DEEPSEEK_API_KEY"), reason="no API key")
   @pytest.mark.skipif(os.environ.get("CI") == "true", reason="CI blocks real API")
   @pytest.mark.skipif(os.environ.get("E2E_DEEPSEEK_REAL") != "1", reason="not enabled")
   ```
3. **消息截断 200 字符**（observability 模块）

### 熔断

`BaseProvider` 默认 `DEFAULT_TIMEOUT_S=60`、`DEFAULT_MAX_RETRIES=3`，单样本总耗时上限 ~187s。任何 LLM 调用必须经 `BaseProvider` 走熔断，不允许裸调用。

---

## 关键陷阱（必看）

### 1. `build_taiqu{,_v2,_v3,_v4}` 是历史构建产物

不在 `.gitignore` 的默认 `build/` 模式内（因为带前缀 `build_taiqu`），但**不是产品代码**。修改前先确认是否在清理范围内（v2 决策报告建议纳入 `.gitignore`）。

### 2. `scripts/` ≠ 产品代码

`scripts/stage4_validate.py`（866 行测试覆盖）是 Stage 4/5 诊断脚本，**不在 `src/`**，CLI 也不暴露 `audit` 子命令（v2 待办）。如果新增诊断能力，请放在 `scripts/` 并对应加 `tests/unit/test_stage4_validate.py`。

### 3. `cim17` 版本号硬编码

`src/cim_ontology/ir/registry.py:66` 的 `CANONICAL["cim"]` 写死 `cim17`。一旦国标升 cim18，OWL IRI 会失效。v2 决策报告（P0-2）建议加 `OntologyIR.ontology_version` 字段并通过 OWL `<Ontology>` 头管理。

### 4. `tests/property/conftest.py` 切 hypothesis profile

默认 `ci` profile（`max_examples=20`）。开发时要详细测：
```python
from hypothesis import settings; settings.load_profile("dev")  # max_examples=100
```

### 5. `.hypothesis/` 缓存目录会被 git 排除但 `.gitignore` 不显式管理

本地会累积缓存，不需要清理。

---

## 必读文档（按重要性）

| 优先级 | 文档 | 何时读 |
|--------|------|--------|
| ★★★★★ | `docs/superpowers/specs/2026-06-22-grid-ontology-design.md` | 任何架构改动前 |
| ★★★★★ | `docs/cim-e2e-validation-report.md` | 评估数据侧改动影响 |
| ★★★★☆ | `docs/reviews/2026-07-11-v2-architecture-decision.md` | v2 战略决策时 |
| ★★★★☆ | `docs/superpowers/plans/2026-06-22-grid-ontology.md` | 看任务依赖 |
| ★★★☆☆ | `CHANGELOG.md` | 看版本 P0/P1 优先级 |
| ★★★☆☆ | `docs/superpowers/plans/2026-07-{03..10}-*.md` | 看 Stage 4/5 子计划 |

---

## 测试约定

- 测试文件位于 `tests/{unit,property,integration,e2e}/`
- fixtures 路径：`tests/fixtures/{tiny,small,medium,large,dirty,llm}/`
- LLM mock fixtures：`tests/fixtures/llm/{default,semantic_*.json}.json`
- `MockProvider` 自动识别 `case_id` 命中的 fixture 文件
- 所有 dataclass（除 Stage 5 验证脚本的某些内部模型外）应 `frozen=True`

---

## 提交约定

- Conventional Commits（`feat:` / `fix:` / `test:` / `refactor:` / `docs:`）
- 每个 P0/P1 任务独立 commit，不批量
- CHANGELOG.md 在 `Added` / `Changed` / `Fixed` / `Test` / `Security` 五段中对应段写
- 不主动 commit / push（除非用户明确要求）