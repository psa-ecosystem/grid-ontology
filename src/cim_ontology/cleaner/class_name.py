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