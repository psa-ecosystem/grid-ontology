"""包去重辅助（v1.2.1 hotfix，P3-B 防线 + v1.4 OCR 模糊合并）。

P3-B 防线：Hypothesis 属性测试在 v1.1 闭环最后一步拦截了 IRI 碰撞 edge case。
根因：owl.py / python_types.py 的 `packages_by_name = {p.name: p for p in ir.packages}`
会因两个同名 Package 发生 dict 静默覆盖，第一个 Package 内的所有 ClassDef
永久丢失；json_schema.py / jsonld_context.py 虽直接遍历不丢数据，但同名输出文件互相覆盖。

v1.4 P1 扩展：cim-base-full.md 含 6 对 OCR 噪声包名（如 Packae1/Package1），
精确名匹配无法识别，导致产物文件名带 OCR 噪声（如 cim17_Packae1.ttl）。
新增 `merge_fuzzy_duplicate_packages`：基于 Levenshtein ≤ 2 + 共同前缀 ≥ 3
检测 OCR 变体对，规范化到较长的规范名。

修复策略（OCP 一致性）：
  - 4 个 adapter 统一调用 merge_duplicate_packages(ir.packages) 作为 emit 入口预处理
  - 合并而非 raise：符合 v1.1 三层熔断的 fail-soft 设计哲学
  - classes 按 name 去重：保持"同名类不重复 emit"的 RDF 唯一性
  - 第一个 Package 的元数据（description/iri）保留：与 iri 合并语义一致

参考：tests/property/test_iri_uniqueness.py::test_each_class_appears_with_canonical_uri
"""
from __future__ import annotations

from cim_ontology.ir.models import Package
from cim_ontology.ir.registry import levenshtein


def merge_duplicate_packages(packages: list[Package]) -> list[Package]:
    """合并同名 Package 的 classes，返回去重后的 Package 列表。

    合并规则：
      - 同名包合并为一个，保留第一个出现的 Package（ir/description/iri 来自首次出现）
      - classes 按 name 去重（先到先得），保留首次出现的 ClassDef
      - 顺序：保留原始 packages 列表的相对顺序

    Args:
        packages: IR 中的包列表（可能含重复 name）

    Returns:
        去重后的 Package 列表（同名包已合并 classes）

    Examples:
        >>> pkgs = [
        ...     Package(iri='http://x#A', name='A', classes=[ClassDef(name='A1')]),
        ...     Package(iri='http://x#A', name='A', classes=[ClassDef(name='A2')]),
        ... ]
        >>> result = merge_duplicate_packages(pkgs)
        >>> len(result)
        1
        >>> sorted(c.name for c in result[0].classes)
        ['A1', 'A2']
    """
    by_name: dict[str, Package] = {}
    for pkg in packages:
        if pkg.name not in by_name:
            # 首次出现：深拷贝避免污染原始 IR
            by_name[pkg.name] = pkg.model_copy(deep=True)
        else:
            existing = by_name[pkg.name]
            seen = {c.name for c in existing.classes}
            for cls in pkg.classes:
                if cls.name not in seen:
                    existing.classes.append(cls)
                    seen.add(cls.name)
    return list(by_name.values())


# OCR 模糊合并的默认阈值
# 注意：cim-base-full.md OCR 变体的实际距离最大为 3
# （AuxiliarEuiment/AuxiliaryEquipment），长度差最大 3。
DEFAULT_FUZZY_THRESHOLD = 6
# 最短字符串长度（防御性：< 5 的字符串 OCR 误判率高，跳过）
MIN_FUZZY_NAME_LEN = 5
# 长度差上限（绝对值，cim 实测最大 3）
MAX_FUZZY_LENGTH_DIFF = 3
# 长度差下限：要求 |len(a) - len(b)| ≥ MIN_FUZZY_LENGTH_DIFF 才合并。
# 关键启发式：OCR 噪声几乎总会插入/删除字符（产生长度差），而两个真不同的
# 短缩略词（如 Production/Protection、Bar/Baz）通常同长度。cim 实测 6 对
# OCR 变体的长度差均 ≥ 1（最小 1，最大 3），因此这个门槛有效区分 OCR 变体
# 和同长度 false-positive。
MIN_FUZZY_LENGTH_DIFF = 1


def _find_fuzzy_groups(
    names: list[str],
    threshold: int,
) -> list[list[int]]:
    """找出 names 中所有需要合并的下标组（union-find 风格）。

    合并条件（多重防御）：
      1. min(len(a), len(b)) ≥ MIN_FUZZY_NAME_LEN  短字符串跳过（防误合并）
      2. 1 ≤ |len(a) - len(b)| ≤ MAX_FUZZY_LENGTH_DIFF   长度差必须 ≥ 1
         （防同长度 false-positive，如 Production/Protection、Bar/Baz）
         同时 ≤ 3（防差距过大）
      3. Levenshtein(a, b) ≤ max(2, max_len // 3)    长度感知阈值

    cim-base-full.md 实测 6 对 OCR 变体均通过；同时有效阻止 'Production/Protection'、
    'Bar/Baz' 等 false-positive 合并。
    """
    n = len(names)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            a, b = names[i], names[j]
            # 防御 1：最短字符串防御
            if min(len(a), len(b)) < MIN_FUZZY_NAME_LEN:
                continue
            # 防御 2a：长度差必须 ≥ MIN_FUZZY_LENGTH_DIFF（防同长度 false-positive）
            if abs(len(a) - len(b)) < MIN_FUZZY_LENGTH_DIFF:
                continue
            # 防御 2b：长度差上限（防差距过大）
            if abs(len(a) - len(b)) > MAX_FUZZY_LENGTH_DIFF:
                continue
            # 长度感知阈值
            max_len = max(len(a), len(b))
            eff_threshold = max(2, max_len // 3)
            if levenshtein(a, b) <= min(threshold, eff_threshold):
                union(i, j)

    # 收集分组
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def merge_fuzzy_duplicate_packages(
    packages: list[Package],
    threshold: int = DEFAULT_FUZZY_THRESHOLD,
) -> list[Package]:
    """合并 OCR 噪声变体 Package（如 Packae1/Package1）。

    合并规则：
      - Levenshtein(a, b) ≤ max(2, max_len // 3) **且** 1 ≤ 长度差 ≤ 3 → 视为同一 Package
      - 长度差下限 ≥ 1：防止同长度 false-positive（如 Production/Protection）
      - 同一组内选择**最长的**包名作为规范名（OCR 通常截断或加噪，长名更可能是正确的）
      - 同名 classes 去重（先到先得）
      - 顺序：保留首次出现规范名的位置

    Args:
        packages: IR 中的包列表
        threshold: 绝对距离上限（默认 6，配合长度感知阈值 max(2, max_len // 3)）

    Returns:
        去重后的 Package 列表（OCR 变体已规范化到规范名）

    Examples:
        >>> pkgs = [
        ...     Package(iri='http://x#A', name='Packae1', classes=[ClassDef(name='Class1')]),
        ...     Package(iri='http://x#A', name='Package1', classes=[ClassDef(name='Class2')]),
        ... ]
        >>> result = merge_fuzzy_duplicate_packages(pkgs)
        >>> len(result)
        1
        >>> result[0].name
        'Package1'
    """
    if not packages:
        return []

    # 防御 1：先做精确合并（merge_duplicate_packages），
    # 这样精确同名包（如 'Core' + 'Core'）被先合并，
    # 避免短字符串被 fuzzy 阈值排除（MIN_FUZZY_NAME_LEN=5 防 Foo/Fox 误合并）。
    packages = merge_duplicate_packages(packages)
    names = [p.name for p in packages]
    groups = _find_fuzzy_groups(names, threshold)

    if not groups:
        # 无需合并，按原顺序返回
        return [p.model_copy(deep=True) for p in packages]

    # 为每个 group 选择规范名（最长的）
    # 关键：必须用 key=len 而非默认 max()，否则按字典序选错：
    #   'Euivalents' > 'Equivalents'（'u' > 'q'）但长度 9 < 11，OCR 噪声反而胜出。
    canonical: dict[int, str] = {}
    for g in groups:
        # 同组内最长的名（OCR 噪声通常是截断的，所以长名更可能是正确名）
        canonical[min(g)] = max((names[i] for i in g), key=len)

    # 合并：按原始顺序遍历，同组内合并到第一个出现的位置
    by_canonical: dict[str, Package] = {}
    for idx, pkg in enumerate(packages):
        # 找到 idx 所属的 group（若不在任何组中，canonical_idx = idx）
        canonical_idx = next(
            (min(g) for g in groups if idx in g),
            idx,
        )
        # canonical.get() 在 idx 所属 group 时一定有值（见上方 canonical 填充），
        # 否则 fallback 到 pkg.name。显式 or 避免 Pyright 把 None 误推断。
        canon_name = canonical.get(canonical_idx) or pkg.name
        if canon_name not in by_canonical:
            # 首次出现：深拷贝并改名为规范名
            merged = pkg.model_copy(deep=True)
            merged.name = canon_name
            by_canonical[canon_name] = merged
        else:
            existing = by_canonical[canon_name]
            seen = {c.name for c in existing.classes}
            for cls in pkg.classes:
                if cls.name not in seen:
                    existing.classes.append(cls)
                    seen.add(cls.name)

    return list(by_canonical.values())
