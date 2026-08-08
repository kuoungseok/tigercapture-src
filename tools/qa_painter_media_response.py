"""Write the reproducible Painter media parameter-response report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debugCapture/painter/media_response/report.json"),
    )
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.painter_media_response import measure_painter_media_response

    _app = QApplication.instance() or QApplication([])
    report = measure_painter_media_response()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "schema": report["schema"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
