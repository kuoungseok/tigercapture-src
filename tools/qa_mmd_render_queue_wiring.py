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
    DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    DEFAULT_MMD_RENDER_QUEUE_QA_REPORT,
    run_mmd_render_queue_wiring_qa,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MMD render-queue export wiring QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MMD_QA_MANIFEST)
    parser.add_argument("--entry-id", default=DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_MMD_RENDER_QUEUE_QA_REPORT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = run_mmd_render_queue_wiring_qa(
        manifest=args.manifest,
        entry_id=args.entry_id,
        out_dir=args.out_dir,
        report_path=args.report,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        print(f"ok              : {bool(payload.get('ok'))}")
        print(f"entry_id        : {payload.get('entry_id')}")
        print(f"report          : {payload.get('report')}")
        print(f"out_dir         : {payload.get('outputs', {}).get('out_dir')}")
        print(f"queued_jobs     : {summary.get('queued_jobs')}")
        print(f"pre_render_calls: {summary.get('pre_render_calls')}")
        print(f"thread_inits    : {summary.get('thread_inits')}")
        print(f"segments        : {summary.get('segments')}")
        print(f"progress_values : {summary.get('progress_values')}")
        failures = list(payload.get("failures") or [])
        if failures:
            print("failures        :")
            for failure in failures:
                print(f"  - {failure}")
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
