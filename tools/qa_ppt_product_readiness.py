from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pptgen.product_readiness import run_ppt_product_readiness_qa


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TigerCapture PPT product-readiness QA scenarios.")
    parser.add_argument("--out-dir", default="debugCapture/ppt_product_readiness", help="QA artifact output directory.")
    parser.add_argument("--video", action="store_true", help="Export MP4 videos for each readiness scenario.")
    parser.add_argument("--video-fps", type=int, default=8)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--warning-budget", type=int, default=6)
    args = parser.parse_args()

    manifest = run_ppt_product_readiness_qa(
        args.out_dir,
        export_video=bool(args.video),
        video_fps=int(args.video_fps or 8),
        width=int(args.width or 960),
        height=int(args.height or 540),
        warning_budget=int(args.warning_budget),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0 if manifest.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
