"""Capture real Painter UI and Motion boards with the shared color picker."""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.i18n import set_language
    from app.motion_designer.schema import (
        MotionComposition,
        MotionLayer,
        SourceRef,
    )
    from app.motion_designer.ui.window import MotionDesignerWindow

    output = ROOT / "debugCapture" / "shared_color_picker"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    set_language("en")
    apply_ui_font(app)

    painter = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(720, 720, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    painter.resize(1360, 820)
    registry = ActionRegistry(owner=painter)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    added = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "button",
            "name": "Shared Color Button",
            "x": 170,
            "y": 220,
            "width": 380,
            "height": 120,
            "style": {
                "fill": "#405FD6",
                "stroke": "#90A7FF",
                "stroke_width": 3,
                "radius": 18,
            },
            "content": {"text": "TIGER COLOR"},
        },
    ).to_dict()
    object_id = str(added["result"]["ui_design"]["selected_object_id"])
    registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [object_id], "primary_object_id": object_id},
    )
    registry.execute("paint.ui.inspector.presentation", {"mode": "pinned"})
    painter.show()
    app.processEvents()
    painter_path = output / "painter_ui_color_picker.png"
    if not painter.grab().save(str(painter_path), "PNG"):
        raise RuntimeError("Could not capture Painter UI color picker")

    composition = MotionComposition(
        name="Shared Color Picker",
        width=960,
        height=540,
        duration_ms=3000,
    )
    background = MotionLayer(
        name="Background",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 960,
                "height": 540,
                "fill": "#161B24",
                "stroke": "#161B24",
            },
        ),
        out_ms=3000,
    )
    background.transform.position.default = [480, 270]
    card = MotionLayer(
        name="Color Card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 560,
                "height": 250,
                "radius": 30,
                "fill": "#FF3F8FBA",
                "stroke": "#FF8FD8EF",
                "stroke_width": 5,
            },
        ),
        out_ms=3000,
    )
    card.transform.position.default = [480, 270]
    composition.layers.extend([background, card])
    motion = MotionDesignerWindow(composition)
    motion.resize(1360, 820)
    motion.show()
    app.processEvents()
    motion._select_layer(card.id)
    motion.viewer_header.color_picker.set_color("#FF3F8FBA")
    app.processEvents()
    motion_header_path = output / "motion_portrait_palette.png"
    if not motion.viewer_header.grab().save(str(motion_header_path), "PNG"):
        raise RuntimeError("Could not capture Motion portrait palette")
    motion_path = output / "motion_color_picker.png"
    if not motion.grab().save(str(motion_path), "PNG"):
        raise RuntimeError("Could not capture Motion color picker")

    painter_image = QImage(str(painter_path))
    motion_image = QImage(str(motion_path))
    tile_width = 900
    tile_height = 544
    canvas = QImage(
        tile_width * 2,
        tile_height + 54,
        QImage.Format.Format_ARGB32,
    )
    canvas.fill(QColor("#0F1218"))
    proof = QPainter(canvas)
    proof.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    proof.setPen(QColor("#EEF3FA"))
    title_font = QFont(app.font())
    title_font.setPixelSize(22)
    title_font.setBold(True)
    proof.setFont(title_font)
    proof.drawText(
        QRect(0, 0, tile_width, 48),
        Qt.AlignmentFlag.AlignCenter,
        "Painter UI Design · Fill / Stroke Picker",
    )
    proof.drawText(
        QRect(tile_width, 0, tile_width, 48),
        Qt.AlignmentFlag.AlignCenter,
        "Motion Designer · Canvas / Preview Picker",
    )
    proof.drawImage(
        QRect(0, 54, tile_width, tile_height),
        painter_image,
        painter_image.rect(),
    )
    proof.drawImage(
        QRect(tile_width, 54, tile_width, tile_height),
        motion_image,
        motion_image.rect(),
    )
    proof.end()
    combined_path = output / "shared_color_picker_boards.png"
    if not canvas.save(str(combined_path), "PNG"):
        raise RuntimeError("Could not save shared color picker proof")

    painter.close()
    motion.close()
    app.processEvents()
    print(combined_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
