from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mmd.editor_composite_qa import (
    DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR,
    DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT,
    run_mmd_editor_composite_qa,
)
from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MMD editor video-composite/export smoke QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MMD_QA_MANIFEST)
    parser.add_argument("--entry-id", default=DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--duration-ms", type=int, default=1000)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--sample-time-ms", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = run_mmd_editor_composite_qa(
        manifest=args.manifest,
        entry_id=args.entry_id,
        out_dir=args.out_dir,
        report_path=args.report,
        width=args.width,
        height=args.height,
        duration_ms=args.duration_ms,
        fps=args.fps,
        sample_time_ms=args.sample_time_ms,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"ok            : {bool(payload.get('ok'))}")
        print(f"entry_id      : {payload.get('entry_id')}")
        print(f"report        : {payload.get('report')}")
        print(f"preview_png   : {payload.get('outputs', {}).get('preview_composite')}")
        print(f"export_frame  : {payload.get('outputs', {}).get('export_frame')}")
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        print(f"alpha_coverage: {float(summary.get('alpha_coverage', 0.0) or 0.0):.4f}")
        print(f"export_inside : {float(summary.get('export_inside_mean_abs_diff', 0.0) or 0.0):.3f}")
        print(f"export_outside: {float(summary.get('export_outside_mean_abs_diff', 0.0) or 0.0):.3f}")
        failures = list(payload.get("failures") or [])
        if failures:
            print("failures      :")
            for failure in failures:
                print(f"  - {failure}")
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
