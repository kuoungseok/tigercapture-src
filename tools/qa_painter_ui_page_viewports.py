"""Capture per-artboard Painter UI viewport restoration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _same_view(first: dict, second: dict) -> bool:
    return (
        first["zoom_percent"] == second["zoom_percent"]
        and abs(first["center_x"] - second["center_x"]) < 0.001
        and abs(first["center_y"] - second["center_y"]) < 0.001
    )


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF, Qt

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_page_viewports_m1"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    results = {}

    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                390,
                844,
                "#F5F7FA",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        registry.execute(
            "paint.ui.navigator.presentation",
            {"mode": "auto_hide"},
        )
        registry.execute(
            "paint.ui.inspector.presentation",
            {"mode": "auto_hide"},
        )
        dialog.resize(*size)
        dialog.show()
        app.processEvents()

        registry.execute("paint.ui.view.zoom", {"percent": 118})
        phone = registry.execute(
            "paint.ui.view.pan",
            {"dx": 44, "dy": -26},
        ).to_dict()["result"]["ui_view"]
        desktop_id = registry.execute(
            "paint.ui.artboard.add",
            {"name": "Desktop", "width": 1440, "height": 900},
        ).to_dict()["result"]["ui_design"]["active_artboard_id"]
        registry.execute("paint.ui.view.zoom", {"percent": 76})
        desktop = registry.execute(
            "paint.ui.view.pan",
            {"dx": -35, "dy": 31},
        ).to_dict()["result"]["ui_view"]

        registry.execute(
            "paint.ui.artboard.activate",
            {"artboard_id": "artboard-1"},
        )
        phone_restored = dialog._painter_ui_overlay.view_state()
        phone_path = output_dir / f"phone_restored_{label}.png"
        phone_saved = dialog.grab().save(str(phone_path), "PNG")

        registry.execute(
            "paint.ui.artboard.activate",
            {"artboard_id": desktop_id},
        )
        desktop_restored = dialog._painter_ui_overlay.view_state()
        desktop_path = output_dir / f"desktop_restored_{label}.png"
        desktop_saved = dialog.grab().save(str(desktop_path), "PNG")
        overlay = dialog._painter_ui_overlay
        native_before = overlay.view_state()
        native_zoomed = overlay.apply_native_gesture(
            Qt.NativeGestureType.ZoomNativeGesture,
            value=0.12,
            position=QPointF(
                float(overlay.width()) * 0.5,
                float(overlay.height()) * 0.5,
            ),
        )
        native_panned = overlay.apply_native_gesture(
            Qt.NativeGestureType.PanNativeGesture,
            delta=QPointF(13.5, -8.25),
        )
        overlay.pan_view(x=1_000_000.0, y=-1_000_000.0)
        native_view = overlay.view_state()
        bounds = overlay._scene_bounds()
        clamped = bool(
            bounds.left() * native_view["scale"] + native_view["offset_x"]
            <= float(overlay.width()) - 24.0
            and bounds.right() * native_view["scale"]
            + native_view["offset_x"]
            >= 24.0
            and bounds.top() * native_view["scale"] + native_view["offset_y"]
            <= float(overlay.height()) - 24.0
            and bounds.bottom() * native_view["scale"]
            + native_view["offset_y"]
            >= 24.0
        )
        native_path = output_dir / f"native_clamp_{label}.png"
        native_saved = dialog.grab().save(str(native_path), "PNG")

        results[label] = {
            "ok": bool(
                phone_saved
                and desktop_saved
                and native_saved
                and _same_view(phone, phone_restored)
                and _same_view(desktop, desktop_restored)
                and native_zoomed
                and native_panned
                and native_view["scale"] > native_before["scale"]
                and clamped
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "phone_screenshot": str(phone_path),
            "desktop_screenshot": str(desktop_path),
            "native_clamp_screenshot": str(native_path),
            "phone": phone_restored,
            "desktop": desktop_restored,
            "native_clamped": clamped,
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.page_viewports.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "page_viewports_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
