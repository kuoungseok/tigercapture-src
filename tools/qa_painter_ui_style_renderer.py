"""Render a deterministic Painter UI style-parity proof image."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def render_style_proof(output: Path) -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QFont, QFontDatabase, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    document = create_ui_document(600, 380, name="Style Preview")
    document, _ = add_ui_object(
        document,
        kind="rectangle",
        name="Card",
        x=55,
        y=55,
        width=490,
        height=270,
        style={
            "fill": "#1B2430FF",
            "stroke": "#6F8299FF",
            "stroke_width": 2,
            "radius": 20,
            "shadow": {
                "x": 0,
                "y": 14,
                "blur": 24,
                "spread": 1,
                "color": "#00000088",
            },
        },
    )
    document, _ = add_ui_object(
        document,
        kind="text",
        name="Title",
        x=90,
        y=70,
        width=420,
        height=135,
        style={
            "font_size": 32,
            "font_weight": 700,
            "text_align": "right",
            "line_height": 1.35,
            "text_color": "#F2F5F9FF",
        },
        content={"text": "Tiger Studio\nUI Designer"},
    )
    document, _ = add_ui_object(
        document,
        kind="button",
        name="Button",
        x=305,
        y=235,
        width=205,
        height=58,
        style={
            "fill": "#4D73B8FF",
            "stroke": "#88A9DAFF",
            "stroke_width": 1.5,
            "radius": 12,
            "font_size": 18,
            "font_weight": 600,
            "text_align": "center",
            "text_color": "#FFFFFFFF",
            "shadow": {
                "x": 0,
                "y": 6,
                "blur": 12,
                "spread": 0,
                "color": "#10203088",
            },
        },
        content={"text": "Continue"},
    )
    document["selection"] = {"object_id": "", "object_ids": []}

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.setFont(QFont("Segoe UI", 9))
    overlay.set_document(document)
    overlay.fit_all()
    image = QImage(900, 650, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    overlay.render(painter, QPoint())
    painter.end()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output)):
        raise RuntimeError(f"Failed to save Painter UI style proof: {output}")
    overlay.deleteLater()
    app.processEvents()
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debugCapture/painter_ui_style_qa/style_parity.png"),
    )
    args = parser.parse_args()
    print(render_style_proof(args.output).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
