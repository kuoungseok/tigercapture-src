from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pptgen.release_acceptance import run_ppt_release_acceptance_qa


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TigerCapture PPT release-acceptance QA through item 4.")
    parser.add_argument("--out-dir", default="debugCapture/ppt_release_acceptance")
    parser.add_argument("--host-backend", default="auto", choices=("auto", "libreoffice", "powerpoint", "powerpoint_com"))
    parser.add_argument("--host-timeout-sec", type=int, default=45)
    parser.add_argument("--require-office-host", action="store_true")
    parser.add_argument("--stability-iterations", type=int, default=80)
    parser.add_argument("--parity-fps", type=int, default=6)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    args = parser.parse_args()

    manifest = run_ppt_release_acceptance_qa(
        args.out_dir,
        host_backend=args.host_backend,
        host_timeout_sec=int(args.host_timeout_sec or 45),
        require_office_host=bool(args.require_office_host),
        stability_iterations=int(args.stability_iterations or 80),
        parity_fps=int(args.parity_fps or 6),
        width=int(args.width or 640),
        height=int(args.height or 360),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0 if manifest.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
