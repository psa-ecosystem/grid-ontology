# 项目使用指南

> **Grid Ontology** — GB/T 43259.301-2024（IDT IEC 61970-301:2020）CIM 本体提取与生成器
>
> 当前版本：**v1.5.0**（2026-07-01）

---

## 目录

1. [概述](#1-概述)
2. [安装](#2-安装)
3. [快速开始](#3-快速开始)
4. [Pipeline 架构](#4-pipeline-架构)
5. [CLI 参考](#5-cli-参考)
6. [Python API](#6-python-api)
7. [适配器与产物](#7-适配器与产物)
8. [LLM Provider 配置](#8-llm-provider-配置)
9. [测试与验证](#9-测试与验证)
10. [常见任务](#10-常见任务)
11. [Troubleshooting](#11-troubleshooting)
12. [参考](#12-参考)

---

## 1. 概述

`cim-ontology` 将 CIM（Common Information Model）标准 Markdown 文档解析为统一的中间表示（IR），并通过可选的 LLM 复审清洗 OCR 噪声，最终发射为 5 种机器可读格式：

- **OWL / RDF Turtle** — 语义 Web 本体（`cim17_full.ttl`）
- **SHACL Shapes** — 数据校验规则
- **JSON-LD Context** — 关联数据上下文
- **JSON Schema** — 结构化数据校验
- **Python Types** — 类型化的 Python 数据类（含跨包 import 边）

**适用场景**：

- IEC 61970-301 / GB/T 43259.301 标准的二次开发
- 电力行业知识图谱构建
- 多格式数据交换中间层生成

---

## 2. 安装

### 2.1 前置依赖

- Python ≥ 3.12
- （可选）LLM Provider API Key：Claude / DeepSeek

### 2.2 步骤

```bash
# 进入项目目录
cd /Users/nexlume/AI-Workspace/grid-ontology

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装（含 dev 依赖）
pip install -e ".[dev]"
```

`[dev]` 包含 pytest、hypothesis、syrupy、ruff、mypy。

### 2.3 验证安装

```bash
cim-ontology --help
# 应输出 typer 帮助信息
```

---

## 3. 快速开始

### 3.1 最小示例（无 LLM）

```bash
# 从标准 markdown 构建 OWL + SHACL + JSON-LD Context
cim-ontology build \
  --input docs/GBT43259301—2024/cim-base-full.md \
  --output ./build
```

### 3.2 完整 5 格式输出 + LLM 复审

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # 或 DEEPSEEK_API_KEY

cim-ontology build \
  --input docs/GBT43259301—2024/cim-base-full.md \
  --output ./build \
  --format owl \
  --format shacl \
  --format jsonld-context \
  --format json-schema \
  --format python-types \
  --llm
```

### 3.3 编程方式

```python
from pathlib import Path
from cim_ontology.pipeline import build

result = build(
    md_path=Path("docs/GBT43259301—2024/cim-base-full.md"),
    output_dir=Path("./build"),
    formats=["owl", "python-types"],
    use_llm=False,
)

print(result["stats"])  # 各 adapter 的统计
print(result["ir"].stats.class_count, "classes")
```

---

## 4. Pipeline 架构

```
┌────────────────────────────────────────────────────────────────┐
│ Markdown 文档                                                   │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                  ┌────────────▼─────────────┐
                  │ Stage 1: 规则清洗         │ clean_markdown_to_ir()
                  │   markdown-it-py 解析      │
                  │   章节分割 + 表格抽取      │
                  │   ClassDef / DataProperty  │
                  └────────────┬──────────────┘
                               │
                          IR (Pydantic v2)
                               │
                  ┌────────────▼─────────────┐
                  │ Stage 2: LLM 复审（可选） │ LLMReviewer.review()
                  │   OCR 噪声识别            │
                  │   batch review（节省 RTT）│
                  │   known_classes 业务校验   │
                  └────────────┬──────────────┘
                               │
                          IR（修订后）
                               │
       ┌───────────┬───────────┼───────────┬───────────┐
       ▼           ▼           ▼           ▼           ▼
   ┌──────┐   ┌──────┐   ┌────────┐  ┌────────┐  ┌────────┐
   │ OWL  │   │SHACL │   │JSON-LD │  │  JSON  │  │ Python │
   │      │   │      │   │Context │  │ Schema │  │ Types  │
   └──────┘   └──────┘   └────────┘  └────────┘  └────────┘
       │           │           │           │           │
       └───────────┴───────────┴───────────┴───────────┘
                               │
                  ┌────────────▼─────────────┐
                  │ Stage 4: 跨适配器一致性    │ adapter.verify()
                  │   IRI 唯一性               │
                  │   零循环 import            │
                  └────────────────────────────┘
```

**关键模块**：

| 模块 | 路径 | 职责 |
|------|------|------|
| `cleaner` | `src/cim_ontology/cleaner/` | Stage 1 markdown 解析 |
| `reviewer` | `src/cim_ontology/reviewer/` | Stage 2 LLM 复审 |
| `adapters` | `src/cim_ontology/adapters/` | Stage 3 + 4 输出 |
| `ir` | `src/cim_ontology/ir/` | 中间表示模型 |
| `observability` | `src/cim_ontology/observability/` | Metrics / 结构化日志 |

---

## 5. CLI 参考

### 5.1 `cim-ontology build`

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--input, -i` | Path | **必填** | 输入 Markdown 文件 |
| `--output, -o` | Path | `./build` | 输出根目录 |
| `--format, -f` | list[str] | `[owl, shacl, jsonld-context]` | 输出格式（可重复） |
| `--llm` | bool | `False` | 启用 LLM 复审（Stage 2） |

**支持的 `--format` 值**：

| 值 | 适配器 | 产物 |
|----|--------|------|
| `owl` | `OwlTurtleAdapter` | `<output>/owl/cim17_full.ttl` + 20 包文件 |
| `shacl` | `ShaclAdapter` | `<output>/shacl/cim17_shapes.ttl` |
| `jsonld-context` | `JsonLdContextAdapter` | `<output>/jsonld-context/*.jsonld`（20 文件） |
| `json-schema` | `JsonSchemaAdapter` | `<output>/json-schema/*.json`（20 文件） |
| `python-types` | `PythonTypesAdapter` | `<output>/python-types/*_types.py`（20 文件，含跨包 import） |

### 5.2 示例

```bash
# 仅 OWL 输出
cim-ontology build -i input.md -f owl -o ./owl-only

# OWL + Python Types（验证跨包 import）
cim-ontology build -i input.md -f owl -f python-types -o ./mixed

# 完整 5 格式 + LLM 复审
cim-ontology build -i input.md -f owl -f shacl -f jsonld-context -f json-schema -f python-types --llm -o ./full
```

---

## 6. Python API

### 6.1 顶层入口

```python
from cim_ontology.pipeline import build
result = build(md_path, output_dir, formats=..., use_llm=..., llm_provider=...)
```

返回 `dict`，包含：

| 键 | 类型 | 说明 |
|----|------|------|
| `ir` | `OntologyIR` | 中间表示 |
| `stats` | `dict` | 各 adapter 统计 |
| `emits` | `dict[str, EmitResult]` | 每个格式的 emit 结果 |

### 6.2 单 Adapter 调用

```python
from pathlib import Path
from cim_ontology.adapters import get_adapter
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir

# Stage 1
ir = clean_markdown_to_ir(Path("input.md"))

# Stage 3 (单个 adapter)
adapter = get_adapter("owl")
emit_result = adapter.emit(ir, Path("./build/owl"))

print(emit_result.files)        # list[Path]
print(emit_result.stats)        # dict
```

### 6.3 自定义 LLM Provider

实现 `LLMProvider` 协议：

```python
from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt

class MyProvider(LLMProvider):
    def review(self, prompt: ReviewPrompt) -> str:
        # 调用你的 LLM API
        # 返回 JSON 数组字符串
        return '[{"case_id": "...", "decision": "accept", "new_name": "..."}]'

# 用法
from cim_ontology.pipeline import build
result = build(input_path, output_dir, llm_provider=MyProvider(), use_llm=True)
```

详见 `src/cim_ontology/reviewer/providers.py` 的内置 `ClaudeProvider` / `DeepSeekProvider` / `OllamaProvider`。

---

## 7. 适配器与产物

### 7.1 OWL / RDF Turtle

```
build/owl/
├── cim17_full.ttl              # 完整本体（~26 876 triples）
└── cim17_<package>.ttl         # 20 个分包文件
```

验证：

```python
from rdflib import Graph, RDF, OWL
g = Graph().parse("build/owl/cim17_full.ttl", format="turtle")
classes = {str(s) for s, _, _ in g.triples((None, RDF.type, OWL.Class))}
print(f"OWL Class 数: {len(classes)}")  # 期望 472（去重后）
```

### 7.2 SHACL

```
build/shacl/
└── cim17_shapes.ttl            # ~992 shapes
```

### 7.3 JSON-LD Context

```
build/jsonld-context/
├── Core.jsonld
├── Wires.jsonld
└── ... (20 文件)
```

### 7.4 JSON Schema

```
build/json-schema/
├── Core.json
├── Wires.json
└── ... (20 文件)
```

### 7.5 Python Types

```
build/python-types/
├── Core_types.py
├── Wires_types.py
└── ... (20 文件)
```

**v1.5 新增**：跨包 import 边（例如 `Wires_types.py` 含 `from Core_types import IdentifiedObject`），运行时不依赖循环 import。

---

## 8. LLM Provider 配置

### 8.1 支持的 Provider

| Provider | 类 | 环境变量 | base_url |
|----------|-----|----------|----------|
| Claude | `ClaudeProvider` | `ANTHROPIC_API_KEY` | api.anthropic.com |
| DeepSeek | `DeepSeekProvider` | `DEEPSEEK_API_KEY` | api.deepseek.com |
| Ollama | `OllamaProvider` | （无） | localhost:11434 |
| Mock | `MockProvider` | （无） | fixtures |

### 8.2 配置示例

```bash
# Claude（推荐用于复杂推理）
export ANTHROPIC_API_KEY="sk-ant-..."

# DeepSeek（成本更低）
export DEEPSEEK_API_KEY="sk-..."

# Ollama（本地、完全离线）
ollama serve  # 确保 localhost:11434 可访问
```

⚠️ **API Key 安全**：

- 切勿硬编码或写入 git tracked 文件
- 永远通过环境变量或 `export` 注入
- 错误日志已自动截断到 200 字符（F2 SENSITIVE-TO-OBSERVABILITY）

### 8.3 选择 Provider

CLI 不直接接受 `--provider` 参数；通过 `use_llm=True` 时使用 `MockProvider`（fixtures），要切换 Provider 需编程方式：

```python
from cim_ontology.pipeline import build
from cim_ontology.reviewer.providers import ClaudeProvider

result = build(
    md_path=input_path,
    output_dir=output_path,
    use_llm=True,
    llm_provider=ClaudeProvider(),
)
```

---

## 9. 测试与验证

### 9.1 运行测试

```bash
# 全量
.venv/bin/python -m pytest tests/ -q
# 期望：486 passed, 4 skipped in ~19s

# 单文件
.venv/bin/python -m pytest tests/unit/test_class_dedup.py -v

# 特定 marker
.venv/bin/python -m pytest tests/ -m hypothesis -v
```

### 9.2 测试金字塔

| 层级 | 路径 | 数量 | 覆盖 |
|------|------|------|------|
| Unit | `tests/unit/` | ~470 | 适配器、Reviewer、IR 模型 |
| Integration | `tests/integration/` | ~10 | 端到端流程 |
| Property | `tests/property/` | ~6 | Hypothesis 不变量 |
| E2E | `tests/e2e/` | 极少 | 真实 LLM API（需 key） |

### 9.3 E2E 真实 API 测试

```bash
export DEEPSEEK_API_KEY="sk-..."
export E2E_DEEPSEEK_REAL=1
.venv/bin/python -m pytest tests/e2e/test_deepseek_e2e.py -v
```

三重守卫（`DEEPSEEK_API_KEY` 已设置 + `CI != true` + `E2E_DEEPSEEK_REAL=1`）防止 CI 误触发。

---

## 10. 常见任务

### 10.1 添加新适配器

```python
# src/cim_ontology/adapters/my_format.py
from cim_ontology.adapters.base import OutputAdapter, EmitResult, VerifyResult

class MyFormatAdapter(OutputAdapter):
    def emit(self, ir, output_dir: Path) -> EmitResult:
        # 你的实现
        return EmitResult(files=[...], stats={...})

    def verify(self, output_dir: Path) -> VerifyResult:
        # 一致性校验
        return VerifyResult(passed=True, issues=[])
```

注册（`src/cim_ontology/adapters/__init__.py`）：

```python
ADAPTERS["my-format"] = MyFormatAdapter
```

### 10.2 增加 OCR 测试样本

编辑 `tests/fixtures/ocr_noise_samples.json`：

```json
{
  "case_id": "noise_sample_51",
  "source_table": 51,
  "package": "Core",
  "raw_text": "Voltge1..*",
  "rule_attempt": {"value": "Voltge1..*"},
  "uncertainty_reason": "multiplicity_leak",
  "expected_correction": "Voltage",
  "category": "multiplicity_leak",
  "context_snippet": "..."
}
```

无需修改测试代码——`test_p2d_stage2_ocr_samples.py` 自动参数化新样本。

### 10.3 修改 Reviewer Prompt

`src/cim_ontology/reviewer/prompts.py`：

```python
_SYSTEM = """你是一位 CIM 17 标准专家 ..."""

_USER_TEMPLATE = """待复审条目：
{entries}

已知类名清单：
{known_classes}

... 输出 JSON 数组 ..."""
```

### 10.4 调试 IR

```python
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir
from pathlib import Path

ir = clean_markdown_to_ir(Path("input.md"))
print(ir.model_dump_json(indent=2))  # 完整 IR dump

# 统计
print(f"包数: {ir.stats.package_count}")
print(f"类数: {ir.stats.class_count}")
print(f"不确定条目: {len(ir.uncertain_entries)}")
```

### 10.5 单独运行 Stage 1 或 Stage 3

```python
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir
from cim_ontology.adapters import get_adapter

# Stage 1
ir = clean_markdown_to_ir(Path("input.md"))

# 单独 emit（绕过完整 pipeline）
adapter = get_adapter("owl")
adapter.emit(ir, Path("./owl-only"))
```

### 10.6 检查结构化日志

所有阶段输出 structlog JSON 日志。运行 pipeline 时：

```bash
.venv/bin/python -c "
from cim_ontology.pipeline import build
build(...)
" 2>&1 | jq .
```

关键事件：

- `stage_start` / `stage_end` — 阶段边界
- `class_dedup_started` / `class_dedup_picked_winner` / `class_dedup_completed` — 去重追踪
- `cross_package_refs_inferred` — 跨包引用推断结果
- `python_types_ocr_parent_skipped` / `python_types_ocr_assoc_target_skipped` — fail-soft 跳过

---

## 11. Troubleshooting

### 11.1 `PythonTypesAdapter` 抛出 ValueError

**症状**：`emit` 阶段 ValueError: OCR 噪声 ...

**原因**：v1.4 前曾 fail-fast。v1.4+ 已 fail-soft 跳过（OCR 属性），但 `_validate_class_name` 仍 fail-fast。

**修复**：检查 IR 是否含 LaTeX 残骸 / 多重性 leak 的 **类名**（不是属性）。这类需要 Stage 1 修复或手动排除。

### 11.2 OWL `rdfs:isDefinedBy` 冲突

**症状**：同一 class 在 OWL 多处出现。

**原因**：v1.5 之前。v1.5+ 已通过 `deduplicate_cross_package_classes` 自动去重。

**解决**：确认使用 v1.5.0（`git log -1 --oneline` 应显示 `chore(release): v1.5.0`）。

### 11.3 `cross_package_refs = []` 空

**症状**：OWL 缺 `owl:imports`，Python 缺 `from X import`。

**原因**：v1.5 之前。v1.5+ 自动推断（`_infer_refs.infer_cross_package_refs`）。

**验证**：

```python
from rdflib import Graph, OWL
g = Graph().parse("build/owl/cim17_full.ttl", format="turtle")
imports = list(g.triples((None, OWL.imports, None)))
print(f"owl:imports 数: {len(imports)}")  # 期望 20
```

### 11.4 LLM Reviewer 不工作

**检查项**：

1. API Key 是否设置（`echo $ANTHROPIC_API_KEY`）
2. `use_llm=True` 是否传入
3. `--llm` CLI 标志是否启用
4. 错误日志（`error` 级别）是否有 rate limit / timeout

### 11.5 测试失败但本地工作

**常见原因**：

- 缺少 venv 依赖：`pip install -e ".[dev]"`
- Python 版本不符（要求 ≥ 3.12）
- Pyright 报告 import 错误——**已知 false positive**，运行时无影响

### 11.6 ICCP 类归属 Core

**症状**：OWL 输出中 Core 反向 import Wires。

**原因**：Stage 1 markdown 解析将 ICCP 类放在 Core section（实际是 ICCP 包语义）。Core 含 14 个 ICCP 类深度扎根（4-12 same-pkg refs），richest-wins 决策正确。

**状态**：v1.6+ 待办（需 Stage 1 引入 `is_abstract` + 包归属 metadata），不影响正确性（OWL 允许循环 import）。

---

## 12. 参考

### 12.1 核心文档

| 文档 | 路径 |
|------|------|
| 设计规范 | `docs/superpowers/specs/2026-06-22-grid-ontology-design.md` |
| 实施计划 | `docs/superpowers/plans/2026-06-22-grid-ontology.md` |
| E2E 验证报告 | `docs/cim-e2e-validation-report.md` |
| CHANGELOG | `CHANGELOG.md` |
| 本指南 | `docs/USAGE.md` |

### 12.2 关键模块索引

| 模块 | 入口 | 用途 |
|------|------|------|
| `cleaner` | `clean_markdown_to_ir()` | Stage 1 |
| `reviewer` | `LLMReviewer` | Stage 2 |
| `adapters` | `get_adapter(fmt)` | Stage 3 |
| `pipeline` | `build()` | 顶层编排 |
| `ir.models` | `OntologyIR` / `ClassDef` / `Package` | IR 定义 |
| `observability` | `Metrics` | 可观测性 |

### 12.3 版本演进

| 版本 | 日期 | 关键变更 |
|------|------|----------|
| v1.5.0 | 2026-07-01 | 跨包引用推断、Class 去重、Stage 2 扩样 |
| v1.4.x | 2026-06-30 | OCR 鲁棒标识符、fuzzy 包去重 |
| v1.3.0 | 2026-06-30 | Metrics / 结构化日志 |
| v1.2.2 | 2026-06-30 | OCR 样本扩样、批处理 max_tokens |
| v1.1.0 | 2026-06-30 | Reviewer 批处理、DeepSeek Provider、IRI 安全 |
| v1.0.0 | 2026-06-22 | 脚手架 + 5 阶段 Pipeline |

### 12.4 贡献流程

修改代码后：

1. **写测试**：新增逻辑必须有对应单元测试
2. **运行测试**：`pytest tests/ -q` 全部通过
3. **更新文档**：本指南 + CHANGELOG（如有新功能）
4. **commit**：用户授权后执行（默认不会主动 commit）

---

**反馈与改进**：发现错误或有改进建议，编辑 `docs/USAGE.md` 并提交 PR。