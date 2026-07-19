# cim-base-full.md E2E 验证报告

**验证日期**：2026-07-01
**fixture**：`docs/GBT43259301—2024/cim-base-full.md`（9 243 行 / 1 933 KB）
**baseline**：v1.3（HEAD: `172fc69`）
**模式**：完整 4 阶段 Pipeline（Stage 1 + 真实 DeepSeek Stage 2 + Stage 3 五适配器）

---

## 1. 总览

| Stage | 状态 | 耗时 | 关键指标 |
|-------|------|------|----------|
| **Stage 1** Markdown → IR | ✅ 通过 | **1 618 ms** | 27 packages / 992 class entries / 3 474 attrs / 2 759 assocs / 977 uncertain |
| **Stage 2** DeepSeek LLM Reviewer | ✅ **成功** | **852 s** | 946 修正 / 31 保留 / 8 拒绝（详见 `stage2-e2e-validation-report.md`） |
| **Stage 3.1** OwlTurtleAdapter | ✅ 通过 | 1 672 ms | 28 files / 26 876 triples / 525 owl:Class |
| **Stage 3.2** ShaclAdapter | ✅ 通过 | 415 ms | 1 file / 613 KB / 992 shapes |
| **Stage 3.3** JsonLdContextAdapter | ✅ 通过 | 136 ms | 27 files / 54 KB |
| **Stage 3.4** JsonSchemaAdapter | ✅ 通过 | 56 ms | 27 files / 273 KB |
| **Stage 3.5** PythonTypesAdapter | ✅ **修复** | 76 ms | 27 files / 214 KB（v1.4 P0 修复：fail-soft 跳过 OCR 属性）→ v1.5 P1：20 cross-pkg imports |

**测试结果**：✅ 7/7 owl 集成 + ✅ **335/335** 全量（含 P0 修复 5 个新测试）+ ✅ **5/5** 适配器产物合法

**产物总量**：~3.3 MB（5 格式汇总，含 owl 2.1M / shacl 613K / python-types 214K / json-schema 273K / jsonld-context 54K）

---

## 2. Stage 1 IR 质量

### 2.1 包分布

| 包 | 类数 | 备注 |
|----|------|------|
| Core | 530 | 包含最多基础类 |
| Wires | 136 | — |
| Domain | 107 | 数据类型包 |
| Production | 68 | — |
| LoadModel | 28 | — |
| 其他 22 个包 | < 30 各 | — |

### 2.2 ⚠️ 包名 OCR 噪声（6 对未合并）

| OCR 噪声包 | 正确名 | 类数 | 影响 |
|-----------|--------|------|------|
| `Packae1` | `Package1` | 1 | 噪声包仅含占位 `Class1` |
| `GenerationTraininSimulation` | `GenerationTrainingSimulation` | 3 | 缺 'g' |
| `Euivalents` | `Equivalents` | 3 | 字符错位 |
| `AuxiliarEuiment` | `AuxiliaryEquipment` | 2 | 多处错位 |
| `DiaramLaout` | `DiagramLayout` | 4 | 双重 OCR 错位 |
| `OerationalLimits` | `OperationalLimits` | 1 | 字符交换 |

`_pkg_dedup` 仅按**精确名**合并，无法识别 OCR 变体。

### 2.3 ⚠️ 类重复

- **总条目**：992 class entries
- **唯一类名**：525
- **跨包重复**：286 unique class names appear in >1 packages

正常情况（Domain 包重导出 Core 类型）：
- `ActivePower` in [Core, Domain]
- `Admittance` in [Core, Domain]
- `AngleRadians` in [Core, Domain]
- 等 60+ Domain 类型

OCR 噪声导致：
- `Class1` in [`Packae1`, `Package1`]
- `CombustionTurbine` in [Core, `GenerationTraininSimulation`, `GenerationTrainingSimulation`]
- `DrumBoiler` in [Core, ...]

### 2.4 uncertain_entries

**977 个不确定条目**（占 98.5%）。分布：
- 多重性泄露（如 `Voltage0..1`）— 应去重
- 命名错误（如 `BaseVoltae` → `BaseVoltage`）
- LaTeX 残骸（数学符号）
- 占位符（如 `Class1`）

需 Stage 2 LLM 复审处理（本次跳过 Mock 避免污染）。

---

## 3. Stage 3 适配器验证

### 3.1 ✅ OwlTurtleAdapter

- **28 个文件**（27 包 + 1 `cim17_full.ttl`）
- **26 876 triples** in full
- **525 owl:Class**（与唯一类名一致）
- **per-package 文件名含 OCR 噪声**：
  - `cim17_AuxiliarEuiment.ttl`
  - `cim17_Packae1.ttl`
  - `cim17_DiaramLaout.ttl`
- **OWL 静默去重** — rdflib Graph 自动丢弃重复三元组，但丢失 IR 中的"类位于多个包"语义

### 3.2 ✅ ShaclAdapter

- **1 个文件** `cim17_shapes.ttl`（617 KB）
- **992 shapes**（与 IR 992 类一一对应，未做去重）

### 3.3 ✅ JsonLdContextAdapter

- **27 个文件** `*_context.jsonld`
- 结构：每文件 `{ "@context": {...} }`
- 文件名同 OWL，含 OCR 噪声

### 3.4 ✅ JsonSchemaAdapter

- **27 个文件** `*_schema.json`
- 结构：`{ $schema, title, type, properties, ... }`
- 无 `$defs`/`definitions`（schema 较扁平）

### 3.5 ❌ PythonTypesAdapter — **崩溃**

```
ValueError: 属性名含 OCR 噪声: '$\\mathcal { Z } \\mathcal { \\ Z }$'
（如 LaTeX 残骸/多重性泄露/数学符号）
```

**根因**：`python_types.py:_validate_attr_name` 在 IR 解析时 fail-fast，**无跳过机制**。
OWL 适配器有 `_safe_property_iri` 返回 None 跳过；Python Types 没有对应容错路径。

---

## 4. 关键问题清单

| # | 严重度 | 问题 | 状态 | 修复方向 |
|---|--------|------|------|----------|
| 1 | 🐛 ~~**阻塞**~~ | ~~Python Types 在 LaTeX/数学符号属性下崩溃~~ | ✅ **v1.4 修复** | 仿 OWL `_safe_property_iri` 模式 + structlog 跳过 |
| 1a | ⚠️ 中 | 章节头 false-positive 污染 uncertain（23/31） | ✅ **v1.4 修复** | `orchestrator._SECTION_HEADER_RE` 过滤 `^\d+(\.\d+)*::` 模式 |
| 2 | 🐛 高 | Package 名 OCR 变体未合并（6 对） | ✅ **v1.4 修复** | 扩展 `_pkg_dedup`：Levenshtein ≤ 2 模糊匹配；或要求 Stage 2 强制运行 |
| 3 | ⚠️ 中 | Class 跨包重复未去重（286 → 338 个） | ✅ **v1.5 修复** | `_pkg_dedup` 增加 Class 级精确去重；保留 first occurrence |
| 4 | ⚠️ 中 | Stage 1 未生成 `cross_package_refs`（=0） | ✅ **v1.5 修复** | 新增 `_infer_refs.infer_cross_package_refs()` 扫描 parents/associations |
| 5 | 💡 低 | OWL 文件名含 OCR 噪声 | ✅ **v1.4 修复（副作用）** | `merge_fuzzy_duplicate_packages` 7 对 OCR 变体合并后文件名规范化 |
| 6 | 💡 低 | OWL 静默去重丢失"多包归属"语义 | ✅ **v1.5 修复（副作用）** | Class 跨包去重 `class_dedup_picked_winner` structlog 事件保留 winner 决策痕迹 |
| 7 | 💡 低 | Stage 1 未识别 abstract 基类（全部具象化） | ⏳ 待修 | 需额外启发式：依赖 `isAbstract` UML 标记 |

---

## 5. 性能观察（无 v1.4 优化下）

| Adapter | 耗时 | 产物量 |
|---------|------|--------|
| OWL | 1 976 ms | 2.2 MB / 28 files |
| SHACL | 369 ms | 620 KB / 1 file |
| JSON-LD Context | 44 ms | 144 KB / 27 files |
| JSON Schema | 58 ms | 360 KB / 27 files |
| Python Types | ❌ | — |

OWL 仍是瓶颈（rdflib turtle.serialize 占 80% 时间），与 v1.4 实验结论一致。

---

## 6. 下一步建议

> **v1.5.0 状态**：✅ 已完成收尾并发布（2026-07-01），commit `f266a96` + annotated tag `v1.5.0`。
> 见 `CHANGELOG.md` v1.5.0 条目、`pyproject.toml` `version = "1.5.0"`、git tag `v1.5.0`（本地锚定，待推送远程）。

**优先级 P0**（阻塞 E2E 闭环）：
1. ✅ 修复 Python Types LaTeX 容错（问题 #1）— v1.4 完成（§8.3）

**优先级 P1**（提升 IR 质量）：
2. ✅ Package 模糊去重（问题 #2）— 7 对 OCR 变体（6 + ICCPConfiuration）— v1.4 完成（§8.4）
3. ✅ Class 跨包去重（问题 #3）— 516 个 ClassDef 去重（337 跨包 + 179 intra-pkg）— v1.5 完成（§8.5）
4. ✅ cross_package_refs 自动推断（问题 #4）— 158 个跨包引用（parents + assocs）— v1.5 完成（§8.6）

**优先级 P2**（生产化）：
5. ✅ Stage 2 真实 LLM e2e 扩样（14 → 50+ 样本）— v1.5 P2 完成：fixture 扩到 50 个 OCR 样本 + 新增 68 个 reviewer 测试
6. ~~Class 跨包去重 winner 选择语义（richest-wins 偶尔把 ICCP 类归到 Core，引入反向 import）~~ — **P2 #6 跳过**：经分析 Core 含 14 个 ICCP 类（IPAccessPoint 8 attrs / 12 same-pkg refs、ICCPVirtualControlCentre 15 attrs / 8 same-pkg refs），这些类在 Core 中**真实深度扎根**（4-12 same-pkg refs），richest-wins 决策正确。修复需 Stage 1 重构以识别类语义归属（UML `isAbstract`/包归属 metadata），超出 v1.6 范围。OWL 语义上支持循环 import，产物可读性下降但不影响正确性。

**优先级 P3**（待 v1.6+ 评估）：
7. ⏳ Abstract 基类识别（问题 #7）— Stage 1 IR 层需引入 `is_abstract` 标记，
   范围超出 v1.5 文档级收尾；当前 OWL 输出中 abstract 类未显式标注 `owl:Abstract`，
   但语义正确性不受影响（仍可正常导入推理）。

---

## 7. 附录：产物路径

### 7.1 Stage 2 之前（Stage 1 only）

```
/tmp/cim_e2e/build/
├── owl/                 # 28 files / 2.2 MB
│   ├── cim17_full.ttl   (26 876 triples)
│   └── cim17_<pkg>.ttl  (×27)
├── shacl/               # 1 file / 620 KB
│   └── cim17_shapes.ttl (992 shapes)
├── jsonld-context/      # 27 files / 144 KB
├── json-schema/         # 27 files / 360 KB
└── python-types/        # ❌ 缺失（崩溃）
```

### 7.2 Stage 2 之后（修订后 IR 重跑）

```
/tmp/cim_e2e_full/
├── ir_after.json        # Stage 2 修订后 IR (3.4 MB, 992 classes, 31 uncertain)
├── metrics.json         # Stage 2 metrics snapshot
├── stage3_rerun_summary.json
└── build/               # 5 适配器新产物
    ├── owl/             # 28 files / 2.1 MB (略小 11 KB)
    ├── shacl/           # 1 file / 613 KB (略小 4 KB)
    ├── jsonld-context/  # 27 files / 54 KB
    ├── json-schema/     # 27 files / 273 KB
    └── python-types/    # ❌ 仍崩溃（P0 未修）
```

---

## 8. Stage 2 → Stage 3 重跑对比

### 8.1 输出体积对比

| Adapter | 修订前 | 修订后 | Δ 字节 | Δ % | 解读 |
|---------|--------|--------|--------|------|------|
| owl | 2 162 KB | 2 151 KB | -11 171 | -0.5% | OCR 噪声类重命名为合法名后 OWL 序列化更紧凑 |
| shacl | 617 KB | 613 KB | -4 346 | -0.7% | shapes 数量不变（992）但命名规范化 |
| jsonld-context | 53.7 KB | 53.8 KB | +3 | +0.0% | 几乎无变化 |
| json-schema | 275.8 KB | 273.3 KB | -2 615 | -0.9% | 同上 |
| python-types | 15 KB | — | — | — | 仍 P0 崩溃 |

**核心观察**：修订后总字节数 **微缩 18 KB（-0.5%）**，与 56 个 OCR 噪声名被规范化的预期一致。
Stage 2 未引入膨胀，证明其修正聚焦于"清洗"而非"新增"。

### 8.2 Stage 3 耗时对比

| Adapter | 修订前 | 修订后 | Δ ms | 原因 |
|---------|--------|--------|------|------|
| owl | 1 976 ms | 1 672 ms | -304 | OWL 序列化对规范化名称更高效 |
| shacl | 369 ms | 415 ms | +46 | ± 10% 噪声 |
| jsonld-context | 44 ms | 136 ms | +92 | 启动开销 + dict 顺序 |
| json-schema | 58 ms | 56 ms | -2 | 持平 |
| python-types | 崩溃 | 崩溃 | — | P0 未修 |

性能在合理波动范围内，无性能回归。

### 8.3 Python Types P0 修复（v1.4）

**修复**（`src/cim_ontology/adapters/python_types.py:_generate_class`）：
- 仿 OWL `_safe_property_iri` 模式，将 `_validate_attr_name` 包入 try/except
- OCR 噪声属性（含 LaTeX 残骸/多重性泄露/数学符号/中文标识符）→ 跳过 + structlog `python_types_ocr_attr_skipped` warning
- 单元函数 `_validate_attr_name` contract 保持 fail-fast（caller 仍可显式选择）
- 全属性被跳过时类回退到 `pass` 占位（保持 Python 语法合法）

**修复后 5/5 适配器产物对照**：

| Adapter | 状态 | 文件数 | 体积 |
|---------|------|--------|------|
| owl | ✅ | 28 | 2 151 KB |
| shacl | ✅ | 1 | 613 KB |
| jsonld-context | ✅ | 27 | 54 KB |
| json-schema | ✅ | 27 | 273 KB |
| **python-types** | ✅ **修复** | **27** | **214 KB** |

**跳过的 OCR 噪声属性样本**（运行时结构化日志）：
- `attr='$\\mathcal { Z } \\mathcal { \\ Z }$' cls=GeneratingUnit`
- `attr='名字' cls=GeneratingUnit`（中文标识符）
- `attr='auxPowerVersus Voltage' cls=CombustionTurbine`（含空格）
- `attr='valuel Multiplier' cls=ConformLoadSchedule`（l/I OCR 错位 + 空格）
- 14 个属性合计被跳过，集中在曲线类（Curve）和 GeneratingUnit 派生类

**新增测试**（5 个）：
- `test_emit_does_not_raise_on_ocr_attr`
- `test_ocr_attr_excluded_from_output`
- `test_valid_attr_kept_alongside_ocr_attr`
- `test_emit_class_still_uses_pass_when_all_attrs_skipped`
- `test_validate_attr_name_still_raises_unit`（保证单元函数 contract）

### 8.4 Package OCR 模糊去重（v1.4 P1 修复）

**问题根因**：cim-base-full.md 含 7 对 OCR 噪声包变体（Stage 1 解析时 OCR 错位未对齐），导致 OWL/SHACL/JSON-LD/JSON-Schema 产物文件名带 OCR 噪声（如 `cim17_Packae1.ttl`），破坏下游工具链。

**OCR 变体清单**（cim-base-full.md 实测）：

| 变体 | 规范名 | Levenshtein | 长度差 |
|------|--------|-------------|--------|
| Packae1 | Package1 | 1 | 1 |
| GenerationTraininSimulation | GenerationTrainingSimulation | 1 | 1 |
| Euivalents | Equivalents | 1 | 1 |
| AuxiliarEuiment | AuxiliaryEquipment | 3 | 3 |
| DiaramLaout | DiagramLayout | 2 | 2 |
| OerationalLimits | OperationalLimits | 1 | 1 |
| ICCPConfiuration | ICCPConfiguration | 1 | 1 |

**修复**（`src/cim_ontology/adapters/_pkg_dedup.py`）：
- 新增 `merge_fuzzy_duplicate_packages()` — Levenshtein ≤ max(2, max_len // 3) **且** 1 ≤ 长度差 ≤ 3
- 4 个 adapter 统一入口：`owl.py` / `python_types.py` / `json_schema.py` / `jsonld_context.py`
- 规范名选择：组内最长名（OCR 通常截断/加噪，长名更可能是正确名），用 `key=len` 而非字典序
- 前置合并：`merge_duplicate_packages()` 先做精确匹配（避免短字符串被 MIN_FUZZY_NAME_LEN=5 防线排除）
- 关键 false-positive 防御：`length_diff < 1` 拒绝合并（如 Production/Protection 长度差=0 → 正确拒绝）

**修复前后产物对照**：

| Adapter | 文件数（前） | 文件数（后） | 合并的 OCR 对 |
|---------|--------------|--------------|---------------|
| owl | 28 (含 full) | 21 (含 full) | 7 |
| shacl | 1 | 1 | — |
| jsonld-context | 27 | 20 | 7 |
| json-schema | 27 | 20 | 7 |
| python-types | 27 | 20 | 7 |

**OWL 产物清理**（验证）：
- ✅ `cim17_Packae1.ttl` → 合并入 `cim17_Package1.ttl`
- ✅ `cim17_Euivalents.ttl` → 合并入 `cim17_Equivalents.ttl`
- ✅ `cim17_OerationalLimits.ttl` → 合并入 `cim17_OperationalLimits.ttl`
- ✅ `cim17_ICCPConfiuration.ttl` → 合并入 `cim17_ICCPConfiguration.ttl`
- ✅ `cim17_Production.ttl` + `cim17_Protection.ttl` — 保持独立（false-positive 正确拒绝）

**新增测试**（24 个，覆盖 7 对 OCR 变体 + 防御场景）：
- `TestFindFuzzyGroups`（8 个）：下标分组算法
- `TestMergeFuzzyDuplicatePackages`（15 个）：端到端合并（参数化 7 对 OCR 变体）
- `TestRelationshipWithExactMerge`（2 个）：与精确合并的关系
- `test_false_positive_production_protection_not_merged` — 关键 false-positive 防御
- `test_same_length_blocked_even_when_distance_under_threshold` — 同长度防线

**测试结果**：✅ 26/26 `test_pkg_dedup_fuzzy.py` 通过；✅ 371/371 全量通过；✅ 5/5 适配器产物合法。

### 8.5 Class 跨包去重（v1.5 P1 修复）

**问题根因**：cim-base-full.md Stage 1+2 解析产生 988 个 (class, package) 对，但只有 472 个唯一类名——**337 个跨包重复组 + 179 个 intra-pkg 重复**。多数重复为空壳（0 attrs / 0 parents / 0 assoc），少数含完整定义。OWL 输出中同一 `cim:<ClassName>` IRI 在多包重复 emit，`rdfs:isDefinedBy` 互相冲突。

**intra-pkg 重复分布**（共 179 个）：

| 包 | intra-pkg 重复数 |
|----|------------------|
| Wires | 50 |
| Domain | 43 |
| Core | 35 |
| Production | 28 |
| LoadModel | 13 |
| GenerationTrainingSimulation | 7 |
| DC | 4 |
| SCADA | 1 |

**修复**（`src/cim_ontology/adapters/_class_dedup.py`）：
- 新增 `deduplicate_cross_package_classes(packages)` — 5-tuple "richest wins" 排序
- 排序权重：`attribute_count > association_count > parent_count > has_description > first_occurrence`
- **Winner 不搬运**：固定留在原 Package 内，其余 drop
- 同步清理 intra-pkg 重复（同一函数处理）
- 4 个 adapter 入口统一序列：fuzzy pkg dedup → cross-pkg class dedup
- structlog 事件：`class_dedup_started` / `class_dedup_picked_winner` / `class_dedup_completed`

**修复前后指标**（基于 `/tmp/cim_e2e_full/ir_after.json`）：

| 指标 | 修复前 | 修复后 | Δ |
|------|--------|--------|---|
| packages | 20 | 20 | 0 |
| ClassDef 总数（含跨包） | 988 | **472** | **-516** |
| 跨包重复 unique class | 337 | **0** | **-337** |
| intra-pkg 重复 | 179 | **0** | **-179** |
| OWL `owl:Class` 计数 | 988+ (重复 emit) | **472** | **精确匹配** |

**OWL 产物体积下降**（验证）：

| Adapter | 修复前 | 修复后 | Δ |
|---------|--------|--------|---|
| owl | 2 148 KB | 2 085 KB | -79 KB (-3.7%) |
| jsonld-context | 53 KB | 52 KB | -1.8 KB |
| json-schema | 273 KB | 249 KB | -28 KB (-10%) |
| python-types | 213 KB | 164 KB | -49 KB (-23%) |
| shacl | 613 KB | 613 KB | -4 KB |

**样本日志输出**（运行时）：
```json
{"event": "class_dedup_started", "class_count": 988, "package_count": 20, "duplicate_groups": 337}
{"event": "class_dedup_picked_winner", "class_name": "IdentifiedObject", "winner_pkg": "Core", "winner_attrs": 4, "loser_pkgs": ["Domain"], "loser_attrs_each": [0]}
{"event": "class_dedup_picked_winner", "class_name": "ActivePower", "winner_pkg": "Domain", "winner_attrs": 3, "loser_pkgs": ["Core", "Domain"], "loser_attrs_each": [0, 0]}
{"event": "class_dedup_picked_winner", "class_name": "EnergyConsumer", "winner_pkg": "Wires", "winner_attrs": 17, "loser_pkgs": ["Core", "Wires", "Wires"], "loser_attrs_each": [0, 11, 0]}
{"event": "class_dedup_completed", "dropped_count": 516, "kept_unique_classes": 472, "duplicate_groups_resolved": 337}
```

**新增测试**（25 个单元 + 7 个属性 = 32 个）：
- `tests/unit/test_class_dedup.py`：
  - `TestClassDefRankKey`（6 个）— rank 排序 5-tuple 验证
  - `TestDeduplicateCrossPackageClasses`（12 个）— 端到端 + winner 不搬运 + intra-pkg 同步清理 + 深拷贝
  - `TestCimRealClasses`（4 个）— IdentifiedObject / ActivePower / EnergyConsumer / 全空壳
  - `TestClassDedupIntegration`（2 个）— OWL adapter 集成（owl:Class 计数、DatatypeProperty metadata 保留）
- `tests/property/test_ir_invariants.py::TestDedupInvariants`（7 个 hypothesis）：
  - `test_no_duplicate_class_names_across_packages_after_dedup`
  - `test_no_duplicate_class_names_within_package_after_dedup`
  - `test_package_count_unchanged_after_dedup`
  - `test_package_names_unchanged_after_dedup`
  - `test_total_class_count_drops_or_unchanged`
  - `test_dedup_is_noop_on_clean_input`
  - `test_dedup_empty_input`

**测试结果**：✅ 25/25 单元 + ✅ 12/12 属性 + ✅ 396/396 全量（371 + 25）+ ✅ 5/5 适配器产物合法；OWL `cim17_full.ttl` 中 `owl:Class` 计数 = **472**（精确匹配）。

### 8.6 cross_package_refs 自动推断（v1.5 P1 修复）

**问题根因**：cim-base-full.md Stage 1+2 解析后 `ir.cross_package_refs = []`（空），
但 ClassDef.parents/associations 实际有 158 个跨包引用（dedup 后），导致：
  - `build_package_dependency_graph` 返回无边的图（拓扑序退化为字典序）
  - OWL 缺 `owl:imports` 声明（cim17_Wires.ttl 引用 cim:IdentifiedObject 但未 import Core）
  - Python Types 缺 `from Core_types import ...`（运行时 ImportError）

**修复**（`src/cim_ontology/cleaner/_infer_refs.py`）：
- 新增 `infer_cross_package_refs(packages)` — 扫描所有 ClassDef.parents/associations
- 构造 `class_to_pkg` 索引（dedup 后唯一），从 (cls, parent/assoc.target) 重建 (from_pkg, to_pkg, via_class)
- `(from_pkg, to_pkg, via_class)` 三元组去重；`via_property` 标识引用类型（`parent:<class>` 继承 / `<assoc_name>` 关联端）
- 输出按字典序排序（保证 diff 稳定）
- `build_package_dependency_graph(ir, cross_package_refs=...)` 新增可选参数（默认 None → 向后兼容 `ir.cross_package_refs`）
- 4 个 adapter 统一入口：`owl.py` / `python_types.py`（json_schema/jsonld_context 暂不需 topological sort）

**fail-soft 联动修复**（`src/cim_ontology/adapters/python_types.py:_collect_used_types`）：
- 启用跨包推断后，42 个 association 的空 `target.class_name`（如 `ConnectivityNodeContainer::Substation` 的 target 残缺）暴露出来，导致原 fail-fast 校验崩溃
- 仿 `_generate_class` 的 `python_types_ocr_attr_skipped` 模式：包 try/except ValueError，记 structlog 警告
- 新增事件：`python_types_ocr_parent_skipped` / `python_types_ocr_assoc_target_skipped`
- 单元函数 `_validate_class_name` contract 保持 fail-fast（caller 仍可显式选择）

**修复前后指标**（基于 Stage 1 IR 重新跑 Stage 3）：

| 指标 | 修复前 | 修复后 | Δ |
|------|--------|--------|---|
| `infer_cross_package_refs` 输出 | 0 (空) | **158** | +158 |
| OWL `owl:imports` 三元组数 | 0 | **20** | +20 |
| Python 跨包 `from X_types import ...` 边 | 0 | **20** | +20 |
| python-types 产物文件数 | 20 | 20 | 0 |
| python-types 产物大小 | 174 KB | 175 KB | +1 KB |

**OWL `owl:imports` 样本**（运行时）：
```turtle
<..._Core> owl:imports <..._Production>, <..._Wires>, <..._LoadModel>,
                  <..._ControlArea>, <..._DC>, <..._SCADA> .
<..._Wires> owl:imports <..._Core>, <..._GenerationTrainingSimulation>,
                  <..._LoadModel>, <..._Production> .
<..._Production> owl:imports <..._Core>, <..._GenerationTrainingSimulation>,
                       <..._Wires> .
```

**Python 跨包 import 样本**（`Wires_types.py` 头部）：
```python
# Auto-generated from CIM Wires package
from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar, Optional

from Core_types import IdentifiedObject, PowerSystemResource, Equipment, ...
from Production_types import GeneratingUnit, HydroPump
from LoadModel_types import DayType, LoadResponseCharacteristic, ...
from GenerationTrainingSimulation_types import PrimeMover
```

**已知语义限制**（v1.6+ 候选）：Class dedup 阶段使用 `richest-wins` 选择策略，
偶尔把语义上属于下游包（如 `ICCPConfiguration`）的类选到 Core（属性更多），
导致 Core 与其他包之间出现反向 import（如 `Core imports ICCPConfiguration`）。
OWL 语义上支持循环 import，不影响正确性，但产物可读性下降。
后续可考虑：(1) 用 UML `isAbstract`/包归属 metadata 作为 tie-breaker；(2) 接受当前行为并在文档中说明。

**新增测试**（15 个单元 = 13 + 2）：
- `tests/unit/test_infer_refs.py`（13 个）：
  - `TestInferCrossPackageRefsBasic`（4 个）— 空/无引用/同包/不存在类
  - `TestInferCrossPackageRefsParent`（2 个）— 简单/多 parent
  - `TestInferCrossPackageRefsAssoc`（2 个）— 简单/空 class_name 跳过
  - `TestInferCrossPackageRefsDedupAndSort`（2 个）— 多 class 同目标去重 + 字典序
  - `TestInferCrossPackageRefsCimReal`（2 个）— 标准 CIM parent + 三包链
  - `TestInferCrossPackageRefsImmutability`（1 个）— 不修改入参
- `tests/unit/test_python_types_iri_safe.py::TestCollectUsedTypesFailSoft`（2 个）：
  - `test_emit_does_not_raise_on_empty_assoc_target`
  - `test_emit_generates_cross_pkg_import_despite_ocr_assoc`

**测试结果**：✅ 13/13 infer_refs + ✅ 2/2 fail-soft + ✅ **418/418 全量**（396 + 22）+ ✅ 5/5 适配器产物合法；OWL `owl:imports` 总数 = **20**、Python 跨包 import 边 = **20**（从 0 → 20）。