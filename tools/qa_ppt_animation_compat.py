from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pptgen.animation_qa import write_animation_qa_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a PPTX animation compatibility QA deck.")
    parser.add_argument(
        "--out-dir",
        default="debugCapture/ppt_animation_compat",
        help="Directory for PPTX, .tgppt, PNG previews, contact sheet, and manifest.",
    )
    parser.add_argument(
        "--host-check",
        choices=("none", "auto", "libreoffice", "powerpoint"),
        default="none",
        help="Optionally validate the generated PPTX through an installed Office host.",
    )
    parser.add_argument(
        "--require-host",
        action="store_true",
        help="Fail the QA if --host-check does not produce a passed host validation.",
    )
    parser.add_argument(
        "--host-timeout-sec",
        type=int,
        default=60,
        help="Timeout for each host validation command.",
    )
    args = parser.parse_args()
    manifest = write_animation_qa_outputs(
        Path(args.out_dir),
        host_check=args.host_check,
        require_host=bool(args.require_host),
        host_timeout_sec=max(1, int(args.host_timeout_sec)),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
