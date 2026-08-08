from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import sleep

if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QT_OPENGL", "desktop")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "gpu_context_recovery"


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Context Recovery Vector", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "star", "width": 360, "height": 360, "sides": 7,
            "inner_ratio": 0.46, "fill": "#42d6b5", "stroke": "#ffffff",
            "stroke_width": 6,
        }), out_ms=2000,
    )
    layer.transform.position.default = [480, 270]
    layer.transform.rotation.default = 17
    return MotionComposition(width=960, height=540, duration_ms=2000, layers=[layer])


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine(),
    )
    return data[:, : converted.width() * 4].reshape(converted.height(), converted.width(), 4).copy()


def _open_and_capture(app: QApplication, composition: MotionComposition, output: Path,
                      destruction: list[bool]) -> tuple[dict, np.ndarray]:
    window = MotionDesignerWindow(composition)
    window.setAttribute(Qt.WA_DeleteOnClose, True)
    window.resize(1400, 860)
    window.show()
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(700)
    for _ in range(45):
        app.processEvents()
        sleep(0.015)
    context = window.preview.context()
    if context is not None:
        context.aboutToBeDestroyed.connect(lambda: destruction.append(True))
    framebuffer = window.preview.grabFramebuffer()
    diagnostics = window.preview.diagnostics()
    if framebuffer.isNull() or not framebuffer.save(str(output), "PNG"):
        raise RuntimeError(f"Could not capture Motion GPU recovery frame: {output}")
    pixels = _rgba(framebuffer)
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    for _ in range(10):
        app.processEvents()
        sleep(0.01)
    return diagnostics, pixels


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    composition = _composition()
    destroyed: list[bool] = []
    first_diagnostics, first = _open_and_capture(
        app, composition, OUTPUT / "before_context_destroy.png", destroyed,
    )
    second_diagnostics, second = _open_and_capture(
        app, composition, OUTPUT / "after_context_recreate.png", destroyed,
    )
    difference = np.abs(first.astype(np.int16) - second.astype(np.int16))
    first_gpu = (
        first_diagnostics.get("backend") == "motion_vector_gpu"
        and first_diagnostics.get("context_valid")
        and int(first_diagnostics.get("gl_error", -1)) == 0
    )
    second_gpu = (
        second_diagnostics.get("backend") == "motion_vector_gpu"
        and second_diagnostics.get("context_valid")
        and int(second_diagnostics.get("gl_error", -1)) == 0
    )
    report = {
        "ok": bool(destroyed and first_gpu and second_gpu and float(difference.mean()) <= 0.25),
        "opengl_only": True,
        "software_renderer_used": False,
        "context_destroy_signal_count": len(destroyed),
        "before": first_diagnostics,
        "after": second_diagnostics,
        "parity": {
            "mean_rgba_abs_error": float(difference.mean()),
            "max_rgba_abs_error": int(difference.max()),
        },
        "outputs": {
            "before": str((OUTPUT / "before_context_destroy.png").resolve()),
            "after": str((OUTPUT / "after_context_recreate.png").resolve()),
        },
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise RuntimeError(f"Motion GPU context recovery QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
