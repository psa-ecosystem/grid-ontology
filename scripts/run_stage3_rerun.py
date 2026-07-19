"""Stage 3 重新验证：用 Stage 2 修订后的 IR 重跑 5 个适配器。

输入：/tmp/cim_e2e_full/ir_after.json（Stage 2 后，含 946 LLM 修正）
对比：/tmp/cim_e2e/build/（Stage 2 前的 5 适配器产物）
输出：/tmp/cim_e2e_full/build/ 新产物 + 对比报告
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# `src/` 也在 path 上以便 pyright 在 IDE 中解析（运行时无影响）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cim_ontology.ir.models import OntologyIR
from cim_ontology.adapters import get_adapter


def main():
    ir_path = Path("/tmp/cim_e2e_full/ir_after.json")
    out_dir = Path("/tmp/cim_e2e_full/build")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Stage 3 Rerun: 5 适配器 (修订后 IR)")
    print("=" * 60)

    # 加载修订后 IR
    t0 = time.perf_counter()
    ir_after = OntologyIR.model_validate_json(ir_path.read_text(encoding="utf-8"))
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"\nIR 加载: {load_ms:.0f} ms")
    print(f"  packages: {len(ir_after.packages)}")
    print(f"  classes: {sum(len(p.classes) for p in ir_after.packages)}")
    print(f"  uncertain_entries: {len(ir_after.uncertain_entries)}")

    # 5 个适配器
    ADAPTERS = ["owl", "shacl", "jsonld-context", "json-schema", "python-types"]
    results = {}
    for fmt in ADAPTERS:
        print(f"\n--- {fmt} ---")
        try:
            adapter = get_adapter(fmt)
            t0 = time.perf_counter()
            adapter.emit(ir_after, out_dir / fmt)
            elapsed = (time.perf_counter() - t0) * 1000

            out_files = sorted(p for p in (out_dir / fmt).iterdir() if p.is_file())
            total_bytes = sum(p.stat().st_size for p in out_files)

            results[fmt] = {
                "status": "ok",
                "elapsed_ms": elapsed,
                "files": len(out_files),
                "bytes": total_bytes,
            }
            print(f"  ✅ {elapsed:.0f} ms / {len(out_files)} files / {total_bytes/1024:.1f} KB")
        except Exception as e:
            elapsed = 0
            results[fmt] = {
                "status": "error",
                "error_type": type(e).__name__,
                "error": str(e)[:200],
            }
            print(f"  ❌ {type(e).__name__}: {str(e)[:200]}")

    # 对比修订前 /tmp/cim_e2e/build/
    print(f"\n=== 对比：修订前 (Stage 1 only) vs 修订后 (Stage 2 LLM) ===")
    before = Path("/tmp/cim_e2e/build")
    for fmt in ADAPTERS:
        b_files = sorted(p for p in (before / fmt).iterdir() if p.is_file()) if (before / fmt).exists() else []
        a_files = sorted(p for p in (out_dir / fmt).iterdir() if p.is_file()) if (out_dir / fmt).exists() else []
        b_bytes = sum(p.stat().st_size for p in b_files)
        a_bytes = sum(p.stat().st_size for p in a_files)
        delta_files = len(a_files) - len(b_files)
        delta_bytes = a_bytes - b_bytes
        r = results.get(fmt, {})
        status = r.get("status", "?")
        print(f"  {fmt:18s}: before={len(b_files)}/{b_bytes/1024:7.1f}KB → "
              f"after={len(a_files)}/{a_bytes/1024:7.1f}KB "
              f"(Δ {delta_files:+d} files, {delta_bytes:+d} B) [{status}]")

    # 写入摘要
    summary = {
        "ir_after_uncertain": len(ir_after.uncertain_entries),
        "adapters": results,
    }
    summary_path = Path("/tmp/cim_e2e_full/stage3_rerun_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n摘要 → {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
