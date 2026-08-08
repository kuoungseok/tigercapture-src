"""Turn a completed raw two-hour Painter soak into narrowly scoped evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _latest_completed_raw_report() -> Path:
    candidates: list[Path] = []
    for path in (ROOT / "debugCapture" / "painter" / "soak").glob("*/report.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            payload.get("schema") == "tigerstudio.painter.native-soak-measurement.v1"
            and float(payload.get("requested_duration_seconds") or 0) >= 7200.0
        ):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("No completed 7200-second raw Painter soak report found")
    return max(candidates, key=lambda item: item.stat().st_mtime_ns)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_report", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw_path = (args.raw_report or _latest_completed_raw_report()).resolve()
    output = (args.output or ROOT / "debugCapture" / "painter" / "soak" / "long_session_acceptance" / "report.json").resolve()

    from app.painter_soak_acceptance import evaluate_long_soak

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    report = evaluate_long_soak(raw, raw_report_path=raw_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "passed": report["passed"], "failures": report["failures"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
