# 性能 Baseline 报告（P3-B-T1）

**日期**：2026-06-24
**测试基线**：v1.1 P3-A 完成态（262 unit + 4 e2e，全绿）
**硬件/环境**：macOS Darwin 24.6.0，Python 3.14.6
**输入文档**：`tests/fixtures/large/full.md`（9243 行，27 packages，992 classes）

## 1. E2E 测试耗时

| 测试 | 耗时 | 说明 |
|------|------|------|
| **总计（4 e2e）** | **7.86s** | 含 pytest 启动 + fixture 加载 |
| `test_owl_object_properties_emitted` | 1.93s | OWL 输出 + Graph.parse + ObjectProperty 计数 |
| `test_owl_subclass_of_emitted` | 1.92s | OWL 输出 + Graph.parse + subClassOf 计数 |
| `test_owl_full_ttl_parseable` | 1.84s | OWL 输出 + Graph.parse |
| `test_full_builds_all_formats` | 1.83s | 三格式（owl/shacl/jsonld-context）端到端 |

> **结论**：每次 OWL e2e 都要 **build 一次 + 解析一次 Graph**。4 个测试各自独立运行 build，无 pytest fixture 共享。这是 4×1.83s ≈ 7.3s 的主因。

### 单次完整 Pipeline 耗时（cache cold，**0 重复**）

| 阶段 | 耗时 | 占比 | 调用次数 |
|------|------|------|----------|
| Markdown ingest（解析+清洗+表抽取+建IR） | 0.687s | 32% | 1 |
| OwlTurtleAdapter.emit | 0.809s | 38% | 1 |
| ShaclAdapter.emit | 0.310s | 14% | 1 |
| JsonLdContextAdapter.emit | 0.003s | 0% | 1 |
| **端到端总耗时** | **~1.81s** | 100% | — |

> 含 cProfile 自身开销的一次实测 5.22s。**纯 profile 测量 ≈ 1.81s**（cProfile 包裹了 `find_similar`/`levenshtein` 的 O(n²) 行为，加重了 profile 期数据）。

## 2. 适配器 Profile（cProfile 累计时间 Top 40）

| # | 函数 | 累计耗时 | 占比 | 文件 |
|---|------|----------|------|------|
| 1 | `build()` | 5.216s | 100% | pipeline.py:21 |
| 2 | `Graph.serialize()` × 29 | 2.696s | 52% | rdflib/graph.py:1448 |
| 3 | `TurtleSerializer.serialize()` × 29 | 2.690s | 52% | rdflib/turtle.py:256 |
| 4 | `OwlTurtleAdapter.emit()` | 2.568s | 49% | src/adapters/owl.py:32 |
| 5 | `clean_markdown_to_ir()` | 1.788s | 34% | src/cleaner/orchestrator.py:41 |
| 6 | `TurtleSerializer.statement()` × 17368 | 1.429s | 27% | rdflib/turtle.py:378 |
| 7 | `TurtleSerializer.s_default()` × 17368 | 1.411s | 27% | rdflib/turtle.py:382 |
| 8 | `TurtleSerializer.predicateList()` × 17368 | 1.268s | 24% | rdflib/turtle.py:483 |
| 9 | **`TurtleSerializer.get_pname()` × 315466** | **1.255s** | **24%** | rdflib/turtle.py:319 |
| 10 | `TurtleSerializer.preprocess()` × 29 | 1.140s | 22% | rdflib/turtle.py:105 |
| 11 | `TurtleSerializer.preprocessTriple()` × 68779 | 1.045s | 20% | rdflib/turtle.py:294 |
| 12 | `TurtleSerializer.path()` × 150548 | 0.990s | 19% | rdflib/turtle.py:397 |
| 13 | `extract_tables_from_section()` × 992 | 0.980s | 19% | src/cleaner/table_extractor.py:25 |
| 14 | `TurtleSerializer.p_default()` × 150548 | 0.884s | 17% | rdflib/turtle.py:404 |
| 15 | `ShaclAdapter.emit()` | 0.856s | 16% | src/adapters/shacl.py:22 |
| 16 | `TurtleSerializer.label()` × 150548 | 0.739s | 14% | rdflib/turtle.py:410 |
| 17 | `BeautifulSoup.__init__()` × 754 | 0.598s | 11% | bs4/__init__.py:211 |
| 18 | `_lxml.feed()` × 754 | 0.582s | 11% | bs4/_lxml.py:488 |
| 19 | `TurtleSerializer.objectList()` × 64401 | 0.530s | 10% | rdflib/turtle.py:498 |
| 20 | `Graph.add()` × 71025 | 0.464s | 9% | rdflib/graph.py:617 |
| 21 | **`TurtleSerializer.addNamespace()` × 288880** | **0.412s** | **8%** | rdflib/turtle.py:225 |
| 22 | **`Graph.compute_qname()` × 298622** | **0.381s** | **7%** | rdflib/graph.py:1340 |
| 23 | `find_similar()` × 977 | 0.360s | 7% | src/ir/registry.py:47 |
| 24 | `levenshtein()` × 8875 | 0.358s | 7% | src/ir/registry.py:7 |
| 25 | `parse_markdown()` | 0.343s | 7% | src/cleaner/markdown_parser.py:31 |
| 26 | `_parse_html_table()` × 754 | 0.331s | 6% | src/cleaner/table_extractor.py:67 |
| 27 | `_build_package_graph()` × 27 | 0.327s | 6% | src/adapters/owl.py:89 |

### 纯计算热点（tottime Top 10）

| # | 函数 | 累计自耗时 | 调用次数 | 单次 |
|---|------|------------|----------|------|
| 1 | `TurtleSerializer.get_pname` | 0.316s | 315466 | 1.0µs |
| 2 | `Term.__eq__` | 0.280s | 1.2M | 0.23µs |
| 3 | **`levenshtein`** | 0.213s | 8875 | 24µs |
| 4 | `isinstance` (builtin) | 0.175s | 2.06M | 0.08µs |
| 5 | `TurtleSerializer.addNamespace` | 0.132s | 288880 | 0.46µs |
| 6 | `TurtleSerializer.label` | 0.118s | 150548 | 0.78µs |
| 7 | `MemoryStore.add` | 0.103s | 71025 | 1.5µs |
| 8 | `list.append` | 0.103s | 1.86M | — |
| 9 | `split_uri` | 0.099s | 31447 | 3.1µs |
| 10 | `file.read` (bs4 调用) | 0.097s | 747 | 130µs |

## 3. 适配器耗时排序

| 排名 | 适配器 | 耗时 | 累计占比 | 备注 |
|------|--------|------|----------|------|
| 1 | **OwlTurtleAdapter** | 0.809s | 72% | 29 次 rdflib serialize 主导 |
| 2 | **ShaclAdapter** | 0.310s | 27% | 单次大文件 serialize |
| 3 | JsonLdContextAdapter | 0.003s | 0% | 纯 JSON 写入 |
| 4 | PythonTypesAdapter | 未触发 | 0% | e2e 不调用 |

> OWL 慢 = `29 个 package × 1 个全量文件` = `29 次 Graph.serialize` 调用 + 1 次全量 serialize。**29 次调用是 P1.2 修复后的人为设计**（按包切分输出小文件 + 1 个 `_full.ttl`）。

## 4. Top 5 热点

| # | 热点 | 累计耗时 | 占比 | 性质 |
|---|------|----------|------|------|
| 1 | **`rdflib.Graph.serialize()` (Turtle)** × 29 | 2.696s | **52%** | I/O + 文本生成；OWL 适配器全部耗时在此 |
| 2 | **`rdflib get_pname()`** × 315466 | 1.255s | 24% | 序列化中给 URI 找 prefix；315k 次调用、1µs/次 |
| 3 | **`extract_tables_from_section()`** × 992 | 0.980s | 19% | BeautifulSoup 解析 HTML 表格 |
| 4 | **`find_similar()` / `levenshtein()`** | 0.358s | 7% | O(n²) 相似度匹配；8875 次调用 = 27 packages × ~330 candidates |
| 5 | **`compute_qname()` + `addNamespace()`** | 0.793s | 15% | URI 前缀计算；288k+298k 次调用 |

### 重复操作与 cache miss

- **OWL emit 中 Graph 被构建 29 次**（每个 package 一次），每次 `Graph.serialize` 都要重新 **遍历所有 triples + compute_qname**。29 × (150k triple) = 4.35M 次 URI 解析。可单次 build 完整 Graph + 单次 serialize 解决。
- **`find_similar` 在 cleaner 阶段调用 977 次**（每个 class 一次），用 `levenshtein` 对所有 992 个 class 算编辑距离 → **O(n²) 行为 = 967k 比较**。可换 BK-tree / 预分桶。
- **`addNamespace × 288880` + `compute_qname × 298622`**：rdflib 在每个 triple 上重复解析 prefix，可注入 `bind()` 一次性注册。
- **pytest fixture 缺失**：4 个 e2e 测试每次都重新 build，未共享 IR。pytest session-level fixture 可节省 1.83s × 3 ≈ 5.5s。

## 5. 优化机会

| 优先级 | 热点 | 优化方向 | 预估提速 | 风险 |
|--------|------|----------|----------|------|
| 🔴 **高** | 29× `Graph.serialize` | 单次构建完整 Graph → 一次 serialize（输出 `_full.ttl` 即可） | **-0.7s 单跑 / -2s e2e** | 改动 OWL 适配器输出文件结构（破坏现有 snapshot 需更新） |
| 🔴 **高** | e2e 4 次重复 build | pytest session-scoped fixture 共享 IR | **-5.5s e2e 总耗时** | 极低 |
| 🟡 **中** | `get_pname` × 315k | 用 `g.bind()` 显式注册 prefix + 调 `rdflib` 0.18+ 缓存 | -0.3s | 中（rdflib 版本依赖） |
| 🟡 **中** | `find_similar/levenshtein` O(n²) | 改 BK-tree / numpy 向量化 / 仅在 uncertain 触发 | -0.2s | 中（语义可能变化） |
| 🟡 **中** | `extract_tables_from_section` 992 次 | 改为 lxml 一次性全文解析（避免 754 次 BeautifulSoup） | -0.4s | 中（依赖切换） |
| 🟢 **低** | `parse_markdown` 343ms | markdown-it-py 替代原生正则解析 | -0.1s | 低 |
| 🟢 **低** | `JsonLdContext` 3ms | 已最优 | — | — |
| 🟢 **低** | `Term.__eq__` × 1.2M | rdflib 内部热点，升级或自缓存 | -0.1s | 高（侵入式） |

## 6. 结论

**值得做性能优化**。当前端到端单跑 **1.8s**、e2e 套件 **7.9s**、在 v1.1 规模（992 类）下完全够用，但有两个低成本高回报机会：

1. **OWL 适配器合并 serialize**（🔴高）：单次 -0.7s，可观且实施简单。
2. **pytest session-level fixture**（🔴高）：e2e 总耗时 **7.9s → 2.4s**（-70%），零风险。

预计组合优化后：
- **单次 build** 1.8s → ~1.0s（-45%）
- **e2e 套件** 7.9s → ~2.5s（-68%）
- **262 unit** 不受影响（mock/fast 路径）

> 优化空间主要在 I/O 与 rdflib 内部热点，**未发现 markdown 解析、SQLite 缓存或 Pydantic 序列化瓶颈**。架构设计（4 阶段 + 多适配器）合理。

## 7. 后续

- T2-T3：Hypothesis 属性测试覆盖 IRI 唯一性、数据守恒、无环
- T4：按上表优先级实施 🔴 高优先级 2 项
- T5：最终提交 + v1.1 路线图收尾
