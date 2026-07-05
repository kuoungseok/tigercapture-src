from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio manual zoom editing QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_manual_zoom_qa.json"))
    args = parser.parse_args()

    from app.screenstudio_polish import screenstudio_manual_zoom_editor_report

    report = screenstudio_manual_zoom_editor_report()
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["kind"] = "screenstudio_manual_zoom"
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report.get("ok"), "score": report.get("score"), "out": str(out)}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
