"""LLM Reviewer：三层熔断机制（设计规范 §5.5）。

P2-B 生产化强化：
  - 修订实际应用到 IR 中的 ClassDef.name（修复 no-op bug）
  - LLMCache 集成：命中跳过 Provider，回写未命中响应
  - Provider 失败 / JSON 损坏 / 业务校验失败 → 保留原 uncertain 条目

v1.1.1 known_classes 扩充：
  - 新增 load_known_classes_from_file() 从 fixtures 加载 CIM 标准类名
  - 默认 fixture: tests/fixtures/cim_known_classes.txt

v1.2 批处理优化：
  - 新增 review_batch()：单次 LLM 调用处理多条 uncertain，节省 ~80% 网络往返
  - 优先利用 cache（per-case_id 粒度保持不变）
  - 错误隔离：单条响应失败不影响其他条目

v1.3 observability 强化：
  - 集成 Metrics 原语：calls / latency / cache / fallbacks / corrections / batch.size
  - 路径维度（path=single|batch）区分逐条与批处理路径
  - 通过 metrics 参数注入（OCP），未传则内部创建默认实例
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import structlog

from cim_ontology.ir.models import ClassDef, OntologyIR, UncertainEntry
from cim_ontology.ir.registry import ClassRegistry
from cim_ontology.observability import Metrics
from cim_ontology.reviewer.cache import LLMCache
from cim_ontology.reviewer.providers import LLMProvider
from cim_ontology.reviewer.prompts import build_batch_review_prompt, build_review_prompt

log = structlog.get_logger()


def load_known_classes_from_file(path: Path | str) -> list[str]:
    """从 fixtures 加载 CIM 已知类名清单（v1.1.1）。

    文件格式（行级）：
      - '#' 开头的注释行忽略
      - 空行忽略
      - 其他每行一个类名（去重 + strip）

    Args:
        path: 文件路径（如 tests/fixtures/cim_known_classes.txt）

    Returns:
        去重后的类名 list

    Raises:
        FileNotFoundError: 文件不存在
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CIM 已知类名清单不存在: {p}")
    seen: set[str] = set()
    result: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


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
        cache: LLMCache | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        self._provider = provider
        self._registry = ClassRegistry()
        for cls in (known_classes or []):
            self._registry.add("any", cls)
        self._known_namespaces = known_namespaces or ["cim", "rdfs", "rdf", "xsd", "owl"]
        # P2-B：可选 SQLite 缓存（命中 → 跳过 Provider）
        self._cache = cache
        # v1.3 observability：可选 Metrics（默认创建新实例；外部注入可统一收集）
        self._metrics = metrics or Metrics()

    def review(self, ir: OntologyIR) -> OntologyIR:
        """复审 IR 中所有 uncertain 条目，返回更新后的 IR。

        P2-B：成功修订会同时更新 ClassDef.name 并从 uncertain_entries
        中移除（之前为 no-op，仅丢弃 LLM 结果）。

        v1.3 observability：埋点 corrections.applied / corrections.kept_uncertain
        路径维度 path=single。
        """
        reviewed: list[UncertainEntry] = []
        # P2-B：在所有 Package 中按 name 索引便于快速查找/重命名
        class_index: dict[str, tuple[int, int]] = {}
        for pi, pkg in enumerate(ir.packages):
            for ci, cls in enumerate(pkg.classes):
                class_index[cls.name] = (pi, ci)

        for entry in ir.uncertain_entries:
            try:
                result = self._review_one(entry, path="single")
                if result is None:
                    # fallback：保留 uncertain
                    self._metrics.inc("reviewer.corrections", {"applied": "false", "path": "single"})
                    reviewed.append(entry)
                    continue
                # P2-B：实际应用修订到 ClassDef
                corrected_name = (result.get("corrected") or {}).get("class_name")
                if corrected_name and entry.raw_text in class_index:
                    pi, ci = class_index[entry.raw_text]
                    old_class = ir.packages[pi].classes[ci]
                    # 不可变：构造新 ClassDef，name 改为 corrected_name
                    new_class = old_class.model_copy(update={"name": corrected_name})
                    ir.packages[pi].classes[ci] = new_class
                    log.info(
                        "llm_correction_applied",
                        case_id=entry.case_id,
                        old=entry.raw_text,
                        new=corrected_name,
                    )
                    self._metrics.inc(
                        "reviewer.corrections",
                        {"applied": "true", "path": "single"},
                    )
                    # 修订成功：从 uncertain 移除
                else:
                    # 修订结果无 class_name 或 raw_text 不在 IR 中 → 保留
                    self._metrics.inc(
                        "reviewer.corrections",
                        {"applied": "false", "path": "single"},
                    )
                    reviewed.append(entry)
            except Exception as e:
                log.warning("llm_review_exception", case_id=entry.case_id, error=str(e))
                self._metrics.inc(
                    "reviewer.fallbacks",
                    {"reason": "exception", "path": "single"},
                )
                reviewed.append(entry)

        # 不可变：构造新 IR
        return ir.model_copy(update={
            "packages": ir.packages,
            "uncertain_entries": reviewed,
        })

    def _review_one(self, entry: UncertainEntry, path: str = "single") -> dict | None:
        """复审单个条目，返回修订 dict 或 None（fallback）。

        P2-B：先查缓存；未命中调 Provider 并回写。
        v1.3 observability：埋点 cache.{hit,miss,failure} / calls.{success,failure} /
        latency.seconds / fallbacks.{provider_exception,json_invalid,business_invalid}。
        """
        prompt = build_review_prompt(
            entry,
            known_namespaces=self._known_namespaces,
            known_classes=self._registry.all_names(),
        )

        # P2-B：缓存优先
        cached: str | None = None
        if self._cache is not None:
            try:
                cached = self._cache.get(entry.case_id)
                if cached is not None:
                    self._metrics.inc("reviewer.cache", {"result": "hit", "path": path})
                else:
                    self._metrics.inc("reviewer.cache", {"result": "miss", "path": path})
            except Exception as e:
                self._metrics.inc("reviewer.cache", {"result": "failure", "path": path})
                log.warning("cache_read_failed", case_id=entry.case_id, error=str(e))

        if cached is not None:
            raw = cached
        else:
            # 调用 LLM（埋点延迟 + 成功/失败）
            start = time.perf_counter()
            try:
                raw = self._provider.review(prompt)
                elapsed = time.perf_counter() - start
                self._metrics.observe(
                    "reviewer.latency", elapsed, {"path": path, "outcome": "success"}
                )
                self._metrics.inc("reviewer.calls", {"outcome": "success", "path": path})
            except Exception as e:
                elapsed = time.perf_counter() - start
                self._metrics.observe(
                    "reviewer.latency", elapsed, {"path": path, "outcome": "failure"}
                )
                self._metrics.inc("reviewer.calls", {"outcome": "failure", "path": path})
                self._metrics.inc(
                    "reviewer.fallbacks",
                    {"reason": "provider_exception", "path": path},
                )
                log.warning("llm_call_failed", path=path, error=str(e))
                return None
            # 回写缓存
            if self._cache is not None:
                try:
                    self._cache.put(entry.case_id, raw)
                except Exception as e:
                    log.warning("cache_write_failed", case_id=entry.case_id, path=path, error=str(e))

        # 熔断 1: JSON 解析
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._metrics.inc(
                "reviewer.fallbacks", {"reason": "json_invalid", "path": path}
            )
            log.warning("llm_invalid_json", path=path, raw=raw[:100])
            return None

        # 熔断 2: 业务校验
        corrected = data.get("corrected", {})
        if corrected.get("class_name") and not self._registry.has(corrected["class_name"]):
            self._metrics.inc(
                "reviewer.fallbacks",
                {"reason": "business_invalid", "path": path},
            )
            log.warning(
                "llm_business_invalid_class",
                path=path,
                name=corrected.get("class_name"),
            )
            return None

        return data

    def review_batch(self, entries: list[UncertainEntry]) -> dict[str, dict | None]:
        """v1.2 批处理：单次 LLM API 调用处理多条 uncertain 条目。

        与逐条 review() 的对比：
          - 逐条：N 次 HTTP RTT + N 次 Provider 调用 ≈ N × (RTT + 推理时间)
          - 批处理：1 次 HTTP RTT + 1 次 Provider 调用 ≈ RTT + N × (推理时间 / batch)
          - 典型节省：80% 网络开销（HTTP RTT 占总耗时 ~95%）

        错误隔离策略：
          - 整批调用失败（Provider 异常）→ 全部 entries 返回 None
          - JSON 解析失败 → 全部 entries 返回 None（fallback）
          - 单条响应业务校验失败 → 仅该条返回 None，其他正常应用

        v1.3 observability：埋点与 _review_one 对齐（path=batch），
        另加 reviewer.batch.size gauge 记录本次批次规模。

        Returns:
            {case_id: revision_dict_or_None}：与 entries 一一对应
        """
        if not entries:
            return {}

        # v1.3 observability：记录批次规模
        self._metrics.set_gauge("reviewer.batch.size", len(entries), {"path": "batch"})

        # Step 1: 优先用 cache（per-case_id 粒度，避免重复请求）
        results: dict[str, dict | None] = {}
        to_call: list[UncertainEntry] = []
        for entry in entries:
            cached: str | None = None
            if self._cache is not None:
                try:
                    cached = self._cache.get(entry.case_id)
                    if cached is not None:
                        self._metrics.inc(
                            "reviewer.cache", {"result": "hit", "path": "batch"}
                        )
                    else:
                        self._metrics.inc(
                            "reviewer.cache", {"result": "miss", "path": "batch"}
                        )
                except Exception as e:
                    self._metrics.inc(
                        "reviewer.cache", {"result": "failure", "path": "batch"}
                    )
                    log.warning("cache_read_failed", case_id=entry.case_id, error=str(e))
            if cached is not None:
                results[entry.case_id] = self._parse_response(cached, entry.case_id, path="batch")
            else:
                to_call.append(entry)

        if not to_call:
            log.info("batch_all_cache_hits", count=len(entries))
            return results

        # Step 2: 批量调用 LLM（单次 HTTP RTT）
        prompt = build_batch_review_prompt(
            to_call,
            known_namespaces=self._known_namespaces,
            known_classes=self._registry.all_names(),
        )
        start = time.perf_counter()
        try:
            raw = self._provider.review(prompt)
            elapsed = time.perf_counter() - start
            self._metrics.observe(
                "reviewer.latency", elapsed, {"path": "batch", "outcome": "success"}
            )
            self._metrics.inc(
                "reviewer.calls", {"outcome": "success", "path": "batch"}
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            self._metrics.observe(
                "reviewer.latency", elapsed, {"path": "batch", "outcome": "failure"}
            )
            self._metrics.inc(
                "reviewer.calls", {"outcome": "failure", "path": "batch"}
            )
            self._metrics.inc(
                "reviewer.fallbacks",
                {"reason": "provider_exception", "path": "batch"},
                value=len(to_call),
            )
            log.warning("batch_llm_call_failed", count=len(to_call), error=str(e))
            # 整批失败：所有待调条目返回 None（fallback）
            for entry in to_call:
                results[entry.case_id] = None
            return results

        # Step 3: 解析批量 JSON array
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._metrics.inc(
                "reviewer.fallbacks",
                {"reason": "json_invalid", "path": "batch"},
                value=len(to_call),
            )
            log.warning("batch_invalid_json", raw=raw[:100])
            for entry in to_call:
                results[entry.case_id] = None
            return results

        if not isinstance(data, list):
            self._metrics.inc(
                "reviewer.fallbacks",
                {"reason": "invalid_format", "path": "batch"},
                value=len(to_call),
            )
            log.warning("batch_invalid_format", type=type(data).__name__)
            for entry in to_call:
                results[entry.case_id] = None
            return results

        # Step 4: 按 case_id 索引 + 错误隔离
        by_case: dict[str, dict] = {}
        for item in data:
            if isinstance(item, dict) and "case_id" in item:
                by_case[item["case_id"]] = item

        for entry in to_call:
            item = by_case.get(entry.case_id)
            if item is None:
                # LLM 没返回这一条 → fallback
                self._metrics.inc(
                    "reviewer.fallbacks", {"reason": "missing_entry", "path": "batch"}
                )
                results[entry.case_id] = None
                continue
            # 单条业务校验
            parsed = self._validate_one_response(item, entry.case_id, path="batch")
            results[entry.case_id] = parsed
            # 单条 cache 回写（无论成功失败）
            if self._cache is not None:
                try:
                    self._cache.put(entry.case_id, json.dumps(item))
                except Exception as e:
                    log.warning("cache_write_failed", case_id=entry.case_id, error=str(e))

        log.info(
            "batch_review_done",
            total=len(entries),
            from_cache=len(entries) - len(to_call),
            from_llm=len(to_call),
        )
        return results

    def _parse_response(self, raw: str, case_id: str, path: str = "single") -> dict | None:
        """解析单条 LLM 响应（从 cache 读取时用）。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._metrics.inc(
                "reviewer.fallbacks", {"reason": "json_invalid", "path": path}
            )
            log.warning("llm_invalid_json", case_id=case_id, path=path, raw=raw[:100])
            return None
        return self._validate_one_response(data, case_id, path=path)

    def _validate_one_response(self, data: dict, case_id: str, path: str = "single") -> dict | None:
        """单条响应业务校验：class_name 必须存在于 known_classes。"""
        if not isinstance(data, dict):
            return None
        corrected = data.get("corrected", {})
        if corrected.get("class_name") and not self._registry.has(corrected["class_name"]):
            self._metrics.inc(
                "reviewer.fallbacks",
                {"reason": "business_invalid", "path": path},
            )
            log.warning(
                "llm_business_invalid_class",
                case_id=case_id,
                path=path,
                name=corrected.get("class_name"),
            )
            return None
        return data