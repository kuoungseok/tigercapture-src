from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation.paths import DEFAULT_REVIEW_OUTPUT_DIR, DEFAULT_REVIEW_REPORT, DEFAULT_REVIEW_SAMPLE_REPORT, DEFAULT_REVIEW_SAMPLE_ROOT


def main() -> int:
    from tools.generate_review_assets import generate_review_assets

    parser = argparse.ArgumentParser(description="Build the TigerCapture review automation PPTX deck.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REVIEW_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument("--sample-root", type=Path, default=DEFAULT_REVIEW_SAMPLE_ROOT)
    parser.add_argument("--sample-report", type=Path, default=DEFAULT_REVIEW_SAMPLE_REPORT)
    parser.add_argument(
        "--deck-mode",
        choices=("summary", "detailed", "evidence-full"),
        default="summary",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.run_qa = False
    args.skip_html = True
    args.skip_ppt = False
    args.manifest_only = False
    report = generate_review_assets(args)
    print(json.dumps({"ok": report.get("ok"), "pptx": report.get("outputs", {}).get("pptx")}, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
