# Stage 5: 跨适配器语义一致性 LLM 复审设计

## 背景

grid-ontology v1.6.0 Stage 4 已建立跨 adapter **IRI 存在性**诊断能力（100 类 × 5 adapter = 500 探测点），输出 `docs/stage4-validation-report.md`。但 Stage 4 仅检查 IRI/类名存在性（found/missing），**不解析语义结构**。例如：

- IR 含 `ACLineSegment.length: float` 属性，OWL / SHACL / JSON Schema 都正确导出，但 Python Types 漏该属性（Stage 4 报 found=True，因为类存在）
- IR 含 `ACLineSegment -[0..*]→ Terminal` 关联，OWL `owl:ObjectProperty` 正确，但 JSON-LD `@context` 未导出该关联术语
- IR 多重性 `[0..*]`，SHACL `sh:maxCount` 缺失，Python 用 `list[Terminal]`，OWL 无 cardinality 约束 — 三者语义是否等价？

**Stage 5 目标**：在 Stage 4 基础上建立跨 adapter **语义一致性**诊断能力（属性覆盖 + 关联 + 多重性），用 LLM 判断结构化语义摘要是否一致，结果合并到 Stage 4 报告 §5。

### 数据驱动决策

针对 Stage 4 已诊断的 ~100 抽样类（同一批样本，seed=42 可复现）：

| 指标 | Stage 4 现状 | Stage 5 后 |
|------|------------|-----------|
| IRI 存在性诊断 | 500 探测点（100 类 × 5 adapter）| 不变（Stage 4 既有） |
| 属性覆盖诊断 | 0 | 100 类 × 5 adapter = 500 属性覆盖点 |
| 关联 + 多重性诊断 | 0 | 100 类 × 5 adapter = 500 关联点 |
| LLM 语义判断 | 0 | ≤100 次 LLM 调用（cache 命中可降至 0） |
| 报告节数 | 4 节 | 5 节（新增 §5 语义一致性） |

---

## 目标

建立 Stage 5 跨适配器语义一致性 LLM 复审能力，覆盖以下 5 个目标：

1. ✅ **语义抽取确定性**：5 个 `_extract_<adapter>_semantics()` 纯函数（无 LLM），解析 5 adapter 产物中每类的属性/关联/多重性
2. ✅ **LLM 仅判断一致性**：LLM 输入 = IR 类定义 + 5 adapter 结构化摘要（JSON），输出 `SemanticMismatch`
3. ✅ **默认 Mock，opt-in 真实**：默认 `MockProvider`（fixtures），`--use-real-llm` 走 `DeepSeekProvider`，CI 强制 Mock
4. ✅ **报告合并**：在 Stage 4 报告末尾追加 §5 语义一致性段（缺失属性表 + 缺失关联表 + 多重性冲突表）
5. ✅ **仅诊断**：不绑流水线退出码，单类失败不扩散，报告永不失败

**核心改动**：
- 修改 `scripts/stage4_validate.py`（+~250 行：4 dataclass + 5 抽取函数 + prompt/response + 编排 + 渲染 + CLI 选项）
- 修改 `tests/unit/test_stage4_validate.py`（+20 用例）
- 新增 `tests/fixtures/llm/semantic_*.json`（~3 个 mock fixture）

**非目标（post-Stage-5 候选）**：
- ❌ data_type 一致性（xsd:float ↔ Python float ↔ JSON number 映射）— 留待后续
- ❌ 父类 / 继承一致性（rdfs:subClassOf 在 5 adapter 中展开）— 留待后续
- ❌ 真实 LLM 默认调用 — 默认 Mock，避免 CI 意外消耗 API quota
- ❌ 输出修复建议 patch（如"建议在 Python Types 添加 voltage"）— Stage 5 仅诊断，不生成修复
- ❌ 修改任何 `adapter.verify()/emit()` 方法
- ❌ 修改 `src/cim_ontology/reviewer/` 现有模块（LLMReviewer 用于 Stage 2 OCR，Stage 5 不复用其 `review()` 入口）
- ❌ 不引入新 PyPI 依赖（rdflib + openai + stdlib 已够）

---

## 范围与优先级

| ID | 任务 | 优先级 | 工作量 |
|----|------|--------|--------|
| A1 | 4 个 frozen dataclass（AttrSemantics / AssocSemantics / ClassSemantics / SemanticMismatch）| P0 | S |
| A2 | 5 个 `_extract_<adapter>_semantics()` 确定性抽取函数 | P0 | L |
| A3 | `_build_semantic_prompt()` + `_parse_semantic_response()` | P0 | M |
| A4 | `_semantic_review_all()` 编排（cache + metrics + fallback）| P0 | M |
| A5 | `_render_semantic_section()` + `_render_markdown` 扩展 | P0 | S |
| A6 | `_cli()` 增 `--semantic-review` / `--use-real-llm` / `--provider-fixtures` | P0 | S |
| B1 | Mock fixture ×3 + MockProvider 匹配扩展 | P0 | S |
| B2 | 20 个测试用例（TDD red→green，10 个 task）| P0 | L |
| C1 | 全量回归（669 → 689 passed）| P0 | XS |
| C2 | 真实数据烟雾测试（待 IR 重新生成）| P1 | S |

---

## 架构总览

**目标**：在 `scripts/stage4_validate.py` 增加 `--semantic-review` 选项，对 Stage 4 抽样的同一批 ~100 类做语义一致性复审（属性覆盖 + 关联 + 多重性），LLM 判断结果合并到 Stage 4 报告 §5。

**文件布局**（仅扩展，不重构）：
```
scripts/stage4_validate.py (修改，+~250 行)
  + AttrSemantics / AssocSemantics / ClassSemantics / SemanticMismatch (frozen dataclass)
  + 5 个 _extract_<adapter>_semantics()      # 确定性纯函数
  + _build_semantic_prompt()                 # 构造 ReviewPrompt
  + _parse_semantic_response()               # 解析 LLM JSON + 业务校验
  + _semantic_review_all()                   # 编排：抽样 → 抽取 → LLM → 解析
  + _render_semantic_section()               # 渲染 §5 Markdown
  + _cli() 增 --semantic-review / --use-real-llm / --provider-fixtures
  + _render_markdown(matrix, mismatches=None)  # 增可选 §5 段

tests/unit/test_stage4_validate.py (修改，+~120 行，+20 用例)
  + TestClassSemantics (3) / TestExtractOwl/Shacl/JsonSchema/JsonLd/Python (10)
  + TestSemanticPrompt (2) / TestSemanticResponse (3) / TestSemanticE2E (2)

tests/fixtures/llm/semantic_*.json (新增 ~3 个 mock fixture)
```

**复用基础设施**（零改动）：
- `get_provider()` / `DeepSeekProvider` / `MockProvider`
- `LLMCache`（case_id = `f"semantic:{class_iri}"` namespace 隔离）
- `Metrics`（path=`semantic` 维度）
- CIM 17 专家 system prompt（复用 `prompts.py` 模板）

**架构边界**：
- scripts/ 内联 5 个抽取函数（不进 src/，避免污染 adapter）
- LLM 仅判断结构化摘要，不直接解析产物（KISS）
- 与 Stage 4 共用抽样（同一批 ~100 类），报告合一份

---

## 组件设计（接口契约）

**核心 dataclass**（frozen=True，与 Stage 4 风格一致）：

```python
@dataclass(frozen=True)
class AttrSemantics:
    name: str
    data_type: str          # xsd:float / cim:Voltage / string 等（raw 字符串）
    multiplicity: str       # "1" / "0..1" / "0..*" / "1..*"（原始，不归一化）

@dataclass(frozen=True)
class AssocSemantics:
    name: str
    target_class: str       # 关联目标类名
    multiplicity: str       # 同上

@dataclass(frozen=True)
class ClassSemantics:
    class_iri: str
    adapter: str            # "OWL" / "SHACL" / "JSON Schema" / "JSON-LD" / "Python Types"
    attrs: tuple[AttrSemantics, ...]
    assocs: tuple[AssocSemantics, ...]
    error: str | None       # FILE_MISSING / PARSE_ERROR / CLASS_NOT_FOUND / None

@dataclass(frozen=True)
class SemanticMismatch:
    class_iri: str
    missing_attrs: dict[str, list[str]]     # adapter → [缺失属性名]
    missing_assocs: dict[str, list[str]]    # adapter → [缺失关联名]
    multiplicity_mismatch: list[str]        # ["OWL:ACLineSegment.length 0..1 vs SHACL 1"]
    llm_notes: str
    confidence: float
```

**5 个抽取函数契约**（纯函数，无 LLM，确定性）：

```python
def _extract_owl_semantics(class_iri: str, build_dir: Path) -> ClassSemantics:
    """rdflib 解析 cim17_full.ttl：
    attrs = 该类所有 owl:DatatypeProperty（domain=class_iri）的 (name, range, cardinality)
    assocs = 该类所有 owl:ObjectProperty 的 (name, range, cardinality)
    注：OWL 中属性是全局的，通过 rdfs:domain 关联到类；多重性通过 owl:cardinality 约束（较少用）。
    """

def _extract_shacl_semantics(class_iri: str, build_dir: Path) -> ClassSemantics:
    """rdflib 解析 cim17_shapes.ttl：sh:targetClass=class_iri 的 NodeShape
    attrs = sh:property[sh:datatype] 的 (path, datatype, minCount/maxCount)
    assocs = sh:property[sh:class] 的 (path, class, minCount/maxCount)
    多重性：minCount/maxCount → "0..1" / "1..*" / "0..*"
    """

def _extract_json_schema_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """扫描 *_schema.json：definitions/<class_name>/properties
    attrs = properties 中 type≠object/array 的（标量属性）
    assocs = properties 中 type=object/array 的（引用其他类）
    多重性：required 数组 + type=array → "1" / "0..1" / "0..*"
    """

def _extract_jsonld_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """扫描 *_context.jsonld：@context/<class_name>/**
    注：JSON-LD @context 通常只含术语映射（"@id": "cim:Foo"），不含属性结构。
    大多数类将返回 error="CLASS_NOT_FOUND" 或 attrs=()/assocs=()。
    这是已知限制，§5 报告中明确标注 "JSON-LD: 语义稀疏"。
    """

def _extract_python_types_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """ast.parse *_types.py：class <class_name> 的 annotations
    attrs = 实例注解（name: float）+ 默认值
    assocs = list[OtherClass] / OtherClass 类型的字段
    多重性：list[X] → "0..*"；Optional[X] → "0..1"；X → "1"
    """
```

**LLM 判断**（复用 `get_provider()`）：

```python
def _build_semantic_prompt(
    class_name: str,
    ir_class_def: ClassDef | None,
    semantics: dict[str, ClassSemantics],
) -> ReviewPrompt:
    """构造 ReviewPrompt：
    system = CIM 17 专家 prompt（复用 prompts.py 的 _SYSTEM）
    user = IR 类定义 + 5 adapter 摘要（JSON）+ 任务指令
    raw_text = class_name（MockProvider 匹配用）
    """

def _parse_semantic_response(raw: str, class_iri: str) -> SemanticMismatch | None:
    """解析 LLM JSON 响应，三层熔断：
    1. json.loads 失败 → None（fallback，metrics json_invalid）
    2. confidence < 0.5 或缺 'missing_attrs' 字段 → None（fallback，metrics business_invalid）
    3. 通过 → SemanticMismatch
    """
```

---

## 数据流（端到端）

**触发**：`python -m scripts.stage4_validate --ir IR --build BUILD --out report.md --semantic-review [--use-real-llm]`

```
Stage 4 主流程（不变）：
  _load_ir → _stratified_sample(seed=42) → samples (~100)
  → _probe_all → _aggregate → matrix (IRI 一致性矩阵)
                            ↓ (samples 复用)
Stage 5 语义复审（--semantic-review 时执行）：
  for sample in samples:
    1. 5 adapter 抽取（确定性，无 LLM）：
       sem = {adapter: _extract_<adapter>_semantics(...)}
    2. cache lookup: case_id = f"semantic:{sample.class_iri}"
       - hit → 跳过 LLM，直接用 cached SemanticMismatch
       - miss → 继续
    3. _build_semantic_prompt(sample, ir_class_def, sem)
    4. provider.review(prompt) → raw JSON
       - MockProvider（默认）/ DeepSeekProvider（--use-real-llm）
    5. _parse_semantic_response(raw) → SemanticMismatch | None
    6. cache write-back (per-case_id)
    7. Metrics 埋点：semantic.calls / latency / cache / fallbacks
  → mismatches: list[SemanticMismatch]
                            ↓
报告合并（_render_markdown 扩展）：
  §1 抽样策略 + §2 一致性矩阵 + §3 不一致点 + §4 结论（Stage 4）
  §5 语义一致性复审（Stage 5 新增，仅 --semantic-review 时显示）
    - 摘要：X/Y 类语义一致（Z%）
    - 缺失属性表：类 | adapter | 缺失属性 | LLM 推理
    - 缺失关联表：类 | adapter | 缺失关联 | 多重性 | LLM 推理
    - 多重性映射冲突表（如有）
```

**集成点**：
- `_cli()` 在 `_render_markdown` 前调用 `_semantic_review_all(samples, ir, build_dir, provider, cache, metrics)`
- `mismatches` 作为新参数传入 `_render_markdown(matrix, mismatches=None)`
- 不传 `mismatches`（默认）→ 不渲染 §5（向后兼容 Stage 4 行为）
- `--semantic-review` 时 LLM 失败 → 不阻断报告生成（仅 §5 标注 "LLM 复审失败 N 类"）

**关键不变量**：
- Stage 4 默认行为不变（无 `--semantic-review` 时 0 LLM 调用）
- LLM 调用失败 / cache 失败 / 解析失败 → 单类 fallback，不影响其他类
- Metrics path 维度隔离（`semantic` vs `reviewer` 已有 `single`/`batch`）

---

## 错误处理（fallback 矩阵）

| 失败点 | 触发条件 | 处理策略 | 报告呈现 |
|--------|---------|---------|---------|
| Adapter 产物缺失 | `owl/cim17_full.ttl` 等不存在 | `_extract_*` 返回 `ClassSemantics(error="FILE_MISSING", attrs=(), assocs=())` | §5 表标注 "OWL: 文件缺失" |
| Adapter 解析失败 | rdflib/ast/json 抛异常 | `_extract_*` 返回 `error="PARSE_ERROR: {e}"` | §5 表标注 "JSON Schema: 解析失败" |
| 类在 adapter 不存在 | 5 adapter 中某 adapter 无该类 | `_extract_*` 返回 `error="CLASS_NOT_FOUND"` | §5 表标注 "JSON-LD: 类未导出" |
| IR 中无类定义 | sample.class_name 不在 IR.packages.classes | 跳过 LLM 调用，metrics `semantic.skipped{reason="ir_class_missing"}` | §5 摘要 "跳过 N 类（IR 无定义）" |
| LLM 调用失败 | Provider 抛异常（网络/超时/401）| `_parse_semantic_response` 返回 None，cache 不回写，metrics `fallbacks.provider_exception` | §5 摘要 "LLM 失败 N 类" |
| LLM JSON 损坏 | `json.loads` 失败 | 返回 None，metrics `fallbacks.json_invalid` | §5 摘要 "LLM 响应无效 N 类" |
| LLM 业务校验失败 | `confidence < 0.5` 或缺 `missing_attrs` 字段 | 返回 None，metrics `fallbacks.business_invalid` | §5 摘要 "LLM 低置信 N 类" |
| Cache 读失败 | SQLite 损坏/锁冲突 | 视为 miss，继续调 LLM（不阻断） | 不呈现（metrics 记录） |
| Cache 写失败 | SQLite 满/权限 | log warning，不阻断 | 不呈现 |

**三层熔断（与 LLMReviewer 一致）**：
1. JSON 解析失败 → fallback（该类判 None）
2. 业务校验失败 → fallback（confidence 低 / 字段缺）
3. 通过 → SemanticMismatch

**关键原则**：
- 单类失败不扩散：任何一类错误不影响其他 ~99 类（try/except 包裹 per-class 循环）
- 报告永不失败：即使所有 LLM 调用失败，§5 仍渲染（标注失败计数），Stage 4 §1-4 不受影响
- Adapter 缺失 ≠ 类缺失：`FILE_MISSING`（产物未生成）vs `CLASS_NOT_FOUND`（产物在但类未导出）语义不同，报告分别标注

---

## 测试策略（TDD 用例清单）

**新增 20 个测试用例**（与 Stage 4 节奏一致：每个组件 red→green）：

| 测试类 | 用例数 | 覆盖 |
|--------|--------|------|
| `TestClassSemantics` | 3 | dataclass frozen / AttrSemantics / AssocSemantics / ClassSemantics.error / SemanticMismatch 字段 |
| `TestExtractOwl` | 2 | finds class attrs+assocs / class not found |
| `TestExtractShacl` | 2 | finds sh:property attrs+assocs / class not found |
| `TestExtractJsonSchema` | 2 | finds properties（标量 vs object）/ class not found |
| `TestExtractJsonLd` | 2 | @context 稀疏（CLASS_NOT_FOUND）/ class not found |
| `TestExtractPythonTypes` | 2 | finds annotations（float + list[OtherClass]）/ class not found |
| `TestSemanticPrompt` | 2 | prompt 含 IR 定义 + 5 adapter 摘要 / system 是 CIM 17 专家 |
| `TestSemanticResponse` | 3 | 解析一致响应 / 解析缺失属性 / 业务校验拒绝（confidence<0.5） |
| `TestSemanticE2E` | 2 | Mock fixture 端到端（consistent + missing_attrs）/ --semantic-review 渲染 §5 |
| **合计** | **20** | |

**Mock fixture 设计**（`tests/fixtures/llm/semantic_*.json`）：

```json
// semantic_consistent.json
{"class_iri": "http://iec.ch/...#Foo", "consistent": true,
 "missing_attrs": {}, "missing_assocs": {}, "multiplicity_mismatch": [],
 "notes": "5 adapter 语义一致", "confidence": 0.95}

// semantic_missing_attrs.json
{"class_iri": "http://iec.ch/...#Bar", "consistent": false,
 "missing_attrs": {"Python Types": ["voltage"], "JSON-LD": ["voltage"]},
 "missing_assocs": {}, "multiplicity_mismatch": [],
 "notes": "Python Types 缺 voltage 属性", "confidence": 0.88}
```

**MockProvider 匹配**：扩展 `MockProvider.review()` 识别 `prompt.raw_text` 含 `class_iri` 时匹配 `semantic_<class_name>.json`。

**TDD 任务切分**（10 个 task，与 Stage 4 同节奏）：
1. Task 1: 写 4 dataclass 契约失败测试（3 用例）
2. Task 2: 实现 4 frozen dataclass
3. Task 3: 写 5 抽取函数失败测试（10 用例）
4. Task 4: 实现 5 抽取函数
5. Task 5: 写 prompt + response 失败测试（5 用例）
6. Task 6: 实现 _build_semantic_prompt + _parse_semantic_response
7. Task 7: 写 编排 + 报告失败测试（含 §5 渲染）
8. Task 8: 实现 _semantic_review_all + _render_semantic_section
9. Task 9: 写 E2E 失败测试（2 用例）+ 实现 _cli --semantic-review
10. Task 10: 全量回归（669 → 689 passed）+ 真实数据烟雾（待 IR 可用）

---

## 关键文件清单

| 路径 | 操作 | 原因 |
|------|------|------|
| `scripts/stage4_validate.py` | 修改（+~250 行） | Stage 5 实现主体（dataclass + 抽取 + prompt/response + 编排 + 渲染 + CLI） |
| `tests/unit/test_stage4_validate.py` | 修改（+~120 行，+20 用例） | TDD 测试覆盖 |
| `tests/fixtures/llm/semantic_consistent.json` | 新建 | Mock fixture：语义一致 |
| `tests/fixtures/llm/semantic_missing_attrs.json` | 新建 | Mock fixture：缺属性 |
| `tests/fixtures/llm/semantic_missing_assocs.json` | 新建 | Mock fixture：缺关联 |
| `src/cim_ontology/reviewer/providers.py` | 修改（MockProvider 匹配扩展，~5 行） | 识别 `semantic_*.json` fixture |

---

## 验证策略

| 验证项 | 方法 | 期望 |
|--------|------|------|
| 5 抽取函数确定性 | 单元测试，固定 build_dir fixture | 同输入 → 同输出（无 random / 无时间） |
| LLM 判断可测试 | Mock fixture（consistent / missing_attrs / missing_assocs） | 解析 → SemanticMismatch 字段正确 |
| 业务校验熔断 | confidence=0.3 / 缺字段 fixture | 返回 None + metrics 埋点 |
| E2E 报告合并 | sys.argv 调用 `_cli(["--semantic-review", ...])` | §5 段渲染，含缺失属性/关联表 |
| Stage 4 向后兼容 | 不传 `--semantic-review` | §5 不渲染，669 测试不变 |
| 全量回归 | `pytest tests/ -v` | 689 passed（669 + 20）+ 4 skipped，0 failure |
| CLI 帮助 | `python -m scripts.stage4_validate --help` | 显示 `--semantic-review` / `--use-real-llm` 选项 |
| Pyright 诊断 | IDE 检查 | 仅留 rdflib namespace package false positive |

---

## 设计权衡

| 决策 | 备选 | 选择理由 |
|------|------|----------|
| 方案 A（adapter 端确定性抽取 + LLM 仅判断）| 方案 B（LLM 直接解析产物）/ 方案 C（规则预检 + LLM 不确定介入）| KISS：adapter 端抽取纯函数可测试；LLM 输入小（结构化摘要），cache 友好；不引入规则预检复杂度 |
| Stage 4 脚本扩展（`--semantic-review`）| 独立 stage5 脚本 / 业务逻辑在 src/ | 复用抽样 + 探测 + 报告，单一入口；避免代码重复 |
| 5 抽取函数内联 scripts/ | 抽取逻辑下沉到各 adapter | adapter.verify()/emit() 不变量约束（零改动）；抽取是诊断逻辑，不属于 adapter 责任 |
| LLM 输入 = IR 定义 + 5 adapter 摘要 | 仅 5 adapter 摘要 / 仅 IR 定义 | IR 定义是 ground truth，摘要是待校验对象；两者对比才能判断覆盖度 |
| 默认 Mock，`--use-real-llm` opt-in | 默认真实 / 只 Mock | 与 `pipeline.build(use_llm=...)` 模式一致；CI 强制 Mock；本地可控 |
| 报告合并到 Stage 4 §5 | 独立 stage5 报告 / 两者支持 | 用户读一份文件即可；避免文件管理复杂度 |
| `tuple[AttrSemantics, ...]` 不可变 | `list[AttrSemantics]` | 与 Stage 4 frozen dataclass 风格一致；避免意外修改 |
| 多重性保留原始字符串（不归一化）| 归一化为 "0..1"/"1..*"/"0..*" | 各 adapter 多重性表示不同（OWL cardinality vs SHACL minCount vs Python list），归一化会丢失信息；LLM 负责判断等价性 |
| JSON-LD 稀疏类返回 CLASS_NOT_FOUND | 强行解析 @context 术语 | @context 通常只含术语映射，不含属性结构；CLASS_NOT_FOUND 是诚实标注 |

---

## 不变量

- Stage 4 默认行为不变（无 `--semantic-review` 时 0 LLM 调用，669 测试不变）
- 5 个 `adapter.verify()/emit()` 方法零改动
- IR 模型 / cleaner 模块零改动
- `src/cim_ontology/reviewer/LLMReviewer` 零改动（Stage 5 不复用其 `review()` 入口，仅复用 Provider / Cache / Metrics / prompts）
- 流水线退出码语义不变（Stage 5 是诊断工具，非门禁）
- 不引入新 PyPI 依赖（rdflib + openai + stdlib 已够）
- 报告永不失败（所有错误 fallback，§5 仍渲染）

---

## 不在范围（post-Stage-5 候选）

- ❌ data_type 一致性（xsd:float ↔ Python float ↔ JSON number 映射）
- ❌ 父类 / 继承一致性（rdfs:subClassOf 在 5 adapter 中展开）
- ❌ 真实 LLM 默认调用（默认 Mock）
- ❌ 输出修复建议 patch（如"建议在 Python Types 添加 voltage"）
- ❌ JSON-LD 语义稀疏问题根治（需 JsonLdContextAdapter 改造，导出属性结构）
- ❌ 多重性归一化（保留原始字符串，LLM 判断等价性）
- ❌ 报告 JSON 输出（Markdown only，延续 Stage 4 决策）
- ❌ 流水线硬约束（不一致不退化 exit code）

---

## 后续接口（Stage 6+ 候选）

- 真实数据烟雾测试：先运行 `scripts/run_stage2_e2e.py` 重新生成 `ir_after.json`，然后 `--use-real-llm` 跑 Stage 5 真实复审
- data_type + 父类继承维度扩展（在 5 抽取函数中补充字段）
- LLM 输出修复建议（`SemanticMismatch.suggested_fix` 字段）
- `--fail-on-mismatch N` 选项（如 Stage 5 进入 CI）
