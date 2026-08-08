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

from app.i18n import initialize, set_language
from app.motion_designer.templates import instantiate_template
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_painterly_ui"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    initialize()
    set_language("en")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    composition = instantiate_template(
        "painterly_3d_character_spot",
        variant="16:9",
    )
    target = next(
        layer
        for layer in composition.layers
        if any(effect.kind == "painterly_look" for effect in layer.effects)
    )
    window = MotionDesignerWindow(composition)
    window.resize(1520, 920)
    window.show()
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.looks)
    window.looks.setCurrentWidget(window.lookdev)
    window._select_layer(target.id)
    window.project_and_viewer.setSizes([280, 920])
    window.timeline.set_time_and_emit(1800)
    app.processEvents()

    screenshot = OUTPUT / "painterly_inspector_workspace.png"
    capture_ok = window.grab().save(str(screenshot), "PNG")
    swatches = {
        "line": window.lookdev.line_color.text(),
        "paper": window.lookdev.paper_color.text(),
    }
    report = {
        "schema": "tigerstudio.motion.painterly_ui_qa.v1",
        "ok": bool(
            capture_ok
            and screenshot.is_file()
            and screenshot.stat().st_size > 0
            and window.lookdev.preset.count() == 5
            and all(value.startswith("#") for value in swatches.values())
            and window.lookdev.texture_blend.count() == 3
            and window.lookdev.texture_opacity.maximum() == 1.0
        ),
        "screenshot": str(screenshot),
        "source": "real_qt_motion_designer_window",
        "template": "painterly_3d_character_spot",
        "selected_layer": target.name,
        "preset_count": window.lookdev.preset.count(),
        "swatches": swatches,
        "texture_blend_modes": [
            window.lookdev.texture_blend.itemData(index)
            for index in range(window.lookdev.texture_blend.count())
        ],
        "texture_opacity": window.lookdev.texture_opacity.value(),
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
