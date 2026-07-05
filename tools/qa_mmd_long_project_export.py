from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST
from app.mmd.render_queue_qa import (
    DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT,
    DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    run_mmd_long_project_export_qa,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run long-project MMD render-queue export QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MMD_QA_MANIFEST)
    parser.add_argument("--entry-id", default=DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=270)
    parser.add_argument("--duration-ms", type=int, default=10000)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = run_mmd_long_project_export_qa(
        manifest=args.manifest,
        entry_id=args.entry_id,
        out_dir=args.out_dir,
        report_path=args.report,
        width=args.width,
        height=args.height,
        duration_ms=args.duration_ms,
        fps=args.fps,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        print(f"ok              : {bool(payload.get('ok'))}")
        print(f"entry_id        : {payload.get('entry_id')}")
        print(f"report          : {payload.get('report')}")
        print(f"out_dir         : {payload.get('outputs', {}).get('out_dir')}")
        print(f"duration_ms     : {payload.get('duration_ms')}")
        print(f"total_output_ms : {payload.get('total_output_ms')}")
        print(f"queued_jobs     : {summary.get('queued_jobs')}")
        print(f"mmd_track_count : {summary.get('mmd_track_count')}")
        print(f"pre_render_count: {summary.get('pre_render_count')}")
        print(f"pre_render_sizes: {summary.get('pre_render_sizes')}")
        print(f"segments        : {payload.get('segments')}")
        print(f"sample_project  : {summary.get('sample_project_ms')}")
        print(f"export_inside   : {float(summary.get('max_export_inside_mean_abs_diff', 0.0) or 0.0):.3f}")
        print(f"export_outside  : {float(summary.get('max_export_outside_mean_abs_diff', 0.0) or 0.0):.3f}")
        failures = list(payload.get("failures") or [])
        if failures:
            print("failures        :")
            for failure in failures:
                print(f"  - {failure}")
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
