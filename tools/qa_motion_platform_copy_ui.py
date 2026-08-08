"""Capture real Motion AI platform-copy review UI evidence."""
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

from app.font_fallback import apply_ui_font
from app.i18n import set_language
from app.motion_designer.platform_copy import (
    generate_platform_copy_plan,
    preflight_platform_copy_plan,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.story_direction import add_story_beat
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_platform_copy_ui"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    set_language("en")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    headline = (
        "Turn one idea into a complete animated campaign for every screen"
    )
    composition = MotionComposition(
        name="Platform Copy QA",
        width=1920,
        height=1080,
        duration_ms=6000,
        layers=[
            MotionLayer(
                id="qa_headline",
                name="Main Headline",
                layer_type="text",
                source=SourceRef(
                    kind="text",
                    params={
                        "role": "headline",
                        "text": headline,
                        "font_size": 88,
                        "fill": "#18202a",
                        "width": 1500,
                        "height": 220,
                        "align": "center",
                    },
                ),
                out_ms=6000,
            ),
        ],
    )
    composition.layers[0].transform.position.default = [960.0, 540.0]
    add_story_beat(
        composition,
        role="hook",
        start_ms=0,
        end_ms=1800,
        copy="Start with the promise, then reveal the complete creative workflow",
        layer_ids=["qa_headline"],
    )
    plan = generate_platform_copy_plan(
        composition,
        platform="vertical_9_16",
        prompt="Make this concise for a fast vertical product launch.",
        provider_id="rule_based",
    )
    preflight = preflight_platform_copy_plan(composition, plan)

    window = MotionDesignerWindow(composition)
    window.resize(1520, 920)
    window.show()
    window.ai_dock.show()
    window.ai_dock.raise_()
    window.ai.platform.setCurrentIndex(
        window.ai.platform.findData("vertical_9_16")
    )
    window.ai.prompt.setPlainText(
        "Make this concise for a fast vertical product launch."
    )
    window.ai.set_platform_copy_plan({
        "plan": plan,
        "preflight": preflight,
    })
    app.processEvents()

    screenshot = OUTPUT / "platform_copy_review_workspace.png"
    capture_ok = window.grab().save(str(screenshot), "PNG")
    report = {
        "schema": "tigerstudio.motion.platform_copy_ui_qa.v1",
        "ok": bool(
            capture_ok
            and screenshot.is_file()
            and screenshot.stat().st_size > 0
            and preflight["ok"]
            and window.ai.apply_button.isEnabled()
            and window.ai.platform.currentData() == "vertical_9_16"
            and "Review changes:" in window.ai.result.toPlainText()
        ),
        "platform": window.ai.platform.currentData(),
        "operation_count": len(plan["operations"]),
        "apply_enabled": window.ai.apply_button.isEnabled(),
        "provider": plan["provider"],
        "screenshot": str(screenshot),
        "source": "real_qt_motion_designer_window",
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
