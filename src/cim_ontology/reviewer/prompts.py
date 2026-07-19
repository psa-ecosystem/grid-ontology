"""Prompt 模板与构建器（设计规范 §5.4 + v1.1.1 known_classes 扩充）。"""
from __future__ import annotations

from cim_ontology.ir.models import UncertainEntry
from cim_ontology.reviewer.providers import ReviewPrompt


# v1.1.1：增强 system prompt，明确告诉 LLM 这是 CIM 17 标准、清单是核心类
# 不完整清单，但足够引导 LLM 通过上下文推断绝大多数正确类名
# （避免把全部 ~992 个类名都塞进 prompt 导致 token 爆炸）
_SYSTEM = (
    "你是 IEC 61970-301 CIM（公共信息模型）本体建模专家，熟悉 CIM 17 标准。"
    "请复核从标准文档 OCR 中抽取的本体条目，纠正可能的识别错误。"
    "CIM 17 标准定义了约 992 个类，涵盖 27 个核心包（Core / Wires / Generation 等）。"
    "下方『已注册的类清单』列出了 ~200 个最核心的类，"
    "若候选类不在清单中但符合 CIM 命名约定（驼峰英文），仍可推断为正确。"
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

## 已注册的类清单（CIM 17 ~200 个核心类，非完整列表）
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


# ---------------------------------------------------------------------------
# v1.2 批处理：单次 API 调用送多条 uncertain，节省 ~80% 网络往返
# ---------------------------------------------------------------------------

_BATCH_USER_TEMPLATE = """## 已注册的命名空间
{known_namespaces}

## 已注册的类清单（CIM 17 ~200 个核心类，非完整列表）
{known_classes}

## 任务
对以下 {n} 条 uncertain 条目分别复审，逐条输出 JSON 对象。

{entries_block}

## 输出格式
输出 JSON 数组（不要 markdown 围栏），形如：
[
  {{ "case_id": "...", "corrected": {{ "class_name": "...", "namespace": "..." }}, "confidence": 0.0, "notes": "..." }},
  ...
]

数组长度必须等于条目数 {n}，每条对应一个 case_id。
若某条无法推断正确类名，输出 {{ "case_id": "...", "corrected": {{}}, "confidence": 0.0, "notes": "..." }}。
"""


def build_batch_review_prompt(
    entries: list[UncertainEntry],
    known_namespaces: list[str],
    known_classes: list[str],
) -> ReviewPrompt:
    """构建批处理复审 prompt（v1.2）。

    Args:
        entries: 待复审的条目列表（典型 5-20 条）
        known_namespaces: 已注册命名空间
        known_classes: 已注册类清单

    Returns:
        ReviewPrompt（raw_text 为所有 case_id 的拼接，用于缓存键）
    """
    if not entries:
        raise ValueError("entries 不能为空")

    # 每个 entry 一个块，用 --- 分隔
    blocks: list[str] = []
    for e in entries:
        blocks.append(
            f"--- case_id: {e.case_id} ---\n"
            f"- 包: {e.package}\n"
            f"- 表号: 表 {e.source_table}\n"
            f"- 不确定原因: {e.uncertainty_reason}\n"
            f"- 邻近文本: {e.context_snippet[:200]}\n"
            f"- 待复核: {e.raw_text}\n"
            f"- 规则引擎初步结果: {e.rule_attempt}\n"
        )
    entries_block = "\n".join(blocks)

    user = _BATCH_USER_TEMPLATE.format(
        n=len(entries),
        entries_block=entries_block,
        known_namespaces=", ".join(known_namespaces) or "(无)",
        known_classes=", ".join(known_classes) or "(无)",
    )
    # raw_text 用于缓存键：使用 sorted case_ids 拼接保证顺序无关
    raw_text = "|".join(sorted(e.case_id for e in entries))
    return ReviewPrompt(system=_SYSTEM, user=user, raw_text=raw_text)
