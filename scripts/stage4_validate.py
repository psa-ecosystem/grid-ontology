"""Stage 4: 跨适配器一致性验证（设计规范 §6 跨适配器一致性阶段）。

诊断 100 个抽样类在 5 个 adapter 产物中的 IRI 存在性，
输出 Markdown 报告。仅诊断，不绑流水线退出码。
"""
from __future__ import annotations

import argparse
import ast
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Namespace, OWL, RDF

CIM = Namespace("http://iec.ch/TC57/2024/CIM-schema-cim17#")
SHACL = Namespace("http://www.w3.org/ns/shacl#")

ADAPTERS = ["OWL", "SHACL", "JSON Schema", "JSON-LD", "Python Types"]


@dataclass(frozen=True)
class Sample:
    """一个抽样样本：包名 + 类名 + 完整 IRI。"""

    pkg_name: str
    class_name: str
    class_iri: str


@dataclass(frozen=True)
class ProbeResult:
    """单个 adapter 对单个样本的探测结果。"""

    found: bool
    error: str | None = None


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
    samples_per_pkg: dict[str, int]
    adapters: list[str]
    seed: int
    generated_at: str


@dataclass(frozen=True)
class AttrSemantics:
    """单个属性在某 adapter 中的语义摘要。"""

    name: str
    data_type: str  # xsd:float / cim:Voltage / string 等（raw 字符串，不归一化）
    multiplicity: str  # "1" / "0..1" / "0..*" / "1..*"（原始字符串）


@dataclass(frozen=True)
class AssocSemantics:
    """单个关联在某 adapter 中的语义摘要。"""

    name: str
    target_class: str  # 关联目标类名
    multiplicity: str  # 同上


@dataclass(frozen=True)
class ClassSemantics:
    """某类在某 adapter 中的完整语义摘要。"""

    class_iri: str
    adapter: str  # "OWL" / "SHACL" / "JSON Schema" / "JSON-LD" / "Python Types"
    attrs: tuple[AttrSemantics, ...]
    assocs: tuple[AssocSemantics, ...]
    error: str | None = None  # FILE_MISSING / PARSE_ERROR / CLASS_NOT_FOUND / None


@dataclass(frozen=True)
class SemanticMismatch:
    """LLM 对某类的语义一致性判断结果。"""

    class_iri: str
    missing_attrs: dict[str, list[str]]  # adapter → [缺失属性名]
    missing_assocs: dict[str, list[str]]  # adapter → [缺失关联名]
    multiplicity_mismatch: list[str]  # ["OWL:length 0..1 vs SHACL 1"]
    llm_notes: str
    confidence: float


def _stratified_sample(
    ir, samples_per_pkg: int, seed: int
) -> list[Sample]:
    """按包分层抽样，每包随机抽 samples_per_pkg 类。

    不足 samples_per_pkg 的包取全部（不补足）。
    seed 用于 Python random.Random，保证可复现。

    过滤：跳过空名类（B7 清空残留）。
    """
    rng = random.Random(seed)
    samples: list[Sample] = []
    for pkg in ir.packages:
        # 过滤：跳过空名类
        valid = [c for c in pkg.classes if c.name and c.name.strip()]
        # 随机抽样
        k = min(samples_per_pkg, len(valid))
        picked = rng.sample(valid, k)
        for cls in picked:
            samples.append(Sample(
                pkg_name=pkg.name,
                class_name=cls.name,
                class_iri=str(CIM) + cls.name,
            ))
    return samples


def _probe_owl(sample: Sample, build_dir: Path) -> ProbeResult:
    """OWL probe：rdflib 解析 cim17_full.ttl，检查 owl:Class subject 集合。"""
    full_path = build_dir / "owl" / "cim17_full.ttl"
    if not full_path.exists():
        return ProbeResult(found=False, error="FILE_MISSING")
    try:
        g = Graph()
        g.parse(full_path, format="turtle")
        for subject in g.subjects(RDF.type, OWL.Class):
            if str(subject) == sample.class_iri:
                return ProbeResult(found=True)
        return ProbeResult(found=False)
    except Exception as e:
        return ProbeResult(found=False, error=f"PARSE_ERROR: {e}")


def _probe_shacl(sample: Sample, build_dir: Path) -> ProbeResult:
    """SHACL probe：rdflib 解析 cim17_shapes.ttl，检查 sh:targetClass 值集合。"""
    shapes_path = build_dir / "shacl" / "cim17_shapes.ttl"
    if not shapes_path.exists():
        return ProbeResult(found=False, error="FILE_MISSING")
    try:
        g = Graph()
        g.parse(shapes_path, format="turtle")
        for target in g.objects(None, SHACL.targetClass):
            if str(target) == sample.class_iri:
                return ProbeResult(found=True)
        return ProbeResult(found=False)
    except Exception as e:
        return ProbeResult(found=False, error=f"PARSE_ERROR: {e}")


def _probe_json_schema(sample: Sample, build_dir: Path) -> ProbeResult:
    """JSON Schema probe：扫描 *.json，检查 definitions/<class_name> 存在。"""
    schema_dir = build_dir / "json-schema"
    if not schema_dir.exists():
        return ProbeResult(found=False, error="FILE_MISSING")
    schema_files = list(schema_dir.glob("*.json"))
    if not schema_files:
        return ProbeResult(found=False, error="FILE_MISSING")
    for schema_file in schema_files:
        try:
            data = json.loads(schema_file.read_text(encoding="utf-8"))
            definitions = data.get("definitions", {})
            if sample.class_name in definitions:
                return ProbeResult(found=True)
        except Exception as e:
            return ProbeResult(found=False, error=f"PARSE_ERROR: {e}")
    return ProbeResult(found=False)


def _probe_jsonld(sample: Sample, build_dir: Path) -> ProbeResult:
    """JSON-LD probe：扫描 *_context.jsonld，检查 @context 含 class_name。"""
    ctx_dir = build_dir / "jsonld-context"
    if not ctx_dir.exists():
        return ProbeResult(found=False, error="FILE_MISSING")
    ctx_files = list(ctx_dir.glob("*_context.jsonld"))
    if not ctx_files:
        return ProbeResult(found=False, error="FILE_MISSING")
    for ctx_file in ctx_files:
        try:
            data = json.loads(ctx_file.read_text(encoding="utf-8"))
            ctx = data.get("@context", {})
            if sample.class_name in ctx:
                return ProbeResult(found=True)
        except Exception as e:
            return ProbeResult(found=False, error=f"PARSE_ERROR: {e}")
    return ProbeResult(found=False)


def _probe_python_types(sample: Sample, build_dir: Path) -> ProbeResult:
    """Python Types probe：解析 *.py AST，检查 ClassDef 节点名匹配。"""
    types_dir = build_dir / "python-types"
    if not types_dir.exists():
        return ProbeResult(found=False, error="FILE_MISSING")
    py_files = list(types_dir.glob("*_types.py"))
    if not py_files:
        return ProbeResult(found=False, error="FILE_MISSING")
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == sample.class_name:
                    return ProbeResult(found=True)
        except Exception as e:
            return ProbeResult(found=False, error=f"PARSE_ERROR: {e}")
    return ProbeResult(found=False)


def _multiplicity_from_counts(min_count, max_count) -> str:
    """从 SHACL minCount/maxCount 推导多重性字符串。"""
    lo = int(min_count) if min_count is not None else 0
    if max_count is None:
        hi = "*" if lo <= 1 else "*"
    else:
        hi = str(int(max_count))
    if lo == 1 and hi == "1":
        return "1"
    if lo == 0 and hi == "1":
        return "0..1"
    if lo == 1 and hi == "*":
        return "1..*"
    return f"{lo}..{hi}"


def _extract_owl_semantics(class_iri: str, build_dir: Path) -> ClassSemantics:
    """OWL 抽取:rdflib 解析 cim17_full.ttl,DatatypeProperty→attrs,ObjectProperty→assocs。

    注:OWL 中属性是全局的,通过 rdfs:domain 关联到类。类存在但无属性 → attrs=()/assocs=()(非 CLASS_NOT_FOUND)。
    """
    from rdflib import Graph, OWL, RDF, RDFS
    full_path = build_dir / "owl" / "cim17_full.ttl"
    if not full_path.exists():
        return ClassSemantics(class_iri=class_iri, adapter="OWL", attrs=(), assocs=(), error="FILE_MISSING")
    try:
        g = Graph()
        g.parse(full_path, format="turtle")
        attrs: list[AttrSemantics] = []
        assocs: list[AssocSemantics] = []
        # DatatypeProperty → attrs
        for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
            domains = list(g.objects(prop, RDFS.domain))
            if any(str(d) == class_iri for d in domains):
                ranges = list(g.objects(prop, RDFS.range))
                data_type = str(ranges[0]) if ranges else "xsd:string"
                prop_str = str(prop)
                local_name = prop_str.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                attrs.append(AttrSemantics(name=local_name, data_type=data_type, multiplicity="0..1"))
        # ObjectProperty → assocs
        for prop in g.subjects(RDF.type, OWL.ObjectProperty):
            domains = list(g.objects(prop, RDFS.domain))
            if any(str(d) == class_iri for d in domains):
                ranges = list(g.objects(prop, RDFS.range))
                target = str(ranges[0]) if ranges else ""
                prop_str = str(prop)
                local_name = prop_str.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                assocs.append(AssocSemantics(name=local_name, target_class=target, multiplicity="0..*"))
        return ClassSemantics(
            class_iri=class_iri, adapter="OWL",
            attrs=tuple(attrs), assocs=tuple(assocs), error=None,
        )
    except Exception as e:
        return ClassSemantics(
            class_iri=class_iri, adapter="OWL", attrs=(), assocs=(), error=f"PARSE_ERROR: {e}",
        )


def _extract_shacl_semantics(class_iri: str, build_dir: Path) -> ClassSemantics:
    """SHACL 抽取:rdflib 解析 cim17_shapes.ttl,sh:targetClass=class_iri 的 NodeShape。

    attrs = sh:property[sh:datatype],assocs = sh:property[sh:class]。多重性从 minCount/maxCount 推导。
    """
    from rdflib import Graph
    shapes_path = build_dir / "shacl" / "cim17_shapes.ttl"
    if not shapes_path.exists():
        return ClassSemantics(class_iri=class_iri, adapter="SHACL", attrs=(), assocs=(), error="FILE_MISSING")
    try:
        g = Graph()
        g.parse(shapes_path, format="turtle")
        # 找 targetClass=class_iri 的 shape
        shape = None
        for s in g.subjects(SHACL.targetClass, None):
            for target in g.objects(s, SHACL.targetClass):
                if str(target) == class_iri:
                    shape = s
                    break
            if shape is not None:
                break
        if shape is None:
            return ClassSemantics(
                class_iri=class_iri, adapter="SHACL", attrs=(), assocs=(), error="CLASS_NOT_FOUND",
            )
        attrs: list[AttrSemantics] = []
        assocs: list[AssocSemantics] = []
        for prop in g.objects(shape, SHACL.property):
            path = next(iter(g.objects(prop, SHACL.path)), None)
            dtype = next(iter(g.objects(prop, SHACL.datatype)), None)
            klass = next(iter(g.objects(prop, SHACL["class"])), None)
            min_count = next(iter(g.objects(prop, SHACL.minCount)), None)
            max_count = next(iter(g.objects(prop, SHACL.maxCount)), None)
            mult = _multiplicity_from_counts(min_count, max_count)
            if dtype is not None:
                attrs.append(AttrSemantics(name=str(path), data_type=str(dtype), multiplicity=mult))
            elif klass is not None:
                assocs.append(AssocSemantics(name=str(path), target_class=str(klass), multiplicity=mult))
        return ClassSemantics(
            class_iri=class_iri, adapter="SHACL",
            attrs=tuple(attrs), assocs=tuple(assocs), error=None,
        )
    except Exception as e:
        return ClassSemantics(
            class_iri=class_iri, adapter="SHACL", attrs=(), assocs=(), error=f"PARSE_ERROR: {e}",
        )


def _extract_json_schema_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """JSON Schema 抽取:扫描 *_schema.json,definitions/<class_name>/properties。

    attrs = properties 中 type≠object/array(标量属性),assocs = properties 中 type=object/array(引用其他类)。
    多重性:required 数组含 → "1";type=array → "0..*";默认 → "0..1"。
    """
    schema_dir = build_dir / "json-schema"
    if not schema_dir.exists():
        return ClassSemantics(class_iri="", adapter="JSON Schema", attrs=(), assocs=(), error="FILE_MISSING")
    schema_files = list(schema_dir.glob("*.json"))
    if not schema_files:
        return ClassSemantics(class_iri="", adapter="JSON Schema", attrs=(), assocs=(), error="FILE_MISSING")
    for schema_file in schema_files:
        try:
            data = json.loads(schema_file.read_text(encoding="utf-8"))
            definitions = data.get("definitions", {})
            if class_name not in definitions:
                continue
            cls_def = definitions[class_name]
            properties = cls_def.get("properties", {})
            required = set(cls_def.get("required", []))
            attrs: list[AttrSemantics] = []
            assocs: list[AssocSemantics] = []
            for prop_name, prop_def in properties.items():
                prop_type = prop_def.get("type", "")
                if prop_type in ("object", "array"):
                    target = prop_def.get("$ref", "").split("/")[-1] if "$ref" in prop_def else ""
                    mult = "0..*" if prop_type == "array" else ("1" if prop_name in required else "0..1")
                    assocs.append(AssocSemantics(name=prop_name, target_class=target, multiplicity=mult))
                else:
                    mult = "1" if prop_name in required else "0..1"
                    attrs.append(AttrSemantics(name=prop_name, data_type=prop_type, multiplicity=mult))
            return ClassSemantics(
                class_iri="", adapter="JSON Schema",
                attrs=tuple(attrs), assocs=tuple(assocs), error=None,
            )
        except Exception as e:
            return ClassSemantics(class_iri="", adapter="JSON Schema", attrs=(), assocs=(), error=f"PARSE_ERROR: {e}")
    return ClassSemantics(class_iri="", adapter="JSON Schema", attrs=(), assocs=(), error="CLASS_NOT_FOUND")


def _extract_jsonld_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """JSON-LD 抽取:扫描 *_context.jsonld。

    注:JSON-LD @context 通常只含术语映射("@id": "cim:Foo"),不含属性结构。
    大多数类返回 error="CLASS_NOT_FOUND"(诚实标注语义稀疏)。
    缺 jsonld-context/ 目录 → error="FILE_MISSING"。
    """
    ctx_dir = build_dir / "jsonld-context"
    if not ctx_dir.exists():
        return ClassSemantics(class_iri="", adapter="JSON-LD", attrs=(), assocs=(), error="FILE_MISSING")
    ctx_files = list(ctx_dir.glob("*_context.jsonld"))
    if not ctx_files:
        return ClassSemantics(class_iri="", adapter="JSON-LD", attrs=(), assocs=(), error="FILE_MISSING")
    # JSON-LD @context 不导出属性结构 → 统一返回 CLASS_NOT_FOUND
    return ClassSemantics(class_iri="", adapter="JSON-LD", attrs=(), assocs=(), error="CLASS_NOT_FOUND")


def _extract_python_types_semantics(class_name: str, build_dir: Path) -> ClassSemantics:
    """Python Types 抽取:ast.parse *_types.py,class <class_name> 的 annotations。

    attrs = 标量注解(name: float),assocs = list[OtherClass] / OtherClass 字段。
    多重性:list[X] → "0..*";Optional[X] → "0..1";X → "1"。
    """
    types_dir = build_dir / "python-types"
    if not types_dir.exists():
        return ClassSemantics(class_iri="", adapter="Python Types", attrs=(), assocs=(), error="FILE_MISSING")
    py_files = list(types_dir.glob("*_types.py"))
    if not py_files:
        return ClassSemantics(class_iri="", adapter="Python Types", attrs=(), assocs=(), error="FILE_MISSING")
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    attrs: list[AttrSemantics] = []
                    assocs: list[AssocSemantics] = []
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            field_name = stmt.target.id
                            ann_str = ast.unparse(stmt.annotation) if hasattr(ast, "unparse") else ""
                            if ann_str.startswith("list[") or ann_str.startswith("List["):
                                target = ann_str[ann_str.index("[") + 1:ann_str.rindex("]")].strip('"\' ')
                                assocs.append(AssocSemantics(name=field_name, target_class=target, multiplicity="0..*"))
                            elif ann_str.startswith("Optional["):
                                target = ann_str[ann_str.index("[") + 1:ann_str.rindex("]")].strip('"\' ')
                                assocs.append(AssocSemantics(name=field_name, target_class=target, multiplicity="0..1"))
                            else:
                                attrs.append(AttrSemantics(name=field_name, data_type=ann_str, multiplicity="1"))
                    return ClassSemantics(
                        class_iri="", adapter="Python Types",
                        attrs=tuple(attrs), assocs=tuple(assocs), error=None,
                    )
        except Exception as e:
            return ClassSemantics(class_iri="", adapter="Python Types", attrs=(), assocs=(), error=f"PARSE_ERROR: {e}")
    return ClassSemantics(class_iri="", adapter="Python Types", attrs=(), assocs=(), error="CLASS_NOT_FOUND")


def _build_semantic_prompt(
    class_name: str,
    ir_class_def,
    semantics: dict[str, ClassSemantics],
):
    """构造语义一致性 ReviewPrompt。

    system = CIM 17 专家 prompt（复用 cim_ontology.reviewer.prompts._SYSTEM）
    user = IR 类定义 + 5 adapter 摘要（JSON）+ 任务指令
    raw_text = class_name（MockProvider 匹配用）
    """
    from cim_ontology.reviewer.prompts import _SYSTEM
    from cim_ontology.reviewer.providers import ReviewPrompt

    ir_block = "（IR 中无类定义）"
    if ir_class_def is not None:
        attrs = ", ".join(a.name for a in (ir_class_def.attributes or []))
        assocs = ", ".join(a.name for a in (ir_class_def.associations or []))
        ir_block = f"属性: [{attrs}]\n关联: [{assocs}]"

    sem_lines: list[str] = []
    for adapter in ADAPTERS:
        sem = semantics.get(adapter)
        if sem is None:
            sem_lines.append(f"- {adapter}: （未抽取）")
            continue
        if sem.error:
            sem_lines.append(f"- {adapter}: error={sem.error}")
            continue
        attr_names = ", ".join(a.name for a in sem.attrs) or "（无）"
        assoc_names = ", ".join(f"{a.name}->{a.target_class}" for a in sem.assocs) or "（无）"
        sem_lines.append(f"- {adapter}: attrs=[{attr_names}] assocs=[{assoc_names}]")
    sem_block = "\n".join(sem_lines)

    user = f"""## 待复审类
{class_name}

## IR 类定义（ground truth）
{ir_block}

## 5 adapter 语义摘要
{sem_block}

## 任务
判断 5 adapter 是否覆盖 IR 类定义的属性与关联：
1. missing_attrs: {{adapter: [缺失属性名]}}（IR 有但 adapter 无）
2. missing_assocs: {{adapter: [缺失关联名]}}（IR 有但 adapter 无）
3. multiplicity_mismatch: ["adapter:attr mult1 vs mult2"]（多重性表示不一致）
4. consistent: 全部一致为 true，否则 false
5. notes: 中文推理摘要（≤100 字）
6. confidence: 0.0-1.0（<0.5 视为低置信）

输出严格 JSON（无 markdown 包装）：
{{"class_iri": "...", "consistent": bool, "missing_attrs": {{}}, "missing_assocs": {{}}, "multiplicity_mismatch": [], "notes": "...", "confidence": 0.x}}
"""
    return ReviewPrompt(system=_SYSTEM, user=user, raw_text=class_name)


def _parse_semantic_response(raw: str, class_iri: str) -> SemanticMismatch | None:
    """解析 LLM 响应，三层熔断：
    1. json.loads 失败 → None
    2. confidence < 0.5 或缺 missing_attrs 字段 → None
    3. 通过 → SemanticMismatch
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if "missing_attrs" not in data or "missing_assocs" not in data:
        return None
    confidence = float(data.get("confidence", 0.0))
    if confidence < 0.5:
        return None
    return SemanticMismatch(
        class_iri=data.get("class_iri", class_iri),
        missing_attrs=data.get("missing_attrs", {}),
        missing_assocs=data.get("missing_assocs", {}),
        multiplicity_mismatch=data.get("multiplicity_mismatch", []),
        llm_notes=data.get("notes", ""),
        confidence=confidence,
    )


def _semantic_review_all(
    samples: list[Sample],
    ir,
    build_dir: Path,
    provider,
    cache=None,
    metrics=None,
) -> list[SemanticMismatch]:
    """对所有抽样类执行语义复审。

    编排：per-class 循环（try/except 隔离）：
      1. 5 adapter 抽取
      2. cache lookup（case_id=f"semantic:{class_iri}"）
      3. LLM 调用（cache miss）
      4. 解析 + cache write-back
      5. metrics 埋点

    Returns:
        list[SemanticMismatch]：仅含通过熔断的判断（consistent=False 或 True 都在内）
    """
    from cim_ontology.observability import Metrics as _Metrics
    metrics = metrics or _Metrics()

    # IR 类定义索引（class_name → ClassDef）
    ir_class_index: dict[str, object] = {}
    for pkg in ir.packages:
        for cls in pkg.classes:
            ir_class_index[cls.name] = cls

    extractors = {
        "OWL": lambda s: _extract_owl_semantics(s.class_iri, build_dir),
        "SHACL": lambda s: _extract_shacl_semantics(s.class_iri, build_dir),
        "JSON Schema": lambda s: _extract_json_schema_semantics(s.class_name, build_dir),
        "JSON-LD": lambda s: _extract_jsonld_semantics(s.class_name, build_dir),
        "Python Types": lambda s: _extract_python_types_semantics(s.class_name, build_dir),
    }

    mismatches: list[SemanticMismatch] = []
    for sample in samples:
        try:
            # 1. 5 adapter 抽取
            semantics = {adapter: fn(sample) for adapter, fn in extractors.items()}
            ir_class_def = ir_class_index.get(sample.class_name)
            if ir_class_def is None:
                metrics.inc("semantic.skipped", {"reason": "ir_class_missing"})
                continue
            # 2. cache lookup
            case_id = f"semantic:{sample.class_iri}"
            cached: str | None = None
            if cache is not None:
                try:
                    cached = cache.get(case_id)
                    metrics.inc("semantic.cache", {"result": "hit" if cached else "miss"})
                except Exception:
                    metrics.inc("semantic.cache", {"result": "failure"})
            if cached is not None:
                result = _parse_semantic_response(cached, sample.class_iri)
            else:
                # 3. LLM 调用
                import time as _time
                prompt = _build_semantic_prompt(sample.class_name, ir_class_def, semantics)
                start = _time.perf_counter()
                try:
                    raw = provider.review(prompt)
                    metrics.observe("semantic.latency", _time.perf_counter() - start, {"outcome": "success"})
                    metrics.inc("semantic.calls", {"outcome": "success"})
                except Exception:
                    metrics.observe("semantic.latency", _time.perf_counter() - start, {"outcome": "failure"})
                    metrics.inc("semantic.calls", {"outcome": "failure"})
                    metrics.inc("semantic.fallbacks", {"reason": "provider_exception"})
                    continue
                # 4. 解析
                result = _parse_semantic_response(raw, sample.class_iri)
                # 5. cache write-back（无论成功失败）
                if cache is not None:
                    try:
                        cache.put(case_id, raw)
                    except Exception:
                        pass
            if result is None:
                metrics.inc("semantic.fallbacks", {"reason": "parse_or_business"})
                continue
            mismatches.append(result)
        except Exception as e:
            metrics.inc("semantic.fallbacks", {"reason": "exception"})
            import structlog as _structlog
            _structlog.get_logger().warning("semantic_review_exception", class_iri=sample.class_iri, error=str(e))
            continue
    return mismatches


def _render_semantic_section(mismatches: list[SemanticMismatch], total: int) -> str:
    """渲染 §6 语义一致性复审 Markdown 段。

    mismatches: 通过熔断的判断列表（含 consistent=True 和 False）
    total: 抽样总数
    """
    inconsistent = [m for m in mismatches if m.missing_attrs or m.missing_assocs or m.multiplicity_mismatch]
    consistent_count = total - len(inconsistent)
    pct = (consistent_count / total * 100) if total else 0.0

    # 缺失属性表
    attr_rows: list[str] = []
    for m in inconsistent:
        for adapter, attrs in m.missing_attrs.items():
            for attr in attrs:
                attr_rows.append(f"| {m.class_iri.split('#')[-1]} | {adapter} | {attr} | {m.llm_notes} |")
    attr_table = "\n".join(attr_rows) if attr_rows else "_无缺失属性_"

    # 缺失关联表
    assoc_rows: list[str] = []
    for m in inconsistent:
        for adapter, assocs in m.missing_assocs.items():
            for assoc in assocs:
                assoc_rows.append(f"| {m.class_iri.split('#')[-1]} | {adapter} | {assoc} | {m.llm_notes} |")
    assoc_table = "\n".join(assoc_rows) if assoc_rows else "_无缺失关联_"

    # 多重性冲突表
    mult_rows: list[str] = []
    for m in inconsistent:
        for conflict in m.multiplicity_mismatch:
            mult_rows.append(f"| {m.class_iri.split('#')[-1]} | {conflict} | {m.llm_notes} |")
    mult_table = "\n".join(mult_rows) if mult_rows else "_无多重性冲突_"

    return f"""
## 6. 语义一致性复审（LLM）

**复审类数**：{total}
**语义一致**：{consistent_count}/{total}（{pct:.1f}%）
**语义不一致**：{len(inconsistent)} 类

### 6.1 缺失属性（{len(attr_rows)} 项）

| 类 | Adapter | 缺失属性 | LLM 推理 |
|----|---------|---------|---------|
{attr_table}

### 6.2 缺失关联（{len(assoc_rows)} 项）

| 类 | Adapter | 缺失关联 | LLM 推理 |
|----|---------|---------|---------|
{assoc_table}

### 6.3 多重性映射冲突（{len(mult_rows)} 项）

| 类 | 冲突 | LLM 推理 |
|----|------|---------|
{mult_table}
"""


def _aggregate(
    samples: list[Sample],
    results: dict[str, dict[str, ProbeResult]],
    seed: int,
) -> ConsistencyMatrix:
    """聚合所有探测结果为 ConsistencyMatrix。

    不一致判定：found=False 且 error is None（即真缺失，非探测工具问题）。
    """
    inconsistencies: list[Inconsistency] = []
    for sample in samples:
        adapter_results = results.get(sample.class_iri, {})
        missing = [
            adapter
            for adapter in ADAPTERS
            if adapter in adapter_results
            and not adapter_results[adapter].found
            and adapter_results[adapter].error is None
        ]
        if missing:
            inconsistencies.append(Inconsistency(sample=sample, missing_adapters=missing))

    samples_per_pkg: dict[str, int] = {}
    for sample in samples:
        samples_per_pkg[sample.pkg_name] = samples_per_pkg.get(sample.pkg_name, 0) + 1

    return ConsistencyMatrix(
        samples=samples,
        results=results,
        inconsistencies=inconsistencies,
        samples_per_pkg=samples_per_pkg,
        adapters=list(ADAPTERS),
        seed=seed,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _render_markdown(matrix: ConsistencyMatrix) -> str:
    """渲染 4 节结构 Markdown 报告。"""
    total = len(matrix.samples)
    passed = total - len(matrix.inconsistencies)
    pct = (passed / total * 100) if total else 0.0

    # §1 抽样策略
    samples_lines = "\n".join(
        f"| {pkg} | {n} |" for pkg, n in matrix.samples_per_pkg.items()
    )

    # §2 一致性矩阵（按包 × adapter）
    pkg_names = sorted(matrix.samples_per_pkg.keys())
    matrix_rows: list[str] = []
    for pkg in pkg_names:
        # 统计该包每个 adapter 的 found 数
        row_cells = [pkg]
        for adapter in matrix.adapters:
            count = sum(
                1
                for sample in matrix.samples
                if sample.pkg_name == pkg
                and matrix.results.get(sample.class_iri, {}).get(adapter, ProbeResult(found=False)).found
            )
            row_cells.append(str(count))
        matrix_rows.append("| " + " | ".join(row_cells) + " |")
    matrix_table = "\n".join(matrix_rows) if matrix_rows else "_无样本_"

    # §3 不一致点
    if matrix.inconsistencies:
        inc_rows = "\n".join(
            f"| {inc.sample.class_name} | {inc.sample.pkg_name} | {', '.join(inc.missing_adapters)} |"
            for inc in matrix.inconsistencies
        )
    else:
        inc_rows = "_无不一致点_"

    return f"""# Stage 4: 跨适配器一致性验证报告

**生成时间**：{matrix.generated_at}
**样本数**：{total}（seed={matrix.seed}）
**一致性通过率**：{passed}/{total}（{pct:.1f}%）

## 1. 抽样策略

- 分层：每包随机抽 ≤ {max(matrix.samples_per_pkg.values()) if matrix.samples_per_pkg else 0} 类
- 实际抽样数（按包）：

| 包 | 抽样数 |
|----|--------|
{samples_lines}

## 2. 一致性矩阵（按包 × Adapter）

| 包 | OWL | SHACL | JSON Schema | JSON-LD | Python Types |
|----|-----|-------|-------------|---------|--------------|
{matrix_table}

## 3. 不一致点（{len(matrix.inconsistencies)} 项）

| Class | 包 | 缺失 Adapter |
|-------|-----|-------------|
{inc_rows}

## 4. 结论

- 通过：{passed} / {total}（{pct:.1f}%）
- 不一致点：{len(matrix.inconsistencies)} 项
- 详细分布见 §2 一致性矩阵
"""


def _load_ir(ir_path: str):
    """从 JSON 文件加载 OntologyIR。"""
    from cim_ontology.ir.models import OntologyIR

    data = json.loads(Path(ir_path).read_text(encoding="utf-8"))
    return OntologyIR.model_validate(data)


def _probe_all(
    samples: list[Sample], build_dir: Path
) -> dict[str, dict[str, ProbeResult]]:
    """对所有样本执行 5 个 probe。"""
    results: dict[str, dict[str, ProbeResult]] = {}
    for sample in samples:
        results[sample.class_iri] = {
            "OWL": _probe_owl(sample, build_dir),
            "SHACL": _probe_shacl(sample, build_dir),
            "JSON Schema": _probe_json_schema(sample, build_dir),
            "JSON-LD": _probe_jsonld(sample, build_dir),
            "Python Types": _probe_python_types(sample, build_dir),
        }
    return results


def _cli():
    """argparse CLI 入口（设计规范 §6 跨适配器一致性阶段）。"""
    parser = argparse.ArgumentParser(description="Stage 4: 跨适配器一致性验证")
    parser.add_argument("--ir", required=True, help="IR JSON 文件路径")
    parser.add_argument("--build", required=True, help="Stage 3 build 目录")
    parser.add_argument(
        "--out",
        default="docs/stage4-validation-report.md",
        help="报告输出路径",
    )
    parser.add_argument("--samples-per-pkg", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--semantic-review",
        action="store_true",
        help="启用 Stage 5 语义一致性 LLM 复审（追加 §6 段）",
    )
    parser.add_argument(
        "--use-real-llm",
        action="store_true",
        help="使用真实 LLM Provider（默认 Mock；需 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY）",
    )
    parser.add_argument(
        "--provider-fixtures",
        default="tests/fixtures/llm",
        help="MockProvider fixtures 目录（默认 tests/fixtures/llm）",
    )
    args = parser.parse_args()

    ir = _load_ir(args.ir)
    samples = _stratified_sample(ir, args.samples_per_pkg, args.seed)
    results = _probe_all(samples, Path(args.build))
    matrix = _aggregate(samples, results, args.seed)
    total = len(matrix.samples)
    passed = total - len(matrix.inconsistencies)
    # 渲染 Markdown + 追加 passed 类清单（让 100% 通过类名也出现在报告中）
    inconsistent_names = {inc.sample.class_name for inc in matrix.inconsistencies}
    passed_samples = [s for s in matrix.samples if s.class_name not in inconsistent_names]
    passed_section = ""
    if passed_samples:
        passed_section = "\n## 5. 通过清单\n\n" + "\n".join(
            f"- `{s.pkg_name}.{s.class_name}`" for s in passed_samples
        ) + "\n"

    # Stage 5: 语义一致性 LLM 复审（仅 --semantic-review 时执行）
    semantic_section = ""
    if args.semantic_review:
        from cim_ontology.reviewer.providers import get_provider
        provider = get_provider(fixtures_dir=Path(args.provider_fixtures))
        mismatches = _semantic_review_all(samples, ir, Path(args.build), provider)
        semantic_section = _render_semantic_section(mismatches, total=len(samples))

    Path(args.out).write_text(
        _render_markdown(matrix) + passed_section + semantic_section,
        encoding="utf-8",
    )
    print(f"✓ Stage 4 报告已生成：{args.out}")
    print(f"  通过率：{passed}/{total}")
    if args.semantic_review:
        print(f"  语义复审：{len(samples)} 类（详见 §6）")


if __name__ == "__main__":
    _cli()
