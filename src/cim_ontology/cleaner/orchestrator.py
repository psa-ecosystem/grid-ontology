"""Stage 1 编排器：Markdown → OntologyIR 主入口。"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import structlog

from cim_ontology.adapters._iri_safe import is_table_separator
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


# 兜底包名（仅当 section 完全没有 package 信息时使用）
_DEFAULT_PACKAGE = "Core"

# P1：章节头 false-positive 模式。
# GB/T 文档的章节编号（如 "6.3"、"66"、"6.4.74"）被误识为 class_name 前缀，
# 导致 case_id 形如 "6.3::Core"、"66::Generation"、"52::Class1"。
# 这些条目不是真不确定，而是文档结构噪声，直接跳过。
_SECTION_HEADER_RE = re.compile(r"^\d+(\.\d+)*::")


def clean_markdown_to_ir(md_path: Path) -> OntologyIR:
    """Stage 1 入口：解析 Markdown 标准文档为 IR-JSON。

    流程：
      1. 读取文件 + 计算 SHA256
      2. Markdown → tokens
      3. tokens → sections
      4. sections → ClassDef（应用所有清洗规则）
      5. 按 section.package 分组到不同 Package
      6. 汇总 stats

    P1.1 扩展：按 section.package（从表标题 '表XX Pkg::Class' 提取）分组，
    支持 multi-package 输出（不再是单包兜底）。
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
            # P1 修复：剔除章节头 false-positive（case_id 以 X.Y.Z:: 开头，
            # 实际是 GB/T 文档的章节编号被误识为 class_name）。
            # 例：6.3::Core, 6.4::Wires, 66::Generation, 52::Class1
            # 注意：只跳过 UncertainEntry 的创建，**不**影响 ClassDef 的生成
            # （类本身是合法的，仅 case_id 命名含章节前缀需要清理）。
            if _SECTION_HEADER_RE.match(f"{section.path}::{cls.name}"):
                log.debug(
                    "section_header_skipped",
                    case_id=f"{section.path}::{cls.name}",
                    reason="章节编号误识为 class_name",
                )
            else:
                uncertain.append(UncertainEntry(
                    case_id=f"{section.path}::{cls.name}",
                    source_table=0,
                    package=section.package or _DEFAULT_PACKAGE,
                    raw_text=cls.name,
                    rule_attempt={"value": cls.name},
                    uncertainty_reason=cleaned.uncertainty_reason,
                    context_snippet=section.heading,
                ))
        # 提取 tables → attributes / associations
        tables = extract_tables_from_section(section.tokens)
        _apply_tables(cls, tables)
        # P1.1: 将 section.package 附加到 ClassDef（通过额外属性传递）
        cls._source_package = section.package  # type: ignore[attr-defined]
        classes.append(cls)

    # P1.1: 按 section.package 分组到不同 Package
    packages_by_name: dict[str, list[ClassDef]] = {}
    for cls in classes:
        pkg_name = getattr(cls, "_source_package", None) or _DEFAULT_PACKAGE
        packages_by_name.setdefault(pkg_name, []).append(cls)

    packages = [
        Package(
            iri=f"http://iec.ch/TC57/2024/CIM-schema-cim17#{name}",
            name=name,
            classes=pkg_classes,
        )
        for name, pkg_classes in packages_by_name.items()
    ]

    # 统计
    stats = IRStats(
        package_count=len(packages),
        class_count=len(classes),
        attribute_count=sum(len(c.attributes) for c in classes),
        association_count=sum(len(c.associations) for c in classes),
        uncertain_count=len(uncertain),
    )

    ir = OntologyIR(
        packages=packages,
        uncertain_entries=uncertain,
        stats=stats,
        source=SourceInfo(
            document_path=str(md_path),
            document_sha256=sha256,
            parsed_at=datetime.now(UTC),
            parser_version="0.2.0",
        ),
    )

    # B6：Stage 2 关联 target OCR 修复
    # 在所有 IR 构建完成后调用，统一修复 associations.target.class_name
    resolve_association_targets(ir)

    # B7：Stage 2 属性名 OCR 修复
    # 与 B6 对称架构，修复 DataProperty.name 的噪声（LaTeX/CJK/分隔符/混合标点）
    resolve_attr_names(ir)

    return ir


# ---------------------------------------------------------------------------
# B6 Stage 2：关联 target OCR 鲁棒解析
# ---------------------------------------------------------------------------


def resolve_association_targets(ir: OntologyIR) -> dict[str, int]:
    """Stage 2：在所有类已注册后，二次修复 associations.target.class_name。

    处理两类 OCR 截断：
      1. Noise target：明显非类名（"---"、纯 CJK、含 multiplicity 模式等）
         → target.class_name 设为 None（标记为不可恢复）
      2. Truncated target：缺前缀（如 `ispatchActTicket` → `DispatchActTicket`）
         → 用 endswith 唯一候选替换

    Returns:
        修复统计 dict：{kept_exact, fuzzy_resolved, noise_dropped,
                       ambiguous_kept, unresolved_kept}
    """
    # 收集全量已知类名（用于 fuzzy match 候选）
    known_names: set[str] = set()
    for pkg in ir.packages:
        for cls in pkg.classes:
            known_names.add(cls.name)

    kept_exact = 0
    fuzzy_resolved = 0
    noise_dropped = 0
    ambiguous_kept = 0
    unresolved_kept = 0

    for pkg in ir.packages:
        for cls in pkg.classes:
            for assoc in cls.associations:
                target = assoc.target.class_name
                if not target:
                    noise_dropped += 1
                    continue
                target = target.strip()
                if not target:
                    assoc.target.class_name = None
                    noise_dropped += 1
                    continue
                # 1. Noise 检测
                if _is_ocr_noise_target(target):
                    assoc.target.class_name = None
                    noise_dropped += 1
                    continue
                # 2. 完全匹配
                if target in known_names:
                    kept_exact += 1
                    continue
                # 3. endswith fuzzy match
                candidates = [
                    n for n in known_names
                    if n != target and n.endswith(target) and len(n) > len(target)
                ]
                if len(candidates) == 1:
                    assoc.target.class_name = candidates[0]
                    fuzzy_resolved += 1
                elif len(candidates) > 1:
                    ambiguous_kept += 1  # 多候选歧义：保守保留原值
                else:
                    unresolved_kept += 1  # 无候选：保留原值

    return {
        "kept_exact": kept_exact,
        "fuzzy_resolved": fuzzy_resolved,
        "noise_dropped": noise_dropped,
        "ambiguous_kept": ambiguous_kept,
        "unresolved_kept": unresolved_kept,
    }


def _is_ocr_noise_target(name: str) -> bool:
    """检测 target.class_name 是否为 OCR 噪声（不可恢复）。

    噪声模式：
      - Markdown 分隔符（"---" / ":---:"）
      - 纯 CJK 字符（中文混入，非合法 CamelCase）
      - 纯 ASCII 单字符或多字符短串但非 CamelCase
      - 含冒号 / 连字符的"描述列"内容
      - 纯 multiplicity 模式（"0..1" / "0..*" / "1" / "0..* D"）
    """
    if not name:
        return True
    s = name.strip()
    if not s:
        return True
    # Markdown 表格分隔符
    if is_table_separator(s):
        return True
    # 纯 CJK 字符
    has_ascii = any(ord(c) < 128 for c in s)
    if not has_ascii:
        return True
    # 纯 multiplicity 模式（"0..1" / "0..*" / "1..* Di" 等以数字开头 + ".." 起始）
    if re.match(r"^\d+\.\.", s):
        return True
    # 纯数字（"1" / "0" 等 mult min/max 值）
    if s.isdigit():
        return True
    # 含中英文混合标点（描述列泄露）
    if "：" in s or "—" in s or "（" in s:
        return True
    return False


# ---------------------------------------------------------------------------
# B7 Stage 2: 属性名 OCR 鲁棒解析
# ---------------------------------------------------------------------------


def _classify_attr_noise(name: str) -> str | None:
    """判定 DataProperty.name 是否为 OCR 噪声，返回分类标签；非噪声返回 None。

    噪声分类：
      - latex: LaTeX 残骸（包含 $ 或 \\）
      - cjk: 纯 CJK 字符
      - separator: Markdown 表格分隔符
      - mixed_punct: 含中文标点（描述列泄露）

    与 B6 _is_ocr_noise_target 区别：
      - 本函数返回分类标签（用于日志 reason 字段），不是 bool
      - 不检测纯 multiplicity 模式（属性名不含 "0..1" 等数字开头模式）
      - 不做 fuzzy 替换（attr.name 噪声样本不适用 endswith 策略）
    """
    if is_table_separator(name):
        return "separator"
    if "$" in name or "\\" in name:
        return "latex"
    if not any(ord(c) < 128 for c in name):
        return "cjk"
    if any(p in name for p in ("：", "—", "（", "「", "」")):
        return "mixed_punct"
    return None


def resolve_attr_names(ir: OntologyIR) -> dict[str, int]:
    """Stage 2 (B7): 二次修复 DataProperty.name 的 OCR 噪声。

    与 B6 resolve_association_targets 对称架构：噪声 → attr.name = "",
    下游 _validate_attr_name 已 fail-soft 跳过空名。

    噪声分类（详见 _classify_attr_noise）：
      - latex: LaTeX 残骸
      - cjk: 纯 CJK 字符
      - separator: Markdown 表格分隔符
      - mixed_punct: 中文标点混入（描述列泄露）

    Returns:
        统计 dict：{latex, cjk, separator, mixed_punct, total_cleaned, kept}

    注意：
      - 不做 fuzzy 替换（数据驱动决策：attr.name 噪声样本不适用 endswith）
      - 不改 attr 列表长度（仅清空 name，保持下游字段计数稳定）
      - 不改 DataProperty 模型（保持 Pydantic 兼容）
    """
    latex = cjk = separator = mixed_punct = kept = 0
    for pkg in ir.packages:
        for cls in pkg.classes:
            for attr in cls.attributes:
                name = (attr.name or "").strip()
                if not name:
                    # 已为空字符串或 None：视为合法，计入 kept
                    kept += 1
                    continue
                kind = _classify_attr_noise(name)
                if kind is None:
                    kept += 1
                    continue
                # 噪声：清空 name 并发出结构化日志
                attr.name = ""
                log.warning(
                    "b7_attr_noise_dropped",
                    cls=cls.name,
                    original=name[:60],
                    reason=kind,
                )
                if kind == "latex":
                    latex += 1
                elif kind == "cjk":
                    cjk += 1
                elif kind == "separator":
                    separator += 1
                elif kind == "mixed_punct":
                    mixed_punct += 1
    return {
        "latex": latex,
        "cjk": cjk,
        "separator": separator,
        "mixed_punct": mixed_punct,
        "total_cleaned": latex + cjk + separator + mixed_punct,
        "kept": kept,
    }


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


def _apply_tables(cls: ClassDef, tables: list[Table]) -> None:
    """根据表格类型填充 ClassDef 属性。

    P2-A：在表格解析后聚合所有 inherited_from → cls.parents。
    CIM 使用多重继承（`Bay` 同时继承 `EquipmentContainer` /
    `ConnectivityNodeContainer`），所以收集 unique parent names 而非只取
    最频繁者。OWL/RDFS 语义支持多重 subClassOf。
    """
    for table in tables:
        if table.kind == "property":
            cls.attributes = _parse_property_table(table)
        elif table.kind == "association":
            cls.associations = _parse_association_table(table)
        elif table.kind == "inheritance":
            cls.parents = _parse_inheritance_table(table)

    # P2-A：聚合 inherited_from → cls.parents（多重继承）
    if not cls.parents:
        inherited_parents: list[str] = []
        for attr in cls.attributes:
            if attr.inherited_from and attr.inherited_from not in inherited_parents:
                inherited_parents.append(attr.inherited_from)
        for assoc in cls.associations:
            if assoc.inherited_from and assoc.inherited_from not in inherited_parents:
                inherited_parents.append(assoc.inherited_from)
        if inherited_parents:
            cls.parents = [
                ClassRef(package="Core", class_name=name)
                for name in inherited_parents
            ]


def _parse_property_table(table: Table) -> list[DataProperty]:
    """解析属性表（P1.3 表头驱动 + P2-A 继承抽取）。

    列定义按表头关键字动态定位（不再硬编码列索引）：
      - "名字" / "名称" / "name" / "property" → name
      - "类型" / "type" → data_type
      - "重数" / "cardinality" / "multiplicity" → multiplicity
      - "描述" / "description" / "desc" → inherited_from (P2-A)

    兼容 OCR 真实列序（名字 | 重数 | 类型 | 描述）与原 markdown（名字 | 类型 | 基数）。

    P2-A：从描述列抽取 `继承自：X` / `继承自:X` 模式，记录到 DataProperty.inherited_from。
    """
    col_name = _find_column(table.headers, ["名字", "名称", "name", "property", "属性"])
    col_type = _find_column(table.headers, ["类型", "type"])
    col_mult = _find_column(table.headers, ["重数", "cardinality", "multiplicity", "基数"])
    col_desc = _find_column(table.headers, ["描述", "description", "desc", "说明"])

    attrs: list[DataProperty] = []
    for row in table.rows:
        # 至少需要 name 列可访问
        if col_name is None or col_name >= len(row):
            continue
        name = row[col_name]
        data_type = row[col_type] if col_type is not None and col_type < len(row) else ""
        mult_str = row[col_mult] if col_mult is not None and col_mult < len(row) else "0..1"
        desc_str = row[col_desc] if col_desc is not None and col_desc < len(row) else ""
        inherited = _extract_inherited_from(desc_str)
        try:
            multiplicity = clean_multiplicity(mult_str)
        except Exception:
            multiplicity = Multiplicity(min=0, max=1, raw=mult_str or "0..1")
        attrs.append(DataProperty(
            name=name,
            data_type=data_type,
            multiplicity=multiplicity,
            required=multiplicity.min >= 1,
            inherited_from=inherited,
        ))
    return attrs


def _parse_association_table(table: Table) -> list[ObjectProperty]:
    """解析关联端表（P1.3 表头驱动 + P2-A 继承抽取 + B3 SG-CIM 4 列布局适配）。

    列定义按表头关键字动态定位：
      - "名字" / "名称" / "name" / "关联端" / "association" → name
      - "类型" / "type" / "目标" / "target" / "class" → target_class_name
      - "重数自" / "重数到" / "cardinality" / "基数" → multiplicity
      - "描述" / "description" / "desc" → inherited_from (P2-A)

    兼容 OCR 真实列序（重数自 | 名字 | 重数到 | 类型 | 描述）：重数自/重数到
    取第一个非空者作为本端 multiplicity。

    OCR 噪声兜底：若 name 列被完全污染（如 "$\\mathcal{"），按列序兜底：
      - name = column 1（OCR 重数自 | name | 重数到 | 类型 | 描述 中的索引 1）
      - type = column 3（OCR 中"类型"列）

    B3：SG-CIM LDM `### 关联` 段落采用 4 列布局 `重数 | 目标 | 类型 | 描述`：
      - 第 1 列"目标"实际承担 name + target.class_name（OCR 截断的对象名）
      - 第 3 列"类型"实际是 multiplicity 的副本（如 "0..1"），不是类名
      - 修复：检测到该布局（4 列 + 含 "目标" 列头）时，将 col_type 重定向到 col_name
    """
    col_name = _find_column(table.headers, ["名字", "名称", "name", "关联端", "association"])
    col_type = _find_column(table.headers, ["类型", "type", "目标", "target", "class"])
    col_mult_to = _find_column(table.headers, ["重数到", "cardinality_to"])
    col_mult_from = _find_column(table.headers, ["重数自", "cardinality_from"])
    col_mult = _find_column(table.headers, ["重数", "cardinality", "基数", "multiplicity"])
    col_desc = _find_column(table.headers, ["描述", "description", "desc", "说明"])

    # OCR 列序兜底：当 name/type 列被噪声污染无法关键字匹配时使用
    if col_name is None and len(table.headers) >= 2:
        col_name = 1  # OCR 重数自 | name | 重数到 | 类型 | 描述
    if col_type is None and len(table.headers) >= 4:
        col_type = 3  # OCR ... | 类型 | 描述

    # B3：SG-CIM LDM 4 列布局适配（重数 | 目标 | 类型 | 描述）。
    # 该布局下"目标"列同时承担 name + target.class_name（OCR 截断的对象名），
    # "类型"列实际是 multiplicity 副本（冗余），需重定向 col_type → col_name。
    # 检测条件：4 列表头 + 表头含"目标"关键字（其它 header 可 OCR 退化或被噪声污染）。
    _has_target_col = any("目标" in (h or "") or "target" in (h or "").lower()
                          for h in table.headers)
    if len(table.headers) == 4 and _has_target_col:
        col_type = col_name if col_name is not None else 1

    assocs: list[ObjectProperty] = []
    for row in table.rows:
        if col_name is None or col_name >= len(row):
            continue
        name = row[col_name]
        target_name = row[col_type] if col_type is not None and col_type < len(row) else ""
        # 选择 multiplicity：重数到 > 重数自 > 重数（兼容多列变体）
        mult_str = ""
        for col in (col_mult_to, col_mult_from, col_mult):
            if col is not None and col < len(row) and row[col].strip():
                mult_str = row[col]
                break
        if not mult_str:
            mult_str = "0..1"
        desc_str = row[col_desc] if col_desc is not None and col_desc < len(row) else ""
        inherited = _extract_inherited_from(desc_str)
        try:
            multiplicity = clean_multiplicity(mult_str)
        except Exception:
            multiplicity = Multiplicity(min=0, max=1, raw=mult_str or "0..1")
        assocs.append(ObjectProperty(
            name=name,
            target=ClassRef(package="Core", class_name=target_name),
            multiplicity=multiplicity,
            inherited_from=inherited,
        ))
    return assocs


# P2-A：从描述列抽取 `继承自：X` 模式
_INHERITED_FROM_RE = re.compile(
    r"继承\s*自\s*[：:]\s*([A-Z][A-Za-z0-9]+)"
)


def _extract_inherited_from(description: str | None) -> str | None:
    """从描述文本中抽取 `继承自：X` 的父类名。

    OCR 容忍：
      - 全角/半角冒号 `：` / `:`
      - 任意空白 `继承   自  :  X`
      - 父类名必须 CamelCase（过滤 `类`/`类。` 等中文尾缀）
    """
    if not description:
        return None
    match = _INHERITED_FROM_RE.search(description)
    return match.group(1) if match else None


def _parse_inheritance_table(table: Table) -> list[ClassRef]:
    """解析继承表（P1.3 表头驱动）。

    OCR 文档中继承表通常无表头（直接是父类名列表）或表头为"父类"/"super"。
    策略：扫描每行所有单元格，取第一个 CamelCase 字符串作为父类名。
    """
    parents: list[ClassRef] = []
    camel_re = re.compile(r"^[A-Z][A-Za-z0-9]+$")
    for row in table.rows:
        for cell in row:
            cell = cell.strip() if cell else ""
            if camel_re.match(cell):
                parents.append(ClassRef(package="Core", class_name=cell))
                break  # 每行只取一个父类
    return parents


def _find_column(headers: list[str], keywords: list[str]) -> int | None:
    """按关键字列表定位列索引。

    匹配规则（首个匹配返回）：
      1. 完整相等（去除空白）
      2. 单元格包含任一关键字
      3. 表头含 OCR 噪声（$/\\^）时跳过该列

    OCR 噪声容忍：若所有列都被噪声污染（如 association 表的 "名字" 列变成
    "$\\mathcal { "），按列序兜底：name=col_1（association）或 col_0（property），
    type=col_3（association）或 col_2（property）。
    """
    for kw in keywords:
        for i, h in enumerate(headers):
            h_clean = (h or "").strip()
            if h_clean == kw:
                return i
        # 含关键字（跳过 OCR 噪声）
        for i, h in enumerate(headers):
            h_clean = (h or "").strip()
            if not h_clean or _is_ocr_noise_header(h_clean):
                continue
            if kw in h_clean:
                return i
    return None


_OCR_NOISE_HEADER_PATTERNS = (r"\$", r"\\", r"\^\s*\{")


def _is_ocr_noise_header(header: str) -> bool:
    """判定表头是否为 OCR 噪声（LaTeX 公式 / 数学符号残骸）。"""
    import re as _re
    return any(_re.search(pat, header) for pat in _OCR_NOISE_HEADER_PATTERNS)
