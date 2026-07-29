"""Capture the compact selection-driven Painter UI Prototype panel."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.painter_ui_document import (
    add_ui_interaction,
    add_ui_object,
    create_ui_document,
)
from app.painter_ui_prototype_authoring import (
    add_ui_prototype_flow,
    set_ui_prototype_transition,
)
from app.painter_ui_prototype_panel import PainterUIPrototypePanel


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document, button = add_ui_object(
        create_ui_document(390, 844, name="Checkout"),
        kind="button",
        name="Continue",
    )
    document, interaction = add_ui_interaction(
        document,
        name="Continue to payment",
        source_object_id=button["id"],
        trigger="click",
        action="navigate",
        target_artboard_id="artboard-1",
    )
    document, _flow = add_ui_prototype_flow(
        document,
        name="Checkout Flow",
        artboard_id="artboard-1",
        start_object_id=button["id"],
        device_preset="iPhone 390 x 844",
    )
    document, _ = set_ui_prototype_transition(
        document,
        interaction["id"],
        {"kind": "smart_animate", "duration_ms": 320},
    )
    document["selection"] = {
        "object_id": button["id"],
        "object_ids": [button["id"]],
    }
    panel = PainterUIPrototypePanel()
    panel.resize(360, 410)
    panel.set_document(document)
    panel.set_preview_state(
        {
            "artboard_id": "artboard-1",
            "variables": {"theme": "dark"},
            "events": [{"action": "navigate"}],
        },
        enabled=True,
    )
    panel.connection_list.setCurrentRow(0)
    panel.show()
    app.processEvents()
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "painter_ui_designer_m4_prototype_connections.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not panel.grab().save(str(output)):
        raise RuntimeError(f"Failed to save Prototype QA: {output}")
    print(output)
    panel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
