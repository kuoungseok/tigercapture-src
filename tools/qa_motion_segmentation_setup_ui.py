"""Capture the real Motion Designer cutout-model setup state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui.window import MotionDesignerWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(
        MotionComposition(width=1280, height=720, duration_ms=5000)
    )
    window.resize(1520, 900)
    window.ai.advanced_button.setChecked(True)
    window.show()
    app.processEvents()

    output = (
        Path("debugCapture")
        / "motion_designer"
        / "segmentation_setup_ui"
    )
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / "motion_ai_cutout_not_installed.png"
    window.grab().save(str(screenshot))
    status = window.ai.extraction.refresh_setup_status()
    report = {
        "ok": True,
        "screenshot": str(screenshot.resolve()),
        "automatic_cutout_ready": bool(status.get("automatic_cutout_ready")),
        "assisted_segmentation_ready": bool(status.get("assisted_segmentation_ready")),
        "combo_text": window.ai.extraction.segmentation.currentText(),
        "install_button_visible": not window.ai.extraction.install_button.isHidden(),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
