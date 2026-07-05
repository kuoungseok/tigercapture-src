"""Capture and sanity-check the main editor layout at common monitor sizes.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_ui_layout.py --out debugCapture/ui_qa

By default the script uses Qt's offscreen platform so it can run in CI. Pass
``--onscreen`` when doing a manual real-monitor QA pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_SIZES = ((960, 700), (1180, 760), (1366, 768), (1920, 1080), (2560, 1080))


def _thresholds_for(width: int, height: int) -> dict[str, int]:
    """Window-aware layout floors.

    The editor intentionally keeps media pool and workbench visible in normal
    windowed mode, so sub-1200px windows use compact side-rail floors instead
    of the desktop baselines.
    """
    if width < 1200:
        return {
            "media_width": 160,
            "center_width": 420,
            "right_width": 270,
            "workbench_height": 180,
            "timeline_height": 220,
            "color_dock_height": 180,
        }
    if width < 1500:
        return {
            "media_width": 180,
            "center_width": 520,
            "right_width": 290,
            "workbench_height": 180,
            "timeline_height": 220,
            "color_dock_height": 180,
        }
    return {
        "media_width": 180,
        "center_width": 520,
        "right_width": 300,
        "workbench_height": 180,
        "timeline_height": 220,
        "color_dock_height": 180,
    }


def _grab_layout(width: int, height: int, out_dir: Path) -> dict:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QFrame

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    initialize()
    editor = VideoEditorWindow()
    editor.resize(width, height)
    editor.show()
    app.processEvents()
    editor.raise_()
    app.processEvents()

    shot = out_dir / f"ui_{width}x{height}.png"
    pixmap = editor.grab()
    pixmap.save(str(shot))

    media_host = getattr(editor, "_media_pool_section_host", None)
    workbench_host = getattr(editor, "_workbench_section_host", None)
    timeline_host = getattr(editor, "_timeline_section_host", None)
    splitter = getattr(editor, "_main_dock_splitter", None)
    center_host = splitter.widget(1) if splitter is not None and splitter.count() > 1 else None
    right_dock = getattr(editor, "_right_dock_host", None)

    metrics = {
        "size": [width, height],
        "actual_size": [editor.width(), editor.height()],
        "minimum_size_hint": [
            editor.minimumSizeHint().width(),
            editor.minimumSizeHint().height(),
        ],
        "screenshot": str(shot),
        "media_width": media_host.width() if media_host is not None else 0,
        "center_width": center_host.width() if center_host is not None else 0,
        "right_width": right_dock.width() if right_dock is not None else 0,
        "workbench_height": workbench_host.height() if workbench_host is not None else 0,
        "timeline_height": timeline_host.height() if timeline_host is not None else 0,
    }

    color_container = getattr(editor, "_color_container", None)
    color_header = getattr(editor, "_color_header_widget", None)
    color_row = getattr(editor, "_color_row_host", None)
    mask_toolbar = getattr(editor, "_mask_toolbar_widget", None)
    for widget in (color_container, color_header, color_row, mask_toolbar):
        if widget is not None:
            widget.show()
    splitter = getattr(editor, "_color_timeline_splitter", None)
    if splitter is not None:
        try:
            splitter.setSizes([250, max(300, height - 250)])
        except Exception:
            pass
    app.processEvents()
    color_shot = out_dir / f"ui_color_dock_{width}x{height}.png"
    editor.grab().save(str(color_shot))
    cards = color_row.findChildren(QFrame, "ColorPaletteCard") if color_row is not None else []
    spinboxes = color_row.findChildren(QDoubleSpinBox) if color_row is not None else []
    metrics.update({
        "color_dock_screenshot": str(color_shot),
        "color_dock_height": color_row.height() if color_row is not None else 0,
        "color_dock_max_height": color_row.maximumHeight() if color_row is not None else 0,
        "color_dock_cards": len(cards),
        "color_dock_spinboxes": len(spinboxes),
    })
    thresholds = _thresholds_for(width, height)
    metrics["thresholds"] = thresholds
    metrics["ok"] = (
        metrics["actual_size"][0] <= width + 24
        and metrics["media_width"] >= thresholds["media_width"]
        and metrics["center_width"] >= thresholds["center_width"]
        and metrics["right_width"] >= thresholds["right_width"]
        and metrics["workbench_height"] >= thresholds["workbench_height"]
        and metrics["timeline_height"] >= thresholds["timeline_height"]
        and metrics["color_dock_height"] >= thresholds["color_dock_height"]
        and metrics["color_dock_max_height"] <= 260
        and metrics["color_dock_cards"] >= 5
        and metrics["color_dock_spinboxes"] == 0
    )
    editor.close()
    app.processEvents()
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="debugCapture/ui_qa", help="Output screenshot directory.")
    parser.add_argument("--size", action="append", help="Add a WxH size, e.g. 1600x900.")
    parser.add_argument("--onscreen", action="store_true", help="Use the default Qt platform.")
    args = parser.parse_args()

    if not args.onscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = list(DEFAULT_SIZES)
    for raw in args.size or []:
        w, h = raw.lower().split("x", 1)
        sizes.append((int(w), int(h)))

    results = [_grab_layout(w, h, out_dir) for w, h in sizes]
    report_path = out_dir / "layout_report.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
