# B5: 多包 OWL 质量硬化设计

## 背景

grid-ontology v1.5+ Stage 3 包含 5 个 adapter，其中 `OwlTurtleAdapter` 在 B-series 早期已完成"按包拆分"——每包独立写 `cim17_<pkg>.ttl`，再累加成 `cim17_full.ttl`。然而 v1.5.0 实际运行（2026-07-05）发现：

```
Files written: 21 (含 cim17_full.ttl)
Stats: {'packages': 20, 'classes': 992}
- 12/20 包 0 KB 输出：AuxiliaryEquipment, ControlArea, DiagramLayout,
  Equivalents, Faults, ICCPConfiguration, Meas, OperationalLimits,
  Package1, Protection, StateVariables, Topology
- 1 ERROR log: '包依赖图中存在环，降级为字典序'
  error='Graph contains a cycle or graph changed during iteration'
- INFO: 'class_dedup_completed  dropped_count=463 duplicate_groups_resolved=318
           kept_unique_classes=525'
```

三个质量问题相互纠缠：
1. **过度去重**：`deduplicate_cross_package_classes` 把 463/992 ≈ 47% 类合并到 Core，导致 12 个包因源类被抽空而输出 0 KB
2. **依赖图环路**：`topological_sort` 因跨包 ClassRef 双向引用（OWL 真实语义）触发异常，降级为字典序而非按依赖关系输出
3. **产物歧义**：`cim17_full.ttl` 仅 128 KB，与"992 类"应有的 ~1.5 MB 体量不符（旧 build 残留或 dedup 后真实体积待确认）

B5 不新增功能，仅修复 Stage 3 产物的语义完整性。

### 数据驱动决策

针对 `cim-base-full.md`（9243 行）的实测（2026-07-05）：

| 指标 | v1.5.0 | B5 目标 | 变化 |
|------|--------|---------|------|
| 包文件数 | 20 + full = 21 | 8 + full = 9（B7 清空后实际非空包） | −12（空包不写） |
| `cim17_full.ttl` 类数 | 525（dedup 后） | 992（按原包） | +467（+89%） |
| cim17_full.ttl 体积 | 128 KB（旧 build）| ~1.5 MB（预期） | ~12× |
| `topological_sort` 错误 | 1 ERROR/emit | 0 | 消除 |
| 其他 4 adapter | 未触及 | 未触及 | 0 |

### 当前 vs 目标产物

**当前**（cim17_full.ttl 内容）：
- 525 个 owl:Class（被 dedup 集中到 Core）
- 0 个来自 AuxiliaryEquipment/Faults/Meas 等"独立包"的类（已合并）
- 1 条 ERROR 日志提示 cycle（降级处理）

**B5 目标**：
- 992 个 owl:Class（每个源包独立保留自己的类）
- 即使同名类在不同包出现多次也保留（OWL 多 ontology 共存语义）
- 0 条 ERROR 日志；owl:imports 由 OWL reasoner 原生解析

## 目标

修复 `OwlTurtleAdapter.emit()` 的 3 个质量问题，让多包 OWL 输出反映源 MD 的真实包结构（每个非空包独立可读、`cim17_full.ttl` 聚合所有内容），同时保持 OWL 生态兼容性。

**核心改动**：

1. ✅ 取消 `deduplicate_cross_package_classes` 调用 → 992 类按原包保留
2. ✅ 取消 `topological_sort` 调用 → Core 优先 + IR 原始顺序，OWL 原生处理 import 循环
3. ✅ 空包（0 类或全部 B7 清空）→ 跳过 + `log.warning`
4. ✅ 保留 `cim17_full.ttl`（仅累加非空包）
5. ✅ 验证 `cim17_full.ttl` 仍可被 rdflib 重新解析

**非目标**：

- ❌ 不动 `_class_dedup.py`（其他 adapter 仍可调用，仅 OWL 不再触发）
- ❌ 不动 `_pkg_dedup.py`（包名模糊合并仍需 OCR 鲁棒）
- ❌ 不动 `dep_graph.py` 模块本身（仅移除 owl.py 中的 `topological_sort` 调用）
- ❌ 不动 OWL 输出格式（仍 Turtle + 每包 `cim17_<pkg>.ttl`）
- ❌ 不改其他 4 个 adapter
- ❌ 不引入新依赖

## 架构

```
OwlTurtleAdapter.emit(ir, output_dir)
  ├─ [保留] merge_fuzzy_duplicate_packages(ir.packages)  # OCR 拼写错误包合并
  ├─ [移除] deduplicate_cross_package_classes(...)        # B5 删除此调用
  ├─ [新增] _emit_order(packages) -> list[Package]        # Core 优先 + IR 顺序
  ├─ [新增] _partition_empty(packages) -> (non_empty, empty)
  │              ├─ 返回非空包列表
  │              └─ 空包 log.warning("b5_empty_pkg_skipped", ...)
  ├─ [保留] build_package_dependency_graph(...)           # 仍收集 owl:imports predecessor
  ├─ [移除] topological_sort(dep_graph)                   # B5 删除此调用
  ├─ [改造] for pkg in non_empty:
  │            ├─ _build_package_graph(pkg) → pkg_g
  │            ├─ for dep in dep_graph.predecessors(pkg.name):
  │            │       pkg_g.add((pkg_iri, OWL.imports, dep_iri))
  │            ├─ pkg_g.serialize(cim17_<pkg>.ttl)
  │            └─ for triple in pkg_g: full_g.add(triple)  # 累加
  └─ [保留] full_g.serialize(cim17_full.ttl)
```

### 设计原则

- **KISS**: 单文件 ~30 行净改（不改其他模块、新文件、依赖）
- **DRY**: 复用现有 `build_package_dependency_graph` 与 `_build_package_graph`
- **SOLID - SRP**: `_emit_order` 与 `_partition_empty` 单一职责，可独立测
- **YAGNI**: 不引入 `cycles` 显式检测、`index.ttl` manifest、不改 dedup 模块本身

## 数据流

### 输入

- `ir: OntologyIR`（已通过 B6 + B7 修复链）
- 27 个原始包（9203/9243 行 LDM 中），merge_fuzzy 后 20 个
- 992 个 DataProperty + ObjectProperty 类（按包分布）

### 处理

```
输入 (27 包)
  ↓ merge_fuzzy_dedup
中间 (20 包)
  ↓ _partition_empty
  ├─→ non_empty (8 包：B7 清空后实际非空)
  └─→ empty (12 包)
  ↓ _emit_order
有序 non_empty（Core 优先 + 其余 IR 顺序）
  ↓ for each pkg
  ├─→ _build_package_graph(pkg)
  ├─→ owl:imports 声明
  └─→ .ttl 写入
  ↓ full_g.serialize
cim17_full.ttl
```

### 输出

- 8 个独立 `cim17_<pkg>.ttl`（每个非空包一份）
- 1 个 `cim17_full.ttl`（所有非空包聚合）
- 12 个空包跳过（仅日志）
- 0 条 topological_sort 错误日志

## 核心组件

### 1. 改造 `src/cim_ontology/adapters/owl.py`

#### 1.1 新增 `_emit_order` 函数

```python
def _emit_order(self, packages: list[Package]) -> list[Package]:
    """Core 包优先 + 其余包按 IR 原始顺序（稳定排序）。
    
    替代 topological_sort：B5 取消拓扑排序，依赖 OWL 原生 import 循环处理。
    Core 优先确保：foundation 包先 emit，便于下游 SPARQL 工具从 Core 起解析。
    """
    by_name = {p.name: p for p in packages}
    core = [by_name.pop("Core")] if "Core" in by_name else []
    return core + list(by_name.values())
```

#### 1.2 新增 `_partition_empty` 函数

```python
def _partition_empty(
    self, packages: list[Package]
) -> tuple[list[Package], list[str]]:
    """分类非空包 vs 空包，发出警告日志。
    
    空包定义：
      - 0 个 class（如被 B7 清空后）
      - 所有 class.name 为空字符串
      
    Returns:
        (non_empty, empty_names)
    """
    non_empty: list[Package] = []
    empty_names: list[str] = []
    for pkg in packages:
        # 至少一个非空类名才算非空包
        if any(cls.name for cls in pkg.classes):
            non_empty.append(pkg)
        else:
            empty_names.append(pkg.name)
            log.warning(
                "b5_empty_pkg_skipped",
                pkg=pkg.name,
                class_count=len(pkg.classes),
            )
    return non_empty, empty_names
```

#### 1.3 改造 `emit()` 流程

```python
def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    start = _now_ms()

    # Step 1: OCR 拼写错误包合并（保留 B 系列早期防线）
    packages = merge_fuzzy_duplicate_packages(ir.packages)
    # B5: 移除 deduplicate_cross_package_classes 调用
    #   原代码：packages = deduplicate_cross_package_classes(packages)

    # B5: 计算 emit 顺序（Core 优先 + 其余 IR 顺序）
    ordered = self._emit_order(packages)
    # B5: 空包分类
    non_empty, empty_names = self._partition_empty(ordered)

    # 跨包依赖收集（保留用于 owl:imports 声明，不再 topo 排序）
    cross_refs = infer_cross_package_refs(non_empty)  # 仅非空包参与图
    dep_graph = build_package_dependency_graph(ir, cross_package_refs=cross_refs)

    full_g = Graph()
    full_g.bind("cim", CIM)
    # ... (现有 bind 代码不变)

    # Ontology 头（保留）
    onto_iri = URIRef(str(CIM).rstrip("#"))
    full_g.add((onto_iri, RDF.type, OWL.Ontology))
    full_g.add((onto_iri, OWL.versionInfo, Literal("cim17")))
    full_g.add((onto_iri, RDFS.comment, Literal(
        "GB/T 43259.301-2024 IDT IEC 61970-301:2020", lang="en"
    )))

    files_written: list[Path] = []

    # B5: for pkg in non_empty (而非 ordered_packages)
    for pkg in non_empty:
        pkg_g = self._build_package_graph(pkg)
        # owl:imports 仍按 predecessor 声明
        for dep in dep_graph.predecessors(pkg.name):
            try:
                dep_iri = URIRef(f"{str(CIM).rstrip('#')}_{dep}")
                pkg_iri = URIRef(f"{str(CIM).rstrip('#')}_{pkg.name}")
            except KeyError:
                log.debug("b5_owl_import_skipped", pkg=pkg.name, dep=dep)
                continue
            pkg_g.add((pkg_iri, OWL.imports, dep_iri))
            full_g.add((pkg_iri, OWL.imports, dep_iri))

        out_path = output_dir / f"cim17_{pkg.name}.ttl"
        pkg_g.serialize(out_path, format="turtle")
        files_written.append(out_path)
        log.info("owl_pkg_emitted", pkg=pkg.name, classes=len(pkg.classes))

        # 累加到全量
        for triple in pkg_g:
            full_g.add(triple)

    full_path = output_dir / "cim17_full.ttl"
    full_g.serialize(full_path, format="turtle")
    files_written.append(full_path)

    log.info(
        "b5_emit_completed",
        packages_emitted=len(non_empty),
        packages_skipped=len(empty_names),
    )

    return EmitResult(
        files=files_written,
        stats={
            "packages": len(non_empty),
            "classes": len(ir.all_classes()),
            "skipped_packages": len(empty_names),
            "total_files": len(files_written),
        },
        duration_ms=_now_ms() - start,
    )
```

### 2. 不变量

- ✅ B6/B7 行为不变（orchestrator 未动）
- ✅ B4 JSON-LD Context 不动
- ✅ OWL 输出仍可被 rdflib 重新解析（cim17_full.ttl roundtrip）
- ✅ owl:imports 仍基于 dep_graph.predecessors 声明（仅 non_empty 参与）
- ✅ `cim17_full.ttl` 体积增长但 rdflib 可处理（无内存问题）
- ✅ 其他 4 个 adapter 零改动
- ✅ IR 模型零改动

### 3. 日志契约（structlog）

```python
log.warning("b5_empty_pkg_skipped", pkg=pkg.name, class_count=...)  # 每个空包
log.info("owl_pkg_emitted", pkg=pkg.name, classes=...)               # 每个非空包
log.debug("b5_owl_import_skipped", pkg=pkg.name, dep=dep)            # 边界 case
log.info("b5_emit_completed", packages_emitted=..., packages_skipped=...)  # emit 结束
```

## 错误处理

| 失败模式 | 处理 | 行为 |
|---------|------|------|
| 空包（0 类或 B7 清空后无内容）| `_partition_empty` 跳过 | 不写 .ttl、不入 cim17_full.ttl、警告日志 |
| 跨包 ClassRef 循环 | 不报错 | emit 顺序按 `_emit_order`（Core 优先 + IR 顺序），import 由 OWL reasoner 处理 |
| `dep_graph.predecessors(pkg.name)` 触发 KeyError | try/except + log.debug | 跳过该 predecessor import，继续 |
| rdflib 序列化失败 | propagate | emit 抛错（不改现有行为） |
| cim17_full.ttl 已存在 | `Path.serialize` 覆盖 | 标准 I/O |
| 同名 IRI 在多个包出现（取消 dedup 后）| OWL set semantics | rdflib 自动去重（合法） |

## 测试策略

**测试文件**：`tests/unit/test_b5_multi_package_owl.py`（新建）

| 类别 | 用例数 | 覆盖 |
|------|--------|------|
| 单元：`_emit_order` | 3 | Core 优先 / 无 Core / 全空 / 单包稳定 |
| 单元：`_partition_empty` | 4 | 纯空 / 全 B7 清空 / 混合 / name 全空白 |
| 端到端：`OwlTurtleAdapter.emit` | 5 | dedup 关闭、992 类保留 / 空包不写 / Core 第一 / 无 cycle 错误日志 / roundtrip |
| **总计** | **12** | 与 B4/B7 用例规模对齐 |

### 关键测试样例

```python
def test_dedup_disabled_preserves_all_992_classes(tmp_path):
    """B5 后取消 dedup：cim17_full.ttl 含 ≥800 个 owl:Class。"""
    ir = clean_markdown_to_ir(Path("docs/.../cim-base-full.md"))
    OwlTurtleAdapter().emit(ir, tmp_path)
    g = Graph()
    g.parse(tmp_path / "cim17_full.ttl", format="turtle")
    classes = set(g.subjects(RDF.type, OWL.Class))
    assert len(classes) >= 800, f"期望 ≥800 类，实际 {len(classes)}"


def test_empty_packages_not_emitted(tmp_path):
    """空包不写 .ttl。"""
    ir = _make_ir_with_packages([
        Package(name="Core", classes=[_cls("Foo")]),
        Package(name="Empty1", classes=[]),
        Package(name="Empty2", classes=[_cls("")]),  # 全空名
    ])
    result = OwlTurtleAdapter().emit(ir, tmp_path)
    names = {f.name for f in result.files}
    assert "cim17_Core.ttl" in names
    assert "cim17_Empty1.ttl" not in names
    assert "cim17_Empty2.ttl" not in names


def test_core_emitted_first(tmp_path):
    """Core 永远在 emit 顺序的第一位。"""
    ir = _make_ir_with_packages([
        Package(name="Zeta", classes=[_cls("Z")]),
        Package(name="Core", classes=[_cls("C")]),
        Package(name="Alpha", classes=[_cls("A")]),
    ])
    result = OwlTurtleAdapter().emit(ir, tmp_path)
    owl_files = [f for f in result.files
                 if f.name.startswith("cim17_") and f.name != "cim17_full.ttl"]
    assert owl_files[0].name == "cim17_Core.ttl"


def test_no_cycle_error_in_logs(caplog):
    """B5 后 emit 不触发 'Graph contains a cycle' 错误。"""
    ir = clean_markdown_to_ir(Path("docs/.../cim-base-full.md"))
    with caplog.at_level(logging.ERROR):
        OwlTurtleAdapter().emit(ir, tmp_path)
    assert "Graph contains a cycle" not in caplog.text


def test_full_ttl_roundtrips_through_rdflib(tmp_path):
    """cim17_full.ttl 可被 rdflib 重新解析。"""
    OwlTurtleAdapter().emit(ir, tmp_path)
    g = Graph()
    g.parse(tmp_path / "cim17_full.ttl", format="turtle")
    assert len(set(g.subjects(RDF.type, OWL.Class))) > 0
    assert len(set(g.subjects(RDF.type, OWL.ObjectProperty))) > 0
```

### 回归基线

- B5 前：581/581 PASS（B4 终点）
- B5 后：593/593 PASS（581 + 12 B5 新增）
- E2E：cim17_full.ttl 体积增长至 ~1.5 MB，仍可被 rdflib 解析

## 实施风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 12 空包有 caller 依赖 | 低 | 调用方需适配 | 现状是 0 KB 文件，调用方本就需要适配 |
| 跨包 ClassRef 环导致 OWL reasoner 慢 | 中 | 性能差但不崩 | 文档明示"OWL 推理时延可接受" |
| `cim17_full.ttl` 体积激增 | 中 | ~1.5 MB | 不引入压缩（YAGNI）；rdflib 可处理 |
| 取消 dedup 后同名 IRI 多次声明 | 中 | rdflib 静默 set 去重 | OWL 语义合法；rdflib 自动处理 |
| `_emit_order` 副作用（修改 IR）| 极低 | IR 状态污染 | 仅读 IR（`packages` 是 list[Package]，未修改对象） |

## 不在范围

- ❌ `_class_dedup.py` 模块删除（其他 adapter 仍可能用）
- ❌ `dep_graph.py` 模块改造（仅移除调用，不改模块）
- ❌ OWL 输出格式变化（仍 Turtle）
- ❌ 其他 4 adapter 改动
- ❌ IR 模型改动
- ❌ orchestrator 改动
- ❌ cim17_full.ttl 压缩（gzip / zip 后处理）
- ❌ index.ttl manifest 文件
- ❌ 跨包循环显式检测

## 验证策略

| 验证项 | 方法 | 期望 |
|--------|------|------|
| 单元测试 | `pytest tests/unit/test_b5_multi_package_owl.py -v` | 12/12 PASS |
| 全量回归 | `pytest tests/unit/ -v` | 593/593 PASS |
| E2E 体积 | 重新 emit 后 `du -h cim17_full.ttl` | ~1.5 MB（旧 build 残留 128KB 已污染基线）|
| E2E rdflib 解析 | Python `Graph().parse(full, format="turtle")` | 无异常 |
| E2E 空包跳过 | `ls cim17_*.ttl` | 仅 8 个非空 + full |
| 空包警告日志 | `grep "b5_empty_pkg_skipped"` | 12 条（每空包 1 条）|
| 无 cycle 错误 | `grep "Graph contains a cycle"` | 0 条 |
| Core 优先 | `ls -1 cim17_*.ttl` 排序 | Core 永远首位（full 除外）|

## 文件变更清单

| 文件 | 操作 | 估算行数 |
|------|------|---------|
| `src/cim_ontology/adapters/owl.py` | 取消 dedup 调用 / 取消 topo / 新增 2 函数 / emit 流程微调 | +25 / -10 |
| `tests/unit/test_b5_multi_package_owl.py` | 新建 | +200 |

**总变更**：2 文件，~215 行净增。

## 设计权衡记录

| 决策 | 备选 | 选择理由 |
|------|------|---------|
| 取消 dedup 调用 | 阈值降低 + 保留部分 dedup | 用户决策"完全保留原包"，简化优先 |
| 取消 topo 排序 | 显式环路拆除（NetworkX）| OWL 原生支持循环 import，与现实生态一致 |
| `_emit_order` Core 优先 | 全 IR 原始顺序 | Core 是基础包，下游工具从 Core 起解析更直观 |
| 空包跳过 + 警告 | 占位元信息文件 | 警告可观测；占位文件对 reasoner 无意义 |
| 保留 cim17_full.ttl | 取消聚合文件 | 向后兼容（现有验证脚本依赖）|
| 12 测试用例 | 32+ 用例 | 与 B4/B7 规模对齐；足够覆盖核心场景 |
| 不显式 detect cycles | OWL 推理层处理 | 单文件改动、KISS；现实 OWL 工具均支持 |
| 取消 dedup 不动 `_class_dedup.py` | 删除整个模块 | 其他 adapter 仍可调用；最小破坏面 |
| 不引入 `index.ttl` manifest | 加一份 manifest 文件 | YAGNI；SPARQL 工具通过 glob / SPARQL FROM 即可 |

## 不变量

- 5 个 adapter 的职责边界不变（仅 OWL 内部调整）
- IR 模型字段不变
- orchestrator 流程不变
- 其他 adapter 输出格式不变（OWL/SHACL/JSON Schema/Python Types/JSON-LD Context）
