"""公共 IRI 安全工具（P3-A）。

为所有 OutputAdapter 提供一致的 OCR 鲁棒属性名/标识符处理工具。

设计原则：
  - KISS：每个函数单一职责
  - 策略选择由调用方决定（fail-fast vs fail-soft vs 校验）
  - 不依赖 rdflib（保持 owl.py 解耦）

四种工具：
  1. is_safe_iri_part(name)         → bool   字符白名单（OWL/SHACL IRI 部件）
  2. is_valid_python_identifier(name) → bool  严格 Python 标识符
  3. contains_ocr_noise(name)         → bool   OCR 噪声模式识别
  4. safe_attr_slug(name)            → str    综合清洗（不可逆 fallback 到占位符）

B2 LDM 类型补全扩展：
  5. normalize_xsd_type(data_type)  → str    LDM 裸名/带前缀/大小写变体 → 标准 xsd:foo
  6. is_table_separator(name)       → bool   Markdown 表格分隔符检测（|---|---|）
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 常量：正则表达式
# ---------------------------------------------------------------------------

# 字符白名单：仅 ASCII 字母/数字/下划线/点/连字符
_SAFE_IRI_PART_RE = re.compile(r"^[A-Za-z0-9._\-]+$")

# 严格 Python 标识符：字母/下划线开头，后跟字母/数字/下划线
_PYTHON_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# OCR 噪声模式：与 owl.py:228-238 一致
_OCR_NOISE_PATTERNS = (
    r"\.\.",          # "0..1" / "1..*" 多重性
    r"\\mathcal",     # \mathcal{Z}
    r"\\ldots",       # \ldots
    r"\^\s*\{",       # ^{*}
    r"\$\d+",         # $0 / $1 公式序号
    r"\s+\\cup\s+",   # 集合运算
    r"\s+\\in\s+",    # 集合运算
    r"\s*\\Z\s*",     # 整数集符号
    r"\s*\\R\s*",     # 实数集符号
)
_OCR_NOISE_COMPILED = tuple(re.compile(p) for p in _OCR_NOISE_PATTERNS)

# 不可逆清洗的占位符（避免静默丢失语义）
_OCR_NOISE_PLACEHOLDER = "ocr_noise_attr"

# IRI 属性名长度上限（与 owl.py 对齐）
_MAX_ATTR_LEN = 64


# ---------------------------------------------------------------------------
# 公开 API：标识符校验
# ---------------------------------------------------------------------------


def is_safe_iri_part(name: str | None) -> bool:
    """检查字符串是否为合法的 IRI 部件（仅 ASCII 字母/数字/_/.-）。"""
    if not name:
        return False
    return _SAFE_IRI_PART_RE.match(name.strip()) is not None


def is_valid_python_identifier(name: str | None) -> bool:
    """检查字符串是否为合法的 Python 标识符。"""
    if not name:
        return False
    return _PYTHON_IDENTIFIER_RE.match(name.strip()) is not None


def contains_ocr_noise(name: str | None) -> bool:
    """检查字符串是否含 OCR 噪声（LaTeX 残骸 / 多重性泄露 / 数学符号）。"""
    if not name:
        return False
    return any(pat.search(name) for pat in _OCR_NOISE_COMPILED)


# ---------------------------------------------------------------------------
# 公开 API：B2 LDM 类型规范化
# ---------------------------------------------------------------------------

# 裸名（小写 key）→ 规范 XSD 类型（保留 camelCase 如 dateTime / anyURI）
# 注意：XSD 标准类型中 dateTime / dateTimeStamp / anyURI 等不是纯小写，
# 必须保留规范命名（OWL 输出需与 rdflib 的 XSD 命名空间常量匹配）。
_BARE_TYPE_MAP: dict[str, str] = {
    "string": "xsd:string",
    "int": "xsd:integer",
    "integer": "xsd:integer",
    "long": "xsd:long",
    "float": "xsd:float",
    "double": "xsd:double",
    "decimal": "xsd:decimal",
    "boolean": "xsd:boolean",
    "bool": "xsd:boolean",
    "date": "xsd:date",
    "time": "xsd:time",
    "datetime": "xsd:dateTime",
    "datetimestamp": "xsd:dateTimeStamp",
    "datetimeinterval": "xsd:dateTime",  # SG-CIM LDM 自定义
    "duration": "xsd:duration",
    "uri": "xsd:anyURI",
    "anyuri": "xsd:anyURI",
    "binary": "xsd:base64Binary",
}


# 已带 xsd: 前缀时，对后缀做大小写规范化（小写 key → 标准 XSD 名称）
_PREFIXED_SUFFIX_NORMALIZE: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "long": "long",
    "int": "integer",  # xsd:int → xsd:integer
    "short": "short",
    "byte": "byte",
    "float": "float",
    "double": "double",
    "decimal": "decimal",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "time": "time",
    "datetime": "dateTime",
    "datetimestamp": "dateTimeStamp",
    "duration": "duration",
    "uri": "anyURI",
    "anyuri": "anyURI",
    "binary": "base64Binary",
}


def normalize_xsd_type(data_type: str | None) -> str:
    """规范化 LDM 裸名/带前缀/大小写变体到标准 `xsd:foo` 命名空间形式。

    接受：
      - "String" / "string" / "STRING" → "xsd:string"
      - "Int" / "Integer" / "int" → "xsd:integer"
      - "Date" / "DATE" → "xsd:date"
      - "DateTime" / "Datetime" / "datetime" → "xsd:dateTime"
      - "xsd:string"（已带前缀） → "xsd:string"
      - "xsd:dateTime" / "xsd:dateTimeStamp"（camelCase 标准名）→ 保留
      - 空字符串 / None → "xsd:string"（安全 fallback）
      - 未识别的 CIM 自定义枚举（如 "Status"/"Money"/"ElectronicAddress"）→ 原样返回
        （调用方决定如何处理，可能映射为 {"type": "string", "enum": [...]}）

    Returns:
        标准化的 XSD 类型字符串（"xsd:foo" 形式）或原样（自定义类型）。
    """
    if not data_type:
        return "xsd:string"
    stripped = data_type.strip()
    if not stripped:
        return "xsd:string"
    # 已带 xsd: 前缀 → 规范化后缀大小写（保留 dateTime 等 camelCase）
    if stripped.lower().startswith("xsd:"):
        suffix_raw = stripped[4:]
        normalized_suffix = _PREFIXED_SUFFIX_NORMALIZE.get(
            suffix_raw.lower(), suffix_raw.lower()
        )
        return f"xsd:{normalized_suffix}"
    # 裸名查表（key 全部小写）
    return _BARE_TYPE_MAP.get(stripped.lower(), stripped)


def is_table_separator(name: str | None) -> bool:
    """检查是否为 Markdown 表格分隔符（"|---|---|..."）。

    用于过滤 Table.rows 中混入的 `---` 行（来自 markdown 解析边界）。
    """
    if not name:
        return False
    cleaned = name.strip()
    if not cleaned:
        return True
    return all(c in "-:|" for c in cleaned) and "-" in cleaned


# ---------------------------------------------------------------------------
# 公开 API：属性名清洗
# ---------------------------------------------------------------------------


def safe_attr_slug(name: str | None) -> str:
    """综合清洗属性名为安全的 slug。

    优先级：
      1. OCR 噪声命中 → 返回占位符（不可逆，避免静默错位）
      2. 非法字符 → 替换为下划线
      3. 长度 > 64 → 截断
      4. 空字符串 / None → 返回占位符

    注意：返回的 slug 仍是 ASCII 标识符，但**不保证**是合法 Python 标识符
    （首字符可能为数字）。如需 Python 标识符，调用方需再用 is_valid_python_identifier 校验。
    """
    if not name:
        return _OCR_NOISE_PLACEHOLDER
    name = name.strip()
    if not name:
        return _OCR_NOISE_PLACEHOLDER
    if contains_ocr_noise(name):
        return _OCR_NOISE_PLACEHOLDER
    # 替换非白名单字符为下划线（注意：连字符在 IRI 部件中合法，但不在 slug 中，
    # 因为 slug 需要兼容 Python 标识符 / OWL 属性名常见命名约定）
    slug = re.sub(r"[^A-Za-z0-9._]", "_", name)
    if len(slug) > _MAX_ATTR_LEN:
        slug = slug[:_MAX_ATTR_LEN]
    return slug
