"""Build the final product-readiness gate report.

This is the high-level QA entry point for the remaining commercial polish:
real editing flow, corpus coverage, Screen Studio interaction evidence,
preview/GPU performance, Color/Audio accuracy, timeline feel, preset quality,
crash recovery, and packaging.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_final_product_readiness_qa(*, out: str | Path = "debugCapture/final_product_readiness_qa.json") -> dict:
    from app.final_product_readiness import build_final_product_readiness_report

    report = build_final_product_readiness_report(ROOT)
    out_path = ROOT / Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build final TigerCapture product-readiness report.")
    parser.add_argument("--out", default="debugCapture/final_product_readiness_qa.json")
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Write the report but return 0 even when release_ready is false.",
    )
    args = parser.parse_args()
    report = run_final_product_readiness_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {ROOT / Path(args.out)}")
    return 0 if args.allow_not_ready or report.get("release_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
