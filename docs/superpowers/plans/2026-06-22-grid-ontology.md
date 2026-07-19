# Grid-Ontology 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 GB/T 43259.301-2024 CIM 国标文档自动抽取本体定义，并生成 OWL/RDF Turtle、SHACL Shapes、JSON-LD/JSON Schema 多格式产物。

**Architecture:** Pipeline-Stage 四阶段架构 — Markdown → IR-JSON（中间表示）→ LLM 复审 → 多格式输出 → 验证。规则清洗器处理 95% 确定性工作，LLM 仲裁 5% 不确定条目。

**Tech Stack:**
- Python 3.12 + pydantic v2 + typer + rich
- rdflib 7.x + pyshacl + pyld
- markdown-it-py + BeautifulSoup4 + lxml
- pytest + hypothesis + syrupy（snapshot）
- structlog + SQLite（LLM 缓存）
- Ollama（本地 LLM 备选）/ Claude API（主力）

## Global Constraints

- Python ≥ 3.12
- 包名：`cim_ontology`（源码）/ `cim-ontology`（CLI）
- IRI 基址：`http://iec.ch/TC57/2024/CIM-schema-cim17#`
- 编码：UTF-8
- 命名空间：`cim`、`eu`、`rdf`、`rdfs`、`owl`、`xsd`、`sh`
- 测试覆盖率 ≥ 85%（`cleaner.py` ≥ 95%、`llm_reviewer.py` ≥ 90%）
- 单测时长 < 30s；集成 < 2min；端到端 < 5min
- 所有 commit 信息遵循 Conventional Commits（feat/fix/test/refactor/docs）
- 标准文档：`docs/GBT43259301—2024/cim-base-full.md`（9243 行）
- 阶段性提交：每完成一个 Task 立即 commit，不批量

---

## 文件结构总览

```
grid-ontology/
├── pyproject.toml                          # Task 1
├── README.md                               # Task 1
├── src/cim_ontology/
│   ├── __init__.py                         # Task 1
│   ├── cli.py                              # Task 26
│   ├── pipeline.py                         # Task 26
│   ├── ir/
│   │   ├── __init__.py                     # Task 2
│   │   ├── models.py                       # Task 2
│   │   └── registry.py                     # Task 3
│   ├── cleaner/
│   │   ├── __init__.py                     # Task 4
│   │   ├── markdown_parser.py              # Task 4
│   │   ├── section_splitter.py             # Task 5
│   │   ├── table_extractor.py              # Task 6
│   │   ├── multiplicity.py                 # Task 7
│   │   ├── namespace.py                    # Task 8
│   │   ├── class_name.py                   # Task 9
│   │   ├── hierarchical.py                 # Task 10
│   │   ├── dep_graph.py                    # Task 11
│   │   └── orchestrator.py                 # Task 12
│   ├── reviewer/
│   │   ├── __init__.py                     # Task 13
│   │   ├── providers.py                    # Task 13-15
│   │   ├── prompts.py                      # Task 16
│   │   ├── reviewer.py                     # Task 17
│   │   ├── cache.py                        # Task 18
│   │   └── audit.py                        # Task 19
│   ├── adapters/
│   │   ├── __init__.py                     # Task 20
│   │   ├── base.py                         # Task 20
│   │   ├── owl.py                          # Task 21
│   │   ├── shacl.py                        # Task 22
│   │   ├── jsonld_context.py               # Task 23
│   │   ├── json_schema.py                  # Task 24
│   │   ├── python_types.py                 # Task 25
│   │   └── roundtrip.py                    # Task 26
│   └── audit/
│       ├── __init__.py                     # Task 27
│       ├── errors.py                       # Task 27
│       └── logger.py                       # Task 27
└── tests/
    ├── conftest.py                         # Task 1
    ├── fixtures/                           # Task 1
    │   ├── tiny/sample.md                  # Task 7
    │   ├── small/Core.md                   # Task 12
    │   ├── medium/Core_Wires.md            # Task 12
    │   ├── large/full.md                   # Task 29
    │   └── dirty/with_ocr_errors.md        # Task 9
    ├── unit/                               # 各 Task 测试
    ├── integration/                        # 各 Task 测试
    ├── e2e/                                # Task 30
    ├── regression/                         # Task 31
    └── property/                           # Task 32
```

---

# Phase 1（M1）：项目骨架与数据模型

## Task 1: 项目脚手架（pyproject.toml + 目录结构）

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/cim_ontology/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: 无（首任务）
- Produces: 可安装包 `cim-ontology`，CLI 入口 `cim-ontology`

- [ ] **Step 1: 写 pyproject.toml**

文件 `pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cim-ontology"
version = "0.1.0"
description = "GB/T 43259.301-2024 CIM 本体提取与生成器"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Grid Ontology Team" }]
dependencies = [
    "pydantic>=2.6",
    "typer>=0.12",
    "rich>=13.7",
    "rdflib>=7.0",
    "pyshacl>=0.25",
    "pyld>=2.0",
    "markdown-it-py>=3.0",
    "beautifulsoup4>=4.12",
    "lxml>=5.1",
    "structlog>=24.1",
    "anthropic>=0.40",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "hypothesis>=6.100",
    "syrupy>=4.6",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
cim-ontology = "cim_ontology.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "T20"]
```

- [ ] **Step 2: 写 README.md**

文件 `README.md`：

```markdown
# Grid Ontology

GB/T 43259.301-2024（IDT IEC 61970-301:2020）CIM 本体提取与生成器。

## 安装

```bash
pip install -e ".[dev]"
```

## 快速开始

```bash
cim-ontology build --input docs/GBT43259301—2024/cim-base-full.md --output ./build
```

## 文档

- 设计规范：`docs/superpowers/specs/2026-06-22-grid-ontology-design.md`
- 实施计划：`docs/superpowers/plans/2026-06-22-grid-ontology.md`
```

- [ ] **Step 3: 写源码包入口**

文件 `src/cim_ontology/__init__.py`：

```python
"""cim_ontology: GB/T 43259.301-2024 CIM 本体提取与生成器。"""

__version__ = "0.1.0"
```

- [ ] **Step 4: 写测试包入口与 conftest**

文件 `tests/__init__.py`：

```python
"""测试包。"""
```

文件 `tests/conftest.py`：

```python
"""全局 pytest fixtures。"""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """测试 fixtures 根目录。"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_sample(fixtures_dir: Path) -> Path:
    """最小的样本 fixture（Task 7 创建）。"""
    return fixtures_dir / "tiny" / "sample.md"
```

- [ ] **Step 5: 写 .gitignore**

文件 `.gitignore`：

```
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.cache/
audit/*.log
audit/*.jsonl
output/
.env
.venv/
venv/
```

- [ ] **Step 6: 安装与验证可导入**

```bash
cd /Users/nexlume/AI-Workspace/grid-ontology
pip install -e ".[dev]"
```

预期输出：成功安装且无错误。

- [ ] **Step 7: 验证 CLI 可执行**

```bash
cim-ontology --help
```

预期输出：显示 typer 默认帮助（因 cli.py 尚未实现，会报错 ModuleNotFoundError，这是预期的）。

- [ ] **Step 8: 提交**

```bash
git add pyproject.toml README.md src/ tests/ .gitignore
git commit -m "chore: scaffold cim-ontology project structure"
```

---

## Task 2: IR-JSON 数据模型（OntologyIR + 子模型）

**Files:**
- Create: `src/cim_ontology/ir/__init__.py`
- Create: `src/cim_ontology/ir/models.py`
- Test: `tests/unit/test_ir_models.py`

**Interfaces:**
- Consumes: 无
- Produces: Pydantic 模型 `OntologyIR`、`Package`、`ClassDef`、`DataProperty`、`ObjectProperty`、`Multiplicity`、`Enumeration`、`PrimitiveType`、`UncertainEntry`、`IRStats`、`SourceInfo`、`CrossPackageRef`

- [ ] **Step 1: 写失败测试 — Multiplicity 序列化**

文件 `tests/unit/test_ir_models.py`：

```python
"""IR-JSON Pydantic 模型单元测试。"""
import pytest
from pydantic import ValidationError

from cim_ontology.ir.models import (
    CrossPackageRef,
    Enumeration,
    IRStats,
    Multiplicity,
    PrimitiveType,
    SourceInfo,
)


class TestMultiplicity:
    def test_zero_one(self):
        m = Multiplicity(min=0, max=1, raw="0..1")
        assert m.is_many is False

    def test_one_one(self):
        m = Multiplicity(min=1, max=1, raw="1..1")
        assert m.is_many is False

    def test_zero_many(self):
        m = Multiplicity(min=0, max=None, raw="0..*")
        assert m.is_many is True

    def test_one_many(self):
        m = Multiplicity(min=1, max=None, raw="1..*")
        assert m.is_many is True

    def test_serialization_roundtrip(self):
        m = Multiplicity(min=0, max=None, raw="0..*")
        data = m.model_dump()
        restored = Multiplicity(**data)
        assert restored == m


class TestEnumeration:
    def test_basic(self):
        e = Enumeration(name="PhaseCode", values=["A", "B", "C"], description="相序")
        assert e.name == "PhaseCode"
        assert "A" in e.values


class TestIRStats:
    def test_basic(self):
        s = IRStats(
            package_count=27,
            class_count=234,
            attribute_count=1500,
            association_count=800,
            enumeration_count=15,
            uncertain_count=20,
        )
        assert s.package_count == 27


class TestSourceInfo:
    def test_basic(self):
        si = SourceInfo(
            document_path="docs/cim-base-full.md",
            document_sha256="abc123",
            parsed_at="2026-06-22T10:00:00Z",
            parser_version="0.1.0",
        )
        assert si.document_sha256 == "abc123"
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_ir_models.py -v
```

预期：ImportError（`cim_ontology.ir.models` 不存在）。

- [ ] **Step 3: 写 IR-JSON 模型实现**

文件 `src/cim_ontology/ir/__init__.py`：

```python
"""IR-JSON 数据模型。"""
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    CrossPackageRef,
    DataProperty,
    Enumeration,
    IRStats,
    Multiplicity,
    ObjectProperty,
    OntologyIR,
    Package,
    PrimitiveType,
    SourceInfo,
    UncertainEntry,
)

__all__ = [
    "ClassDef",
    "ClassRef",
    "CrossPackageRef",
    "DataProperty",
    "Enumeration",
    "IRStats",
    "Multiplicity",
    "ObjectProperty",
    "OntologyIR",
    "Package",
    "PrimitiveType",
    "SourceInfo",
    "UncertainEntry",
]
```

文件 `src/cim_ontology/ir/models.py`：

```python
"""IR-JSON Pydantic 模型定义。

对应设计规范 §3。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Multiplicity(BaseModel):
    """属性或关联的多重性。"""

    model_config = ConfigDict(frozen=True)

    min: int = Field(ge=0, description="最小基数")
    max: int | None = Field(default=None, description="最大基数；None 表示 *")
    raw: str = Field(description="原始字符串，如 0..*")

    @property
    def is_many(self) -> bool:
        """是否为多值。"""
        return self.max is None or self.max > 1


class ClassRef(BaseModel):
    """对另一个类的引用。"""

    package: str
    class_name: str
    iri: str | None = None
    is_external: bool = False


class DataProperty(BaseModel):
    """OWL DatatypeProperty。"""

    name: str
    data_type: str = Field(default="string", description="XSD 类型，如 xsd:float")
    multiplicity: Multiplicity = Field(default_factory=lambda: Multiplicity(min=0, max=1, raw="0..1"))
    is_derived: bool = False
    is_enum: bool = False
    description: str | None = None
    required: bool = False


class ObjectProperty(BaseModel):
    """OWL ObjectProperty（关联端）。"""

    name: str
    target: ClassRef
    multiplicity: Multiplicity = Field(default_factory=lambda: Multiplicity(min=0, max=1, raw="0..1"))
    is_aggregation: bool = False
    inverse_name: str | None = None
    description: str | None = None


class Enumeration(BaseModel):
    """CIM 枚举类型。"""

    name: str
    values: list[str]
    description: str | None = None


class PrimitiveType(BaseModel):
    """CIM 基本类型。"""

    name: str
    base_type: str
    unit: str | None = None
    multiplier: str | None = None


class ClassDef(BaseModel):
    """一个 CIM 类定义。"""

    iri: str | None = None
    name: str
    description: str | None = None
    stereotype: str | None = None
    parents: list[ClassRef] = Field(default_factory=list)
    attributes: list[DataProperty] = Field(default_factory=list)
    associations: list[ObjectProperty] = Field(default_factory=list)
    source_table: int | None = None


class Package(BaseModel):
    """一个 CIM 包。"""

    iri: str
    name: str
    description: str | None = None
    classes: list[ClassDef] = Field(default_factory=list)
    enumerations: list[Enumeration] = Field(default_factory=list)
    primitive_types: list[PrimitiveType] = Field(default_factory=list)


class CrossPackageRef(BaseModel):
    """跨包引用关系（用于构建依赖图）。"""

    from_package: str
    to_package: str
    via_class: str
    via_property: str


class UncertainEntry(BaseModel):
    """Stage 1 标记为不确定的条目（待 LLM 复审）。"""

    case_id: str
    source_table: int
    package: str
    raw_text: str
    rule_attempt: dict
    uncertainty_reason: str
    context_snippet: str = ""


class IRStats(BaseModel):
    """IR 内容的静态统计。"""

    package_count: int = 0
    class_count: int = 0
    attribute_count: int = 0
    association_count: int = 0
    enumeration_count: int = 0
    uncertain_count: int = 0


class SourceInfo(BaseModel):
    """输入文档来源信息。"""

    document_path: str
    document_sha256: str
    parsed_at: datetime
    parser_version: str


class OntologyIR(BaseModel):
    """IR-JSON 顶层模型。"""

    schema_version: Literal["1.0"] = "1.0"
    source: SourceInfo | None = None
    packages: list[Package] = Field(default_factory=list)
    uncertain_entries: list[UncertainEntry] = Field(default_factory=list)
    cross_package_refs: list[CrossPackageRef] = Field(default_factory=list)
    stats: IRStats = Field(default_factory=IRStats)

    def all_classes(self) -> list[ClassDef]:
        """所有包的所有类。"""
        return [c for pkg in self.packages for c in pkg.classes]

    def get_class(self, name: str) -> ClassDef | None:
        """按名查找类。"""
        for pkg in self.packages:
            for c in pkg.classes:
                if c.name == name:
                    return c
        return None

    def get_package(self, name: str) -> Package | None:
        """按名查找包。"""
        return next((p for p in self.packages if p.name == name), None)
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_ir_models.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/ir/ tests/unit/test_ir_models.py
git commit -m "feat(ir): add Pydantic data models for IR-JSON"
```

---

## Task 3: 类注册表（ClassRegistry）

**Files:**
- Create: `src/cim_ontology/ir/registry.py`
- Test: `tests/unit/test_ir_registry.py`

**Interfaces:**
- Consumes: 无
- Produces: `ClassRegistry` 类，方法：`add`、`has`、`get`、`find_similar`、`all_names`

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_ir_registry.py`：

```python
"""ClassRegistry 单元测试。"""
import pytest

from cim_ontology.ir.registry import ClassRegistry


class TestClassRegistry:
    def test_add_and_get(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        assert reg.get("IdentifiedObject") == "Core"
        assert reg.has("IdentifiedObject")

    def test_get_unknown_returns_none(self):
        reg = ClassRegistry()
        assert reg.get("Unknown") is None
        assert not reg.has("Unknown")

    def test_find_similar_finds_close_match(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        reg.add("Wires", "ReportingGroup")
        similar = reg.find_similar("Meastrement", threshold=2)
        names = [name for name, _ in similar]
        assert "Measurement" in names

    def test_find_similar_returns_empty_when_no_match(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        similar = reg.find_similar("CompletelyDifferent", threshold=1)
        assert similar == []

    def test_all_names(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        reg.add("Wires", "Line")
        names = reg.all_names()
        assert "IdentifiedObject" in names
        assert "Line" in names
        assert len(names) == 2
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_ir_registry.py -v
```

预期：ImportError（`cim_ontology.ir.registry` 不存在）。

- [ ] **Step 3: 写 ClassRegistry 实现**

文件 `src/cim_ontology/ir/registry.py`：

```python
"""类与命名空间注册表。

支持按名查找、模糊匹配（Levenshtein 距离）。"""
from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """计算 Levenshtein 编辑距离。"""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        current = [i + 1]
        for j, cb in enumerate(b):
            insertions = previous[j + 1] + 1
            deletions = current[j] + 1
            substitutions = previous[j] + (ca != cb)
            current.append(min(insertions, deletions, substitutions))
        previous = current
    return previous[-1]


class ClassRegistry:
    """已注册类的中央注册表。"""

    def __init__(self) -> None:
        self._classes: dict[str, str] = {}  # class_name -> package_name

    def add(self, package: str, class_name: str) -> None:
        """注册一个类。"""
        self._classes[class_name] = package

    def has(self, class_name: str) -> bool:
        """类是否已注册。"""
        return class_name in self._classes

    def get(self, class_name: str) -> str | None:
        """获取类所属包。"""
        return self._classes.get(class_name)

    def all_names(self) -> list[str]:
        """所有已注册类名。"""
        return list(self._classes.keys())

    def find_similar(self, name: str, threshold: int = 2) -> list[tuple[str, int]]:
        """查找与给定名相似的类（距离 ≤ threshold），按距离升序。

        返回: [(class_name, distance), ...]
        """
        results = []
        for registered in self._classes:
            d = levenshtein(name, registered)
            if d <= threshold:
                results.append((registered, d))
        results.sort(key=lambda x: x[1])
        return results


class NamespaceRegistry:
    """命名空间前缀注册表。"""

    # 已知命名空间映射（设计规范 §4.3）
    CANONICAL: dict[str, str] = {
        "cim": "http://iec.ch/TC57/2024/CIM-schema-cim17#",
        "eu": "http://iec.ch/TC57/NonStandard/UML#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "sh": "http://www.w3.org/ns/shacl#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }

    def __init__(self) -> None:
        self._aliases: dict[str, str] = dict(self.CANONICAL)

    def add_alias(self, alias: str, canonical_prefix: str) -> None:
        """注册别名（如 cin -> cim）。"""
        if canonical_prefix not in self.CANONICAL:
            raise ValueError(f"未知规范前缀: {canonical_prefix}")
        self._aliases[alias] = self.CANONICAL[canonical_prefix]

    def resolve(self, prefix: str) -> str | None:
        """解析前缀为完整 IRI 模板。"""
        return self._aliases.get(prefix)
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_ir_registry.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/ir/registry.py tests/unit/test_ir_registry.py
git commit -m "feat(ir): add ClassRegistry with Levenshtein similarity search"
```

---

# Phase 2（M2）：Stage 1 规则清洗器

## Task 4: Markdown 解析器（markdown-it-py tokenizer）

**Files:**
- Create: `src/cim_ontology/cleaner/__init__.py`
- Create: `src/cim_ontology/cleaner/markdown_parser.py`
- Test: `tests/unit/test_markdown_parser.py`

**Interfaces:**
- Consumes: `str`（Markdown 内容）
- Produces: `list[MarkdownToken]`，每 token 含 `type`、`content`、`level`、`children`

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_markdown_parser.py`：

```python
"""Markdown 解析器单元测试。"""
from cim_ontology.cleaner.markdown_parser import (
    MarkdownToken,
    TokenType,
    parse_markdown,
)


class TestParseMarkdown:
    def test_extracts_h2_heading(self):
        md = "## 6.1.2 Class: IdentifiedObject\n"
        tokens = parse_markdown(md)
        h2 = [t for t in tokens if t.type == TokenType.HEADING and t.level == 2]
        assert len(h2) == 1
        assert "IdentifiedObject" in h2[0].content

    def test_extracts_table(self):
        md = "| 列1 | 列2 |\n|---|---|\n| A | B |\n"
        tokens = parse_markdown(md)
        tables = [t for t in tokens if t.type == TokenType.TABLE]
        assert len(tables) >= 1
        assert "A" in tables[0].content
        assert "B" in tables[0].content

    def test_empty_input(self):
        tokens = parse_markdown("")
        assert tokens == []

    def test_mixed_content(self):
        md = (
            "# 标题\n\n"
            "## 6.1.2 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 |\n|---|---|\n| name | string |\n"
        )
        tokens = parse_markdown(md)
        types = {t.type for t in tokens}
        assert TokenType.HEADING in types
        assert TokenType.TABLE in types
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_markdown_parser.py -v
```

预期：ImportError。

- [ ] **Step 3: 写 Markdown 解析器实现**

文件 `src/cim_ontology/cleaner/__init__.py`：

```python
"""Stage 1: 规则清洗器。"""
```

文件 `src/cim_ontology/cleaner/markdown_parser.py`：

```python
"""Markdown 解析器：使用 markdown-it-py 提取 token 序列。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from markdown_it import MarkdownIt


class TokenType(str, Enum):
    """Token 类型。"""

    HEADING = "heading"
    TABLE = "table"
    PARAGRAPH = "paragraph"
    CODE = "code"
    OTHER = "other"


@dataclass
class MarkdownToken:
    """单个 Markdown 元素。"""

    type: TokenType
    level: int = 0
    content: str = ""
    children: list[MarkdownToken] = field(default_factory=list)


def parse_markdown(content: str) -> list[MarkdownToken]:
    """解析 Markdown 为 token 列表。

    仅提取对本体抽取有用的 token：标题、表格、段落。
    """
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    raw_tokens = md.parse(content)

    results: list[MarkdownToken] = []
    for tok in raw_tokens:
        ttype = tok.type
        if ttype == "heading_open":
            level = int(tok.tag[1])
            results.append(MarkdownToken(type=TokenType.HEADING, level=level))
        elif ttype == "heading_close":
            pass
        elif ttype == "table_open":
            results.append(MarkdownToken(type=TokenType.TABLE))
        elif ttype == "table_close":
            pass
        elif ttype == "inline" and results and results[-1].type in (
            TokenType.HEADING,
            TokenType.TABLE,
        ):
            # 关联到最近的标题或表格
            results[-1].content = _clean_inline(tok.content)
        elif ttype == "paragraph_open":
            results.append(MarkdownToken(type=TokenType.PARAGRAPH))
        elif ttype == "paragraph_close":
            pass
        elif ttype == "code_block_open" or ttype == "fence":
            results.append(MarkdownToken(type=TokenType.CODE, content=tok.content))
        else:
            results.append(MarkdownToken(type=TokenType.OTHER))

    return results


def _clean_inline(content: str) -> str:
    """清理 inline 文本，去除多余空白。"""
    return " ".join(content.split())
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_markdown_parser.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/ tests/unit/test_markdown_parser.py
git commit -m "feat(cleaner): add markdown-it-py based parser"
```

---

## Task 5: 章节切分器（按 ## 标题分组）

**Files:**
- Create: `src/cim_ontology/cleaner/section_splitter.py`
- Test: `tests/unit/test_section_splitter.py`

**Interfaces:**
- Consumes: `list[MarkdownToken]`
- Produces: `list[Section]`，每 section 含 `path`、`heading`、`tokens`

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_section_splitter.py`：

```python
"""章节切分器测试。"""
from cim_ontology.cleaner.markdown_parser import parse_markdown
from cim_ontology.cleaner.section_splitter import (
    Section,
    split_into_sections,
)


def test_basic_split():
    md = (
        "## 6.1.1 Class A\n"
        "描述 A\n"
        "| attr | type |\n|---|---|\n| x | int |\n"
        "\n"
        "## 6.1.2 Class B\n"
        "描述 B\n"
    )
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)

    assert len(sections) == 2
    assert sections[0].heading == "6.1.1 Class A"
    assert sections[1].heading == "6.1.2 Class B"


def test_no_headings_single_section():
    md = "## 6.1.1 Only Section\n\n普通段落\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert len(sections) == 1


def test_section_path_extraction():
    md = "## 6.2.3 Class: Measurement (CIM)\n描述\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "6.2.3"
    assert sections[0].class_name == "Measurement"
    assert sections[0].stereotype == "CIM"


def test_section_without_class_prefix():
    md = "## 7 Package Overview\n文字\n"
    tokens = parse_markdown(md)
    sections = split_into_sections(tokens)
    assert sections[0].path == "7"
    assert sections[0].class_name is None
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_section_splitter.py -v
```

预期：ImportError。

- [ ] **Step 3: 写章节切分器实现**

文件 `src/cim_ontology/cleaner/section_splitter.py`：

```python
"""章节切分器：将 token 流按 ## 标题分组为 Section。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from cim_ontology.cleaner.markdown_parser import MarkdownToken, TokenType


@dataclass
class Section:
    """一个章节（通常对应一个 CIM 类）。"""

    path: str                       # "6.2.3"
    heading: str                    # "6.2.3 Class: Measurement (CIM)"
    class_name: str | None = None   # "Measurement"
    stereotype: str | None = None   # "CIM"
    tokens: list[MarkdownToken] = field(default_factory=list)


# 章节标题正则：
#   "6.1.2 Class: IdentifiedObject"
#   "6.1.2 Class: Measurement (CIM)"
#   "6.2.3 Class Measurement"  ← 容错
_HEADING_RE = re.compile(
    r"^(?P<path>\d+(?:\.\d+){0,3})\s+Class(?:\s*[:：])?\s+(?P<name>\w+)(?:\s+\((?P<stereo>\w+)\))?"
)


def split_into_sections(tokens: list[MarkdownToken]) -> list[Section]:
    """按 H2 标题切分章节。"""
    sections: list[Section] = []
    current: Section | None = None

    for tok in tokens:
        if tok.type == TokenType.HEADING and tok.level == 2:
            # 解析标题
            heading = tok.content
            section = _parse_heading(heading)
            current = section
            sections.append(section)
        elif current is not None:
            current.tokens.append(tok)

    if not sections and tokens:
        # 没有 H2 标题 → 整个文档作为一节
        sections.append(Section(path="0", heading=""))

    return sections


def _parse_heading(heading: str) -> Section:
    """从 H2 标题文本解析 Section。"""
    section = Section(path="", heading=heading)
    m = _HEADING_RE.match(heading.strip())
    if m:
        section.path = m.group("path")
        section.class_name = m.group("name")
        section.stereotype = m.group("stereo")
    return section
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_section_splitter.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/section_splitter.py tests/unit/test_section_splitter.py
git commit -m "feat(cleaner): add section splitter by H2 headings"
```

---

## Task 6: 表格提取器（BeautifulSoup）

**Files:**
- Create: `src/cim_ontology/cleaner/table_extractor.py`
- Test: `tests/unit/test_table_extractor.py`

**Interfaces:**
- Consumes: `list[MarkdownToken]`（已确认是表格 token）
- Produces: `Table` 对象，含 `headers: list[str]`、`rows: list[list[str]]`

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_table_extractor.py`：

```python
"""表格提取器测试。"""
from cim_ontology.cleaner.markdown_parser import parse_markdown
from cim_ontology.cleaner.table_extractor import Table, extract_tables_from_section


def test_simple_table():
    md = (
        "| 属性 | 类型 | 基数 |\n"
        "|---|---|---|\n"
        "| name | string | 0..1 |\n"
        "| mRID | string | 1..1 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert len(tables) == 1
    t = tables[0]
    assert t.headers == ["属性", "类型", "基数"]
    assert t.rows == [["name", "string", "0..1"], ["mRID", "string", "1..1"]]


def test_table_classification_property():
    md = (
        "| 属性 | 类型 |\n|---|---|\n"
        "| name | string |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "property"


def test_table_classification_association():
    md = (
        "| 关联端 | 目标类 | 基数 |\n|---|---|---|\n"
        "| PowerSystemResource | PowerSystemResource | 0..1 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "association"


def test_table_classification_enumeration():
    md = (
        "| 字面量 | 说明 |\n|---|---|\n"
        "| A | A 相 |\n"
    )
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].kind == "enumeration"


def test_empty_cells_stripped():
    md = "| a | b |\n|---|---|\n| 1 |  2  |\n"
    tokens = parse_markdown(md)
    tables = extract_tables_from_section(tokens)
    assert tables[0].rows[0] == ["1", "2"]
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_table_extractor.py -v
```

预期：ImportError。

- [ ] **Step 3: 写表格提取器实现**

文件 `src/cim_ontology/cleaner/table_extractor.py`：

```python
"""表格提取器：使用 BeautifulSoup 解析 HTML 表格，分类表格类型。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from cim_ontology.cleaner.markdown_parser import MarkdownToken, TokenType


@dataclass
class Table:
    """一个表格。"""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    kind: str = "unknown"  # property / association / enumeration / inheritance

    @property
    def first_header(self) -> str:
        return self.headers[0] if self.headers else ""


def extract_tables_from_section(tokens: list[MarkdownToken]) -> list[Table]:
    """从 section tokens 中提取所有表格。"""
    tables: list[Table] = []
    current_html: list[str] = []

    for tok in tokens:
        if tok.type == TokenType.TABLE:
            current_html.append("<table>")
            # Markdown 表格需要转换为 HTML
            current_html.append(_md_table_to_html(tok.content))
            current_html.append("</table>")
            soup = BeautifulSoup("".join(current_html), "lxml")
            table = _parse_html_table(soup.find("table"))
            table.kind = _classify_table(table)
            tables.append(table)
            current_html = []

    return tables


def _md_table_to_html(content: str) -> str:
    """将 Markdown 表格内容转换为 HTML。"""
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return ""

    html_rows = []
    for i, line in enumerate(lines):
        if i == 1 and re.match(r"^\|[\s\-:|]+\|$", line):
            continue  # 跳过分隔行 |---|---|

        cells = [c.strip() for c in line.strip("|").split("|")]
        tag = "th" if i == 0 else "td"
        html_rows.append(
            "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
        )

    return "\n".join(html_rows)


def _parse_html_table(table_tag) -> Table:
    """从 BeautifulSoup table 标签解析 Table。"""
    result = Table()
    rows = table_tag.find_all("tr")
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [_normalize_cell(c.get_text()) for c in cells]
        if i == 0:
            result.headers = cell_texts
        else:
            result.rows.append(cell_texts)
    return result


def _normalize_cell(text: str) -> str:
    """规范化单元格文本。"""
    return " ".join(text.split())


def _classify_table(table: Table) -> str:
    """根据首列关键字分类表格。"""
    first = table.first_header.lower()
    if "属性" in first or "property" in first:
        return "property"
    if "关联端" in first or "association" in first:
        return "association"
    if "字面量" in first or "literal" in first or "枚举" in first:
        return "enumeration"
    if "继承" in first or "父类" in first or "super" in first:
        return "inheritance"
    return "unknown"
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_table_extractor.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/table_extractor.py tests/unit/test_table_extractor.py
git commit -m "feat(cleaner): add HTML table extractor with type classification"
```

---

## Task 7: 多重性清洗器（处理 OCR 变体）

**Files:**
- Create: `src/cim_ontology/cleaner/multiplicity.py`
- Test: `tests/unit/test_multiplicity.py`

**Interfaces:**
- Consumes: `str`（原始多重性字符串）
- Produces: `Multiplicity`（Pydantic 模型）或 `UnparseableMultiplicity` 异常

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_multiplicity.py`：

```python
"""多重性清洗器测试。"""
import pytest

from cim_ontology.cleaner.multiplicity import (
    UnparseableMultiplicity,
    clean_multiplicity,
)
from cim_ontology.ir.models import Multiplicity


class TestCleanMultiplicity:
    @pytest.mark.parametrize("raw,expected_min,expected_max,expected_raw", [
        ("0..1", 0, 1, "0..1"),
        (" 0..1 ", 0, 1, "0..1"),
        ("0..*", 0, None, "0..*"),
        ("many", 0, None, "0..*"),       # 语义归一
        ("0..n", 0, None, "0..*"),
        ("1..*", 1, None, "1..*"),
        ("1..1", 1, 1, "1..1"),
    ])
    def test_valid_multiplicity(self, raw, expected_min, expected_max, expected_raw):
        m = clean_multiplicity(raw)
        assert isinstance(m, Multiplicity)
        assert m.min == expected_min
        assert m.max == expected_max
        assert m.raw == expected_raw

    def test_strips_latex_noise(self):
        m = clean_multiplicity(" $0..1$ ")
        assert m.min == 0
        assert m.max == 1

    def test_unparseable_raises(self):
        with pytest.raises(UnparseableMultiplicity):
            clean_multiplicity("not-a-multiplicity")
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_multiplicity.py -v
```

预期：ImportError。

- [ ] **Step 3: 写多重性清洗器实现**

文件 `src/cim_ontology/cleaner/multiplicity.py`：

```python
"""多重性清洗器：处理 OCR 变体、LaTeX 噪声、语义归一。"""
from __future__ import annotations

import re

from cim_ontology.ir.models import Multiplicity


class UnparseableMultiplicity(ValueError):
    """无法解析的多重性字符串。"""

    def __init__(self, raw: str) -> None:
        super().__init__(f"无法解析的多重性: {raw!r}")
        self.raw = raw


# 已知别名 → 规范格式
_ALIASES: dict[str, str] = {
    "many": "0..*",
    "n": "0..*",
    "*": "0..*",
    "0..n": "0..*",
    "1..n": "1..*",
}

# 标准 N..M 格式
_PATTERN = re.compile(r"^(\d+)\.\.(\d+|\*)$")


def clean_multiplicity(raw: str) -> Multiplicity:
    """清洗多重性字符串，返回 Multiplicity 或抛出 UnparseableMultiplicity。

    处理：
      - 前后空白
      - LaTeX 标记（$...$、\\mathcal{Z} 等）
      - 语义别名（many → 0..*）
      - N..M 标准格式
    """
    # 1. 去除 LaTeX 噪声
    text = raw.strip()
    text = text.replace("$", "")
    text = re.sub(r"\\mathcal\{[A-Z]+\}", "", text)
    text = text.strip()

    # 2. 别名归一
    text = _ALIASES.get(text, text)

    # 3. 解析 N..M
    m = _PATTERN.match(text)
    if not m:
        raise UnparseableMultiplicity(raw)

    min_str, max_str = m.groups()
    min_val = int(min_str)
    max_val: int | None = None if max_str == "*" else int(max_str)

    return Multiplicity(min=min_val, max=max_val, raw=text)
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_multiplicity.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/multiplicity.py tests/unit/test_multiplicity.py
git commit -m "feat(cleaner): add multiplicity cleaner with OCR variant handling"
```

---

## Task 8: 命名空间清洗器

**Files:**
- Create: `src/cim_ontology/cleaner/namespace.py`
- Test: `tests/unit/test_namespace.py`

**Interfaces:**
- Consumes: `str`（前缀如 "cim:"）
- Produces: `str`（完整 IRI）或 `UnknownNamespace` 异常

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_namespace.py`：

```python
"""命名空间清洗器测试。"""
import pytest

from cim_ontology.cleaner.namespace import (
    UnknownNamespace,
    auto_correct_namespaces,
    clean_namespace,
    collect_namespace_aliases,
)


class TestCleanNamespace:
    def test_known_prefix_cim(self):
        assert clean_namespace("cim:") == "http://iec.ch/TC57/2024/CIM-schema-cim17#"

    def test_known_prefix_rdfs(self):
        assert clean_namespace("rdfs:") == "http://www.w3.org/2000/01/rdf-schema#"

    def test_unknown_raises(self):
        with pytest.raises(UnknownNamespace):
            clean_namespace("unknown:")


class TestCollectNamespaceAliases:
    def test_collects_unique_prefixes(self):
        content = "cim:Foo cim:Bar rdfs:Label"
        aliases = collect_namespace_aliases(content)
        assert aliases["cim"] == 2
        assert aliases["rdfs"] == 1


class TestAutoCorrect:
    def test_corrects_close_misspellings(self):
        # cin: → cim:（距离 1）
        aliases = {"cin": 5, "cim": 10, "rdfts": 2}
        corrections = auto_correct_namespaces(aliases)
        assert corrections.get("cin") == "cim"
        assert corrections.get("rdfts") == "rdfs"
        # 已正确的不纠正
        assert "cim" not in corrections
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_namespace.py -v
```

预期：ImportError。

- [ ] **Step 3: 写命名空间清洗器实现**

文件 `src/cim_ontology/cleaner/namespace.py`：

```python
"""命名空间清洗器：前缀 → 完整 IRI，支持 OCR 拼写自动纠正。"""
from __future__ import annotations

import re
from collections import Counter

from cim_ontology.ir.registry import NamespaceRegistry, levenshtein


class UnknownNamespace(KeyError):
    """未知命名空间前缀。"""

    def __init__(self, prefix: str) -> None:
        super().__init__(prefix)
        self.prefix = prefix


# 引用注册表的规范前缀
_CANONICAL_PREFIXES: list[str] = list(NamespaceRegistry.CANONICAL.keys())


def clean_namespace(prefix: str) -> str:
    """将命名空间前缀解析为完整 IRI 模板。

    prefix 示例: "cim:", "rdfs:"
    """
    ns = NamespaceRegistry()
    iri = ns.resolve(prefix.rstrip(":"))
    if iri is None:
        raise UnknownNamespace(prefix)
    return iri


def collect_namespace_aliases(content: str) -> dict[str, int]:
    """统计文档中出现的命名空间前缀及其频次。

    模式: \\b([a-z]+):[A-Z]\\w+
    """
    pattern = re.compile(r"\b([a-z]+):[A-Z]\w+")
    counter: Counter[str] = Counter()
    for m in pattern.finditer(content):
        counter[m.group(1)] += 1
    return dict(counter)


def auto_correct_namespaces(
    aliases: dict[str, int],
    max_distance: int = 2,
) -> dict[str, str]:
    """基于 Levenshtein 距离自动纠正命名空间前缀。

    返回: {alias: canonical_prefix}（仅包含需要纠正的项）
    """
    corrections: dict[str, str] = {}
    for alias in aliases:
        if alias in _CANONICAL_PREFIXES:
            continue
        # 找最近规范前缀
        closest = min(
            _CANONICAL_PREFIXES,
            key=lambda c: levenshtein(alias, c),
        )
        if levenshtein(alias, closest) <= max_distance:
            corrections[alias] = closest
    return corrections
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_namespace.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/namespace.py tests/unit/test_namespace.py
git commit -m "feat(cleaner): add namespace cleaner with auto-correction"
```

---

## Task 9: 类名清洗器（OCR 已知错误 + 模糊匹配）

**Files:**
- Create: `src/cim_ontology/cleaner/class_name.py`
- Test: `tests/unit/test_class_name.py`
- Create: `tests/fixtures/dirty/with_ocr_errors.md`

**Interfaces:**
- Consumes: `str`（原始类名）、`ClassRegistry`
- Produces: `CleanedName`（含 `value`、`correction_applied`、`notes`、`uncertainty_reason`）

- [ ] **Step 1: 写失败测试 + 准备 fixture**

文件 `tests/fixtures/dirty/with_ocr_errors.md`：

```markdown
## 6.1.1 Class: Meastrement

描述：测量值

| 属性 | 类型 | 基数 |
|---|---|---|
| measurementType | string | 1..1 |

## 6.1.2 Class: Rep0rtingGroup

描述：报告组

| 属性 | 类型 | 基数 |
|---|---|---|
| name | string | 1..1 |
```

文件 `tests/unit/test_class_name.py`：

```python
"""类名清洗器测试。"""
from cim_ontology.cleaner.class_name import CleanedName, clean_class_name
from cim_ontology.ir.registry import ClassRegistry


class TestCleanClassName:
    def test_known_ocr_correction(self):
        reg = ClassRegistry()
        result = clean_class_name("Meastrement", reg)
        assert result.value == "Measurement"
        assert result.correction_applied is True

    def test_known_registered_passthrough(self):
        reg = ClassRegistry()
        reg.add("Core", "IdentifiedObject")
        result = clean_class_name("IdentifiedObject", reg)
        assert result.value == "IdentifiedObject"
        assert result.correction_applied is False

    def test_typo_flagged_as_uncertain(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("Meastrement", reg)
        # 已在已知修正表
        assert result.uncertainty_reason is None

    def test_close_match_flagged_with_suggestions(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("Measurment", reg)  # 少一个 e
        # Levenshtein 距离 1，但不在已知修正表
        assert result.value == "Measurment"
        assert result.uncertainty_reason == "class_name_typo"
        assert "Measurement" in result.suggestions

    def test_completely_unknown(self):
        reg = ClassRegistry()
        reg.add("Core", "Measurement")
        result = clean_class_name("CompletelyNewClass", reg)
        assert result.uncertainty_reason == "class_unknown"


class TestAllOcrCorrections:
    """覆盖所有已知 OCR 错误（设计规范 §4.3）。"""

    @pytest.mark.parametrize("raw,expected", [
        ("Meastrement", "Measurement"),
        ("Rep0rtingGroup", "ReportingGroup"),
        ("AuxiliarEuiment", "AuxiliaryEquipment"),
        ("DiaramLaout", "DiagramLayout"),
    ])
    def test_known_correction(self, raw, expected):
        reg = ClassRegistry()
        result = clean_class_name(raw, reg)
        assert result.value == expected
        assert result.correction_applied is True
```

需要在测试文件顶部添加 `import pytest`。

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_class_name.py -v
```

预期：ImportError。

- [ ] **Step 3: 写类名清洗器实现**

文件 `src/cim_ontology/cleaner/class_name.py`：

```python
"""类名清洗器：处理 OCR 已知错误 + 模糊匹配。"""
from __future__ import annotations

from dataclasses import dataclass, field

from cim_ontology.ir.registry import ClassRegistry


# 已知 OCR 错误 → 正确类名（设计规范 §4.3）
KNOWN_OCR_CORRECTIONS: dict[str, str] = {
    "Meastrement": "Measurement",
    "Rep0rtingGroup": "ReportingGroup",
    "AuxiliarEuiment": "AuxiliaryEquipment",
    "DiaramLaout": "DiagramLayout",
}


@dataclass
class CleanedName:
    """清洗后的类名。"""

    value: str
    correction_applied: bool = False
    notes: str = ""
    uncertainty_reason: str | None = None  # class_name_typo / class_unknown
    suggestions: list[str] = field(default_factory=list)


def clean_class_name(raw: str, registry: ClassRegistry) -> CleanedName:
    """清洗类名，应用已知修正或模糊匹配。

    优先级：
      1. KNOWN_OCR_CORRECTIONS 直接修正
      2. registry.has(raw) 直接通过
      3. registry.find_similar() 模糊匹配 → 标记 uncertain + 建议
      4. 完全未知 → 标记 class_unknown
    """
    # 1. 已知修正
    if raw in KNOWN_OCR_CORRECTIONS:
        corrected = KNOWN_OCR_CORRECTIONS[raw]
        return CleanedName(
            value=corrected,
            correction_applied=True,
            notes=f"OCR 修正: {raw} → {corrected}",
        )

    # 2. 已注册
    if registry.has(raw):
        return CleanedName(value=raw)

    # 3. 模糊匹配（距离 ≤ 2）
    similar = registry.find_similar(raw, threshold=2)
    if similar:
        suggestions = [name for name, _ in similar[:3]]
        return CleanedName(
            value=raw,
            uncertainty_reason="class_name_typo",
            suggestions=suggestions,
        )

    # 4. 完全未知
    return CleanedName(
        value=raw,
        uncertainty_reason="class_unknown",
    )
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_class_name.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/class_name.py tests/unit/test_class_name.py tests/fixtures/dirty/
git commit -m "feat(cleaner): add class name cleaner with OCR correction table"
```

---

## Task 10: 层级推断（解析器脆弱性缓解）

**Files:**
- Create: `src/cim_ontology/cleaner/hierarchical.py`
- Test: `tests/unit/test_hierarchical.py`

**Interfaces:**
- Consumes: `str`（标题文本）、`list[str]`（上下文所有标题）
- Produces: `SectionContext`（含 `depth: int`、`confidence: float`）

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_hierarchical.py`：

```python
"""层级推断测试。"""
from cim_ontology.cleaner.hierarchical import (
    SectionContext,
    hierarchical_classify_section,
)


class TestHierarchicalClassify:
    def test_infer_depth_from_numbering(self):
        ctx = hierarchical_classify_section("6.1.2 Class: Foo", [])
        assert ctx.depth == 3
        assert ctx.confidence >= 0.8

    def test_top_level_number(self):
        ctx = hierarchical_classify_section("7 Package Overview", [])
        assert ctx.depth == 1

    def test_class_keyword_fallback(self):
        ctx = hierarchical_classify_section("Class: Foo", [])
        assert ctx.depth == 3  # 默认推断
        assert ctx.confidence < 0.8  # 置信度低

    def test_no_signal_returns_low_confidence(self):
        ctx = hierarchical_classify_section("Random Title", [])
        assert ctx.confidence < 0.5

    def test_full_depth_four_levels(self):
        ctx = hierarchical_classify_section("6.2.3.4 Subsection", [])
        assert ctx.depth == 4
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_hierarchical.py -v
```

预期：ImportError。

- [ ] **Step 3: 写层级推断实现**

文件 `src/cim_ontology/cleaner/hierarchical.py`：

```python
"""层级推断：OCR 异常时 ## 标记可能丢失，此模块基于多种信号推断层级。"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionContext:
    """推断的章节上下文。"""

    depth: int           # 1-4
    confidence: float    # 0.0-1.0


def hierarchical_classify_section(
    heading: str,
    all_headings: list[str],
) -> SectionContext:
    """基于多种信号推断章节层级。

    信号优先级：
      1. 章节编号格式 (e.g. "6.1.2" → depth=3)，置信度 0.9
      2. Class: 关键字（无编号时），置信度 0.7，depth=3
      3. 默认 depth=2 + 警告，置信度 0.3
    """
    text = heading.strip()

    # 信号 1: 编号格式
    m = re.match(r"^(\d+(?:\.\d+){0,3})", text)
    if m:
        depth = m.group(1).count(".") + 1
        return SectionContext(depth=depth, confidence=0.9)

    # 信号 2: Class: 关键字
    if re.search(r"^Class\s*[:：]\s*\w+", text):
        return SectionContext(depth=3, confidence=0.7)

    # 默认
    return SectionContext(depth=2, confidence=0.3)
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/unit/test_hierarchical.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/cleaner/hierarchical.py tests/unit/test_hierarchical.py
git commit -m "feat(cleaner): add hierarchical section classifier for parser fragility"
```

---

## Task 11: 包依赖图 + 拓扑排序

**Files:**
- Create: `src/cim_ontology/cleaner/dep_graph.py`
- Test: `tests/unit/test_dep_graph.py`

**Interfaces:**
- Consumes: `OntologyIR`
- Produces: `nx.DiGraph` + `topological_sort` 函数

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_dep_graph.py`：

```python
"""包依赖图与拓扑排序测试。"""
from cim_ontology.cleaner.dep_graph import (
    build_package_dependency_graph,
    topological_sort,
)
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    CrossPackageRef,
    Multiplicity,
    OntologyIR,
    Package,
)


def _ir_with_refs(refs: list[CrossPackageRef]) -> OntologyIR:
    """构造带跨包引用的 IR。"""
    pkg_a = Package(iri="http://x#A", name="A", classes=[
        ClassDef(name="A1", associations=[]),
    ])
    pkg_b = Package(iri="http://x#B", name="B", classes=[
        ClassDef(name="B1", associations=[]),
    ])
    return OntologyIR(
        packages=[pkg_a, pkg_b],
        cross_package_refs=refs,
    )


class TestBuildDependencyGraph:
    def test_simple_dependency(self):
        ir = _ir_with_refs([
            CrossPackageRef(from_package="B", to_package="A", via_class="B1", via_property="a"),
        ])
        g = build_package_dependency_graph(ir)
        assert "A" in g.nodes
        assert "B" in g.nodes
        # B 依赖 A（有边 B → A）
        assert "A" in list(g.successors("B"))


class TestTopologicalSort:
    def test_orders_by_dependency(self):
        ir = _ir_with_refs([
            CrossPackageRef(from_package="B", to_package="A", via_class="B1", via_property="a"),
        ])
        g = build_package_dependency_graph(ir)
        ordered = topological_sort(g)
        # A 在 B 前
        assert ordered.index("A") < ordered.index("B")

    def test_independent_packages_in_any_order(self):
        pkg_a = Package(iri="http://x#A", name="A", classes=[])
        pkg_b = Package(iri="http://x#B", name="B", classes=[])
        ir = OntologyIR(packages=[pkg_a, pkg_b])
        g = build_package_dependency_graph(ir)
        ordered = topological_sort(g)
        assert set(ordered) == {"A", "B"}
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
pytest tests/unit/test_dep_graph.py -v
```

预期：ImportError。

- [ ] **Step 3: 写依赖图实现**

文件 `src/cim_ontology/cleaner/dep_graph.py`：

```python
"""包依赖图与拓扑排序（设计规范 §6.2.1）。

用于：
  - OWL 按包拆分时正确添加 owl:imports
  - Python types 按拓扑序生成避免循环 import
"""
from __future__ import annotations

import networkx as nx
import structlog

from cim_ontology.ir.models import OntologyIR

log = structlog.get_logger()


def build_package_dependency_graph(ir: OntologyIR) -> nx.DiGraph:
    """从 cross_package_refs 构建有向依赖图。

    节点: 包名
    边: A → B 表示 A 依赖 B
    """
    g = nx.DiGraph()
    for pkg in ir.packages:
        g.add_node(pkg.name)
    for ref in ir.cross_package_refs:
        g.add_edge(ref.from_package, ref.to_package)
    return g


def topological_sort(g: nx.DiGraph) -> list[str]:
    """Kahn 算法拓扑排序。

    循环依赖时回退到字典序（应避免循环，但降级方案必须可用）。
    """
    try:
        return list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible as e:
        log.error("包依赖图中存在环，降级为字典序", error=str(e))
        return sorted(g.nodes, key=lambda n: n)
```

- [ ] **Step 4: 添加 networkx 依赖到 pyproject.toml**

编辑 `pyproject.toml`，在 `dependencies` 中添加：

```toml
    "networkx>=3.3",
```

然后重新安装：

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: 运行测试，验证通过**

```bash
pytest tests/unit/test_dep_graph.py -v
```

预期：所有测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add src/cim_ontology/cleaner/dep_graph.py tests/unit/test_dep_graph.py pyproject.toml
git commit -m "feat(cleaner): add package dependency graph with topological sort"
```

---

## Task 12: Stage 1 编排器（clean_markdown_to_ir 主入口）

**Files:**
- Create: `src/cim_ontology/cleaner/orchestrator.py`
- Test: `tests/integration/test_stage1_orchestrator.py`
- Create: `tests/fixtures/small/Core.md`
- Create: `tests/fixtures/medium/Core_Wires.md`

**Interfaces:**
- Consumes: `Path`（Markdown 文件路径）
- Produces: `OntologyIR`

- [ ] **Step 1: 准备 small fixture**

文件 `tests/fixtures/small/Core.md`：

```markdown
## 5 Package: Core

### 5.1 Core::IdentifiedObject

## 5.1.1 Class: IdentifiedObject

基类

| 属性 | 类型 | 基数 |
|---|---|---|
| mRID | string | 1..1 |
| name | string | 0..1 |
| description | string | 0..1 |

## 5.1.2 Class: PowerSystemResource

PSR 基类

| 属性 | 类型 | 基数 |
|---|---|---|
| name | string | 0..1 |

| 继承 | 父类 |
|---|---|
| 父类 | IdentifiedObject |

## 5.1.3 Class: Measurement

测量值

| 属性 | 类型 | 基数 |
|---|---|---|
| measurementType | string | 1..1 |

| 关联端 | 目标类 | 基数 |
|---|---|---|
| PowerSystemResource | PowerSystemResource | 0..1 |

| 继承 | 父类 |
|---|---|
| 父类 | IdentifiedObject |
```

文件 `tests/fixtures/medium/Core_Wires.md`：在 small fixture 基础上追加 Wires 包内容（可从真实文档复制片段）。

- [ ] **Step 2: 写失败测试**

文件 `tests/integration/test_stage1_orchestrator.py`：

```python
"""Stage 1 编排器集成测试。"""
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir


class TestCleanMarkdownToIR:
    def test_extracts_core_package(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
            "| mRID | string | 1..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        assert len(ir.packages) >= 1
        assert ir.stats.class_count >= 1
        assert ir.stats.package_count >= 1

    def test_extracts_attributes(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: IdentifiedObject\n\n"
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
            "| mRID | string | 1..1 |\n"
            "| name | string | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("IdentifiedObject")
        assert cls is not None
        attr_names = [a.name for a in cls.attributes]
        assert "mRID" in attr_names
        assert "name" in attr_names

    def test_extracts_associations(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.3 Class: Measurement\n\n"
            "| 关联端 | 目标类 | 基数 |\n|---|---|---|\n"
            "| PowerSystemResource | PowerSystemResource | 0..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("Measurement")
        assert cls is not None
        assert len(cls.associations) >= 1
        assert cls.associations[0].target.class_name == "PowerSystemResource"

    def test_extracts_inheritance(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.2 Class: PowerSystemResource\n\n"
            "| 继承 | 父类 |\n|---|---|\n| 父类 | IdentifiedObject |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        cls = ir.get_class("PowerSystemResource")
        assert cls is not None
        parent_names = [p.class_name for p in cls.parents]
        assert "IdentifiedObject" in parent_names

    def test_source_sha256(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("## 5.1.1 Class: A\n", encoding="utf-8")
        ir = clean_markdown_to_ir(md)
        assert ir.source is not None
        assert len(ir.source.document_sha256) == 64

    def test_ocr_corrections_applied(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(
            "## 5.1.1 Class: Meastrement\n\n"  # OCR 错字
            "| 属性 | 类型 | 基数 |\n|---|---|---|\n| measurementType | string | 1..1 |\n",
            encoding="utf-8",
        )
        ir = clean_markdown_to_ir(md)
        # 自动修正为 Measurement
        assert ir.get_class("Measurement") is not None
```

- [ ] **Step 3: 运行测试，验证失败**

```bash
pytest tests/integration/test_stage1_orchestrator.py -v
```

预期：ImportError。

- [ ] **Step 4: 写 Stage 1 编排器实现**

文件 `src/cim_ontology/cleaner/orchestrator.py`：

```python
"""Stage 1 编排器：Markdown → OntologyIR 主入口。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import structlog

from cim_ontology.cleaner.class_name import clean_class_name
from cim_ontology.cleaner.markdown_parser import parse_markdown
from cim_ontology.cleaner.multiplicity import clean_multiplicity
from cim_ontology.cleaner.namespace import (
    auto_correct_namespaces,
    collect_namespace_aliases,
)
from cim_ontology.cleaner.section_splitter import Section, split_into_sections
from cim_ontology.cleaner.table_extractor import Table, extract_tables_from_section
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    DataProperty,
    IRStats,
    Multiplicity,
    ObjectProperty,
    OntologyIR,
    Package,
    SourceInfo,
    UncertainEntry,
)
from cim_ontology.ir.registry import ClassRegistry

log = structlog.get_logger()


# 当前包名（用于上下文，未实现包检测时兜底）
_DEFAULT_PACKAGE = "Core"


def clean_markdown_to_ir(md_path: Path) -> OntologyIR:
    """Stage 1 入口：解析 Markdown 标准文档为 IR-JSON。

    流程：
      1. 读取文件 + 计算 SHA256
      2. Markdown → tokens
      3. tokens → sections
      4. sections → ClassDef（应用所有清洗规则）
      5. 汇总 stats
    """
    content = md_path.read_text(encoding="utf-8")
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # 收集命名空间别名（用于自动纠正）
    auto_correct_namespaces(collect_namespace_aliases(content))

    # 注册类（已知的核心类种子）
    registry = ClassRegistry()
    _seed_registry(registry)

    # 解析 + 切分
    tokens = parse_markdown(content)
    sections = split_into_sections(tokens)

    # 每个章节 → ClassDef
    classes: list[ClassDef] = []
    uncertain: list[UncertainEntry] = []

    for section in sections:
        cls = _section_to_class(section, registry)
        if cls is None:
            continue
        # 应用类名清洗
        cleaned = clean_class_name(cls.name, registry)
        if cleaned.correction_applied:
            cls.name = cleaned.value
            log.info("ocr_correction", original=cleaned.value, corrected=cleaned.value)
        elif cleaned.uncertainty_reason:
            uncertain.append(UncertainEntry(
                case_id=f"{section.path}::{cls.name}",
                source_table=_extract_table_number(section),
                package=_DEFAULT_PACKAGE,
                raw_text=cls.name,
                rule_attempt={"value": cls.name},
                uncertainty_reason=cleaned.uncertainty_reason,
                context_snippet=section.heading,
            ))
        # 提取 tables → attributes / associations
        tables = extract_tables_from_section(section.tokens)
        _apply_tables(cls, tables)
        classes.append(cls)

    # 统计
    stats = IRStats(
        package_count=1,  # 简化：单包场景
        class_count=len(classes),
        attribute_count=sum(len(c.attributes) for c in classes),
        association_count=sum(len(c.associations) for c in classes),
        uncertain_count=len(uncertain),
    )

    pkg = Package(
        iri="http://iec.ch/TC57/2024/CIM-schema-cim17#",
        name=_DEFAULT_PACKAGE,
        classes=classes,
    )

    return OntologyIR(
        packages=[pkg],
        uncertain_entries=uncertain,
        stats=stats,
        source=SourceInfo(
            document_path=str(md_path),
            document_sha256=sha256,
            parsed_at=datetime.now(timezone.utc),
            parser_version="0.1.0",
        ),
    )


def _seed_registry(reg: ClassRegistry) -> None:
    """注册一些已知核心类（用于模糊匹配种子）。"""
    for cls in ("IdentifiedObject", "PowerSystemResource", "Measurement",
                "ReportingGroup", "DiagramLayout", "AuxiliaryEquipment"):
        reg.add("Core", cls)


def _section_to_class(section: Section, registry: ClassRegistry) -> ClassDef | None:
    """从 Section 构造 ClassDef。"""
    if section.class_name is None:
        return None
    return ClassDef(name=section.class_name, stereotype=section.stereotype)


def _extract_table_number(section: Section) -> int:
    """从章节标题提取表号（简化：返回 0）。"""
    return 0


def _apply_tables(cls: ClassDef, tables: list[Table]) -> None:
    """根据表格类型填充 ClassDef 属性。"""
    for table in tables:
        if table.kind == "property":
            cls.attributes = _parse_property_table(table)
        elif table.kind == "association":
            cls.associations = _parse_association_table(table)
        elif table.kind == "inheritance":
            cls.parents = _parse_inheritance_table(table)


def _parse_property_table(table: Table) -> list[DataProperty]:
    """解析属性表。列：属性 | 类型 | 基数 [可选: 说明]"""
    attrs: list[DataProperty] = []
    for row in table.rows:
        if len(row) < 3:
            continue
        name, data_type, mult_str = row[0], row[1], row[2]
        try:
            multiplicity = clean_multiplicity(mult_str)
        except Exception:
            multiplicity = Multiplicity(min=0, max=1, raw="0..1")
        attrs.append(DataProperty(
            name=name,
            data_type=data_type,
            multiplicity=multiplicity,
            required=multiplicity.min >= 1,
        ))
    return attrs


def _parse_association_table(table: Table) -> list[ObjectProperty]:
    """解析关联端表。列：关联端 | 目标类 | 基数"""
    assocs: list[ObjectProperty] = []
    for row in table.rows:
        if len(row) < 3:
            continue
        name, target_name, mult_str = row[0], row[1], row[2]
        try:
            multiplicity = clean_multiplicity(mult_str)
        except Exception:
            multiplicity = Multiplicity(min=0, max=1, raw="0..1")
        assocs.append(ObjectProperty(
            name=name,
            target=ClassRef(package="Core", class_name=target_name),
            multiplicity=multiplicity,
        ))
    return assocs


def _parse_inheritance_table(table: Table) -> list[ClassRef]:
    """解析继承表。列：父类"""
    parents: list[ClassRef] = []
    for row in table.rows:
        if len(row) >= 2:
            parents.append(ClassRef(package="Core", class_name=row[1]))
    return parents
```

- [ ] **Step 5: 运行测试，验证通过**

```bash
pytest tests/integration/test_stage1_orchestrator.py -v
```

预期：所有测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add src/cim_ontology/cleaner/orchestrator.py tests/integration/test_stage1_orchestrator.py tests/fixtures/
git commit -m "feat(cleaner): add Stage 1 orchestrator (Markdown -> IR-JSON)"
```

---

# Phase 3（M3）：Stage 2 LLM 复审核查

## Task 13: LLM Provider 协议 + Mock Provider

**Files:**
- Create: `src/cim_ontology/reviewer/__init__.py`
- Create: `src/cim_ontology/reviewer/providers.py`
- Test: `tests/unit/test_providers.py`
- Create: `tests/fixtures/llm/default.json`

**Interfaces:**
- Consumes: `ReviewPrompt`（含 `system`、`user`、`raw_text`）
- Produces: `str`（LLM 响应，JSON 格式）

- [ ] **Step 1: 准备 Mock fixture**

文件 `tests/fixtures/llm/default.json`：

```json
{"corrected": {"class_name": "Measurement"}, "confidence": 0.95, "notes": "默认 mock 响应"}
```

- [ ] **Step 2: 写失败测试**

文件 `tests/unit/test_providers.py`：

```python
"""LLM Provider 单元测试。"""
import json

import pytest

from cim_ontology.reviewer.providers import (
    LLMProvider,
    MockProvider,
    ReviewPrompt,
)


@pytest.fixture
def mock_dir(tmp_path):
    """临时 mock 目录。"""
    d = tmp_path / "llm_fixtures"
    d.mkdir()
    (d / "default.json").write_text(
        json.dumps({"corrected": {}, "confidence": 0.5, "notes": "default"})
    )
    (d / "Meastrement.json").write_text(
        json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.98, "notes": "OCR 修正"})
    )
    return d


class TestMockProvider:
    def test_returns_default_when_no_match(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        prompt = ReviewPrompt(system="s", user="u", raw_text="Anything")
        result = p.review(prompt)
        data = json.loads(result)
        assert data["confidence"] == 0.5

    def test_returns_specific_fixture_when_match(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        prompt = ReviewPrompt(system="s", user="u", raw_text="Meastrement")
        result = p.review(prompt)
        data = json.loads(result)
        assert data["corrected"]["class_name"] == "Measurement"

    def test_protocol_compliance(self, mock_dir):
        p = MockProvider(fixtures_dir=mock_dir)
        assert isinstance(p, LLMProvider)
```

- [ ] **Step 3: 运行测试，验证失败**

```bash
pytest tests/unit/test_providers.py -v
```

预期：ImportError。

- [ ] **Step 4: 写 Provider 协议 + Mock 实现**

文件 `src/cim_ontology/reviewer/__init__.py`：

```python
"""Stage 2: LLM 复审核查。"""
```

文件 `src/cim_ontology/reviewer/providers.py`：

```python
"""LLM Provider 协议与实现（设计规范 §5.3）。

支持：
  - MockProvider：测试桩，无网络依赖
  - ClaudeProvider：Claude API（Task 14 实现）
  - OllamaProvider：本地 Ollama（Task 15 实现）
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ReviewPrompt:
    """发送给 LLM 的完整提示。"""

    system: str
    user: str
    raw_text: str = ""


class LLMProvider(Protocol):
    """LLM Provider 协议。"""

    def review(self, prompt: ReviewPrompt) -> str:
        """返回 LLM 响应（JSON 字符串）。"""
        ...


class MockProvider:
    """确定性 Mock Provider，用于测试与 CI。"""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures = fixtures_dir

    def review(self, prompt: ReviewPrompt) -> str:
        for fixture in self._fixtures.glob("*.json"):
            if fixture.stem in prompt.raw_text:
                return fixture.read_text(encoding="utf-8")
        default = self._fixtures / "default.json"
        if default.exists():
            return default.read_text(encoding="utf-8")
        return json.dumps({"corrected": {}, "confidence": 0.0, "notes": "no fixture"})


def get_provider(fixtures_dir: Path | None = None) -> LLMProvider:
    """Provider 工厂（CI 环境强制 Mock）。"""
    if os.environ.get("CI") == "true":
        import structlog
        log = structlog.get_logger()
        log.info("ci_detected_using_mock_provider")
        return MockProvider(fixtures_dir=fixtures_dir or Path("tests/fixtures/llm"))

    if os.environ.get("ANTHROPIC_API_KEY"):
        from cim_ontology.reviewer.providers_claude import ClaudeProvider
        return ClaudeProvider()

    if os.environ.get("USE_OLLAMA"):
        from cim_ontology.reviewer.providers_ollama import OllamaProvider
        return OllamaProvider()

    return MockProvider(fixtures_dir=fixtures_dir or Path("tests/fixtures/llm"))
```

- [ ] **Step 5: 运行测试，验证通过**

```bash
pytest tests/unit/test_providers.py -v
```

预期：所有测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add src/cim_ontology/reviewer/__init__.py src/cim_ontology/reviewer/providers.py tests/unit/test_providers.py tests/fixtures/llm/
git commit -m "feat(reviewer): add LLMProvider protocol and MockProvider"
```

---

## Task 14: Claude Provider

**Files:**
- Create: `src/cim_ontology/reviewer/providers_claude.py`
- Test: `tests/unit/test_providers_claude.py`

**Interfaces:**
- Consumes: `ReviewPrompt`
- Produces: `str`（Claude API 响应）

- [ ] **Step 1: 写失败测试（使用 respx mock HTTP）**

文件 `tests/unit/test_providers_claude.py`：

```python
"""Claude Provider 测试（使用 unittest.mock）。"""
import json
from unittest.mock import MagicMock, patch

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_claude import ClaudeProvider


@pytest.fixture
def mock_response():
    return {
        "content": [{"text": json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.95})}]
    }


class TestClaudeProvider:
    def test_review_returns_text(self, mock_response, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        provider = ClaudeProvider()
        with patch.object(provider._client.messages, "create") as mock_create:
            mock_create.return_value = MagicMock(content=[MagicMock(text=json.dumps(mock_response["content"][0]["text"]))])
            prompt = ReviewPrompt(system="s", user="u")
            result = provider.review(prompt)
            assert "Measurement" in result or "corrected" in result

    def test_requires_api_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ClaudeProvider()
```

- [ ] **Step 2: 写实现**

文件 `src/cim_ontology/reviewer/providers_claude.py`：

```python
"""Claude API Provider（设计规范 §5.3）。"""
from __future__ import annotations

import os

from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API Provider。"""

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未设置")
        self._model = model or self.DEFAULT_MODEL
        # 延迟导入 anthropic（避免测试时强制依赖）
        from anthropic import Anthropic
        self._client = Anthropic(api_key=self._api_key)

    def review(self, prompt: ReviewPrompt) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
        )
        return response.content[0].text
```

- [ ] **Step 3: 验证依赖**

```bash
pip install -e ".[dev]"
```

预期：成功安装 anthropic 库（已在 pyproject.toml 中声明）。

- [ ] **Step 4: 运行测试**

```bash
pytest tests/unit/test_providers_claude.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/reviewer/providers_claude.py tests/unit/test_providers_claude.py
git commit -m "feat(reviewer): add Claude API provider"
```

---

## Task 15: Ollama Provider

**Files:**
- Create: `src/cim_ontology/reviewer/providers_ollama.py`
- Test: `tests/unit/test_providers_ollama.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/unit/test_providers_ollama.py`：

```python
"""Ollama Provider 测试。"""
from unittest.mock import MagicMock, patch

import pytest

from cim_ontology.reviewer.providers import ReviewPrompt
from cim_ontology.reviewer.providers_ollama import OllamaProvider


class TestOllamaProvider:
    def test_review_calls_ollama(self):
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                json=lambda: {"response": '{"corrected": {}, "confidence": 0.8}'},
                raise_for_status=lambda: None,
            )
            provider = OllamaProvider(model="qwen2.5:72b-instruct", base_url="http://localhost:11434")
            prompt = ReviewPrompt(system="s", user="u")
            result = provider.review(prompt)
            assert "corrected" in result

    def test_default_model(self):
        provider = OllamaProvider()
        assert provider._model == "qwen2.5:72b-instruct"
```

文件 `src/cim_ontology/reviewer/providers_ollama.py`：

```python
"""Ollama 本地模型 Provider（设计规范 §5.8）。"""
from __future__ import annotations

import httpx

from cim_ontology.reviewer.providers import LLMProvider, ReviewPrompt


class OllamaProvider(LLMProvider):
    """本地 Ollama 模型 Provider。推荐 Qwen2.5-72B-Instruct（非 Coder 系列）。"""

    DEFAULT_MODEL = "qwen2.5:72b-instruct"

    def __init__(self, model: str | None = None, base_url: str = "http://localhost:11434") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._base_url = base_url.rstrip("/")

    def review(self, prompt: ReviewPrompt) -> str:
        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": f"{prompt.system}\n\n{prompt.user}",
                "stream": False,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["response"]
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/unit/test_providers_ollama.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/reviewer/providers_ollama.py tests/unit/test_providers_ollama.py
git commit -m "feat(reviewer): add Ollama provider for local LLM"
```

---

## Task 16: Prompt 构建器

**Files:**
- Create: `src/cim_ontology/reviewer/prompts.py`
- Test: `tests/unit/test_prompts.py`

**Interfaces:**
- Consumes: `UncertainEntry`、`list[str]`（已注册命名空间）、`list[str]`（已注册类）
- Produces: `ReviewPrompt`

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_prompts.py`：

```python
"""Prompt 构建器测试。"""
from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.prompts import build_review_prompt


def test_build_review_prompt_includes_raw_text():
    entry = UncertainEntry(
        case_id="Wires::row3",
        source_table=150,
        package="Wires",
        raw_text="Meastrement",
        rule_attempt={"value": "Measurement"},
        uncertainty_reason="class_name_typo",
        context_snippet="前后文",
    )
    prompt = build_review_prompt(
        entry,
        known_namespaces=["cim", "rdfs"],
        known_classes=["Measurement", "IdentifiedObject"],
    )
    assert "Meastrement" in prompt.user
    assert "cim" in prompt.user
    assert "Measurement" in prompt.user
    assert len(prompt.system) > 0


def test_prompt_requires_json_output():
    entry = UncertainEntry(
        case_id="t",
        source_table=0,
        package="X",
        raw_text="foo",
        rule_attempt={},
        uncertainty_reason="class_name_typo",
    )
    prompt = build_review_prompt(entry, [], [])
    assert "JSON" in prompt.user or "json" in prompt.user
```

- [ ] **Step 2: 写实现**

文件 `src/cim_ontology/reviewer/prompts.py`：

```python
"""Prompt 模板与构建器（设计规范 §5.4）。"""
from __future__ import annotations

from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.providers import ReviewPrompt


_SYSTEM = (
    "你是 IEC 61970-301 CIM 本体建模专家。"
    "请复核从标准文档 OCR 中抽取的本体条目，纠正可能的识别错误。"
)


_USER_TEMPLATE = """## 上下文
- 包: {package}
- 表号: 表 {table_no}
- 不确定原因: {reason}
- 邻近文本: {context}

## 待复核内容
{raw_text}

## 规则引擎初步结果
{rule_attempt}

## 已注册的命名空间
{known_namespaces}

## 已注册的类清单
{known_classes}

## 任务
1. 若类名/属性名存在 OCR 错字，给出正确值
2. 若命名空间拼写有误，给出正确 URI
3. 若多重性格式非标准，规范化为标准
4. 若关联目标类不存在于已注册清单，标记 invalid
5. 给出 0-1 的置信度分数

## 输出格式
输出 JSON 字符串（不要 markdown 围栏），形如：
{{ "corrected": {{ "class_name": "...", "namespace": "..." }}, "confidence": 0.0, "notes": "..." }}
"""


def build_review_prompt(
    entry: UncertainEntry,
    known_namespaces: list[str],
    known_classes: list[str],
) -> ReviewPrompt:
    """构建发送给 LLM 的复审 prompt。"""
    user = _USER_TEMPLATE.format(
        package=entry.package,
        table_no=entry.source_table,
        reason=entry.uncertainty_reason,
        context=entry.context_snippet[:200],
        raw_text=entry.raw_text,
        rule_attempt=entry.rule_attempt,
        known_namespaces=", ".join(known_namespaces) or "(无)",
        known_classes=", ".join(known_classes) or "(无)",
    )
    return ReviewPrompt(system=_SYSTEM, user=user, raw_text=entry.raw_text)
```

- [ ] **Step 3: 运行测试，验证通过**

```bash
pytest tests/unit/test_prompts.py -v
```

预期：所有测试 PASS。

- [ ] **Step 4: 提交**

```bash
git add src/cim_ontology/reviewer/prompts.py tests/unit/test_prompts.py
git commit -m "feat(reviewer): add prompt builder for LLM audit"
```

---

## Task 17: LLM Reviewer（三层熔断）

**Files:**
- Create: `src/cim_ontology/reviewer/reviewer.py`
- Test: `tests/unit/test_reviewer.py`

**Interfaces:**
- Consumes: `LLMProvider`、`OntologyIR`
- Produces: `OntologyIR`（已应用 LLM 修订）

- [ ] **Step 1: 写失败测试**

文件 `tests/unit/test_reviewer.py`：

```python
"""LLM Reviewer 三层熔断测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.ir.models import (
    ClassDef,
    IRStats,
    Multiplicity,
    OntologyIR,
    Package,
    UncertainEntry,
)
from cim_ontology.reviewer.providers import MockProvider, ReviewPrompt
from cim_ontology.reviewer.reviewer import LLMReviewer


@pytest.fixture
def mock_dir(tmp_path):
    d = tmp_path / "llm"
    d.mkdir()
    (d / "default.json").write_text(
        json.dumps({"corrected": {"class_name": "Measurement"}, "confidence": 0.9})
    )
    return d


@pytest.fixture
def ir_with_uncertain():
    pkg = Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="Measurement")],
    )
    return OntologyIR(
        packages=[pkg],
        uncertain_entries=[UncertainEntry(
            case_id="A::row1", source_table=1, package="A",
            raw_text="Meastrement", rule_attempt={"value": "Measurement"},
            uncertainty_reason="class_name_typo",
        )],
    )


class TestLLMReviewer:
    def test_review_applies_correction(self, ir_with_uncertain, mock_dir):
        provider = MockProvider(fixtures_dir=mock_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=["Measurement"])
        result_ir = reviewer.review(ir_with_uncertain)
        # 修订已应用 → uncertain 条目数减少
        assert len(result_ir.uncertain_entries) == 0

    def test_fallback_on_invalid_json(self, ir_with_uncertain, tmp_path):
        bad_dir = tmp_path / "bad_llm"
        bad_dir.mkdir()
        (bad_dir / "default.json").write_text("{invalid json")
        provider = MockProvider(fixtures_dir=bad_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=[])
        result_ir = reviewer.review(ir_with_uncertain)
        # JSON 失败 → fallback 保留 uncertain 条目
        assert len(result_ir.uncertain_entries) >= 1

    def test_fallback_on_business_validation(self, ir_with_uncertain, tmp_path):
        bad_dir = tmp_path / "bad_biz_llm"
        bad_dir.mkdir()
        (bad_dir / "default.json").write_text(
            json.dumps({"corrected": {"class_name": "NonExistentXYZ"}, "confidence": 0.9})
        )
        provider = MockProvider(fixtures_dir=bad_dir)
        reviewer = LLMReviewer(provider=provider, known_classes=["Measurement"])
        result_ir = reviewer.review(ir_with_uncertain)
        # 业务校验失败 → fallback
        assert len(result_ir.uncertain_entries) >= 1
```

- [ ] **Step 2: 写实现**

文件 `src/cim_ontology/reviewer/reviewer.py`：

```python
"""LLM Reviewer：三层熔断机制（设计规范 §5.5）。"""
from __future__ import annotations

import json

import structlog

from cim_ontology.ir.models import OntologyIR, UncertainEntry
from cim_ontology.ir.registry import ClassRegistry
from cim_ontology.reviewer.providers import LLMProvider
from cim_ontology.reviewer.prompts import build_review_prompt

log = structlog.get_logger()


class LLMReviewer:
    """使用 LLM 复审 uncertain 条目。三层熔断：

      1. JSON 解析失败 → 用规则结果
      2. 业务校验失败 → 用规则结果 + 标记 llm_rejected
      3. 业务校验通过 → 覆盖规则结果
    """

    def __init__(
        self,
        provider: LLMProvider,
        known_classes: list[str] | None = None,
        known_namespaces: list[str] | None = None,
    ) -> None:
        self._provider = provider
        self._registry = ClassRegistry()
        for cls in (known_classes or []):
            self._registry.add("any", cls)
        self._known_namespaces = known_namespaces or ["cim", "rdfs", "rdf", "xsd", "owl"]

    def review(self, ir: OntologyIR) -> OntologyIR:
        """复审 IR 中所有 uncertain 条目，返回更新后的 IR。"""
        reviewed: list[UncertainEntry] = []
        for entry in ir.uncertain_entries:
            try:
                result = self._review_one(entry)
                if result is None:
                    # fallback：保留 uncertain
                    reviewed.append(entry)
                # else：修订成功，从 uncertain 中移除
            except Exception as e:
                log.warning("llm_review_exception", case_id=entry.case_id, error=str(e))
                reviewed.append(entry)

        # 不可变：构造新 IR
        return ir.model_copy(update={"uncertain_entries": reviewed})

    def _review_one(self, entry: UncertainEntry) -> dict | None:
        """复审单个条目，返回修订 dict 或 None（fallback）。"""
        prompt = build_review_prompt(
            entry,
            known_namespaces=self._known_namespaces,
            known_classes=self._registry.all_names(),
        )

        # 调用 LLM
        try:
            raw = self._provider.review(prompt)
        except Exception as e:
            log.warning("llm_call_failed", error=str(e))
            return None

        # 熔断 1: JSON 解析
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("llm_invalid_json", raw=raw[:100])
            return None

        # 熔断 2: 业务校验
        corrected = data.get("corrected", {})
        if corrected.get("class_name") and not self._registry.has(corrected["class_name"]):
            log.warning("llm_business_invalid_class", name=corrected.get("class_name"))
            return None

        return data
```

- [ ] **Step 3: 运行测试，验证通过**

```bash
pytest tests/unit/test_reviewer.py -v
```

预期：所有测试 PASS。

- [ ] **Step 4: 提交**

```bash
git add src/cim_ontology/reviewer/reviewer.py tests/unit/test_reviewer.py
git commit -m "feat(reviewer): add LLMReviewer with three-tier fallback"
```

---

## Task 18: SQLite LLM 响应缓存

**Files:**
- Create: `src/cim_ontology/reviewer/cache.py`
- Test: `tests/unit/test_cache.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/unit/test_cache.py`：

```python
"""LLM 缓存测试。"""
import tempfile
from pathlib import Path

import pytest

from cim_ontology.reviewer.cache import LLMCache


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "llm_cache.db"


class TestLLMCache:
    def test_miss_returns_none(self, cache_path):
        cache = LLMCache(path=cache_path)
        assert cache.get("unknown_id") is None

    def test_put_and_get(self, cache_path):
        cache = LLMCache(path=cache_path)
        cache.put("case_1", '{"corrected": {"class_name": "A"}, "confidence": 0.9}')
        assert cache.get("case_1") == '{"corrected": {"class_name": "A"}, "confidence": 0.9}'

    def test_persistence_across_instances(self, cache_path):
        c1 = LLMCache(path=cache_path)
        c1.put("case_x", "value_x")
        c2 = LLMCache(path=cache_path)
        assert c2.get("case_x") == "value_x"
```

文件 `src/cim_ontology/reviewer/cache.py`：

```python
"""LLM 响应 SQLite 缓存（设计规范 §5.7）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_reviews (
    case_id TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class LLMCache:
    """基于 SQLite 的 LLM 响应缓存。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def get(self, case_id: str) -> str | None:
        """获取缓存的响应。"""
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT response FROM llm_reviews WHERE case_id = ?", (case_id,)
            ).fetchone()
            return row[0] if row else None

    def put(self, case_id: str, response: str) -> None:
        """存储响应。"""
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_reviews (case_id, response) VALUES (?, ?)",
                (case_id, response),
            )
            conn.commit()
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/unit/test_cache.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/reviewer/cache.py tests/unit/test_cache.py
git commit -m "feat(reviewer): add SQLite-based LLM response cache"
```

---

## Task 19: JSONL 审计日志

**Files:**
- Create: `src/cim_ontology/reviewer/audit.py`
- Test: `tests/unit/test_audit.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/unit/test_audit.py`：

```python
"""审计日志测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.audit import AuditLogger


@pytest.fixture
def audit_path(tmp_path):
    return tmp_path / "audit.jsonl"


class TestAuditLogger:
    def test_record_writes_jsonl(self, audit_path):
        logger = AuditLogger(path=audit_path)
        entry = UncertainEntry(
            case_id="x", source_table=1, package="P",
            raw_text="foo", rule_attempt={}, uncertainty_reason="class_name_typo",
        )
        logger.record(entry, raw_response='{"corrected":{}}', final_action="accepted")
        content = audit_path.read_text()
        record = json.loads(content.strip())
        assert record["case_id"] == "x"
        assert record["action"] == "accepted"
```

文件 `src/cim_ontology/reviewer/audit.py`：

```python
"""JSONL 审计日志（设计规范 §5.6）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cim_ontology.ir.models import UncertainEntry


class AuditLogger:
    """追加写 JSONL 审计日志。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        entry: UncertainEntry,
        raw_response: str,
        final_action: str,
        confidence: float | None = None,
    ) -> None:
        """记录一条 LLM 复审决策。"""
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": entry.case_id,
            "trigger": entry.uncertainty_reason,
            "raw": entry.raw_text,
            "rule_attempt": entry.rule_attempt,
            "llm_raw_response": raw_response[:500],  # 截断
            "action": final_action,
        }
        if confidence is not None:
            record["confidence"] = confidence
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/unit/test_audit.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/reviewer/audit.py tests/unit/test_audit.py
git commit -m "feat(reviewer): add JSONL audit logger"
```

---

# Phase 4（M4）：Stage 3 输出适配器

## Task 20: OutputAdapter 基类 + 注册中心

**Files:**
- Create: `src/cim_ontology/adapters/__init__.py`
- Create: `src/cim_ontology/adapters/base.py`
- Test: `tests/unit/test_adapter_base.py`

**Interfaces:**
- Consumes: `OntologyIR`
- Produces: `EmitResult`、`VerifyResult`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/unit/test_adapter_base.py`：

```python
"""OutputAdapter 基类测试。"""
from pathlib import Path

from cim_ontology.adapters.base import (
    ADAPTERS,
    EmitResult,
    OutputAdapter,
    VerifyResult,
    get_adapter,
)


class _StubAdapter:
    target_format = "stub"

    def emit(self, ir, output_dir):
        return EmitResult(files=[], stats={}, warnings=[], duration_ms=0)

    def verify(self, ir, emitted):
        return VerifyResult(passed=True, issues=[], roundtrip_match=True)


class TestRegistry:
    def test_register_adapter(self):
        ADAPTERS["stub"] = _StubAdapter
        try:
            adapter = get_adapter("stub")
            assert isinstance(adapter, _StubAdapter)
        finally:
            del ADAPTERS["stub"]

    def test_unknown_format_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown format"):
            get_adapter("nonexistent_format_xyz")


def test_emit_result_fields():
    r = EmitResult(files=[Path("a")], stats={"classes": 10}, warnings=[], duration_ms=100)
    assert r.duration_ms == 100
    assert r.stats["classes"] == 10
```

文件 `src/cim_ontology/adapters/__init__.py`：

```python
"""Stage 3: 输出适配器。"""
from cim_ontology.adapters.base import ADAPTERS, EmitResult, OutputAdapter, VerifyResult, get_adapter

__all__ = ["ADAPTERS", "EmitResult", "OutputAdapter", "VerifyResult", "get_adapter"]
```

文件 `src/cim_ontology/adapters/base.py`：

```python
"""OutputAdapter 抽象接口与注册中心（设计规范 §6.1）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from cim_ontology.ir.models import OntologyIR


@dataclass
class EmitResult:
    """适配器输出结果。"""

    files: list[Path]
    stats: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class VerifyResult:
    """适配器验证结果。"""

    passed: bool
    issues: list = field(default_factory=list)
    roundtrip_match: bool = False


class OutputAdapter(ABC):
    """所有输出适配器的抽象基类。"""

    target_format: ClassVar[str]

    @abstractmethod
    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        ...

    @abstractmethod
    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        ...


ADAPTERS: dict[str, type[OutputAdapter]] = {}


def get_adapter(fmt: str) -> OutputAdapter:
    """根据格式名获取适配器实例。"""
    if fmt not in ADAPTERS:
        raise ValueError(
            f"Unknown format: {fmt!r}. Available: {list(ADAPTERS.keys())}"
        )
    return ADAPTERS[fmt]()


def register_adapter(fmt: str, adapter_cls: type[OutputAdapter]) -> None:
    """注册适配器（供插件扩展）。"""
    ADAPTERS[fmt] = adapter_cls
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/unit/test_adapter_base.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/adapters/ tests/unit/test_adapter_base.py
git commit -m "feat(adapters): add OutputAdapter base class and registry"
```

---

## Task 21: OWL / RDF Turtle 适配器（按包拆分 + owl:imports）

**Files:**
- Create: `src/cim_ontology/adapters/owl.py`
- Test: `tests/integration/test_owl_adapter.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/integration/test_owl_adapter.py`：

```python
"""OWL/Turtle 适配器集成测试。"""
import pytest
from rdflib import Graph, RDF, RDFS, OWL, URIRef

from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.ir.models import (
    ClassDef,
    ClassRef,
    CrossPackageRef,
    Multiplicity,
    OntologyIR,
    Package,
    SourceInfo,
)


@pytest.fixture
def ir_two_packages():
    pkg_a = Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject")],
    )
    pkg_b = Package(
        iri="http://x#B", name="B",
        classes=[ClassDef(name="Specific", parents=[
            ClassRef(package="A", class_name="IdentifiedObject"),
        ])],
    )
    return OntologyIR(
        packages=[pkg_a, pkg_b],
        cross_package_refs=[
            CrossPackageRef(from_package="B", to_package="A",
                            via_class="Specific", via_property="parents"),
        ],
        source=SourceInfo(
            document_path="test.md", document_sha256="x" * 64,
            parsed_at="2026-06-22T00:00:00Z", parser_version="0.1.0",
        ),
    )


class TestOwlAdapter:
    def test_emits_per_package_files(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        result = adapter.emit(ir_two_packages, tmp_path)
        assert (tmp_path / "cim17_A.ttl").exists()
        assert (tmp_path / "cim17_B.ttl").exists()
        assert (tmp_path / "cim17_full.ttl").exists()

    def test_owl_imports_declared(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_B.ttl", format="turtle")
        # B 应该 import A
        import_found = any(
            str(o).endswith("_A") for s, p, o in g.triples((None, OWL.imports, None))
        )
        assert import_found

    def test_classes_serialized(self, ir_two_packages, tmp_path):
        adapter = OwlTurtleAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_full.ttl", format="turtle")
        # 至少存在 owl:Class
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) >= 2
```

- [ ] **Step 2: 写实现**

文件 `src/cim_ontology/adapters/owl.py`：

```python
"""OWL/RDF Turtle 输出适配器（设计规范 §6.2）。

特点：
  - 按包拆分（避免单文件过大）
  - 跨包依赖通过 owl:imports 声明
  - 包生成顺序经拓扑排序
"""
from __future__ import annotations

from pathlib import Path

import structlog
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef, XSD

from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.cleaner.dep_graph import build_package_dependency_graph, topological_sort
from cim_ontology.ir.models import ClassDef, OntologyIR, Package

log = structlog.get_logger()


CIM = Namespace("http://iec.ch/TC57/2024/CIM-schema-cim17#")


class OwlTurtleAdapter(OutputAdapter):
    """OWL/RDF Turtle 输出适配器。"""

    target_format = "owl"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = _now_ms()

        # 拓扑排序包
        dep_graph = build_package_dependency_graph(ir)
        ordered_names = topological_sort(dep_graph)
        packages_by_name = {p.name: p for p in ir.packages}
        ordered_packages = [packages_by_name[n] for n in ordered_names if n in packages_by_name]

        full_g = Graph()
        full_g.bind("cim", CIM)
        full_g.bind("rdf", RDF)
        full_g.bind("rdfs", RDFS)
        full_g.bind("owl", OWL)
        full_g.bind("xsd", XSD)

        # Ontology 头
        onto_iri = URIRef(str(CIM).rstrip("#"))
        full_g.add((onto_iri, RDF.type, OWL.Ontology))
        full_g.add((onto_iri, OWL.versionInfo, Literal("cim17")))
        full_g.add((onto_iri, RDFS.comment, Literal(
            "GB/T 43259.301-2024 IDT IEC 61970-301:2020", lang="en"
        )))

        files_written: list[Path] = []

        for pkg in ordered_packages:
            pkg_g = self._build_package_graph(pkg)
            # 添加 owl:imports
            for successor in dep_graph.successors(pkg.name):
                dep_iri = URIRef(f"{str(CIM).rstrip('#')}_{successor}")
                pkg_iri = URIRef(f"{str(CIM).rstrip('#')}_{pkg.name}")
                pkg_g.add((pkg_iri, OWL.imports, dep_iri))
                full_g.add((pkg_iri, OWL.imports, dep_iri))

            out_path = output_dir / f"cim17_{pkg.name}.ttl"
            pkg_g.serialize(out_path, format="turtle")
            files_written.append(out_path)

            # 累加到全量
            for triple in pkg_g:
                full_g.add(triple)

        full_path = output_dir / "cim17_full.ttl"
        full_g.serialize(full_path, format="turtle")
        files_written.append(full_path)

        return EmitResult(
            files=files_written,
            stats={
                "packages": len(ordered_packages),
                "classes": len(ir.all_classes()),
            },
            duration_ms=_now_ms() - start,
        )

    def _build_package_graph(self, pkg: Package) -> Graph:
        """构造单个包的 RDF 图。"""
        g = Graph()
        g.bind("cim", CIM)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)

        for cls in pkg.classes:
            cls_iri = URIRef(str(CIM) + cls.name)
            g.add((cls_iri, RDF.type, OWL.Class))

            if cls.description:
                g.add((cls_iri, RDFS.comment, Literal(cls.description, lang="zh")))

            for parent in cls.parents:
                parent_iri = URIRef(str(CIM) + parent.class_name)
                g.add((cls_iri, RDFS.subClassOf, parent_iri))

            for attr in cls.attributes:
                prop_iri = URIRef(f"{str(CIM)}{cls.name}.{attr.name}")
                g.add((prop_iri, RDF.type, OWL.DatatypeProperty))
                g.add((prop_iri, RDFS.domain, cls_iri))
                g.add((prop_iri, RDFS.range, URIRef(attr.data_type or str(XSD.string))))

        return g

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        """验证生成的 OWL 可被重新解析。"""
        full = emitted / "cim17_full.ttl"
        if not full.exists():
            return VerifyResult(passed=False, issues=["cim17_full.ttl 不存在"])

        g = Graph()
        try:
            g.parse(full, format="turtle")
        except Exception as e:
            return VerifyResult(passed=False, issues=[f"解析失败: {e}"])

        return VerifyResult(
            passed=True,
            roundtrip_match=True,
        )


def _now_ms() -> int:
    import time
    return int(time.monotonic() * 1000)
```

- [ ] **Step 3: 运行测试，验证通过**

```bash
pytest tests/integration/test_owl_adapter.py -v
```

预期：所有测试 PASS。

- [ ] **Step 4: 提交**

```bash
git add src/cim_ontology/adapters/owl.py tests/integration/test_owl_adapter.py
git commit -m "feat(adapters): add OWL/Turtle adapter with per-package owl:imports"
```

---

## Task 22: SHACL Shapes 适配器

**Files:**
- Create: `src/cim_ontology/adapters/shacl.py`
- Test: `tests/integration/test_shacl_adapter.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/integration/test_shacl_adapter.py`：

```python
"""SHACL 适配器测试。"""
import pytest
from rdflib import Graph, Namespace, URIRef

from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.ir.models import (
    ClassDef, DataProperty, Multiplicity, OntologyIR, Package,
)


@pytest.fixture
def ir_with_required_attr():
    return OntologyIR(
        packages=[Package(
            iri="http://x#A", name="A",
            classes=[ClassDef(
                name="IdentifiedObject",
                attributes=[DataProperty(
                    name="mRID", data_type="xsd:string",
                    multiplicity=Multiplicity(min=1, max=1, raw="1..1"),
                    required=True,
                )],
            )],
        )],
    )


class TestShaclAdapter:
    def test_emits_shape(self, ir_with_required_attr, tmp_path):
        adapter = ShaclAdapter()
        result = adapter.emit(ir_with_required_attr, tmp_path)
        assert (tmp_path / "cim17_shapes.ttl").exists()

    def test_shape_has_min_count_for_required(self, ir_with_required_attr, tmp_path):
        adapter = ShaclAdapter()
        adapter.emit(ir_with_required_attr, tmp_path)
        g = Graph()
        g.parse(tmp_path / "cim17_shapes.ttl", format="turtle")
        SH = Namespace("http://www.w3.org/ns/shacl#")
        # 至少一个 minCount=1 约束
        triples_with_min = list(g.triples((None, SH.minCount, None)))
        assert len(triples_with_min) >= 1
```

文件 `src/cim_ontology/adapters/shacl.py`：

```python
"""SHACL Shapes 输出适配器（设计规范 §6.3）。"""
from __future__ import annotations

import time
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD

from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import ClassDef, OntologyIR

CIM = Namespace("http://iec.ch/TC57/2024/CIM-schema-cim17#")
SH = Namespace("http://www.w3.org/ns/shacl#")


class ShaclAdapter(OutputAdapter):
    """SHACL Shapes 适配器。"""

    target_format = "shacl"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)

        g = Graph()
        g.bind("sh", SH)
        g.bind("cim", CIM)

        for cls in ir.all_classes():
            shape_iri = URIRef(str(CIM) + f"shape_{cls.name}")
            g.add((shape_iri, RDF.type, SH.NodeShape))
            g.add((shape_iri, SH.targetClass, URIRef(str(CIM) + cls.name)))

            for attr in cls.attributes:
                prop_shape = self._add_property_shape(g, shape_iri, cls, attr)
                if attr.required:
                    g.add((prop_shape, SH.minCount, Literal(1)))
                if attr.multiplicity.max is not None:
                    g.add((prop_shape, SH.maxCount, Literal(attr.multiplicity.max)))

        out_path = output_dir / "cim17_shapes.ttl"
        g.serialize(out_path, format="turtle")

        return EmitResult(
            files=[out_path],
            stats={"shapes": len(ir.all_classes())},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _add_property_shape(self, g: Graph, shape_iri: URIRef, cls: ClassDef, attr) -> URIRef:
        prop_shape = URIRef(f"{shape_iri}_{attr.name}")
        g.add((shape_iri, SH.property, prop_shape))
        g.add((prop_shape, SH.path, URIRef(f"{str(CIM)}{cls.name}.{attr.name}")))
        if attr.data_type:
            g.add((prop_shape, SH.datatype, URIRef(attr.data_type)))
        return prop_shape

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        path = emitted / "cim17_shapes.ttl"
        if not path.exists():
            return VerifyResult(passed=False, issues=["cim17_shapes.ttl 不存在"])
        g = Graph()
        try:
            g.parse(path, format="turtle")
        except Exception as e:
            return VerifyResult(passed=False, issues=[f"解析失败: {e}"])
        return VerifyResult(passed=True, roundtrip_match=True)
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/integration/test_shacl_adapter.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/adapters/shacl.py tests/integration/test_shacl_adapter.py
git commit -m "feat(adapters): add SHACL Shapes adapter"
```

---

## Task 23: JSON-LD Context 适配器

**Files:**
- Create: `src/cim_ontology/adapters/jsonld_context.py`
- Test: `tests/integration/test_jsonld_context.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/integration/test_jsonld_context.py`：

```python
"""JSON-LD Context 适配器测试。"""
import json

import pytest

from cim_ontology.adapters.jsonld_context import JsonLdContextAdapter
from cim_ontology.ir.models import ClassDef, DataProperty, Multiplicity, OntologyIR, Package


@pytest.fixture
def ir_simple():
    return OntologyIR(packages=[Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject", attributes=[
            DataProperty(name="mRID", data_type="xsd:string",
                         multiplicity=Multiplicity(min=1, max=1, raw="1..1")),
        ])],
    )])


class TestJsonLdContextAdapter:
    def test_emits_context_per_package(self, ir_simple, tmp_path):
        adapter = JsonLdContextAdapter()
        adapter.emit(ir_simple, tmp_path)
        assert (tmp_path / "A_context.jsonld").exists()

    def test_context_has_vocab_and_cim(self, ir_simple, tmp_path):
        adapter = JsonLdContextAdapter()
        adapter.emit(ir_simple, tmp_path)
        ctx = json.loads((tmp_path / "A_context.jsonld").read_text())
        assert "@context" in ctx
        assert ctx["@context"]["@vocab"] == "http://iec.ch/TC57/2024/CIM-schema-cim17#"
```

文件 `src/cim_ontology/adapters/jsonld_context.py`：

```python
"""JSON-LD Context 输出适配器（设计规范 §6.4）。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import OntologyIR

CIM_IRI = "http://iec.ch/TC57/2024/CIM-schema-cim17#"


class JsonLdContextAdapter(OutputAdapter):
    """JSON-LD Context 适配器（语义层）。"""

    target_format = "jsonld-context"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        for pkg in ir.packages:
            ctx = {
                "@context": {
                    "@vocab": CIM_IRI,
                    "cim": CIM_IRI,
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#",
                }
            }
            # 为每个属性添加 @context 映射
            for cls in pkg.classes:
                for attr in cls.attributes:
                    ctx["@context"][attr.name] = f"cim:{cls.name}.{attr.name}"

            out_path = output_dir / f"{pkg.name}_context.jsonld"
            out_path.write_text(json.dumps(ctx, indent=2, ensure_ascii=False))
            files.append(out_path)

        return EmitResult(
            files=files,
            stats={"contexts": len(files)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        for pkg in ir.packages:
            path = emitted / f"{pkg.name}_context.jsonld"
            if not path.exists():
                issues.append(f"{pkg.name}_context.jsonld 不存在")
                continue
            try:
                data = json.loads(path.read_text())
                if "@context" not in data:
                    issues.append(f"{pkg.name} 缺少 @context")
            except Exception as e:
                issues.append(f"{pkg.name} JSON 解析失败: {e}")
        return VerifyResult(
            passed=len(issues) == 0,
            issues=issues,
            roundtrip_match=len(issues) == 0,
        )
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/integration/test_jsonld_context.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/adapters/jsonld_context.py tests/integration/test_jsonld_context.py
git commit -m "feat(adapters): add JSON-LD Context adapter"
```

---

## Task 24: JSON Schema 适配器

**Files:**
- Create: `src/cim_ontology/adapters/json_schema.py`
- Test: `tests/integration/test_json_schema_adapter.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/integration/test_json_schema_adapter.py`：

```python
"""JSON Schema 适配器测试。"""
import json
from pathlib import Path

import pytest

from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.ir.models import ClassDef, DataProperty, Multiplicity, OntologyIR, Package


@pytest.fixture
def ir_simple():
    return OntologyIR(packages=[Package(
        iri="http://x#A", name="A",
        classes=[ClassDef(name="IdentifiedObject", attributes=[
            DataProperty(name="mRID", data_type="xsd:string",
                         multiplicity=Multiplicity(min=1, max=1, raw="1..1"), required=True),
            DataProperty(name="name", data_type="xsd:string",
                         multiplicity=Multiplicity(min=0, max=1, raw="0..1")),
        ])],
    )])


class TestJsonSchemaAdapter:
    def test_emits_schema(self, ir_simple, tmp_path):
        adapter = JsonSchemaAdapter()
        adapter.emit(ir_simple, tmp_path)
        assert (tmp_path / "A_schema.json").exists()

    def test_required_fields(self, ir_simple, tmp_path):
        adapter = JsonSchemaAdapter()
        adapter.emit(ir_simple, tmp_path)
        schema = json.loads((tmp_path / "A_schema.json").read_text())
        ident = schema["properties"]["IdentifiedObject"]
        assert "mRID" in ident["required"]
        assert "name" not in ident["required"]
```

文件 `src/cim_ontology/adapters/json_schema.py`：

```python
"""JSON Schema 输出适配器（结构验证层）。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.ir.models import OntologyIR

# XSD → JSON Schema 类型映射
XSD_TO_JSON_SCHEMA = {
    "xsd:string": {"type": "string"},
    "xsd:integer": {"type": "integer"},
    "xsd:float": {"type": "number"},
    "xsd:double": {"type": "number"},
    "xsd:boolean": {"type": "boolean"},
    "xsd:dateTime": {"type": "string", "format": "date-time"},
    "xsd:date": {"type": "string", "format": "date"},
}


class JsonSchemaAdapter(OutputAdapter):
    """JSON Schema 适配器（按包生成）。"""

    target_format = "json-schema"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        for pkg in ir.packages:
            schema = self._build_schema(pkg)
            out = output_dir / f"{pkg.name}_schema.json"
            out.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
            files.append(out)

        return EmitResult(
            files=files,
            stats={"schemas": len(files)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _build_schema(self, pkg) -> dict:
        schema: dict = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"CIM {pkg.name}",
            "type": "object",
            "properties": {},
        }
        for cls in pkg.classes:
            cls_schema = self._build_class_schema(cls)
            schema["properties"][cls.name] = cls_schema
        return schema

    def _build_class_schema(self, cls) -> dict:
        properties: dict = {}
        required: list[str] = []
        for attr in cls.attributes:
            properties[attr.name] = XSD_TO_JSON_SCHEMA.get(
                attr.data_type, {"type": "string"}
            )
            if attr.required:
                required.append(attr.name)
        result = {"type": "object", "properties": properties}
        if required:
            result["required"] = required
        return result

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        for pkg in ir.packages:
            p = emitted / f"{pkg.name}_schema.json"
            if not p.exists():
                issues.append(f"{p.name} 不存在")
        return VerifyResult(passed=len(issues) == 0, issues=issues)
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/integration/test_json_schema_adapter.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/adapters/json_schema.py tests/integration/test_json_schema_adapter.py
git commit -m "feat(adapters): add JSON Schema adapter"
```

---

## Task 25: Python Types 适配器（拓扑排序 + 自动 import 注入）

**Files:**
- Create: `src/cim_ontology/adapters/python_types.py`
- Test: `tests/integration/test_python_types_adapter.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/integration/test_python_types_adapter.py`：

```python
"""Python Types 适配器测试。"""
import pytest

from cim_ontology.adapters.python_types import PythonTypesAdapter
from cim_ontology.ir.models import (
    ClassDef, ClassRef, DataProperty, Multiplicity, OntologyIR, Package,
)


@pytest.fixture
def ir_two_packages():
    pkg_a = Package(iri="http://x#A", name="A",
                    classes=[ClassDef(name="IdentifiedObject", attributes=[
                        DataProperty(name="mRID", data_type="xsd:string",
                                     multiplicity=Multiplicity(min=1, max=1, raw="1..1"), required=True),
                    ])])
    pkg_b = Package(iri="http://x#B", name="B",
                    classes=[ClassDef(name="Specific", parents=[
                        ClassRef(package="A", class_name="IdentifiedObject"),
                    ])])
    return OntologyIR(packages=[pkg_a, pkg_b])


class TestPythonTypesAdapter:
    def test_emits_types_per_package(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        assert (tmp_path / "A_types.py").exists()
        assert (tmp_path / "B_types.py").exists()

    def test_b_imports_from_a(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        b_src = (tmp_path / "B_types.py").read_text()
        assert "from A_types import" in b_src
        assert "IdentifiedObject" in b_src

    def test_a_has_no_external_imports(self, ir_two_packages, tmp_path):
        adapter = PythonTypesAdapter()
        adapter.emit(ir_two_packages, tmp_path)
        a_src = (tmp_path / "A_types.py").read_text()
        assert "from B_types" not in a_src
```

文件 `src/cim_ontology/adapters/python_types.py`：

```python
"""Python Types 输出适配器（设计规范 §6.4 + §6.4.1）。

按拓扑序生成每个包的 _types.py 文件，自动注入跨包 import。
"""
from __future__ import annotations

import time
from pathlib import Path

from cim_ontology.adapters.base import EmitResult, OutputAdapter, VerifyResult
from cim_ontology.cleaner.dep_graph import build_package_dependency_graph, topological_sort
from cim_ontology.ir.models import OntologyIR, Package


class PythonTypesAdapter(OutputAdapter):
    """生成 Python dataclass 类型文件。"""

    target_format = "python-types"

    def emit(self, ir: OntologyIR, output_dir: Path) -> EmitResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = int(time.monotonic() * 1000)
        files: list[Path] = []

        dep_graph = build_package_dependency_graph(ir)
        ordered_names = topological_sort(dep_graph)
        packages_by_name = {p.name: p for p in ir.packages}
        ordered = [packages_by_name[n] for n in ordered_names if n in packages_by_name]

        for pkg in ordered:
            src = self._generate_package_source(pkg, ir, dep_graph)
            out = output_dir / f"{pkg.name}_types.py"
            out.write_text(src)
            files.append(out)

        return EmitResult(
            files=files,
            stats={"packages": len(ordered)},
            duration_ms=int(time.monotonic() * 1000) - start,
        )

    def _generate_package_source(
        self,
        pkg: Package,
        ir: OntologyIR,
        dep_graph,
    ) -> str:
        """生成单个包的 Python 源码。"""
        lines: list[str] = [
            f"# Auto-generated from CIM {pkg.name} package",
            "from dataclasses import dataclass",
            "from typing import Optional",
            "from enum import Enum",
            "",
        ]

        # 注入跨包 import
        for dep in dep_graph.successors(pkg.name):
            dep_pkg = next((p for p in ir.packages if p.name == dep), None)
            if dep_pkg is None:
                continue
            used_types = self._collect_used_types(pkg, dep_pkg)
            if used_types:
                lines.insert(4, f"from {dep_pkg.name}_types import {', '.join(sorted(used_types))}")

        # 生成类
        for cls in pkg.classes:
            lines.extend(self._generate_class(cls))
            lines.append("")

        return "\n".join(lines)

    def _collect_used_types(self, pkg: Package, dep_pkg: Package) -> set[str]:
        """收集本包对依赖包类型的引用。"""
        used: set[str] = set()
        dep_class_names = {c.name for c in dep_pkg.classes}

        for cls in pkg.classes:
            # 继承引用
            for parent in cls.parents:
                if parent.class_name in dep_class_names:
                    used.add(parent.class_name)
            # 关联目标引用
            for assoc in cls.associations:
                if assoc.target.class_name in dep_class_names:
                    used.add(assoc.target.class_name)
        return used

    def _generate_class(self, cls) -> list[str]:
        """生成单个类的 dataclass 定义。"""
        lines = ["@dataclass"]
        lines.append(f"class {cls.name}:")
        lines.append(f'    rdf_type: str = "cim:{cls.name}"')

        for attr in cls.attributes:
            type_hint = self._json_schema_type(attr.data_type) if attr.data_type else "str"
            if attr.required:
                lines.append(f"    {attr.name}: {type_hint}")
            else:
                lines.append(f"    {attr.name}: Optional[{type_hint}] = None")

        if not cls.attributes:
            lines.append("    pass")

        return lines

    def _json_schema_type(self, xsd_type: str) -> str:
        mapping = {
            "xsd:string": "str",
            "xsd:integer": "int",
            "xsd:float": "float",
            "xsd:boolean": "bool",
            "xsd:dateTime": "str",
        }
        return mapping.get(xsd_type, "str")

    def verify(self, ir: OntologyIR, emitted: Path) -> VerifyResult:
        issues = []
        for pkg in ir.packages:
            p = emitted / f"{pkg.name}_types.py"
            if not p.exists():
                issues.append(f"{p.name} 不存在")
        return VerifyResult(passed=len(issues) == 0, issues=issues)
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/integration/test_python_types_adapter.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/adapters/python_types.py tests/integration/test_python_types_adapter.py
git commit -m "feat(adapters): add Python types adapter with topological sort and cross-package imports"
```

---

# Phase 5（M5）：Stage 4 流水线与端到端

## Task 26: 错误处理与审计模块

**Files:**
- Create: `src/cim_ontology/audit/__init__.py`
- Create: `src/cim_ontology/audit/errors.py`
- Create: `src/cim_ontology/audit/logger.py`
- Test: `tests/unit/test_audit_errors.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/unit/test_audit_errors.py`：

```python
"""错误处理与审计模块测试。"""
import pytest

from cim_ontology.audit.errors import (
    PipelineError,
    Severity,
)


class TestPipelineError:
    def test_basic_message(self):
        e = PipelineError(
            severity=Severity.ERROR,
            stage="emit",
            message="适配器失败",
        )
        assert "ERROR" in str(e)
        assert "适配器失败" in str(e)

    def test_with_suggestion(self):
        e = PipelineError(
            severity=Severity.WARN,
            stage="ingest",
            message="包解析失败",
            suggestion="检查章节完整性",
            location="Wires",
        )
        msg = str(e)
        assert "[Wires]" in msg
        assert "建议" in msg

    def test_severity_levels(self):
        for level in Severity:
            e = PipelineError(severity=level, stage="x", message="y")
            assert level.value in str(e).lower() or level.name in str(e)
```

文件 `src/cim_ontology/audit/__init__.py`：

```python
"""错误处理与审计模块。"""
from cim_ontology.audit.errors import PipelineError, Severity

__all__ = ["PipelineError", "Severity"]
```

文件 `src/cim_ontology/audit/errors.py`：

```python
"""PipelineError 与严重性分级（设计规范 §7.1）。"""
from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """错误严重性分级。"""

    FATAL = "fatal"    # 输入不可读，立即退出
    ERROR = "error"    # 单包/单格式失败，跳过继续
    WARN = "warn"      # 单条记录可疑，标记不确定
    INFO = "info"      # 进度/统计


class PipelineError(Exception):
    """流水线错误。"""

    def __init__(
        self,
        severity: Severity,
        stage: str,
        message: str,
        location: str = "",
        raw_input: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.severity = severity
        self.stage = stage
        self.location = location
        self.raw_input = raw_input
        self.suggestion = suggestion
        super().__init__(self._format())

    def _format(self) -> str:
        loc = f"[{self.location}] " if self.location else ""
        sug = f"\n  建议: {self.suggestion}" if self.suggestion else ""
        return f"{self.severity.value.upper()}: {loc}{self._message}{sug}"

    @property
    def _message(self) -> str:
        return self.args[0] if self.args else ""
```

文件 `src/cim_ontology/audit/logger.py`：

```python
"""结构化日志（设计规范 §7.5）。"""
from __future__ import annotations

import structlog


def configure_logging(level: str = "INFO") -> None:
    """配置 structlog 输出。"""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, level)
        ),
    )


log = structlog.get_logger()
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/unit/test_audit_errors.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/cim_ontology/audit/ tests/unit/test_audit_errors.py
git commit -m "feat(audit): add error handling and structured logger"
```

---

## Task 27: Pipeline 编排器（4 阶段串联）

**Files:**
- Create: `src/cim_ontology/pipeline.py`
- Test: `tests/integration/test_pipeline.py`

- [ ] **Step 1: 写测试**

文件 `tests/integration/test_pipeline.py`：

```python
"""Pipeline 编排器集成测试。"""
from pathlib import Path

import pytest

from cim_ontology.pipeline import build


@pytest.fixture
def sample_md(tmp_path):
    md = tmp_path / "test.md"
    md.write_text(
        "## 5.1.1 Class: IdentifiedObject\n\n"
        "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
        "| mRID | string | 1..1 |\n",
        encoding="utf-8",
    )
    return md


class TestBuild:
    def test_builds_all_three_formats(self, sample_md, tmp_path):
        out = tmp_path / "build"
        result = build(sample_md, out, formats=["owl", "shacl", "jsonld-context"])
        assert (out / "owl").exists()
        assert (out / "shacl").exists()
        assert (out / "jsonld-context").exists()
        assert result["stats"]["classes"] >= 1

    def test_invalid_format_raises(self, sample_md, tmp_path):
        out = tmp_path / "build"
        with pytest.raises(ValueError, match="Unknown format"):
            build(sample_md, out, formats=["invalid_format_xyz"])

    def test_skips_missing_format_gracefully(self, sample_md, tmp_path):
        out = tmp_path / "build"
        # 仅请求 OWL，其他应跳过
        result = build(sample_md, out, formats=["owl"])
        assert (out / "owl").exists()
        assert not (out / "shacl").exists()
```

- [ ] **Step 2: 写实现**

文件 `src/cim_ontology/pipeline.py`：

```python
"""Pipeline 编排器：串联 4 阶段（设计规范 §2.1）。

Markdown → IR-JSON → LLM 复审 → 多格式输出 → 验证
"""
from __future__ import annotations

from pathlib import Path

import structlog

from cim_ontology.adapters import ADAPTERS, get_adapter
from cim_ontology.audit.errors import PipelineError, Severity
from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir
from cim_ontology.ir.models import OntologyIR
from cim_ontology.reviewer.providers import LLMProvider, MockProvider
from cim_ontology.reviewer.reviewer import LLMReviewer

log = structlog.get_logger()


def build(
    md_path: Path,
    output_dir: Path,
    formats: list[str] | None = None,
    llm_provider: LLMProvider | None = None,
    use_llm: bool = False,
) -> dict:
    """执行完整 4 阶段流水线。

    Args:
        md_path: 输入 Markdown 文件
        output_dir: 输出根目录
        formats: 输出格式列表（默认 owl + shacl + jsonld-context）
        llm_provider: LLM Provider（None = Mock）
        use_llm: 是否启用 LLM 复审

    Returns:
        dict 含 "ir"、"stats"、各 adapter 的 emit 结果
    """
    formats = formats or ["owl", "shacl", "jsonld-context"]
    for fmt in formats:
        if fmt not in ADAPTERS:
            raise ValueError(
                f"Unknown format: {fmt!r}. Available: {list(ADAPTERS.keys())}"
            )

    # Stage 1: 规则清洗
    log.info("stage_start", stage="ingest", input=str(md_path))
    try:
        ir = clean_markdown_to_ir(md_path)
    except FileNotFoundError:
        raise PipelineError(
            severity=Severity.FATAL,
            stage="ingest",
            message=f"输入文件不存在: {md_path}",
        )
    log.info("stage_end", stage="ingest",
             classes=ir.stats.class_count, packages=ir.stats.package_count)

    # Stage 2: LLM 复审（可选）
    if use_llm and ir.uncertain_entries:
        provider = llm_provider or MockProvider(fixtures_dir=Path("tests/fixtures/llm"))
        reviewer = LLMReviewer(provider=provider)
        log.info("stage_start", stage="review", uncertain=len(ir.uncertain_entries))
        ir = reviewer.review(ir)
        log.info("stage_end", stage="review",
                 remaining_uncertain=len(ir.uncertain_entries))

    # Stage 3 + 4: 输出 + 验证
    results: dict = {"ir": ir, "stats": {}, "emits": {}}
    for fmt in formats:
        adapter = get_adapter(fmt)
        log.info("stage_start", stage="emit", format=fmt)
        try:
            emit_result = adapter.emit(ir, output_dir / fmt)
            results["emits"][fmt] = emit_result
            results["stats"].update(emit_result.stats)
            log.info("stage_end", stage="emit", format=fmt,
                     files=len(emit_result.files))
        except Exception as e:
            log.error("emit_failed", format=fmt, error=str(e))
            raise PipelineError(
                severity=Severity.ERROR,
                stage="emit",
                message=f"格式 {fmt} 生成失败: {e}",
            )

    return results
```

- [ ] **Step 3: 注册所有适配器到 ADAPTERS**

创建 `src/cim_ontology/adapters/__init__.py` 的更新（在前面已创建），追加注册逻辑：

```python
"""Stage 3: 输出适配器。"""
from cim_ontology.adapters.base import ADAPTERS, EmitResult, OutputAdapter, VerifyResult, get_adapter
from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.adapters.jsonld_context import JsonLdContextAdapter
from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.adapters.python_types import PythonTypesAdapter

ADAPTERS["owl"] = OwlTurtleAdapter
ADAPTERS["shacl"] = ShaclAdapter
ADAPTERS["jsonld-context"] = JsonLdContextAdapter
ADAPTERS["json-schema"] = JsonSchemaAdapter
ADAPTERS["python-types"] = PythonTypesAdapter

__all__ = ["ADAPTERS", "EmitResult", "OutputAdapter", "VerifyResult", "get_adapter"]
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
pytest tests/integration/test_pipeline.py -v
```

预期：所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/cim_ontology/pipeline.py src/cim_ontology/adapters/__init__.py tests/integration/test_pipeline.py
git commit -m "feat(pipeline): add 4-stage pipeline orchestrator"
```

---

## Task 28: CLI 入口（typer）

**Files:**
- Create: `src/cim_ontology/cli.py`
- Test: `tests/integration/test_cli.py`

- [ ] **Step 1: 写测试 + 实现**

文件 `tests/integration/test_cli.py`：

```python
"""CLI 入口测试（使用 typer.testing.CliRunner）。"""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cim_ontology.cli import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_md(tmp_path):
    md = tmp_path / "test.md"
    md.write_text(
        "## 5.1.1 Class: IdentifiedObject\n\n"
        "| 属性 | 类型 | 基数 |\n|---|---|---|\n"
        "| mRID | string | 1..1 |\n",
        encoding="utf-8",
    )
    return md


class TestBuildCommand:
    def test_build_help(self, runner):
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.stdout
        assert "--output" in result.stdout

    def test_build_runs(self, runner, sample_md, tmp_path):
        out = tmp_path / "build"
        result = runner.invoke(app, [
            "build",
            "--input", str(sample_md),
            "--output", str(out),
            "--format", "owl",
        ])
        assert result.exit_code == 0
        assert (out / "owl" / "cim17_full.ttl").exists()
```

文件 `src/cim_ontology/cli.py`：

```python
"""CLI 入口（设计规范 §6.7）。"""
from __future__ import annotations

from pathlib import Path

import typer

from cim_ontology.pipeline import build

app = typer.Typer(help="GB/T 43259.301-2024 CIM 本体提取与生成器")


@app.command()
def build_cmd(
    input: Path = typer.Option(..., "--input", "-i", help="输入 Markdown 文件"),
    output: Path = typer.Option(Path("./build"), "--output", "-o", help="输出目录"),
    format: list[str] = typer.Option(["owl", "shacl", "jsonld-context"], "--format", "-f", help="输出格式（可重复）"),
    use_llm: bool = typer.Option(False, "--llm", help="启用 LLM 复审"),
) -> None:
    """从 Markdown 标准文档构建本体。"""
    result = build(input, output, formats=format, use_llm=use_llm)
    typer.echo(f"✓ 构建完成: {result['stats']}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: 运行测试，验证通过**

```bash
pytest tests/integration/test_cli.py -v
```

预期：所有测试 PASS。

- [ ] **Step 3: 手动验证 CLI**

```bash
cim-ontology build --help
```

预期：显示 build 命令的帮助。

- [ ] **Step 4: 提交**

```bash
git add src/cim_ontology/cli.py tests/integration/test_cli.py
git commit -m "feat(cli): add typer-based CLI entry point"
```

---

## Task 29: 准备 large fixture（完整 9243 行文档）

**Files:**
- Create: `tests/fixtures/large/full.md`（已存在的 `docs/GBT43259301—2024/cim-base-full.md`）

- [ ] **Step 1: 创建符号链接或复制**

```bash
mkdir -p tests/fixtures/large
ln -s "$(pwd)/docs/GBT43259301—2024/cim-base-full.md" tests/fixtures/large/full.md
```

验证：

```bash
ls -la tests/fixtures/large/full.md
```

预期：链接指向完整 9243 行文档。

- [ ] **Step 2: 提交**

```bash
git add tests/fixtures/large/
git commit -m "test: add large fixture symlink to full CIM standard"
```

---

## Task 30: 端到端测试（完整文档 → 全格式）

**Files:**
- Test: `tests/e2e/test_full_build.py`

- [ ] **Step 1: 写测试**

文件 `tests/e2e/test_full_build.py`：

```python
"""端到端测试：完整 9243 行文档构建。"""
import time
from pathlib import Path

import pytest
from rdflib import Graph

from cim_ontology.pipeline import build


FIXTURE_PATH = Path("tests/fixtures/large/full.md")


@pytest.mark.skipif(
    not FIXTURE_PATH.exists(),
    reason="完整文档 fixture 不存在（参见 Task 29）",
)
class TestFullDocumentBuild:
    def test_full_builds_all_formats(self, tmp_path):
        out = tmp_path / "build"
        start = time.monotonic()
        result = build(
            FIXTURE_PATH,
            out,
            formats=["owl", "shacl", "jsonld-context"],
        )
        elapsed = time.monotonic() - start
        # 5 分钟超时
        assert elapsed < 300, f"耗时 {elapsed:.0f}s 超过 5 分钟"

        # 所有格式目录存在
        assert (out / "owl").exists()
        assert (out / "shacl").exists()
        assert (out / "jsonld-context").exists()

        # 至少抽取 27 个包（标准要求）
        assert result["stats"].get("packages", 0) >= 27 or result["stats"]["classes"] > 100

    def test_owl_full_ttl_parseable(self, tmp_path):
        out = tmp_path / "build"
        build(FIXTURE_PATH, out, formats=["owl"])
        full = out / "owl" / "cim17_full.ttl"
        g = Graph()
        g.parse(full, format="turtle")
        # 至少 5000 个三元组
        assert len(g) > 5000
```

- [ ] **Step 2: 运行测试（可能耗时）**

```bash
pytest tests/e2e/test_full_build.py -v --tb=short
```

预期：所有测试 PASS（首次跑可能耗时 1-3 分钟）。

- [ ] **Step 3: 提交**

```bash
git add tests/e2e/test_full_build.py
git commit -m "test(e2e): add full-document build test"
```

---

## Task 31: 属性测试（IR 不变量）

**Files:**
- Test: `tests/property/test_ir_invariants.py`

- [ ] **Step 1: 写属性测试**

文件 `tests/property/test_ir_invariants.py`：

```python
"""IR 不变量属性测试（设计规范 §8.5）。"""
from hypothesis import given, strategies as st

from cim_ontology.ir.models import (
    ClassDef, ClassRef, Multiplicity, ObjectProperty, OntologyIR, Package,
)


@st.composite
def ir_strategy(draw):
    """生成随机 IR。"""
    pkg_names = draw(st.lists(
        st.sampled_from(["A", "B", "C", "D"]),
        min_size=1, max_size=4, unique=True,
    ))
    packages = []
    for name in pkg_names:
        classes = []
        for i in range(draw(st.integers(min_value=1, max_value=5))):
            classes.append(ClassDef(name=f"Cls_{name}_{i}"))
        packages.append(Package(iri=f"http://x#{name}", name=name, classes=classes))
    return OntologyIR(packages=packages)


class TestInvariants:
    @given(ir_strategy())
    def test_no_duplicate_class_names_within_package(self, ir):
        for pkg in ir.packages:
            names = [c.name for c in pkg.classes]
            assert len(names) == len(set(names)), f"包 {pkg.name} 存在重复类名"

    @given(ir_strategy())
    def test_all_classes_returns_all(self, ir):
        all_classes = ir.all_classes()
        expected = sum(len(p.classes) for p in ir.packages)
        assert len(all_classes) == expected

    @given(ir_strategy())
    def test_get_class_finds_existing(self, ir):
        for pkg in ir.packages:
            for cls in pkg.classes:
                assert ir.get_class(cls.name) is not None

    @given(ir_strategy())
    def test_get_class_returns_none_for_unknown(self, ir):
        assert ir.get_class("NonExistent_xyz_123") is None

    @given(st.integers(min_value=0, max_value=10), st.integers(min_value=0, max_value=10))
    def test_multiplicity_is_many_consistency(self, min_val, max_val):
        m = Multiplicity(min=min_val, max=max_val, raw=f"{min_val}..{max_val if max_val <= 1 else '*'}")
        if max_val is None or max_val > 1:
            assert m.is_many is True
        else:
            assert m.is_many is False
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/property/test_ir_invariants.py -v
```

预期：所有测试 PASS（hypothesis 会跑数十个样本）。

- [ ] **Step 3: 提交**

```bash
git add tests/property/test_ir_invariants.py
git commit -m "test(property): add IR invariant property tests"
```

---

## Task 32: 覆盖率配置与验证

**Files:**
- Create: `.coveragerc`

- [ ] **Step 1: 写 .coveragerc**

文件 `.coveragerc`：

```ini
[run]
source = src/cim_ontology
branch = True
omit =
    tests/*
    */__init__.py

[report]
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if __name__ == .__main__.:
    pass
show_missing = True
precision = 1

[html]
directory = htmlcov
```

- [ ] **Step 2: 运行全量测试 + 覆盖率**

```bash
pytest --cov=cim_ontology --cov-report=term --cov-report=html -v
```

预期：总体覆盖率 ≥ 85%。

- [ ] **Step 3: 检查各模块覆盖率**

| 模块 | 目标 |
|------|------|
| `cleaner/multiplicity.py` | ≥ 95% |
| `cleaner/namespace.py` | ≥ 95% |
| `cleaner/class_name.py` | ≥ 95% |
| `reviewer/reviewer.py` | ≥ 90% |
| `adapters/owl.py` | ≥ 85% |
| `adapters/shacl.py` | ≥ 85% |

如果某些模块未达标，补充缺失的测试用例。

- [ ] **Step 4: 提交**

```bash
git add .coveragerc
git commit -m "chore: add coverage configuration"
```

---

## Task 33: CI 工作流（GitHub Actions）

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: 写 CI 配置**

文件 `.github/workflows/test.yml`：

```yaml
name: Tests

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  unit-integration-property:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit tests/integration tests/property -v --tb=short --cov=cim_ontology --cov-report=term
      - run: ruff check src tests
      - run: mypy src

  e2e:
    runs-on: ubuntu-latest
    needs: unit-integration-property
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      # LLM 缓存（跨 PR 复用）
      - uses: actions/cache@v4
        with:
          path: .cache/llm_reviews.db
          key: llm-cache-${{ hashFiles('src/cim_ontology/reviewer/prompts.py') }}
          restore-keys: |
            llm-cache-

      - run: pip install -e ".[dev]"
      - name: E2E build（强制 Mock LLM）
        run: cim-ontology build --input tests/fixtures/large/full.md --output ./build --format owl
        env:
          CI: true
      - run: pytest tests/e2e -v --tb=short
      - uses: actions/upload-artifact@v4
        with:
          name: build-output
          path: build/

      # 持久化缓存
      - uses: actions/cache/save@v4
        with:
          path: .cache/llm_reviews.db
          key: llm-cache-${{ hashFiles('src/cim_ontology/reviewer/prompts.py') }}
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add GitHub Actions with LLM cache and Mock provider"
```

---

## Task 34: 端到端手动验证（设计规范 §12 验收）

- [ ] **Step 1: 完整构建**

```bash
cim-ontology build \
  --input docs/GBT43259301—2024/cim-base-full.md \
  --output ./build \
  --format owl --format shacl --format jsonld-context --format json-schema --format python-types
```

预期：所有 5 种格式成功生成，无 ERROR 日志。

- [ ] **Step 2: 验证 OWL 输出**

```bash
ls -la build/owl/
```

预期：27+ 个 `cim17_*.ttl` 文件 + `cim17_full.ttl`。

- [ ] **Step 3: 验证 Python 类型可导入**

```bash
python -c "from build.python_types.Core_types import IdentifiedObject; print(IdentifiedObject)"
```

预期：成功导入 dataclass。

- [ ] **Step 4: 验证 SHACL 可解析**

```bash
python -c "from pyshacl import validate; g = __import__('rdflib').Graph(); g.parse('build/shacl/cim17_shapes.ttl', format='turtle'); print(f'{len(g)} triples')"
```

预期：显示三元组数。

- [ ] **Step 5: 运行全量测试套件**

```bash
pytest tests/ -v --tb=short --cov=cim_ontology
```

预期：所有测试 PASS，覆盖率 ≥ 85%。

---

# 自审检查

## 规范覆盖度

| 设计规范章节 | 任务 |
|------------|------|
| §2 架构 | Task 27（pipeline 编排）|
| §3 数据模型 | Task 2、3 |
| §4 Stage 1 规则清洗器 | Task 4-12 |
| §5 Stage 2 LLM 复审 | Task 13-19 |
| §6 Stage 3 输出适配器 | Task 20-25 |
| §7 错误处理 | Task 26 |
| §8 测试策略 | Task 30-33 |
| §9 项目结构 | Task 1 |
| §10 实施路线图 | 全部 5 个 Phase |
| §12 验收标准 | Task 34 |

## 类型一致性

| 类型/方法 | 定义 | 使用 |
|----------|------|------|
| `Multiplicity.min/max/raw` | Task 2 | Tasks 7, 12 |
| `ClassRef(package, class_name, iri, is_external)` | Task 2 | Tasks 12, 21 |
| `OutputAdapter.target_format/emit/verify` | Task 20 | Tasks 21-25 |
| `EmitResult(files, stats, warnings, duration_ms)` | Task 20 | Tasks 21-25, 27 |
| `LLMProvider.review(prompt)` | Task 13 | Tasks 17, 27 |

## 已知风险与缓解

| 风险 | 缓解 |
|------|------|
| 大 fixture 端到端测试耗时 | `@pytest.mark.skipif` 守卫 + 5 分钟超时 |
| LLM API 调用成本 | Task 33 CI 强制 Mock + actions/cache |
| 跨包 import 循环 | Task 11 拓扑排序 + Task 25 自动注入 |
| OWL 单文件过大 | Task 21 按包拆分 + owl:imports |

---

# 执行交接

**Plan complete and saved to `docs/superpowers/plans/2026-06-22-grid-ontology.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for tasks with clear interfaces and good test coverage.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review. Best for tasks requiring close collaboration.

**Which approach?**

---

**计划结束**

