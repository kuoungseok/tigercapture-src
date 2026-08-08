"""Capture contextual image controls with zero-width Painter side panels."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_source(path: Path) -> None:
    from PySide6.QtGui import QColor, QImage, QPainter

    image = QImage(900, 420, QImage.Format.Format_ARGB32)
    image.fill(QColor("#16314A"))
    painter = QPainter(image)
    painter.fillRect(0, 0, 360, 420, QColor("#D99A45"))
    painter.fillRect(360, 0, 540, 420, QColor("#3A7594"))
    painter.setBrush(QColor("#F2D6A2"))
    painter.setPen(QColor("#FFFFFF"))
    painter.drawEllipse(570, 75, 230, 230)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Could not create QA image: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "debugCapture" / "painter_ui_image_context_m1"),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QPoint, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_image_assets import set_ui_image_fill

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "generated_wide_source.png"
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    _make_source(source_path)
    results: dict[str, dict] = {}

    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1280,
                720,
                "#FFFFFF",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        document = create_ui_document(1280, 720, name="Desktop")
        document, card = add_ui_object(
            document,
            kind="image",
            name="Hero image",
            x=360,
            y=150,
            width=480,
            height=420,
            style={
                "fill": "#1C2734",
                "stroke": "#6E8BAA",
                "stroke_width": 3,
                "radius": 28,
                "effects": [
                    {
                        "type": "drop_shadow",
                        "x": 0,
                        "y": 16,
                        "blur": 36,
                        "spread": 0,
                        "color": "#08111F66",
                    }
                ],
            },
        )
        document, card, _report = set_ui_image_fill(
            document,
            card["id"],
            source_path,
            image_fit="fill",
        )
        dialog._painter_ui_document = document
        dialog._refresh_painter_ui_overlay()
        registry.execute(
            "paint.ui.inspector.presentation",
            {"mode": "auto_hide"},
        )
        registry.execute(
            "paint.ui.navigator.presentation",
            {"mode": "auto_hide"},
        )
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._update_canvas_geometry()
        dialog._sync_painter_ui_image_context()
        dialog._handle_painter_ui_image_context_command("focal")
        app.processEvents()

        overlay = dialog._painter_ui_overlay
        control = overlay._image_focal_control()
        if control is None:
            raise RuntimeError("Image focal control was not available")
        _row, rect, focal = control
        target = QPoint(
            round(rect.left() + rect.width() * 0.72),
            round(rect.top() + rect.height() * 0.36),
        )
        QTest.mousePress(
            overlay,
            Qt.MouseButton.LeftButton,
            pos=focal.toPoint(),
        )
        QTest.mouseMove(overlay, target)
        QTest.mouseRelease(
            overlay,
            Qt.MouseButton.LeftButton,
            pos=target,
        )
        app.processEvents()
        dialog._hide_painter_ui_quick_properties()
        app.processEvents()
        path = output_dir / f"image_context_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        updated = next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == card["id"]
        )
        results[label] = {
            "ok": bool(
                saved
                and float(updated["content"]["focal_x"]) > 0.65
                and float(updated["content"]["focal_y"]) < 0.45
                and not dialog._painter_ui_image_context_bar.isHidden()
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "focal_point": [
                updated["content"]["focal_x"],
                updated["content"]["focal_y"],
            ],
            "image_fit": updated["content"]["image_fit"],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.image_context.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "image_context_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": report["ok"], "report": str(report_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.show:
        return app.exec()
    QTimer.singleShot(0, app.quit)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
