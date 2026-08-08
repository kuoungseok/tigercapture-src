"""Capture the non-destructive Painter UI Component Playground."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.drawing import PaintDialog, create_blank_paint_pixmap
from app.font_fallback import apply_ui_font
from app.painter_ui_components import (
    bind_ui_component_property,
    convert_ui_object_to_component,
    define_ui_component_property,
)
from app.painter_ui_document import add_ui_object, create_ui_document


def _sample() -> tuple[dict, str]:
    document = create_ui_document(640, 480, name="Component Library")
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Product Card",
        x=40,
        y=40,
        width=360,
        height=210,
        style={"fill": "#1B2938", "radius": 12},
    )
    document, label = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=root["id"],
        x=72,
        y=80,
        width=280,
        height=54,
        content={"text": "Studio Headphones"},
        style={"text_color": "#F0F5FA", "font_size": 24},
    )
    document, _ = add_ui_object(
        document,
        kind="button",
        name="Action",
        parent_id=root["id"],
        x=72,
        y=158,
        width=180,
        height=48,
        content={"text": "Open product"},
        style={"fill": "#4D7FD5", "text_color": "#FFFFFF", "radius": 7},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Product Card",
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Title",
        definition={
            "type": "text",
            "default": "Studio Headphones",
        },
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=label["id"],
        property_name="Title",
        target_path="content.text",
    )
    return document, component["id"]


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document, component_id = _sample()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._show_painter_ui_component_playground(component_id)
    panel = dialog._painter_ui_component_playground_panel
    panel._set_property("Title", "Preview title without source edits")
    app.processEvents()
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "painter_ui_designer_m3_component_playground.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not panel.grab().save(str(output)):
        raise RuntimeError(f"Failed to save Component Playground QA: {output}")
    print(output)
    panel.close()
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
