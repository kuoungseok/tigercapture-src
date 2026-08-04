from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure Painter GL context creation during a bounded stroke cycle"
    )
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--strokes-per-cycle", type=int, default=100)
    args = parser.parse_args()

    root = ROOT / "debugCapture" / "painter" / "gl_context_churn"
    root.mkdir(parents=True, exist_ok=True)
    data_root = root / "runtime_data"
    # Painter modules resolve durable state paths during import.  Set the
    # isolated QA root first so the diagnostic cannot touch the user's normal
    # palette/recovery state.
    os.environ["TIGERCAPTURE_DATA_DIR"] = str(data_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    import app.painter_opengl as painter_opengl
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_native_environment import (
        environment_overrides,
        is_native_qt_environment,
    )
    from app.painter_runtime_metrics import windows_process_resources

    app = QApplication.instance() or QApplication([])
    original_make_context = painter_opengl._make_offscreen_context
    context_creations = 0

    def counted_make_context():
        nonlocal context_creations
        context_creations += 1
        return original_make_context()

    painter_opengl._make_offscreen_context = counted_make_context
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
    before = windows_process_resources()
    started = time.perf_counter()
    errors: list[str] = []
    operation_count = 0
    try:
        for cycle in range(max(1, int(args.cycles))):
            for index in range(max(1, int(args.strokes_per_cycle))):
                absolute = cycle * max(1, int(args.strokes_per_cycle)) + index
                x0 = ((absolute * 37) % 900) / 1024.0
                y0 = ((absolute * 53) % 650) / 768.0
                dialog.canvas.add_stroke_direct(
                    Stroke(
                        points=[
                            (x0, y0),
                            (min(0.98, x0 + 0.08), min(0.98, y0 + 0.05)),
                        ],
                        color=(45 + absolute % 180, 110, 220 - absolute % 120),
                        opacity=220,
                        width_px=4.0 + absolute % 18,
                        brush_style="round",
                        point_pressure=[0.3, 0.85],
                    )
                )
                app.processEvents()
                operation_count += 1
            dialog.canvas.set_strokes_snapshot([])
            app.processEvents()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        painter_opengl._make_offscreen_context = original_make_context
    after = windows_process_resources()
    elapsed = time.perf_counter() - started
    report = {
        "schema": "tigerstudio.painter.gl-context-churn-diagnostic.v1",
        "classification": "diagnostic_measurement_not_acceptance",
        "native_environment": is_native_qt_environment(
            app.platformName(), environment_overrides()
        ),
        "cycles": max(1, int(args.cycles)),
        "strokes_per_cycle": max(1, int(args.strokes_per_cycle)),
        "operation_count": operation_count,
        "context_creations": context_creations,
        "context_creations_per_operation": (
            context_creations / operation_count if operation_count else None
        ),
        "elapsed_seconds": elapsed,
        "before": before,
        "after": after,
        "resource_delta": {
            key: int(after[key]) - int(before[key])
            for key in ("working_set_bytes", "private_usage_bytes")
            if before.get(key) is not None and after.get(key) is not None
        },
        "errors": errors,
        "claims": {
            "context_churn_observed": bool(context_creations),
            "root_cause_proven": False,
            "leak_free": False,
        },
    }
    path = root / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path.resolve()), **report}, ensure_ascii=False))
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
