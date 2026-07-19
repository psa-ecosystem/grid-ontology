# 电网本体提取与生成器 — 设计规范

> **项目代号**：`grid-ontology`
> **状态**：已批准，待实施
> **日期**：2026-06-22
> **目标标准**：GB/T 43259.301—2024（IDT IEC 61970-301:2020）

---

## 1. 概述

### 1.1 问题陈述

GB/T 43259.301—2024《能量管理系统应用程序接口（EMS-API）第 301 部分：公共信息模型（CIM）基础》是电力行业数字化的核心本体标准，包含 27 个包、约 200+ 类、约 750 张表。现有挑战：

- 标准原文为 PDF/扫描件，OCR 后存在大量错字、命名空间拼写错误
- 缺乏面向 Protégé/TopBraid 建模者、Python 应用开发者、数据治理工程师的统一资产
- 跨团队使用 OWL/RDF Turtle、SHACL、JSON-LD/JSON Schema 等不同形式

### 1.2 解决方案

构建 Python CLI + 库 `cim-ontology`，从拼接后的 Markdown 标准文档自动抽取本体定义，生成多格式产物，并通过规则清洗 + LLM 复审混合架构保证质量。

### 1.3 目标用户

| 用户 | 主要交付物 | 使用场景 |
|------|-----------|----------|
| 本体建模者 | OWL/Turtle 文件 | 在 Protégé/TopBraid 中可视化编辑 |
| 应用开发者 | Python SDK（dataclass 库） | 业务代码中类型提示与实例化 |
| 数据治理工程师 | SHACL Shapes | 校验电网数据是否符合 CIM 规范 |
| 内部文档 | Markdown 摘要 + 图表 | 培训、参考、归档 |

### 1.4 范围

- **包含**：全部 27 个包、~750 张属性表、~200 个类的抽取与多格式生成
- **不包含**：完整 OWL/XML 序列化（仅 RDF Turtle）、SHACL 高级约束（如路径表达式）、本体推理（reasoning）
- **后续阶段**：SPARQL 查询生成器、CIM/E（欧洲扩展）适配、IEC 61850 桥接

---

## 2. 架构

### 2.1 Pipeline-Stage 四阶段架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Input                                                           │
│  cim-base-full.md (9243 行, 拼接后的完整标准)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: 规则清洗器 (Rules Cleaner)                              │
│  ─ markdown-it-py 解析                                          │
│  ─ 命名空间/类名/多重性规范化                                       │
│  ─ 不确定性条目标记（OCR 错误、命名空间未注册）                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     IR-JSON（中间表示）
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: LLM 复审核查 (LLM Reviewer)                             │
│  ─ 仅处理 Stage 1 标记为 uncertain 的条目（5-10%）               │
│  ─ 三层熔断：JSON 校验 → 业务校验 → 审计追踪                         │
│  ─ 支持多 provider：Claude API / Ollama / Mock                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     IR-JSON（已校验）
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3: 输出适配器 (Output Adapters)                            │
│  ─ OwlTurtleAdapter → 按包拆分 + 全量汇总                          │
│  ─ ShaclAdapter → 结构 + 业务双层约束                              │
│  ─ JsonLdAdapter → Context + Schema + Python types               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: 验证 (Verify)                                          │
│  ─ Roundtrip 测试（IR ↔ 输出）                                    │
│  ─ 与 IEC 61970-301 官方本体对比（95% 覆盖）                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Output                                                          │
│  output/owl/*.ttl + output/shacl/*.ttl + output/jsonld/*.{json,py}│
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计原则

| 原则 | 应用 |
|------|------|
| **KISS** | 每阶段职责单一；IR-JSON 作为唯一中间表示，避免阶段间直接依赖 |
| **DRY** | 所有输出适配器实现统一 `OutputAdapter` 接口；命名空间/类名注册表统一管理 |
| **YAGNI** | 不实现 SPARQL 生成、reasoner、完整 OWL/XML — 仅满足 4 类用户当前明确需求 |
| **SOLID-S** | 规则清洗器、LLM 复审、输出适配器各自单一职责 |
| **SOLID-O** | 输出格式通过注册中心扩展，新增格式无需修改核心代码 |
| **SOLID-D** | 上游依赖 IR-JSON 抽象而非具体格式；下游适配器依赖 IR 抽象而非具体清洗器 |

### 2.3 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 解析 | `markdown-it-py` + `BeautifulSoup4` | 双层解析：AST + DOM 容错 |
| LLM | Claude Sonnet 4.6（API） + Ollama（本地） | 主力精度 + 离线/保密备选 |
| RDF | `rdflib` | OWL/Turtle/JSON-LD 序列化事实标准 |
| SHACL | `pyshacl` | 唯一成熟的 Python SHACL 库 |
| JSON-LD | `pyld` | W3C 参考实现 |
| 数据模型 | `pydantic` v2 | 严格校验 + JSON Schema 自动生成 |
| CLI | `typer` + `rich` | 类型安全 + 美观输出 |
| 测试 | `pytest` + `hypothesis` | 单元/属性测试 |
| 日志 | `structlog` | 结构化 JSON 日志 |
| 缓存 | `sqlite3`（标准库） | LLM 响应本地缓存 |

---

## 3. 数据模型（IR-JSON）

### 3.1 顶层结构

```python
class OntologyIR(BaseModel):
    schema_version: str = "1.0"
    source: SourceInfo
    packages: list[Package]
    uncertain_entries: list[UncertainEntry]   # 待 LLM 复核
    cross_package_refs: list[CrossPackageRef]
    stats: IRStats
```

### 3.2 包与类

```python
class Package(BaseModel):
    iri: str                              # 命名空间 IRI
    name: str                             # "Core" / "Wires" / ...
    description: str | None
    classes: list[ClassDef]
    enumerations: list[Enumeration]
    primitive_types: list[PrimitiveType]


class ClassDef(BaseModel):
    iri: str                              # "http://iec.ch/...#Measurement"
    name: str                             # "Measurement"
    description: str | None
    stereotype: str | None                # "CIM" / "Concrete" / ...
    parents: list[ClassRef]               # 继承
    attributes: list[DataProperty]
    associations: list[ObjectProperty]
    source_table: int | None              # 来自哪张表


class ClassRef(BaseModel):
    package: str
    class_name: str
    iri: str | None = None
    is_external: bool = False
```

### 3.3 属性

```python
class DataProperty(BaseModel):
    name: str                             # "measurementType"
    data_type: str                        # "string" / "Integer" / "DateTime"
    multiplicity: Multiplicity
    is_derived: bool = False
    is_enum: bool = False
    description: str | None


class ObjectProperty(BaseModel):
    name: str                             # "PowerSystemResource"
    target: ClassRef
    multiplicity: Multiplicity
    is_aggregation: bool = False          # 组合/聚合
    inverse_name: str | None
    description: str | None


class Multiplicity(BaseModel):
    min: int                              # 0 / 1
    max: int | None                       # None = *
    raw: str                              # "0..*" / "1..1"

    @property
    def is_many(self) -> bool:
        return self.max is None or self.max > 1
```

### 3.4 枚举与字面量

```python
class Enumeration(BaseModel):
    name: str                             # "PhaseCode"
    values: list[str]                     # ["A", "B", "C", "AB", ...]
    description: str | None


class PrimitiveType(BaseModel):
    name: str                             # "ActivePower"
    base_type: str                        # "float"
    unit: str | None                      # "W"
    multiplier: str | None                # "k" / "M"
```

### 3.5 不确定性条目

```python
class UncertainEntry(BaseModel):
    case_id: str                          # 全局唯一
    source_table: int
    package: str
    raw_text: str
    rule_attempt: dict
    uncertainty_reason: str               # "class_name_typo" / "namespace_unknown" / ...
    context_snippet: str                  # 前后 200 字上下文
```

### 3.6 统计与来源

> ⚠️ **设计决策**：`duration_ms` 不属于本体定义的一部分（不同机器耗时不同，会破坏 IR 哈希的幂等性）。运行耗时放在执行上下文（§6 `EmitResult.duration_ms`）和审计日志中。

```python
class IRStats(BaseModel):
    """IR 内容的静态统计，与执行耗时无关"""
    package_count: int
    class_count: int
    attribute_count: int
    association_count: int
    enumeration_count: int
    uncertain_count: int


class SourceInfo(BaseModel):
    document_path: str                    # "docs/GBT43259301—2024/cim-base-full.md"
    document_sha256: str
    parsed_at: datetime
    parser_version: str
```

### 3.7 CIM 原生类型 → XSD 映射表

> **必要性**：CIM 自定义类型（如 `ActivePower`、`Voltage`、`DateTime`）必须显式映射到标准 `xsd:` 类型，才能保证 OWL/SHACL 输出在不同工具（Protégé、TopBraid、Java 校验器）中的语义一致。

```python
CIM_TO_XSD_TYPE_MAP: dict[str, str] = {
    # 数值类型
    "ActivePower":        "xsd:float",       # 单位: W
    "ReactivePower":      "xsd:float",       # 单位: var
    "ApparentPower":      "xsd:float",       # 单位: VA
    "Voltage":            "xsd:float",       # 单位: V
    "Current":            "xsd:float",       # 单位: A
    "Frequency":          "xsd:float",       # 单位: Hz
    "Angle":              "xsd:float",       # 单位: rad
    "ActivePowerPerCurrent": "xsd:float",
    "RealEnergy":         "xsd:float",       # 单位: Wh
    "ReactiveEnergy":     "xsd:float",
    "Resistance":         "xsd:float",
    "Reactance":          "xsd:float",
    "Length":             "xsd:float",
    "Temperature":        "xsd:float",
    "Pressure":           "xsd:float",
    "CostPerEnergy":      "xsd:float",
    "CostPerActivePower": "xsd:float",

    # 整数类型
    "Integer":            "xsd:integer",
    "IntegerQuantity":    "xsd:integer",
    "Seconds":            "xsd:integer",

    # 时间/日期
    "DateTime":           "xsd:dateTime",
    "Date":               "xsd:date",
    "Time":               "xsd:time",
    "Duration":           "xsd:duration",

    # 字符串
    "String":             "xsd:string",
    "Name":               "xsd:string",
    "NameType":           "xsd:string",
    "Description":        "xsd:string",

    # 布尔
    "Boolean":            "xsd:boolean",

    # 单位相关（CIM 特有的"值+单位"结构，详见 §3.7.1）
}


def normalize_data_type(cim_type: str) -> str:
    """将 CIM 原生类型规范化为 XSD URI"""
    if cim_type in CIM_TO_XSD_TYPE_MAP:
        return CIM_TO_XSD_TYPE_MAP[cim_type]
    # 未注册类型 → 退化为 string 并记录
    log.warn(f"未注册 CIM 类型: {cim_type}，按 string 处理")
    return "xsd:string"
```

#### 3.7.1 带单位类型的处理

CIM 中部分属性采用 `值+单位` 结构（如 `ActivePower.value` + `ActivePower.unit` + `ActivePower.multiplier`），映射为 XSD 时有两种选择：

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| **A. 拆字段** | 一个属性拆为 value / unit / multiplier 三个子属性 | SHACL 可分别校验 | 偏离 CIM 原模型 |
| **B. 单字段 + rdfs:comment** | 单个 float 属性，注释中说明单位 | 简洁 | 失去结构 |
| **C. 复合 datatype** | 自定义 OWL datatype（如 `cim:ActivePower` = `xsd:float` + 单位限制） | 语义完整 | 工具兼容性差 |

**默认采用方案 B**，单位信息放在 `rdfs:comment` 中：
- 应用层用 `cim:PowerSystemResource.ActivePower.value` 等约定访问
- SHACL 仅校验数值类型，不强制单位

---

## 4. Stage 1：规则清洗器

### 4.1 解析策略

| 输入 | 工具 | 目的 |
|------|------|------|
| Markdown AST | `markdown-it-py` | 提取章节结构、表格、代码块 |
| 章节 DOM | `BeautifulSoup4` | 容错的 HTML 树遍历，处理畸形表格 |

**解析路径**：

```
cim-base-full.md
  ↓ markdown-it-py
tokens (heading, table_open, table_row, ...)
  ↓ 章节分组
sections = [{path: "6.1.2 Core::IdentifiedObject",
             heading: "## 6.1.2 ...", tables: [...]}]
  ↓ BeautifulSoup 解析每张表
table_dicts = [{headers: [...], rows: [...]}]
  ↓ 规则清洗
cleaned_records
```

### 4.2 锚点模式

| 类型 | 模式 | 示例 |
|------|------|------|
| 章节 | `^## (\d+\.\d+(?:\.\d+)?) (.+)$` | `## 6.1.2 Class: IdentifiedObject` |
| 包定义 | `^## (\d+) Package: (\w+)$` | `## 5 Package: Core` |
| 属性表 | `^表 ?(\d+)续? Package::(\w+)的属性` | `表 3 Package::Measurement的属性` |
| 关联表 | `^表 ?(\d+)续? Package::(\w+)关联端` | `表 4 Package::Measurement关联端` |
| 字面量 | `^表 ?(\d+)续? Package::(\w+)字面量` | `表 5 Package::PhaseCode字面量` |

### 4.3 清洗规则

```python
NAMESPACE_CORRECTIONS = {
    # OCR 错字 → 正确命名空间
    "cin:":  "cim:",
    "cirn:": "cim:",
    "eu:":   "http://iec.ch/TC57/NonStandard/UML#",  # 扩展包
    "rdf:":  "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs:": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd:":  "http://www.w3.org/2001/XMLSchema#",
}

CLASS_NAME_CORRECTIONS = {
    # 已知 OCR 错误
    "Meastrement":       "Measurement",
    "Rep0rtingGroup":    "ReportingGroup",
    "AuxiliarEuiment":   "AuxiliaryEquipment",
    "DiaramLaout":       "DiagramLayout",
}


def clean_multiplicity(raw: str) -> Multiplicity:
    """规范化多重性，支持 OCR 变体"""
    raw = raw.strip().replace(" ", "")
    raw = raw.replace("$", "").replace("\\mathcal{Z}", "")  # LaTeX 噪声

    # 语义归一
    aliases = {"many": "0..*", "n": "0..*", "*": "0..*"}
    raw = aliases.get(raw, raw)

    if raw == "0..1":
        return Multiplicity(min=0, max=1, raw=raw)
    if raw == "1..1":
        return Multiplicity(min=1, max=1, raw=raw)
    if raw == "0..*":
        return Multiplicity(min=0, max=None, raw=raw)
    if raw == "1..*":
        return Multiplicity(min=1, max=None, raw=raw)

    # 兜底：标记不确定
    raise UnparseableMultiplicity(raw)


def clean_class_name(raw: str, registry: ClassRegistry) -> Cleaned:
    """清洗类名，应用已知 OCR 修正"""
    if raw in CLASS_NAME_CORRECTIONS:
        return Cleaned(
            value=CLASS_NAME_CORRECTIONS[raw],
            correction_applied=True,
            notes=f"OCR 修正: {raw} → {CLASS_NAME_CORRECTIONS[raw]}"
        )

    # 已在注册表 → 直接通过
    if registry.has(raw):
        return Cleaned(value=raw, correction_applied=False)

    # Levenshtein 距离 ≤ 2 的相似类名
    similar = registry.find_similar(raw, threshold=2)
    if similar:
        return Cleaned(
            value=raw,
            correction_applied=False,
            uncertainty_reason="class_name_typo",
            suggestions=[s.name for s in similar[:3]]
        )

    # 完全未知
    return Cleaned(
        value=raw,
        correction_applied=False,
        uncertainty_reason="class_unknown"
    )


def normalize_table_cells(table: BeautifulSoup) -> list[list[str]]:
    """规范化表格单元格"""
    result = []
    for row in table.find_all("tr"):
        cells = []
        for cell in row.find_all(["td", "th"]):
            text = cell.get_text(separator=" ", strip=True)
            text = clean_text(text)        # 去 LaTeX 噪声、合并空白
            cells.append(text)
        result.append(cells)
    return result
```

### 4.4 章节解析

```python
def parse_class_section(heading: str, tables: list[Table]) -> ClassDef:
    """从章节标题 + 表格构造 ClassDef"""
    # 标题形如 "## 6.1.2 Class: IdentifiedObject (CIM)"
    match = re.match(r"## (\d+\.\d+(?:\.\d+)?) Class: (\w+)(?:\s+\((\w+)\))?", heading)
    if not match:
        # 模糊匹配降级：缺失 `##` 标记或缩进异常时仍尝试识别
        fuzzy = re.search(r"(\d+\.\d+(?:\.\d+)?)\s+Class:\s+(\w+)(?:\s+\((\w+)\))?", heading)
        if not fuzzy:
            raise SectionParseError(f"无法解析章节标题: {heading}")
        match = fuzzy

    section_path, class_name, stereotype = match.groups()
    cls = ClassDef(name=class_name, stereotype=stereotype, ...)

    # 按表头分类表格
    for table in tables:
        first_cell = table.rows[0][0].lower()
        if "属性" in first_cell:
            cls.attributes = parse_attribute_table(table)
        elif "关联端" in first_cell:
            cls.associations = parse_association_table(table)
        elif "字面量" in first_cell:
            # 收集到包级枚举
            collect_enumeration(table, cls.package)
        elif "继承" in first_cell or "父类" in first_cell:
            cls.parents = parse_inheritance_table(table)

    return cls


def hierarchical_classify_section(heading: str, content: str, all_headings: list[str]) -> SectionContext:
    """
    层级推断（解析器脆弱性缓解）

    如果原始 Markdown 的 ## 标记因 OCR 异常丢失，可基于以下信号推断层级：
      1. 章节编号 (6.1.2 vs 6 vs 6.1)
      2. 文本长度（章节标题通常 < 100 字）
      3. 上下文（前一个章节的编号 + 1）
      4. 关键字模式 (Class:/Package:/Attribute: 等)
    """
    # 启发式 1: 章节编号格式
    m = re.match(r"^(\d+(?:\.\d+){0,3})", heading.strip())
    if m:
        depth = m.group(1).count(".") + 1
        return SectionContext(depth=depth, confidence=0.9)

    # 启发式 2: 关键字匹配
    if re.search(r"^Class:\s+\w+", heading):
        return SectionContext(depth=3, confidence=0.7)

    # 启发式 3: 默认 + 警告
    log.warn(f"章节层级无法推断: {heading}")
    return SectionContext(depth=2, confidence=0.3)
```

### 4.5 命名空间自动纠正

```python
def collect_namespace_aliases(content: str) -> dict[str, int]:
    """统计文档中出现的所有命名空间前缀及其频次"""
    aliases = {}
    for match in re.finditer(r"\b([a-z]+):[A-Z]\w+", content):
        prefix = match.group(1)
        aliases[prefix] = aliases.get(prefix, 0) + 1
    return aliases


def auto_correct_namespaces(aliases: dict[str, int]) -> dict[str, str]:
    """基于 Levenshtein 距离自动纠正命名空间拼写"""
    canonical = list(NAMESPACE_CORRECTIONS.keys())
    corrections = {}
    for alias, count in aliases.items():
        if alias in canonical:
            continue
        # 距离最近的规范前缀
        closest = min(canonical, key=lambda c: levenshtein(alias, c))
        if levenshtein(alias, closest) <= 2:
            corrections[alias] = closest
    return corrections
```

### 4.6 Stage 1 主入口

```python
def clean_markdown_to_ir(md_path: Path) -> OntologyIR:
    """Stage 1 入口：Markdown → IR-JSON"""
    start = time.monotonic()
    content = md_path.read_text(encoding="utf-8")

    # 1. 收集命名空间别名（用于自动纠正）
    ns_corrections = auto_correct_namespaces(collect_namespace_aliases(content))

    # 2. 章节切分
    sections = split_into_sections(content)   # [{path, heading, tables}, ...]

    # 3. 按包分组
    package_sections = group_by_package(sections)

    # 4. 解析每个包
    packages = []
    uncertain = []
    for pkg_name, pkg_sections in package_sections.items():
        try:
            pkg = parse_package(pkg_name, pkg_sections)
            packages.append(pkg)
        except SectionParseError as e:
            log.warn(f"跳过包 {pkg_name}: {e}")

    # 5. 汇总不确定性条目
    for pkg in packages:
        uncertain.extend(pkg.collect_uncertain())

    # 6. 统计
    stats = IRStats(
        package_count=len(packages),
        class_count=sum(len(p.classes) for p in packages),
        ...
        duration_ms=int((time.monotonic() - start) * 1000),
    )

    return OntologyIR(
        packages=packages,
        uncertain_entries=uncertain,
        stats=stats,
        source=SourceInfo(
            document_path=str(md_path),
            document_sha256=hashlib.sha256(content.encode()).hexdigest(),
            ...
        )
    )
```

### 4.7 不确定性触发条件

Stage 1 在以下情况下标记条目为 `uncertain`，触发 LLM 复审：

1. 类名不在 `CLASS_NAME_CORRECTIONS` 也不在已注册清单
2. 命名空间前缀未在 `NAMESPACE_CORRECTIONS` 中
3. 关联目标类名不在任何已抽取包中
4. 多重性字符串无法解析为 N..M 格式
5. 继承关系出现自引用或环
6. LaTeX 表达式（如 `$\mathcal{Z}$`）残留在非表格位置

---

## 5. Stage 2：LLM 复审核查

### 5.1 核心定位

LLM 不是 Stage 1 的替代品，而是**仲裁者**：

| 阶段 | 职责 | 处理量 |
|------|------|--------|
| Stage 1 规则清洗器 | 95% 的确定性工作 | ~1500 处表条目 |
| **Stage 2 LLM 复审** | 仅处理 Stage 1 标注 `uncertain` 的项 | ~50-200 处/包 |

### 5.2 触发条件

```python
@dataclass
class LLMReviewTrigger:
    case_id: str                    # 全局唯一 ID
    source_table: int               # 表号，如 150续
    package: str                    # 如 "Wires"
    raw_text: str                   # 原始 OCR 文本
    rule_attempt: dict              # Stage 1 的尝试结果
    uncertainty_reason: str         # 为什么需要复核
    context_snippet: str            # 前后 200 字上下文


REVIEW_TRIGGERS = {
    "class_name_typo":      "类名疑似 OCR 错误（如 Meastrement）",
    "namespace_unknown":    "出现未注册命名空间前缀",
    "inheritance_ambiguous":"继承关系存在多解",
    "association_target":   "关联目标类不在已注册清单",
    "multiplicity_invalid": "多重性违反 N..M 语法",
    "description_conflict": "类描述与已抽取属性语义冲突",
}
```

### 5.3 LLM 提供者适配层

```python
class LLMProvider(Protocol):
    def review(self, prompt: ReviewPrompt) -> ReviewResult: ...


class ClaudeProvider:        # 主选：Claude API
class OpenAIProvider:        # 备选
class OllamaProvider:        # 本地模型（断网/保密场景）
class MockProvider:          # 测试桩：返回确定性 mock
```

**配置驱动**（YAML）：

```yaml
llm:
  provider: claude
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY
  max_concurrent: 4
  timeout_s: 30
  cache:
    enabled: true
    backend: sqlite
    path: .cache/llm_reviews.db
  fallback:
    on_error: log_and_skip  # 失败时降级为规则结果
```

### 5.4 Prompt 模板

```python
REVIEW_PROMPT = """
你是 IEC 61970-301 CIM 本体建模专家。请复核以下从标准文档 OCR 中抽取的
本体条目，纠正可能的识别错误。

## 上下文
- 包: {package}
- 表号: 表 {table_no}
- 章节: {chapter_path}
- 邻近文本（前 200 字 / 后 200 字）: {context}

## 待复核内容
{raw_text}

## 规则引擎初步结果（可能错误）
{rule_attempt}

## 已注册的命名空间
{known_namespaces}

## 已注册的类清单（用于关联目标校验）
{known_classes}

## 任务
1. 若类名/属性名存在 OCR 错字，给出正确值
2. 若命名空间拼写有误，给出正确 URI
3. 若多重性格式非标准（如 "0..*" 写为 "many"），规范化为标准
4. 若关联目标类不存在于已注册清单，标记 invalid
5. 给出 0-1 的置信度分数

## 输出格式（严格 JSON 字符串）

输出 JSON 字符串（不要包在任何 markdown 围栏中），形如：
{ "corrected": { "class_name": "...", "namespace": "...",
  "attributes": [...], "associations": [...] },
  "confidence": 0.0, "notes": "修订理由" }
"""
```

### 5.5 输出校验与熔断

```python
class LLMReviewer:
    def __init__(self, provider, validator, audit_log):
        self._provider = provider
        self._validator = validator
        self._audit = audit_log

    def review(self, trigger: LLMReviewTrigger) -> ReviewResult:
        # 1. 缓存命中检查
        cached = self._cache.get(trigger.case_id)
        if cached:
            return cached

        # 2. 调用 LLM
        try:
            raw = self._provider.review(...)
        except LLMError as e:
            return self._fallback(trigger, reason=str(e))

        # 3. JSON Schema 严格校验（不通过则丢弃修订）
        result = self._validator.parse(raw)
        if not result:
            return self._fallback(trigger, reason="schema_invalid")

        # 4. 业务校验：类名/命名空间必须已注册
        if not self._validator.business_check(result, trigger):
            return self._fallback(trigger, reason="business_invalid")

        # 5. 写审计日志
        self._audit.record(trigger, raw, result)

        # 6. 入缓存
        self._cache.put(trigger.case_id, result)
        return result
```

**三层熔断**：
1. JSON 解析失败 → 用规则结果
2. 业务校验失败 → 用规则结果 + 标记 `llm_rejected`
3. 业务校验通过 → 覆盖规则结果

### 5.6 审计追踪

每次 LLM 修订写入 `audit/llm_reviews.jsonl`：

```jsonl
{"ts":"2026-06-22T10:30:00Z","case_id":"Wires::150续::row3",
 "trigger":"class_name_typo",
 "raw":"Meastrement",
 "rule_output":"Measurement",
 "llm_correction":"Measurement",
 "llm_confidence":0.98,
 "final":"Measurement",
 "action":"rule_corrected_by_llm"}
```

**人工审阅入口**：

```bash
cim-ontology audit review --since 2026-06-20
# → 输出表格：每行一条修订，按 confidence 升序
# → 可标记 accepted/rejected
```

### 5.7 成本与并发控制

| 措施 | 实现 |
|------|------|
| **缓存** | SQLite 按 `case_id` 哈希，跨运行复用 |
| **批处理** | 同一包的多个 trigger 合并为一次 LLM 调用（节省 ~40% token） |
| **并发** | `asyncio.Semaphore(max_concurrent)` 控制 |
| **早停** | 简单错误（如纯 OCR 漏字）跳过 LLM，正则直接修 |
| **预算** | `--max-tokens 100000` 硬上限 |

### 5.8 离线/保密场景

> ⚠️ **模型选型**：OCR 错字纠正本质是**指令遵循 + 语义推理**任务，而非代码生成。本地模型推荐**通用指令微调模型**而非代码专用模型：
> - 推荐：`Qwen2.5-72B-Instruct`、`Llama-3.3-70B-Instruct`、`Mistral-Large-2`
> - 不推荐：`*Coder` 系列（过度偏向代码生成，对 OCR 噪声鲁棒性差）

```bash
# 默认调用 Claude API
cim-ontology build --llm claude

# 离线场景：本地 Ollama
cim-ontology build --llm ollama --model qwen2.5:72b-instruct

# 完全禁用 LLM（仅规则 + 人工审计）
cim-ontology build --llm none
```

---

## 6. Stage 3：输出适配器

### 6.1 统一接口

```python
class OutputAdapter(Protocol):
    """所有输出适配器必须实现此接口。"""
    target_format: ClassVar[str]   # "owl" | "shacl" | "jsonld"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult: ...
    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult: ...


@dataclass
class EmitResult:
    files: list[Path]              # 生成的文件列表
    stats: dict[str, int]          # 各类资源计数
    warnings: list[str]            # 警告（如弃用类）
    duration_ms: int


@dataclass
class VerifyResult:
    passed: bool
    issues: list[VerifyIssue]      # 校验问题
    roundtrip_match: bool          # 是否能逆向还原 IR


ADAPTERS: dict[str, type[OutputAdapter]] = {
    "owl":    OwlTurtleAdapter,
    "shacl":  ShaclAdapter,
    "jsonld": JsonLdAdapter,
}
```

### 6.2 OWL / RDF Turtle 适配器

```python
class OwlTurtleAdapter:
    target_format = "owl"
    BASE_IRI = "http://iec.ch/TC57/2024/CIM-schema-cim17#"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        g = rdflib.Graph()
        g.bind("cim", self.BASE_IRI)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # 1. Ontology 头
        onto_iri = URIRef(f"{self.BASE_IRI.rstrip('#')}")
        g.add((onto_iri, RDF.type, OWL.Ontology))
        g.add((onto_iri, OWL.versionInfo, Literal("cim17")))
        g.add((onto_iri, RDFS.comment,
               Literal("GB/T 43259.301-2024 IDT IEC 61970-301:2020",
                       lang="en")))

        # 2. 计算包依赖图（拓扑排序），用于正确添加 owl:imports
        dep_graph = ir.build_package_dependency_graph()
        ordered_packages = topological_sort(dep_graph)
        # 拓扑序：Core → Domain → Wires → DC → ...（依赖在前的先序列化）

        # 3. 按包生成独立文件
        for pkg in ordered_packages:
            pkg_g = self._build_package_graph(pkg)
            # 关键：声明跨包依赖（owl:imports）
            for dep_pkg_name in dep_graph.successors(pkg.name):
                dep_pkg = ir.get_package(dep_pkg_name)
                dep_iri = URIRef(f"{self.BASE_IRI.rstrip('#')}_{dep_pkg.name}")
                pkg_g.add((URIRef(f"{self.BASE_IRI.rstrip('#')}_{pkg.name}"),
                           OWL.imports, dep_iri))

            out = output_dir / f"cim17_{pkg.name}.ttl"
            pkg_g.serialize(out, format="turtle")
            g += pkg_g

        # 4. 全量汇总
        g.serialize(output_dir / "cim17_full.ttl", format="turtle")

        return EmitResult(...)
```

**关键映射规则**：

| IR 概念 | OWL 输出 |
|---------|----------|
| `Package` | `owl:Ontology` 实例 + 命名空间绑定 |
| `Package → Package` 依赖 | `owl:imports` |
| `Class` | `owl:Class` |
| `DataProperty` | `owl:DatatypeProperty` |
| `ObjectProperty` | `owl:ObjectProperty` |
| `Cardinality(many,one)` | `owl:FunctionalProperty` |
| `Cardinality(many,many)` | 无特殊约束 |
| `Inheritance` | `rdfs:subClassOf` |
| `Enumeration` | `owl:oneOf` 集合 |
| `Description` | `rdfs:comment` + `skos:definition` |

#### 6.2.1 跨包依赖图计算

```python
def build_package_dependency_graph(ir: OntologyIR) -> nx.DiGraph:
    """
    从 cross_package_refs 构建有向依赖图

    节点: 包名 (str)
    边:  A → B 表示 A 引用 B（A 依赖 B）
    """
    g = nx.DiGraph()
    for pkg in ir.packages:
        g.add_node(pkg.name)
    for ref in ir.cross_package_refs:
        # from_package 依赖 to_package
        g.add_edge(ref.from_package, ref.to_package)
    return g


def topological_sort(g: nx.DiGraph) -> list[Package]:
    """
    Kahn 算法拓扑排序，循环依赖时回退到字典序

    CIM 标准中各包实际依赖关系（部分）:
        Core ← Domain ← Wires
                       ← Generation
                       ← DC
                       ← ...
    """
    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        # 实际不应出现；出现则降级 + 警告
        log.error(f"包依赖图中存在环: {e}")
        return sorted(g.nodes, key=lambda n: n)  # 字典序 fallback
```

**为什么需要 owl:imports**：
- 当用户在 Protégé 中**只打开单个分包文件**（如 `cim17_Wires.ttl`），工具需要知道从哪里找 `Core:IdentifiedObject`
- 不声明 `owl:imports` 会导致 Wires 包的类缺少 `rdfs:subClassOf cim:IdentifiedObject` 的可解析 URI
- 完整文件 `cim17_full.ttl` 不受影响（所有定义已包含），但仍添加以保持一致性

### 6.3 SHACL Shapes 适配器

**两套 Shapes**：
1. **结构验证**：必填属性、基数、数据类型
2. **业务约束**：命名规范、关联端约束

```python
class ShaclAdapter:
    target_format = "shacl"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        g = rdflib.Graph()
        g.bind("sh", SH)
        g.bind("cim", self.BASE_IRI)

        for cls in ir.all_classes():
            shape_iri = URIRef(f"{self.BASE_IRI}shape_{cls.name}")
            g.add((shape_iri, RDF.type, SH.NodeShape))
            g.add((shape_iri, SH.targetClass, URIRef(f"{self.BASE_IRI}{cls.name}")))

            # 必填属性 → sh:PropertyShape + sh:minCount=1
            for attr in cls.attributes:
                if attr.required:
                    self._add_property_shape(g, shape_iri, attr, min_count=1)

            # 关联基数
            for assoc in cls.associations:
                self._add_property_shape(g, shape_iri, assoc,
                                         min_count=assoc.min_card,
                                         max_count=assoc.max_card)

            # 数据类型
            for attr in cls.attributes:
                if attr.data_type:
                    self._add_datatype_constraint(g, shape_iri, attr)

        g.serialize(output_dir / "cim17_shapes.ttl", format="turtle")
```

**生成示例**（片段）：

```turtle
cim:shape_Measurement a sh:NodeShape ;
    sh:targetClass cim:Measurement ;
    sh:property [
        sh:path cim:Measurement.measurementType ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] ;
    sh:property [
        sh:path cim:Measurement.PowerSystemResource ;
        sh:class cim:PowerSystemResource ;
        sh:minCount 0 ;
        sh:maxCount 1 ;
    ] .
```

### 6.4 JSON-LD / JSON Schema 适配器

```python
class JsonLdAdapter:
    target_format = "jsonld"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        # 输出 3 类文件：
        # 1. JSON-LD context（语义层）
        # 2. JSON Schema（结构验证层）
        # 3. Python dataclass（运行时类型提示）

        results = []
        for pkg in ir.packages:
            # 1. Context
            ctx = self._build_jsonld_context(pkg)
            (output_dir / f"{pkg.name}_context.jsonld").write_text(
                json.dumps(ctx, indent=2, ensure_ascii=False)
            )

            # 2. Schema
            schema = self._build_json_schema(pkg)
            (output_dir / f"{pkg.name}_schema.json").write_text(
                json.dumps(schema, indent=2, ensure_ascii=False)
            )

            # 3. Python types (额外)
            py = self._build_python_types(pkg)
            (output_dir / f"{pkg.name}_types.py").write_text(py)

            results.extend([...])

        return EmitResult(files=results, ...)
```

**JSON-LD Context**（片段）：

```json
{
  "@context": {
    "@vocab": "http://iec.ch/TC57/2024/CIM-schema-cim17#",
    "cim": "http://iec.ch/TC57/2024/CIM-schema-cim17#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "name": "cim:IdentifiedObject.name",
    "description": "cim:IdentifiedObject.description"
  }
}
```

**Python 类型**（自动生成）：

> **关键约束**：Python 类型按包生成多个文件，必须**拓扑排序**避免循环导入。
> Wires 继承 Core 的 `IdentifiedObject`，Wires 的 dataclass 引用 Core 的 `PowerSystemResource` —— 必须先生成 Core 包。

```python
def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
    """JSON-LD 适配器（输出顺序经过拓扑排序）"""
    dep_graph = ir.build_package_dependency_graph()
    ordered_packages = topological_sort(dep_graph)  # Core → Domain → Wires → ...

    results = []
    for pkg in ordered_packages:
        # 1. Context
        ctx = self._build_jsonld_context(pkg)
        (output_dir / f"{pkg.name}_context.jsonld").write_text(
            json.dumps(ctx, indent=2, ensure_ascii=False)
        )

        # 2. Schema
        schema = self._build_json_schema(pkg)
        (output_dir / f"{pkg.name}_schema.json").write_text(
            json.dumps(schema, indent=2, ensure_ascii=False)
        )

        # 3. Python types（按拓扑序生成，避免循环 import）
        py = self._build_python_types(pkg, all_packages=ir.packages)
        (output_dir / f"{pkg.name}_types.py").write_text(py)

        # 每个 _types.py 文件头部添加 `from <dep_pkg>_types import ...`
        # 由 _build_python_types 自动生成

        results.extend([...])

    return EmitResult(files=results, ...)
```

**Python 类型样例**（按包生成，import 自动注入）：

```python
# Auto-generated from CIM Core package (no dependencies)
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class PhaseCode(str, Enum):
    """Enumeration of phase codes A, B, C, N, etc."""
    A = "A"
    B = "B"
    C = "C"
    AB = "AB"
    # ...

@dataclass
class IdentifiedObject:
    rdf_type: str = "cim:IdentifiedObject"
    mRID: str
    name: str
    description: Optional[str] = None

@dataclass
class PowerSystemResource(IdentifiedObject):
    """PSR 基类"""
    pass
```

```python
# Auto-generated from CIM Wires package
# 头部注入依赖包的 import
from Core_types import IdentifiedObject, PowerSystemResource  # ← 自动生成

from dataclasses import dataclass
from typing import Optional

@dataclass
class Conductor(PowerSystemResource):
    rdf_type: str = "cim:Conductor"
    length: Optional[float] = None
```

#### 6.4.1 跨包导入注入规则

```python
def _build_python_types(self, pkg: Package, all_packages: list[Package]) -> str:
    """生成 Python types 源码"""
    dep_graph = self._ir.build_package_dependency_graph()
    direct_deps = list(dep_graph.predecessors(pkg.name))  # 直接依赖

    imports = []
    for dep_name in direct_deps:
        dep_pkg = next(p for p in all_packages if p.name == dep_name)
        # 找出本包实际使用的依赖包类型
        used_types = self._collect_used_types(pkg, dep_pkg)
        if used_types:
            imports.append(
                f"from {dep_name}_types import {', '.join(sorted(used_types))}"
            )

    # 排序 import：标准库 → 第三方 → 本项目
    src_parts = [
        "# Auto-generated from CIM " + pkg.name + " package",
        *sorted(imports),
        "",
        "from dataclasses import dataclass",
        "from typing import Optional",
        "from enum import Enum",
        "",
        *self._generate_classes(pkg),
    ]
    return "\n".join(src_parts)
```

### 6.5 跨格式一致性校验

```python
def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
    # 选 10% 的类做往返测试
    sample = random.sample(ir.all_classes(), k=len(ir.all_classes()) // 10)

    issues = []
    for cls in sample:
        roundtripped = self._reparse(cls, emitted)
        if roundtripped != cls:
            issues.append(VerifyIssue(
                class_name=cls.name,
                format=self.target_format,
                diff=_diff(cls, roundtripped)
            ))

    return VerifyResult(
        passed=len(issues) == 0,
        issues=issues,
        roundtrip_match=len(issues) == 0
    )
```

### 6.6 文件组织

```
output/
├── owl/
│   ├── cim17_Core.ttl           # 按包拆分（推荐入 Git）
│   ├── cim17_Wires.ttl
│   ├── cim17_DC.ttl
│   ├── ...
│   ├── cim17_full.ttl           # 全量汇总（CI 用）
│   └── cim17_full.owl           # XML 格式（部分工具要求）
├── shacl/
│   └── cim17_shapes.ttl         # 单文件
├── jsonld/
│   ├── Core_context.jsonld
│   ├── Core_schema.json
│   ├── Core_types.py            # Python SDK
│   └── ...
└── manifest.json                 # 生成清单 + 哈希
```

### 6.7 CLI 入口

```bash
# 单格式生成
cim-ontology emit --input ir.json --format owl --output ./out/

# 多格式并行
cim-ontology emit --input ir.json --format all --output ./out/

# 仅特定包
cim-ontology emit --input ir.json --format owl --packages Core,Wires

# 包含 roundtrip 验证
cim-ontology emit --input ir.json --format all --verify
```

---

## 7. 错误处理策略

### 7.1 错误分类法

按**严重性 + 可恢复性**两维划分：

| 级别 | 类别 | 处理方式 | 示例 |
|------|------|----------|------|
| **FATAL** | 输入不可读 | 立即退出 | 标准文件不存在/损坏 |
| **ERROR** | 单包解析失败 | 跳过该包，继续 | Wires 包章节缺失 |
| **WARN** | 单条记录可疑 | 标记不确定，继续 | 类名 OCR 错误 |
| **INFO** | 进度/统计 | 记录到日志 | 已抽取 200/750 表 |

```python
class Severity(Enum):
    FATAL = "fatal"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


@dataclass
class PipelineError(Exception):
    severity: Severity
    stage: str                # "ingest" | "validate" | "emit" | "verify"
    location: str             # "table 150续::row3" / "package Wires"
    raw_input: str | None     # 触发错误的原始内容
    message: str
    suggestion: str | None    # 修复建议

    def __str__(self):
        loc = f"[{self.location}] " if self.location else ""
        sug = f"\n  建议: {self.suggestion}" if self.suggestion else ""
        return f"{self.severity.value.upper()}: {loc}{self.message}{sug}"
```

### 7.2 分阶段错误处理

#### Stage 1（清洗）

```python
def clean_markdown_to_ir(self, md_path: Path) -> OntologyIR:
    try:
        content = md_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PipelineError(
            severity=Severity.FATAL,
            stage="ingest",
            location=str(md_path),
            message="CIM 标准文件不存在",
            suggestion="检查 docs/GBT43259301—2024/ 目录"
        )
    except UnicodeDecodeError as e:
        raise PipelineError(
            severity=Severity.FATAL,
            stage="ingest",
            message=f"文件编码错误: {e}",
            suggestion="尝试 iconv -f GB18030 -t UTF-8 转换"
        )

    packages = []
    for pkg_section in self._iter_package_sections(content):
        try:
            pkg = self._parse_package(pkg_section)
            packages.append(pkg)
        except SectionParseError as e:
            log.warn(f"跳过包 {pkg_section.name}: {e}")
            self._error_registry.add(e)

    return OntologyIR(packages=packages)
```

#### Stage 2（LLM 复审）

详见 §5.5 的三层熔断：
- **JSON 解析失败** → 用规则结果（`fallback: log_and_skip`）
- **业务校验失败** → 用规则结果 + 标记 `llm_rejected`
- **网络/超时** → 重试 3 次（指数退避）→ 降级

```python
class LLMReviewer:
    def _call_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                return self._provider.review(prompt)
            except (TimeoutError, RateLimitError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt + random.uniform(0, 1)
                log.warn(f"LLM 调用失败，{wait:.1f}s 后重试: {e}")
                time.sleep(wait)
```

#### Stage 3（Emit）

```python
def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    errors = []
    for fmt, adapter in ADAPTERS.items():
        try:
            adapter.emit(ir, output_dir / fmt)
        except AdapterError as e:
            errors.append(e)
            log.error(f"格式 {fmt} 生成失败: {e}")

    if errors:
        raise PipelineError(
            severity=Severity.ERROR,
            stage="emit",
            message=f"{len(errors)}/{len(ADAPTERS)} 格式生成失败",
            suggestion="查看 audit/emit_errors.log"
        )

    return EmitResult(...)
```

#### Stage 4（Verify）

**软失败策略**：verify 失败不中断，但强制要求确认才能进入发布流程。

```python
def verify(self, ir: OntologyIR, output_dir: Path) -> VerifyResult:
    issues = []
    for fmt, adapter in ADAPTERS.items():
        result = adapter.verify(ir, output_dir / fmt)
        issues.extend(result.issues)

    if issues:
        self._report.write(issues)
        log.warn(f"验证发现 {len(issues)} 处问题，详见 report.md")

    return VerifyResult(passed=len(issues) == 0, issues=issues)
```

### 7.3 用户友好的错误信息

```python
ERROR_TEMPLATES = {
    "table_not_found": """
        在第 {chapter} 章找不到属性表，表号 {table_no}

        可能原因:
          1. 章节顺序与标准不符（请确认 PDF 章节完整性）
          2. OCR 漏字导致表号识别错误
          3. 该表确实不在标准中（极少见）

        建议:
          - 使用 --debug-tables 查看所有识别到的表头
          - 检查 raw/{table_no}.md 是否存在
    """,
    "namespace_typo": """
        识别到未注册命名空间: '{namespace}'

        最相似的已注册命名空间:
          {suggestions}

        是否:
          1. 确认是 OCR 错误，自动修正？
          2. 手动指定正确命名空间？
          3. 跳过该条目？
    """,
}
```

### 7.4 错误清单与人工审阅

**集中错误日志** `audit/errors.jsonl`：

```jsonl
{"ts":"2026-06-22T10:30:00Z","stage":"ingest","severity":"warn",
 "location":"Wires::table_150续::row3",
 "type":"class_name_typo","message":"Meastrement",
 "raw":"Meastrement","corrected":"Measurement",
 "auto_fixed":true}
{"ts":"2026-06-22T10:30:01Z","stage":"emit","severity":"error",
 "location":"shacl","type":"adapter_failure",
 "message":"BNode serialization failed"}
```

**审阅命令**：

```bash
# 查看所有警告
cim-ontology audit show --severity warn --since 2026-06-20

# 按类型统计
cim-ontology audit stats --by type

# 导出未处理的错误（需人工决策）
cim-ontology audit pending --format csv > pending.csv
```

### 7.5 日志与可观测性

**结构化日志**（structlog）：

```python
import structlog
log = structlog.get_logger()

log.info("stage_start", stage="ingest", input=str(md_path))
log.info("stage_end", stage="ingest",
         duration_ms=1234, packages=27, classes=234, warnings=5)
log.warning("ocr_correction_applied",
            raw="Meastrement", corrected="Measurement",
            confidence=0.98)
log.error("adapter_failed", adapter="shacl", error=str(e))
```

**日志输出**：
- 控制台：INFO 级别，人可读
- 文件 `audit/run.log`：DEBUG 级别，结构化 JSON

### 7.6 故障注入测试

```python
# tests/test_error_paths.py
def test_corrupted_md_raises_fatal():
    with pytest.raises(PipelineError) as exc_info:
        pipeline.process(Path("fixtures/corrupted.md"))
    assert exc_info.value.severity == Severity.FATAL


def test_llm_timeout_falls_back_to_rule():
    reviewer = LLMReviewer(provider=MockProvider(timeout=True),
                          validator=MockValidator(),
                          audit_log=MockAudit())
    result = reviewer.review(stub_trigger)
    assert result.source == "rule_fallback"


def test_partial_package_failure_continues():
    ir = pipeline.process(Path("fixtures/partial.md"))
    assert "Core" in [p.name for p in ir.packages]
    assert "Wires" not in [p.name for p in ir.packages]
```

---

## 8. 测试策略

### 8.1 测试金字塔

| 层级 | 数量 | 时长 | 工具 |
|------|------|------|------|
| **单元测试** | 200+ | <30s | `pytest` |
| **集成测试** | 50+ | <2min | `pytest` + 真实 fixture |
| **端到端测试** | 10+ | <5min | `pytest` + 完整 9243 行 Markdown |
| **回归测试** | 5 | <10min | `cim-ontology diff` vs IEC 官方本体 |
| **属性测试** | 20+ | <1min | `hypothesis` |

### 8.2 单元测试（Stage 1 规则清洗器）

```python
# tests/unit/test_cleaner.py
class TestMultiplicityCleaning:
    @pytest.mark.parametrize("raw,expected", [
        ("0..1", "0..1"),
        (" 0..1 ", "0..1"),
        ("0..*", "0..*"),
        ("many", "0..*"),            # 语义归一
        ("0..n", "0..*"),
        ("1..*", "1..*"),
        ("1..1", "1..1"),
    ])
    def test_clean_multiplicity(self, raw, expected):
        assert clean_multiplicity(raw) == expected


class TestNamespaceCleaning:
    @pytest.mark.parametrize("raw,expected", [
        ("cim:", "http://iec.ch/TC57/2024/CIM-schema-cim17#"),
        ("eu:", "http://iec.ch/TC57/NonStandard/UML#"),  # 扩展包
        ("rdfs:", "http://www.w3.org/2000/01/rdf-schema#"),
        ("rdf:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ])
    def test_clean_namespace(self, raw, expected):
        assert clean_namespace(raw) == expected


class TestClassNameCleaning:
    @pytest.mark.parametrize("raw,expected,reason", [
        ("Meastrement", "Measurement", "OCR: e→a, n→rn"),
        ("Rep0rtingGroup", "ReportingGroup", "OCR: 0→o"),
        ("AuxiliarEuiment", "AuxiliaryEquipment", "OCR: y→Eu, p→m"),
        ("DiaramLaout", "DiagramLayout", "OCR: g→a"),
    ])
    def test_known_corrections(self, raw, expected, reason):
        result = clean_class_name(raw, known_classes=REGISTRY)
        assert result.value == expected
        assert result.correction_applied
        assert reason in result.notes
```

### 8.3 集成测试

**Fixture 策略**：从 9243 行完整文档中**切片**为多个代表性样本：

```
tests/fixtures/
├── tiny/
│   └── sample.md           # 50 行，只含 1 个类
├── small/
│   └── Core.md             # 500 行，含 Core 包完整章节
├── medium/
│   └── Core_Wires.md       # 1500 行，两个包
├── large/
│   └── full.md             # 9243 行，完整文档（端到端用）
└── dirty/
    └── with_ocr_errors.md  # 注入已知 OCR 错误的样本
```

```python
# tests/integration/test_pipeline.py
class TestIngestPipeline:
    def test_core_package_full_extraction(self, tmp_path):
        md = FIXTURES / "small/Core.md"
        ir = pipeline.ingest(md)
        assert len(ir.packages) == 1
        assert ir.packages[0].name == "Core"

        names = {c.name for c in ir.classes}
        assert "IdentifiedObject" in names
        assert "Measurement" in names
        assert "PowerSystemResource" in names

        measurement = ir.get_class("Measurement")
        attrs = {a.name for a in measurement.attributes}
        assert "measurementType" in attrs
        assert "PowerSystemResource" in attrs

    def test_ocr_error_correction(self):
        md = FIXTURES / "dirty/with_ocr_errors.md"
        ir = pipeline.ingest(md)
        assert "Measurement" in {c.name for c in ir.classes}
        assert "ReportingGroup" in {c.name for c in ir.classes}

    def test_unknown_class_flagged_for_llm(self):
        md = FIXTURES / "dirty/unknown_class.md"
        ir = pipeline.ingest(md)
        uncertain = ir.get_uncertain_entries()
        assert len(uncertain) >= 1
        assert any(e.uncertainty_reason == "class_name_typo"
                   for e in uncertain)
```

### 8.4 端到端测试

```python
# tests/e2e/test_full_build.py
class TestFullBuild:
    """完整流程：Markdown → IR → OWL+SHACL+JSON-LD → 验证"""

    def test_full_document_builds_to_all_formats(self, tmp_path):
        md = DOCS / "GBT43259301—2024/cim-base-full.md"
        out = tmp_path / "build"

        result = pipeline.build(md, out, formats=["owl", "shacl", "jsonld"])

        assert (out / "owl").exists()
        assert (out / "shacl").exists()
        assert (out / "jsonld").exists()
        assert len(result.ir.packages) == 27

        for pkg in result.ir.packages:
            assert len(pkg.classes) >= 1

        g = rdflib.Graph()
        g.parse(out / "owl/cim17_full.ttl", format="turtle")
        assert len(g) > 5000

    def test_roundtrip_preserves_class_count(self, tmp_path):
        md = DOCS / "GBT43259301—2024/cim-base-full.md"
        out = tmp_path / "build"

        pipeline.build(md, out)
        ir_reparsed = pipeline.parse_output(out)
        assert ir_reparsed.class_count == result.ir.class_count
        assert ir_reparsed.attribute_count == result.ir.attribute_count
```

### 8.5 属性测试（IR 不变量）

```python
# tests/property/test_ir_invariants.py
from hypothesis import given, strategies as st

@given(st.lists(st.sampled_from(ALL_KNOWN_CLASSES), min_size=10, max_size=200))
def test_class_referential_integrity(class_names):
    ir = build_ir_with_classes(class_names)
    for cls in ir.classes:
        for assoc in cls.associations:
            if assoc.target_class not in {c.name for c in ir.classes}:
                if not assoc.is_external_reference:
                    pytest.fail(f"关联目标 {assoc.target_class} 不存在")


@given(st.lists(st.sampled_from(PACKAGES), min_size=1, max_size=27))
def test_no_duplicate_class_names(packages):
    ir = build_ir_with_packages(packages)
    for pkg in ir.packages:
        names = [c.name for c in pkg.classes]
        assert len(names) == len(set(names))


@given(st.integers(min_value=0, max_value=999))
def test_table_id_parsing_idempotent(table_id):
    parsed1 = parse_table_id(f"表 {table_id}")
    parsed2 = parse_table_id(f"表{table_id}")
    parsed3 = parse_table_id(f"表 {table_id} ")
    assert parsed1 == parsed2 == parsed3
```

### 8.6 Snapshot 测试

```python
# tests/snapshot/test_outputs.py
class TestOutputSnapshots:
    """确保输出不会意外变化（防止 LLM/规则修改破坏兼容）"""

    def test_owl_output_stable(self, snapshot):
        ir = load_fixture_ir("small/Core.json")
        adapter = OwlTurtleAdapter()
        adapter.emit(ir, Path("/dev/null"))

        output = adapter.serialize_string(ir, format="turtle")
        normalized = _normalize_output(output)

        assert normalized == snapshot

    def test_shacl_output_stable(self, snapshot):
        ...
```

### 8.7 LLM Mock 测试

```python
# tests/unit/test_llm_reviewer.py
class MockProvider(LLMProvider):
    """确定性 mock，无网络依赖"""
    def __init__(self, fixtures_dir):
        self._fixtures = fixtures_dir

    def review(self, prompt: ReviewPrompt) -> str:
        for fixture in self._fixtures.glob("*.json"):
            if fixture.stem in prompt.raw_text:
                return fixture.read_text()
        return self._fixtures / "default.json"


def test_llm_review_overrides_rule_when_confident():
    reviewer = LLMReviewer(
        provider=MockProvider(FIXTURES / "llm"),
        validator=StrictValidator(),
        audit_log=InMemoryAudit()
    )

    trigger = LLMReviewTrigger(
        case_id="test_1",
        raw_text="Meastrement",
        rule_attempt={"class_name": "Measurement"},
        uncertainty_reason="class_name_typo"
    )

    result = reviewer.review(trigger)
    assert result.confidence > 0.7
    assert result.source.startswith("llm_")


def test_llm_review_falls_back_on_invalid_json():
    provider = MockProvider.with_response("{invalid json")
    reviewer = LLMReviewer(provider=provider, ...)

    result = reviewer.review(stub_trigger)
    assert result.source == "rule_fallback"
```

### 8.8 回归测试（与 IEC 官方本体对比）

```python
# tests/regression/test_vs_official.py
"""核心保证：生成的 OWL 与 IEC 61970-301 官方本体在关键类上一致"""

IEC_OFFICIAL = Path("/path/to/IEC61970-301-cim17.owl")


class TestParityWithIEC:
    def test_core_class_count_matches(self):
        ours = pipeline.ingest(DOCS / "cim-base-full.md")
        official = rdflib.Graph()
        official.parse(IEC_OFFICIAL, format="xml")

        official_classes = {
            str(o).split("#")[-1]
            for o in official.subjects(RDF.type, OWL.Class)
            if "CIM-schema-cim17" in str(o)
        }

        ours_classes = {c.name for c in ours.classes}
        missing = official_classes - ours_classes
        assert len(missing) / len(official_classes) < 0.05

    def test_measurement_inheritance_matches(self):
        ours = pipeline.ingest(DOCS / "cim-base-full.md")
        measurement = ours.get_class("Measurement")

        assert "IdentifiedObject" in [b.name for b in measurement.parents]
```

### 8.9 CI 集成

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  unit-and-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit tests/integration -v --tb=short
      - run: pytest tests/property -v --tb=short
      - run: ruff check src tests
      - run: mypy src

  e2e:
    runs-on: ubuntu-latest
    needs: unit-and-integration
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"

      # 恢复 LLM 缓存（避免每次 PR 都调用真实 API）
      - uses: actions/cache@v4
        with:
          path: .cache/llm_reviews.db
          key: llm-cache-${{ hashFiles('src/cim_ontology/reviewer/prompts.py') }}
          restore-keys: |
            llm-cache-

      # CI 环境强制 MockProvider（即使有 API key 也不调用）
      - name: E2E build (mock LLM)
        run: cim-ontology build --llm mock --output ./build/

      - run: pytest tests/e2e -v --tb=short
      - uses: actions/upload-artifact@v4
        with:
          name: build-output
          path: build/

      # 持久化缓存（下次 build 复用）
      - uses: actions/cache/save@v4
        with:
          path: .cache/llm_reviews.db
          key: llm-cache-${{ hashFiles('src/cim_ontology/reviewer/prompts.py') }}

  regression:
    runs-on: ubuntu-latest
    needs: e2e
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: |
          # 仅 master 分支跑回归（避免 PR 误报）
          if [ "${{ github.ref }}" = "refs/heads/master" ]; then
            pytest tests/regression -v
          fi
```

#### CI 中 LLM provider 的强制 Mock 策略

```python
# src/cim_ontology/reviewer/providers.py
import os

def get_provider(config: LLMConfig) -> LLMProvider:
    """Provider 工厂"""
    # CI 环境检测：强制 Mock（即使配置了 Claude）
    if os.environ.get("CI") == "true":
        log.info("CI 环境检测到，使用 MockProvider")
        return MockProvider(fixtures_dir=FIXTURES / "llm")

    # 本地有 ANTHROPIC_API_KEY → Claude
    if config.provider == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeProvider(...)

    # 离线 → Ollama
    if config.provider == "ollama":
        return OllamaProvider(...)

    # 兜底
    return MockProvider(...)
```

### 8.10 覆盖率目标

| 模块 | 目标 | 关键不变量 |
|------|------|----------|
| `cleaner.py` | **95%** | 所有清洗规则都被测试 |
| `llm_reviewer.py` | **90%** | 三层熔断路径全覆盖 |
| `adapters/*.py` | **85%** | 每格式至少 10 个集成测试 |
| `pipeline.py` | **80%** | 主流程有 e2e 测试 |
| 总体 | **85%+** | 排除类型提示/抽象方法 |

---

## 9. 项目结构

```
grid-ontology/
├── pyproject.toml
├── README.md
├── DESIGN.md                          # 设计系统（本项目不适用）
├── docs/
│   ├── GBT43259301—2024/              # 标准文档
│   │   └── cim-base-full.md           # 9243 行拼接后的完整文档
│   └── superpowers/
│       └── specs/
│           └── 2026-06-22-grid-ontology-design.md
├── src/
│   └── cim_ontology/
│       ├── __init__.py
│       ├── cli.py                     # typer CLI 入口
│       ├── pipeline.py                # 4 阶段编排
│       ├── ir/
│       │   ├── __init__.py
│       │   ├── models.py              # Pydantic 数据模型
│       │   └── registry.py            # 类/命名空间注册表
│       ├── cleaner/                   # Stage 1
│       │   ├── __init__.py
│       │   ├── markdown_parser.py
│       │   ├── table_extractor.py
│       │   ├── text_normalizer.py
│       │   └── section_parser.py
│       ├── reviewer/                  # Stage 2
│       │   ├── __init__.py
│       │   ├── llm_reviewer.py
│       │   ├── providers.py
│       │   └── prompts.py
│       ├── adapters/                  # Stage 3
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── owl.py
│       │   ├── shacl.py
│       │   └── jsonld.py
│       └── audit/                     # 错误处理 + 审计
│           ├── __init__.py
│           ├── errors.py
│           └── logger.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── property/
│   ├── snapshot/
│   ├── regression/
│   └── fixtures/
│       ├── tiny/
│       ├── small/
│       ├── medium/
│       ├── large/
│       └── dirty/
└── audit/                             # 运行时审计输出（gitignore）
    ├── errors.jsonl
    ├── llm_reviews.jsonl
    └── run.log
```

---

## 10. 实施路线图

### 阶段 1（M1）：骨架与数据模型（1 周）

- 项目结构搭建（pyproject.toml + 模块骨架）
- Pydantic 数据模型（§3）实现
- 单测：模型序列化/反序列化

### 阶段 2（M2）：Stage 1 规则清洗器（2 周）

- `markdown-it-py` + `BeautifulSoup` 解析器
- 清洗规则（多重性、命名空间、类名）
- 章节解析与表格分类
- 单测 + 集成测试（tiny/small fixtures）

### 阶段 3（M3）：LLM 复审（1.5 周）

- Provider 适配层（Claude/Ollama/Mock）
- Prompt 模板与三熔断
- 审计追踪
- Mock provider 测试

### 阶段 4（M4）：输出适配器（2 周）

- OWL/Turtle 适配器（按包拆分）
- SHACL 适配器
- JSON-LD 三件套（context + schema + Python types）
- Roundtrip 校验

### 阶段 5（M5）：端到端 + 回归（1.5 周）

- Pipeline 编排与 CLI 入口
- 完整 9243 行端到端测试
- IEC 官方本体回归对比
- CI/CD 配置

**总计**：约 8 周（1 人全职）

---

## 11. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| OCR 错字过多导致抽取质量低 | 高 | 高 | 规则 + LLM 双重校验，审计追踪 |
| IEC 官方本体获取困难 | 中 | 中 | 优先使用 IEC 61970-301:2020 标准附录 C 中的 UML 图 |
| LLM 调用成本超预算 | 中 | 中 | SQLite 缓存 + 批处理 + 早停 + token 上限 |
| PDF→Markdown 拼接可能漏章节 | 低 | 高 | e2e 测试验证 27 包齐全 + 章节完整性断言 |
| 标准后续修订需重新抽取 | 中 | 中 | 流水线化 + SHA256 来源追踪 + 增量更新 |
| rdflib 处理 5000+ 三元组性能 | 低 | 中 | 按包拆分 + 流式序列化 + 性能基准测试 |

---

## 12. 验收标准

实施完成需满足：

1. **功能**：
   - `cim-ontology build` 一条命令从 `cim-base-full.md` 生成 `output/{owl,shacl,jsonld}/`
   - 27 个包全部抽取成功
   - 至少 95% 的类与 IEC 官方本体类名匹配

2. **质量**：
   - 单元测试覆盖率 ≥ 85%
   - 所有 Stage 1 清洗规则有参数化测试
   - 三层 LLM 熔断路径全部有故障注入测试

3. **可观测性**：
   - `audit/errors.jsonl` 包含每次错误的完整上下文
   - `audit/llm_reviews.jsonl` 包含每次 LLM 修订的可追溯记录
   - `cim-ontology audit review` 提供人工审阅界面

4. **可扩展性**：
   - 新增输出格式（如 SKOS）只需实现 `OutputAdapter` 接口并在 `ADAPTERS` 注册
   - 新增 LLM provider 只需实现 `LLMProvider` 接口

5. **可复现**：
   - 同一份 `cim-base-full.md` 输入产生字节级一致的输出（除时间戳）
   - `--verify` 强制 roundtrip 校验通过才能发布

---

## 附录 A：术语表

| 术语 | 含义 |
|------|------|
| **CIM** | Common Information Model，IEC 61970-301 定义的电力系统公共信息模型 |
| **IDT** | Identical，等同采用（GB/T 对应 IEC 标准的等同采用方式）|
| **OWL** | Web Ontology Language，W3C 本体语言标准 |
| **SHACL** | Shapes Constraint Language，W3C 数据约束语言 |
| **JSON-LD** | JSON for Linking Data，JSON 的语义扩展 |
| **Turtle** | Terse RDF Triple Language，简洁的 RDF 序列化格式 |
| **IR-JSON** | Intermediate Representation - JSON，阶段间统一中间表示 |
| **Pipeline-Stage** | 流水线-阶段架构，将处理分为串行阶段 |

## 附录 B：参考资源

- **标准原文**：`docs/GBT43259301—2024/cim-base-full.md`
- **IEC 官方本体**：[CIM Users Group](https://www.cimug.org/) 发布的 `IEC61970-301-cim17.owl`
- **rdflib 文档**：https://rdflib.readthedocs.io/
- **SHACL 规范**：https://www.w3.org/TR/shacl/
- **JSON-LD 规范**：https://www.w3.org/TR/json-ld11/
- **GB/T 43259.301—2024**：国家市场监督管理总局发布

## 附录 C：决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-06-22 | 选 Python CLI + 库 | 用户明确要求 |
| 2026-06-22 | 选 Pipeline-Stage 架构 | 4 阶段清晰边界，便于测试与替换 |
| 2026-06-22 | 规则 + LLM 混合处理 | 95% 规则覆盖 + 5% LLM 仲裁，平衡成本与质量 |
| 2026-06-22 | 覆盖全部 27 包 | 用户明确要求完整覆盖 |
| 2026-06-22 | 多输出格式并行 | 4 类用户不同需求 |
| 2026-06-22 | IR-JSON 作为唯一中间表示 | 解耦阶段间依赖，便于序列化与调试 |
| 2026-06-22 | LLM 三层熔断 | 防止 LLM 错误污染 IR |
| 2026-06-22 | 审计追踪 + 人工审阅入口 | 任何修订可回溯、可拒绝 |
| 2026-06-22 | `duration_ms` 剥离 IR | 同一 IR 在不同机器耗时不同，保留会破坏哈希幂等性 |
| 2026-06-22 | CIM→XSD 显式类型映射表 | 保证 OWL/SHACL 在不同工具（Protégé、TopBraid、Java）语义一致 |
| 2026-06-22 | 解析器模糊匹配 + 层级推断 | OCR 异常时 `##` 标记可能丢失，需降级匹配策略 |
| 2026-06-22 | 本地 LLM 用通用指令模型（Qwen2.5-72B-Instruct），非 Coder 系列 | OCR 纠错是语义推理任务，不是代码生成 |
| 2026-06-22 | OWL 按包拆分 + `owl:imports` | Protégé 单独打开子包时类继承仍可解析 |
| 2026-06-22 | Python types 拓扑排序生成 | 避免 Wires→Core 循环 import 错误 |
| 2026-06-22 | CI 强制 MockProvider + actions/cache 持久化 LLM 缓存 | 避免每次 PR 触发昂贵 API 调用 |

---

**文档结束**
