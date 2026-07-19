# Stage 4: 跨适配器一致性验证（100 类语义对比）设计

## 背景

grid-ontology v1.5+ Stage 3 发射 5 个 adapter 产物：

| Adapter | 产物格式 | 输出文件 |
|---------|---------|---------|
| `OwlTurtleAdapter` | RDF Turtle | `cim17_<pkg>.ttl` + `cim17_full.ttl` |
| `ShaclShapesAdapter` | RDF Turtle (SHACL) | `cim17_shacl.ttl` |
| `JsonSchemaAdapter` | JSON Schema | `<pkg>_schema.json` |
| `JsonLdContextAdapter` | JSON-LD Context | `<pkg>_context.jsonld` |
| `PythonTypesAdapter` | Python source | `<pkg>_types.py` |

每个 adapter 已有 self-only 的 `verify()` 方法：
- OWL: rdflib 解析 `cim17_full.ttl`
- JSON-LD: 读 `<pkg>_context.jsonld`，验证 `@context` 存在
- JSON Schema: 验证 `<pkg>_schema.json` 文件存在
- SHACL / Python Types: 类似

**问题**：5 个 adapter 各自独立 verify，**跨 adapter 一致性**（同 N 个类在 5 个产物中是否都存在）**完全缺失**。例如 Stage 3 B5 修复后，可能存在：
- OWL 含 X 类，JSON Schema 漏 X 类
- OWL 与 SHACL 对同一类的属性定义不一致

**Stage 4 目标**：建立跨 adapter 一致性的**诊断能力**（只读报告，不绑流水线）。

### 数据驱动决策

针对 `docs/GBT43259301—2024/cim-base-full.md`（9243 行）的当前状态：

| 指标 | 现状 | Stage 4 后 |
|------|------|-----------|
| 跨 adapter 一致性诊断 | 不存在 | 100 类 × 5 adapter = 500 探测点 |
| 不一致点可见性 | 0 | 100% 报告化 |
| Stage 5 LLM 复审输入 | 无 | 报告 Markdown 可直接喂 LLM |

---

## 目标

建立 Stage 4 跨适配器一致性诊断能力，覆盖以下 5 个目标：

1. ✅ **分层抽样**：按 Package 分组，每包随机抽 `samples_per_pkg` 类（默认 25），seed=42 可复现
2. ✅ **5 adapter 探测**：对每样本，断言 5 个 adapter 产物均含该类
3. ✅ **Markdown 报告**：输出 `docs/stage4-validation-report.md`，含抽样策略 / 一致性矩阵 / 不一致点表 / 结论
4. ✅ **CLI 可调用**：`python scripts/stage4_validate.py --ir ir_after.json --build build_taiqu`
5. ✅ **只读诊断**：报告不绑流水线退出码，Stage 4 是诊断能力而非门禁

**核心改动**：
- 新建 `scripts/stage4_validate.py`（单文件 ~150 行）
- 新建 `tests/unit/test_stage4_validate.py`（16 用例）
- 输出 `docs/stage4-validation-report.md`（运行时生成）

**非目标**：
- ❌ 属性/关联/data_type 跨 adapter 一致性（Stage 5 候选）
- ❌ LLM 语义复审（Stage 5 候选）
- ❌ 流水线硬约束（不一致点不退化 exit code）
- ❌ 修改任何 `adapter.verify()` 方法
- ❌ 不引入新依赖（rdflib + stdlib 已够）
- ❌ 不生成 JSON 报告（Q3 决策：Markdown only）

---

## 架构

```
scripts/stage4_validate.py
  ├─ main(ir_path, build_dir, out_path, *, samples_per_pkg=25, seed=42)
  │     ├─ _load_ir(ir_path) -> OntologyIR
  │     ├─ _stratified_sample(ir, samples_per_pkg, seed) -> list[Sample]
  │     ├─ for each sample, 5 adapter probes:
  │     │    ├─ _probe_owl(sample, build_dir) -> ProbeResult
  │     │    ├─ _probe_shacl(sample, build_dir) -> ProbeResult
  │     │    ├─ _probe_json_schema(sample, build_dir) -> ProbeResult
  │     │    ├─ _probe_jsonld(sample, build_dir) -> ProbeResult
  │     │    └─ _probe_python_types(sample, build_dir) -> ProbeResult
  │     ├─ _aggregate(results) -> ConsistencyMatrix
  │     └─ _render_markdown(matrix, out_path)
  └─ helpers: dataclasses Sample / ProbeResult / ConsistencyMatrix
```

### 设计原则

- **KISS**：单脚本 ~150 行，无新 Python 包
- **SRP**：5 个 probe 函数单一职责，可独立测
- **OCP**：5 个 probe 函数 + dispatcher pattern，扩展第 6 个 adapter 仅加 1 函数
- **YAGNI**：不引入 `click` / `typer`（用 `argparse`），不引入 `pandas`（用 dataclass + 手写渲染）

---

## 数据流

### 输入

- `ir_after.json`：Stage 2 输出 IR（20 包 × ~50 类 = ~1000 类）
- `build_taiqu/`：Stage 3 输出（5 adapter 产物目录）

### 处理

```
输入 (IR + build_dir)
  ↓ _load_ir
IR.packages (N=20)
  ↓ _stratified_sample(seed=42)
samples: list[Sample] × 100 (Core:25 + Wires:25 + Generation:25 + Other:25)
  ↓ for each sample, 5 probes in parallel (顺序即可，500 探测 < 5 秒)
results: dict[class_iri] -> dict[adapter_name] -> ProbeResult
  ↓ _aggregate
ConsistencyMatrix:
  - samples: 100
  - consistency_rate: 0.95
  - inconsistencies: list[{class, missing_in: [adapter]}]
  - per_pkg_count: dict[pkg_name] -> int
  - per_adapter_count: dict[adapter_name] -> int
  ↓ _render_markdown
docs/stage4-validation-report.md
```

### 输出

- `docs/stage4-validation-report.md`：Markdown 报告
- stdout：进度日志（"Probing OWL... 100/100"）+ 摘要
- exit code：始终 0（Q4 决策：只读诊断）

---

## 核心组件

### 1. `scripts/stage4_validate.py`（新建）

#### 1.1 Dataclass 契约

```python
@dataclass(frozen=True)
class Sample:
    """一个抽样样本：包名 + 类名 + 完整 IRI。"""
    pkg_name: str
    class_name: str
    class_iri: str  # f"http://iec.ch/TC57/2024/CIM-schema-cim17#{class_name}"


@dataclass(frozen=True)
class ProbeResult:
    """单个 adapter 对单个样本的探测结果。"""
    found: bool
    error: str | None = None  # PARSE_ERROR / FILE_MISSING 等


@dataclass(frozen=True)
class Inconsistency:
    """一个不一致点：某类在某 adapter 缺失。"""
    sample: Sample
    missing_adapters: list[str]


@dataclass(frozen=True)
class ConsistencyMatrix:
    """聚合所有探测结果。"""
    samples: list[Sample]
    results: dict[str, dict[str, ProbeResult]]  # class_iri -> adapter -> ProbeResult
    inconsistencies: list[Inconsistency]
    samples_per_pkg: dict[str, int]  # 实际抽样数（可能 < 25）
    adapters: list[str]  # 5 个 adapter 名
    seed: int
    generated_at: str  # ISO 8601
```

#### 1.2 `_stratified_sample`

```python
def _stratified_sample(
    ir: OntologyIR, samples_per_pkg: int, seed: int
) -> list[Sample]:
    """按包分层抽样，每包随机抽 samples_per_pkg 类。
    
    不足 samples_per_pkg 的包取全部（不补足）。
    seed 用于 Python random.Random，保证可复现。
    """
    rng = random.Random(seed)
    samples: list[Sample] = []
    for pkg in ir.packages:
        # 过滤：跳过空名类（B7 清空残留）
        valid = [c for c in pkg.classes if c.name and c.name.strip()]
        # 随机抽样
        k = min(samples_per_pkg, len(valid))
        picked = rng.sample(valid, k)
        for cls in picked:
            samples.append(Sample(
                pkg_name=pkg.name,
                class_name=cls.name,
                class_iri=f"http://iec.ch/TC57/2024/CIM-schema-cim17#{cls.name}",
            ))
    return samples
```

#### 1.3 5 个 Probe 函数

每个 probe 函数签名一致：`probe(sample: Sample, build_dir: Path) -> ProbeResult`

**`_probe_owl`**：rdflib 解析 `build_dir/owl/cim17_full.ttl`，检查 `RDF.type/OWL.Class` subject 集合包含 `sample.class_iri`

**`_probe_shacl`**：rdflib 解析 `build_dir/shacl/cim17_shacl.ttl`，检查 `sh:targetClass` 值集合包含 `sample.class_iri`（或 `rdfs:Class` subject）

**`_probe_json_schema`**：遍历 `build_dir/json-schema/*.json`，检查任一文件的 `properties[<class_iri>]` 或 `definitions[<class_iri>]` 存在

**`_probe_jsonld`**：遍历 `build_dir/jsonld-context/*_context.jsonld`，检查 `@context` 中 `@id` 值包含 `sample.class_name`

**`_probe_python_types`**：遍历 `build_dir/python-types/*.py`，用 `ast.parse` 解析，检查 `ast.ClassDef` 节点名匹配 `sample.class_name`

#### 1.4 `_render_markdown`

```python
def _render_markdown(matrix: ConsistencyMatrix) -> str:
    """渲染 Markdown 报告（4 节结构）。"""
    return f"""# Stage 4: 跨适配器一致性验证报告

**生成时间**：{matrix.generated_at}
**样本数**：{len(matrix.samples)}（seed={matrix.seed}）
**一致性通过率**：{len(matrix.samples) - len(matrix.inconsistencies)}/{len(matrix.samples)}

## 1. 抽样策略

- 分层：每包随机抽 ≤ {max(matrix.samples_per_pkg.values())} 类
- 实际抽样数（按包）：

| 包 | 抽样数 |
|----|--------|
{chr(10).join(f"| {pkg} | {n} |" for pkg, n in matrix.samples_per_pkg.items())}

## 2. 一致性矩阵（按包 × Adapter）

| 包 | OWL | SHACL | JSON Schema | JSON-LD | Python Types |
|----|-----|-------|-------------|---------|--------------|
{_render_pkg_matrix(matrix)}

## 3. 不一致点（{len(matrix.inconsistencies)} 项）

| Class | 包 | 缺失 Adapter |
|-------|-----|-------------|
{chr(10).join(f"| {inc.sample.class_name} | {inc.sample.pkg_name} | {', '.join(inc.missing_adapters)} |" for inc in matrix.inconsistencies) if matrix.inconsistencies else "_无不一致点_"}

## 4. 结论

- 通过：{len(matrix.samples) - len(matrix.inconsistencies)} / {len(matrix.samples)}（{_pct(matrix)}）
- 不一致点：{len(matrix.inconsistencies)} 项
- 详细分布见 §2 一致性矩阵
"""
```

#### 1.5 CLI 入口

```python
def main():
    parser = argparse.ArgumentParser(description="Stage 4: 跨适配器一致性验证")
    parser.add_argument("--ir", required=True, help="IR JSON 文件路径")
    parser.add_argument("--build", required=True, help="Stage 3 build 目录")
    parser.add_argument("--out", default="docs/stage4-validation-report.md")
    parser.add_argument("--samples-per-pkg", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    ir = _load_ir(args.ir)
    samples = _stratified_sample(ir, args.samples_per_pkg, args.seed)
    results = _probe_all(samples, Path(args.build))
    matrix = _aggregate(samples, results, args.seed)
    Path(args.out).write_text(_render_markdown(matrix), encoding="utf-8")
    print(f"✓ Stage 4 报告已生成：{args.out}")
    print(f"  通过率：{len(matrix.samples) - len(matrix.inconsistencies)}/{len(matrix.samples)}")


if __name__ == "__main__":
    main()
```

### 2. 不变量

- ✅ 5 个 `adapter.verify()` 方法零改动
- ✅ `adapter.emit()` 零改动
- ✅ IR 模型零改动
- ✅ Stage 1/2/3 流程不变
- ✅ 不引入新 PyPI 依赖（rdflib 已在 venv）
- ✅ 流水线退出码不变（Stage 4 是诊断工具，非门禁）

### 3. 日志契约

```python
log.info("stage4_started", samples=..., adapters=5, seed=...)
log.info("stage4_probe_progress", adapter="OWL", done=100, total=100)
log.info("stage4_completed", samples=..., inconsistencies=..., report=...)
```

---

## 错误处理

| 失败模式 | 处理 |
|---------|------|
| IR 文件不存在 | stderr + exit 1（CLI 入口） |
| build_dir 不存在 | stderr + exit 1（CLI 入口） |
| 单个 adapter 产物缺失 | 该样本该 adapter 标 `FILE_MISSING` + 计入不一致点 |
| rdflib 解析失败 | 该样本该 adapter 标 `PARSE_ERROR` + 不计入不一致点（探测工具问题，非语义问题）|
| JSON 解析失败 | 同上 |
| Python AST 解析失败 | 同上 |
| 抽样数 < samples_per_pkg | 取该包全部类，不足则在报告中标注"不足" |
| 0 个不一致点 | 报告 §3 显示"_无不一致点_"，§4 通过率 100% |

---

## 测试策略

**测试文件**：`tests/unit/test_stage4_validate.py`（新建）

| 类别 | 用例数 | 覆盖 |
|------|--------|------|
| `TestSampling` | 3 | 分层抽样：每包数正确 / seed 稳定 / 不足时取全部 |
| `TestProbeOwl` | 2 | OWL 探测：存在/不存在 |
| `TestProbeShacl` | 2 | SHACL 探测：存在/不存在 |
| `TestProbeJsonSchema` | 2 | JSON Schema 探测：存在/不存在 |
| `TestProbeJsonLd` | 2 | JSON-LD 探测：存在/不存在 |
| `TestProbePythonTypes` | 2 | Python Types 探测：存在/不存在 |
| `TestReportRendering` | 2 | Markdown 报告：含 4 节 / 不一致点表正确 |
| `TestEndToEnd` | 1 | 端到端：IR + 模拟 5 adapter 产物 → 报告生成 |
| **总计** | **16** | |

### 关键测试样例

```python
def test_stratified_sample_deterministic():
    """seed=42 抽样结果稳定（可复现）。"""
    ir = _make_ir_with_packages([
        Package(name="Core", classes=[ClassDef(name=f"Cls{i}") for i in range(50)]),
        Package(name="Wires", classes=[ClassDef(name=f"Wire{i}") for i in range(30)]),
    ])
    s1 = _stratified_sample(ir, samples_per_pkg=25, seed=42)
    s2 = _stratified_sample(ir, samples_per_pkg=25, seed=42)
    assert [s.class_name for s in s1] == [s.class_name for s in s2]


def test_probe_owl_finds_class(tmp_path):
    """OWL probe：cim17_full.ttl 含 X 类 → found=True。"""
    # 构造含 X 类的 minimal cim17_full.ttl
    (tmp_path / "owl").mkdir()
    g = Graph()
    g.add((URIRef(f"{CIM}Foo"), RDF.type, OWL.Class))
    g.serialize(tmp_path / "owl" / "cim17_full.ttl", format="turtle")
    sample = Sample("Core", "Foo", f"{CIM}Foo")
    result = _probe_owl(sample, tmp_path)
    assert result.found is True
    assert result.error is None


def test_end_to_end_produces_report(tmp_path):
    """端到端：IR + 模拟 build_dir → 报告生成。"""
    # 构造 IR
    ir_path = tmp_path / "ir_after.json"
    ir = _make_ir_with_packages([
        Package(name="Core", classes=[ClassDef(name="Foo")]),
    ])
    ir_path.write_text(ir.model_dump_json())
    # 构造 5 adapter 产物（每个含 Foo）
    build_dir = tmp_path / "build"
    _build_minimal_adapters(build_dir, "Foo")
    # 调用 main
    out_path = tmp_path / "report.md"
    main_entry(ir_path=str(ir_path), build_dir=str(build_dir), out_path=str(out_path))
    # 验证报告
    assert out_path.exists()
    content = out_path.read_text()
    assert "# Stage 4: 跨适配器一致性验证报告" in content
    assert "Foo" in content
```

### 回归基线

- B5 后：649 PASS
- Stage 4 后：665 PASS（649 + 16）
- 真实 cim-base-full.md 报告：1 次运行约 3-5 秒

---

## 实施风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 5 个 adapter 产物路径不一致 | 中 | probe 失败 | 用 `pathlib.glob` 扫描，不硬编码文件名 |
| Python Types AST 解析在某些 .py 上失败 | 低 | 单样本标 PARSE_ERROR | 该样本不计入不一致点（仅报告工具问题）|
| 大型 build_taiqu/ 加载慢 | 低 | 用户体验差 | 不缓存探测结果（每次都重读），保持脚本简单 |
| 真实 Stage 3 跑完后产物未及时生成 | 中 | Stage 4 跑空 | CLI 入口检查 build_dir 关键产物存在 |

---

## 不在范围

- ❌ 属性/关联/data_type 跨 adapter 一致性（Stage 5 候选）
- ❌ LLM 语义复审（Stage 5 候选）
- ❌ 流水线硬约束（exit code 非 0）
- ❌ 修改任何 `adapter.verify()` 方法
- ❌ 生成 JSON 报告（Q3 决策：Markdown only）
- ❌ 增量检测（仅全量重跑）
- ❌ 历史报告对比（仅最新一份）
- ❌ Stage 4 → Stage 1/2/3 反向反馈

---

## 验证策略

| 验证项 | 方法 | 期望 |
|--------|------|------|
| 单元测试 | `pytest tests/unit/test_stage4_validate.py -v` | 16/16 PASS |
| 全量回归 | `pytest tests/ -v` | 665/665 PASS |
| CLI 烟雾测试 | `python scripts/stage4_validate.py --ir ir_after.json --build build_taiqu --out /tmp/test_report.md` | 退出码 0 + report 存在 |
| 真实数据 | 用 `build_taiqu/` 实际产物跑一次 | 报告生成 + 抽样 100 类 |

---

## 文件变更清单

| 文件 | 操作 | 估算行数 |
|------|------|---------|
| `scripts/stage4_validate.py` | 新建 | +150 |
| `tests/unit/test_stage4_validate.py` | 新建 | +200 |
| `docs/stage4-validation-report.md` | 新建（运行时生成） | +50 |

**总变更**：3 文件，~400 行净增（其中 1 个为运行时报告）。

---

## 设计权衡记录

| 决策 | 备选 | 选择理由 |
|------|------|----------|
| 单脚本 ~150 行 | 新建 `stage4/` 子包 | KISS；Stage 4 是诊断工具而非核心模块 |
| 5 个 probe 函数 | 1 个 dispatch 函数 | SRP：每函数单一职责，独立测 |
| Markdown only | JSON 双输出 | Q3 决策；Stage 5 再加 JSON |
| seed=42 抽样 | 不指定 seed（每次随机） | 可复现；CI 友好 |
| 不绑流水线 | 不一致 > 阈值失败 | Q4 决策；Stage 4 是诊断能力 |
| 不引入新依赖 | 用 jq / shell 替代 | Python 一致性 + 复用 rdflib |
| 过滤空名类 | 不过滤 | B7 残留空名不应进入抽样 |

---

## 不变量

- 5 个 `adapter.verify()` 方法行为不变
- Stage 1/2/3 流程不变
- IR 模型不变
- 流水线退出码语义不变
- 不引入新 PyPI 依赖