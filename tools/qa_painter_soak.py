from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure a bounded native Painter soak workload")
    parser.add_argument("--duration-seconds", type=float, default=120.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=1.0)
    parser.add_argument("--operation-interval-ms", type=float, default=20.0)
    parser.add_argument("--release-evidence", action="store_true")
    args = parser.parse_args()
    requested_duration = max(1.0, float(args.duration_seconds))
    if args.release_evidence and requested_duration < 7200.0:
        print(json.dumps({
            "passed": False,
            "reason": "release soak requires at least 7200 measured seconds",
            "requested_duration_seconds": requested_duration,
        }))
        return 2

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    root = ROOT / "debugCapture" / "painter" / "soak" / run_id
    data_root = root / "runtime_data"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["TIGERCAPTURE_DATA_DIR"] = str(data_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_evidence_contract import evidence_record
    from app.painter_native_environment import environment_overrides, is_native_qt_environment
    from app.painter_runtime_metrics import resource_sample, summarize_runtime_samples

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1024, 768, "#263A50"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.resize(1100, 720)
    dialog.show()
    dialog._painter_recovery_timer.stop()
    app.processEvents()

    samples = []
    latencies = []
    operation_errors = []
    operation_count = 0
    cycle_count = 0
    started = time.perf_counter()
    next_sample = started
    interval = max(0.0, float(args.operation_interval_ms) / 1000.0)
    sample_interval = max(0.1, float(args.sample_interval_seconds))
    while True:
        now = time.perf_counter()
        elapsed = now - started
        if elapsed >= requested_duration:
            break
        try:
            op_started = time.perf_counter()
            phase = operation_count % 120
            if phase < 100:
                index = operation_count
                x0 = ((index * 37) % 900) / 1024.0
                y0 = ((index * 53) % 650) / 768.0
                dialog.canvas.add_stroke_direct(Stroke(
                    points=[(x0, y0), (min(0.98, x0 + 0.08), min(0.98, y0 + 0.05))],
                    color=(45 + index % 180, 110, 220 - index % 120),
                    opacity=220,
                    width_px=4.0 + index % 18,
                    brush_style="round",
                    point_pressure=[0.3, 0.85],
                ))
            elif phase == 100:
                dialog._painter_composite_pil(include_background=False)
            elif phase == 101:
                dialog._painter_document_dirty = True
                scheduled = dialog._schedule_painter_recovery_snapshot(force=True)
                if scheduled.get("scheduled"):
                    dialog._painter_recovery_future.result(timeout=30)
            elif phase == 119:
                dialog.canvas.set_strokes_snapshot([])
                gc.collect()
                cycle_count += 1
            app.processEvents()
            latencies.append((time.perf_counter() - op_started) * 1000.0)
        except Exception as exc:
            operation_errors.append({
                "operation": operation_count,
                "type": type(exc).__name__,
                "message": str(exc),
            })
        operation_count += 1
        now = time.perf_counter()
        if now >= next_sample:
            samples.append(resource_sample(
                elapsed_seconds=now - started,
                operation_count=operation_count,
                cycle_count=cycle_count,
            ))
            next_sample = now + sample_interval
        if interval:
            time.sleep(interval)

    ended = time.perf_counter()
    samples.append(resource_sample(
        elapsed_seconds=ended - started,
        operation_count=operation_count,
        cycle_count=cycle_count,
    ))
    summary = summarize_runtime_samples(samples, latencies)
    native = is_native_qt_environment(app.platformName(), environment_overrides())
    measurement_completed = bool(native and not operation_errors and cycle_count > 0)
    # A single run has no evidence-derived leak envelope. Even a two-hour run
    # remains a measurement until repeated baselines define comparison bounds.
    release_claim_passed = False
    report_path = root / "report.json"
    provenance = evidence_record(
        "native-painter-soak-measurement",
        "native_runtime",
        passed=release_claim_passed,
        producer="tools/qa_painter_soak.py",
        claims=(),
        command=(
            f"python tools/qa_painter_soak.py --duration-seconds {requested_duration:g}"
            + (" --release-evidence" if args.release_evidence else "")
        ),
        environment={"qt_platform": app.platformName(), "overrides": environment_overrides()},
        artifacts=(),
        limitations=(
            "This run reports raw slopes and percentiles; no evidence-derived acceptance envelope exists yet.",
            "The workload is cyclic and bounded so retained growth can be distinguished from expected document growth.",
        ),
    )
    report = {
        "schema": "tigerstudio.painter.native-soak-measurement.v1",
        "run_id": run_id,
        "classification": "native_runtime_measurement_not_release_evidence",
        "requested_duration_seconds": requested_duration,
        "measured_duration_seconds": ended - started,
        "native_environment": native,
        "workload": {
            "cycle_operations": 120,
            "strokes_per_cycle": 100,
            "operation_count": operation_count,
            "cycle_count": cycle_count,
        },
        "samples": samples,
        "summary": summary,
        "operation_errors": operation_errors,
        "measurement_completed": measurement_completed,
        "release_claim_passed": release_claim_passed,
        "provenance": [provenance],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(report_path.resolve()),
        "measurement_completed": measurement_completed,
        "release_claim_passed": release_claim_passed,
        "duration_seconds": round(ended - started, 3),
        "operation_count": operation_count,
        "cycle_count": cycle_count,
        "latency_ms": summary["operation_latency_ms"],
        "resource_deltas": {
            key: row["delta"] for key, row in summary["resources"].items()
        },
    }, ensure_ascii=False))
    dialog.close()
    app.processEvents()
    return 0 if measurement_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
