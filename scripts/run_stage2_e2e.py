"""Stage 2 真实 LLM e2e：批处理 review 真实 fixture 的所有 uncertain entries。

输入：cim-base-full.md
输出：metrics snapshot + before/after IR 统计

使用 .env 加载 API Key（gitignored）。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _load_env import load_env
load_env()

from cim_ontology.cleaner.orchestrator import clean_markdown_to_ir
from cim_ontology.reviewer.providers_deepseek import DeepSeekProvider
from cim_ontology.reviewer.reviewer import LLMReviewer
from cim_ontology.reviewer.cache import LLMCache
from cim_ontology.observability import Metrics


def main():
    md = Path("docs/GBT43259301—2024/cim-base-full.md")
    out_dir = Path("/tmp/cim_e2e_full")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Stage 2 真实 LLM e2e: DeepSeek batch review")
    print("=" * 60)

    # Stage 1
    t0 = time.perf_counter()
    ir = clean_markdown_to_ir(md)
    s1 = (time.perf_counter() - t0) * 1000
    print(f"\nStage 1: {s1:.0f} ms")
    print(f"  packages: {len(ir.packages)}")
    print(f"  classes: {sum(len(p.classes) for p in ir.packages)}")
    print(f"  uncertain_entries: {len(ir.uncertain_entries)}")

    # 去重 (case_id 不唯一)
    unique_entries = {e.case_id: e for e in ir.uncertain_entries}.values()
    entries_list = list(unique_entries)
    print(f"  unique case_ids: {len(entries_list)}")

    # Stage 2 setup
    provider = DeepSeekProvider()
    cache = LLMCache(path=Path(".cache/llm_reviews_full.db"))

    # Fix: 自动从 Stage 1 IR 提取所有类名 + 从 fixture 加载，组成完整 known_classes
    # 原因：v1.3 之前的 e2e 传 known_classes=None → registry 为空 → business check 拒绝所有
    from cim_ontology.reviewer.reviewer import load_known_classes_from_file
    fixture_kc = load_known_classes_from_file("tests/fixtures/cim_known_classes.txt")
    ir_kc = list({c.name for p in ir.packages for c in p.classes})
    full_kc = sorted(set(fixture_kc) | set(ir_kc))
    print(f"  known_classes: fixture={len(fixture_kc)}, from_ir={len(ir_kc)}, merged={len(full_kc)}")

    metrics = Metrics()
    reviewer = LLMReviewer(
        provider=provider,
        cache=cache,
        metrics=metrics,
        known_classes=full_kc,
    )

    # 分批 (batch_size=14 跟随现有 fixtures)
    BATCH_SIZE = 14
    n_batches = (len(entries_list) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nStage 2: {len(entries_list)} entries × {BATCH_SIZE} = {n_batches} batches")

    t0 = time.perf_counter()
    all_results = []
    failed_batches = 0
    for i in range(0, len(entries_list), BATCH_SIZE):
        batch = entries_list[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        try:
            results = reviewer.review_batch(batch)
            all_results.extend(results)
            if batch_num % 10 == 0 or batch_num == n_batches:
                print(f"  batch {batch_num}/{n_batches} done ({len(all_results)} entries processed)")
        except Exception as e:
            failed_batches += 1
            print(f"  batch {batch_num}/{n_batches} FAILED: {type(e).__name__}: {str(e)[:80]}")
    total_elapsed = (time.perf_counter() - t0) * 1000
    print(f"\nStage 2 total: {total_elapsed:.0f} ms ({total_elapsed / 1000:.1f}s)")
    print(f"  results collected: {len(all_results)}")
    print(f"  failed batches: {failed_batches}")

    # 应用修订到 IR（用公开 API reviewer.review(ir)）
    t0 = time.perf_counter()
    ir_after = reviewer.review(ir)
    apply_elapsed = (time.perf_counter() - t0) * 1000
    print(f"\nreviewer.review(ir): {apply_elapsed:.0f} ms")

    # IR 统计 before/after
    print(f"\n=== IR before vs after ===")
    print(f"  before: {sum(len(p.classes) for p in ir.packages)} classes, {len(ir.uncertain_entries)} uncertain")
    print(f"  after:  {sum(len(p.classes) for p in ir_after.packages)} classes, {len(ir_after.uncertain_entries)} uncertain")

    # Metrics summary
    snap = metrics.snapshot()
    print(f"\n=== Metrics ===")
    print(f"Counters:")
    for c in snap["counters"]:
        print(f"  {c['name']} {c['labels']}: {c['value']}")
    print(f"Histograms:")
    for h in snap["histograms"]:
        avg = h['sum'] / h['count'] if h['count'] else 0
        print(f"  {h['name']} {h['labels']}: count={h['count']}, sum={h['sum']:.2f}, avg={avg:.2f}")
    print(f"Gauges:")
    for g in snap["gauges"]:
        print(f"  {g['name']} {g['labels']}: {g['value']}")

    # 序列化 IR after 用于 Stage 3
    ir_after_json = out_dir / "ir_after.json"
    if hasattr(ir_after, "model_dump_json"):
        ir_after_json.write_text(ir_after.model_dump_json(indent=2))
    else:
        import json
        ir_after_json.write_text(json.dumps({
            "packages": [{"name": p.name, "classes": [c.name for c in p.classes]} for p in ir_after.packages],
            "uncertain_entries": len(ir_after.uncertain_entries),
        }, indent=2))
    print(f"\nIR after → {ir_after_json}")

    metrics_json = out_dir / "metrics.json"
    metrics_json.write_text(__import__('json').dumps(snap, indent=2))
    print(f"Metrics → {metrics_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())