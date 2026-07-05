"""Build the Descript-lite implementation plan QA report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "descript_lite_implementation_plan_qa.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Descript-lite implementation plan report.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    from app.descript_lite_implementation_plan import build_descript_lite_implementation_plan

    report = build_descript_lite_implementation_plan()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "items": int(dict(report.get("summary") or {}).get("items", 0) or 0),
                "video_editor_window_primary_touches": int(
                    dict(report.get("summary") or {}).get("video_editor_window_primary_touches", 0) or 0
                ),
                "report": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
