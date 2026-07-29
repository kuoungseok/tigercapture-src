"""Capture the transient Painter UI responsive preview matrix."""
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
from app.painter_ui_document import add_ui_object, create_ui_document
from app.painter_ui_responsive import set_ui_responsive_override


def _sample_document() -> dict:
    document = create_ui_document(1440, 900, name="Product overview")
    document, shell = add_ui_object(
        document,
        kind="frame",
        name="Product shell",
        x=80,
        y=70,
        width=1280,
        height=760,
        style={"fill": "#172331", "radius": 24},
    )
    document, title = add_ui_object(
        document,
        kind="text",
        name="Headline",
        parent_id=shell["id"],
        x=128,
        y=120,
        width=620,
        height=96,
        content={"text": "Design once. Verify every screen."},
        style={"text_color": "#F3F7FB", "font_size": 42},
    )
    document, action = add_ui_object(
        document,
        kind="button",
        name="Primary action",
        parent_id=shell["id"],
        x=128,
        y=260,
        width=240,
        height=56,
        content={"text": "Open project"},
        style={"fill": "#4F80D8", "text_color": "#FFFFFF", "radius": 8},
    )
    document, panel = add_ui_object(
        document,
        kind="rectangle",
        name="Preview panel",
        parent_id=shell["id"],
        x=800,
        y=120,
        width=430,
        height=520,
        style={"fill": "#30475F", "stroke": "#6A8BAA", "stroke_width": 1},
    )
    for row in document["objects"]:
        if row["id"] == shell["id"]:
            row["responsive_overrides"] = set_ui_responsive_override(
                row,
                breakpoint="mobile",
                orientation="portrait",
                changes={"x": 18, "y": 18, "width": 354, "height": 808},
            )
        elif row["id"] == title["id"]:
            row["responsive_overrides"] = set_ui_responsive_override(
                row,
                breakpoint="mobile",
                orientation="portrait",
                changes={
                    "x": 36,
                    "y": 54,
                    "width": 318,
                    "height": 128,
                    "style": {"font_size": 30},
                },
            )
        elif row["id"] == action["id"]:
            row["responsive_overrides"] = set_ui_responsive_override(
                row,
                breakpoint="mobile",
                orientation="portrait",
                changes={"x": 36, "y": 690, "width": 318},
            )
        elif row["id"] == panel["id"]:
            row["responsive_overrides"] = set_ui_responsive_override(
                row,
                breakpoint="mobile",
                orientation="portrait",
                changes={"x": 36, "y": 210, "width": 318, "height": 430},
            )
    return document


def main() -> int:
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _sample_document()
    dialog._show_painter_ui_responsive_preview()
    panel = dialog._painter_ui_responsive_preview_panel
    app.processEvents()
    output = (
        Path(__file__).resolve().parents[1]
        / "debugCapture"
        / "painter_ui_designer"
        / "painter_ui_designer_m2_responsive_preview_matrix.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not panel.grab().save(str(output)):
        raise RuntimeError(f"Failed to save responsive preview QA: {output}")
    print(output)
    panel.close()
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
