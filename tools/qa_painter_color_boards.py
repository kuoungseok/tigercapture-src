"""Capture the real Painter Painting color-board tabs."""
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

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.i18n import set_language

    output = ROOT / "debugCapture" / "painter_color_boards"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    set_language("en")
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(960, 720, "#F5F2EC"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1360, 900)
    dialog.show()
    app.processEvents()
    dialog._apply_pen_color(QColor("#FF4B12"), remember=False)
    dialog._previous_pen_color = QColor("#2D2D2D")
    dialog._highlight_selected_palette()
    app.processEvents()

    names = ("presets", "color_control")
    images: list[QImage] = []
    for index, name in enumerate(names):
        dialog._paint_color_tabs.setCurrentIndex(index)
        app.processEvents()
        image = dialog._paint_color_panel.grab().toImage().copy()
        if image.isNull():
            raise RuntimeError(f"Could not capture {name}")
        image.save(str(output / f"{name}.png"), "PNG")
        images.append(image)

    dialog._paint_color_tabs.setCurrentIndex(1)
    dialog._ensure_paint_inspector_visible()
    app.processEvents()
    window_path = output / "painter_color_control_window.png"
    if not dialog.grab().save(str(window_path), "PNG"):
        raise RuntimeError("Could not capture responsive Painter window")

    tile_width = 500
    tile_height = 330
    header_height = 58
    proof = QImage(
        tile_width * 2,
        tile_height + header_height,
        QImage.Format.Format_ARGB32,
    )
    proof.fill(QColor("#161718"))
    painter = QPainter(proof)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    font = QFont(app.font())
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#F3F0EA"))
    titles = ("Presets", "Color Control")
    for index, (title, image) in enumerate(zip(titles, images)):
        x = index * tile_width
        painter.drawText(
            QRect(x, 0, tile_width, header_height),
            Qt.AlignmentFlag.AlignCenter,
            title,
        )
        scaled = image.scaled(
            tile_width - 16,
            tile_height - 8,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawImage(
            x + (tile_width - scaled.width()) // 2,
            header_height,
            scaled,
        )
    painter.end()
    proof_path = output / "painter_color_boards.png"
    if not proof.save(str(proof_path), "PNG"):
        raise RuntimeError("Could not save Painter color-board proof")
    dialog.close()
    app.processEvents()
    print(proof_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
