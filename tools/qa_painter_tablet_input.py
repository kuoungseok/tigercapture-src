from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture actual Painter QTabletEvent evidence")
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    args = parser.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from app.painter_evidence_contract import evidence_record
    from app.painter_native_environment import environment_overrides, is_native_qt_environment
    from app.painter_tablet_capture import PainterTabletCaptureSurface, summarize_tablet_events

    app = QApplication.instance() or QApplication([])
    surface = PainterTabletCaptureSurface()
    surface.show()
    duration_ms = max(250, int(float(args.duration_seconds) * 1000.0))
    QTimer.singleShot(duration_ms, app.quit)
    app.exec()

    summary = summarize_tablet_events(surface.events)
    native = is_native_qt_environment(app.platformName(), environment_overrides())
    passed = bool(native and summary["required_sequence_captured"] and summary["device_count"] > 0)
    root = ROOT / "debugCapture" / "painter" / "tablet_input"
    root.mkdir(parents=True, exist_ok=True)
    raw_path = root / "events.json"
    raw_path.write_text(json.dumps(surface.events, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = evidence_record(
        "physical-tablet-qtabletevent",
        "physical_hardware",
        passed=passed,
        producer="tools/qa_painter_tablet_input.py",
        claims=("physical_tablet_input",),
        command=f"python tools/qa_painter_tablet_input.py --duration-seconds {args.duration_seconds:g}",
        environment={"qt_platform": app.platformName(), "overrides": environment_overrides()},
        artifacts=(raw_path,),
        limitations=summary["limitations"],
    )
    report = {
        "schema": "tigerstudio.painter.physical-tablet-qa.v1",
        "classification": "physical_hardware" if passed else "blocked_external",
        "duration_ms": duration_ms,
        "native_environment": native,
        "summary": summary,
        "events_path": str(raw_path.resolve()),
        "provenance": [provenance],
        "passed": passed,
    }
    destination = root / "report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(destination.resolve()), **summary, "passed": passed}, ensure_ascii=False))
    surface.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
