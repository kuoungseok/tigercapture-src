from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pptgen.export_qa import run_ppt_export_qa


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TigerCapture PPT export QA.")
    parser.add_argument("--out-dir", default="debugCapture/ppt_export_qa", help="QA artifact output directory.")
    parser.add_argument("--skip-pdf", action="store_true", help="Do not attempt PDF export.")
    parser.add_argument("--require-pdf", action="store_true", help="Fail QA if PDF export cannot be produced.")
    parser.add_argument("--pdf-backend", default="auto", choices=("auto", "libreoffice", "powerpoint", "powerpoint_com"))
    parser.add_argument("--skip-video", action="store_true", help="Do not export MP4 video.")
    parser.add_argument("--video-fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    manifest = run_ppt_export_qa(
        args.out_dir,
        export_pdf=not bool(args.skip_pdf),
        require_pdf=bool(args.require_pdf),
        pdf_backend=args.pdf_backend,
        export_video=not bool(args.skip_video),
        video_fps=int(args.video_fps or 12),
        width=int(args.width or 1280),
        height=int(args.height or 720),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0 if manifest.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
