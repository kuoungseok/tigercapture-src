"""Open the Painter UI and the UMG widget view on one frame of a .fig.

``tmp/launch_umg_view.py`` routed the import through the action registry, which
on a 9,000-object playground file took long enough that neither window ever
appeared. This imports headlessly, hands the document straight to the dialog,
and prints the elapsed time of every step so a slow stage is visible instead of
looking like a hang.

    .venv/Scripts/python.exe tmp/launch_umg_view2.py <file.fig> "Auto Layout"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_START = time.monotonic()


def step(message: str) -> None:
    print(f"[{time.monotonic() - _START:7.1f}s] {message}", flush=True)


def main() -> int:
    source = Path(sys.argv[1]).expanduser().resolve()
    wanted = sys.argv[2] if len(sys.argv) > 2 else ""
    if not source.is_file():
        raise SystemExit(f"Figma source not found: {source}")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_figma import import_fig_file

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)

    step(f"importing {source.name}")
    document, report = import_fig_file(source)
    step(
        f"imported {len(document.get('artboards') or [])} artboards, "
        f"{len(document.get('objects') or [])} objects"
    )

    boards = document.get("artboards") or []
    target = next(
        (row for row in boards if str(row.get("name")) == wanted),
        None,
    ) or (boards[0] if boards else None)
    if target is None:
        raise SystemExit("the imported document has no artboard")
    document["active_artboard_id"] = str(target["id"])
    page_id = str(target.get("page_id") or "")
    if page_id:
        document["active_page_id"] = page_id
    step(f"target frame {str(target['name'])!r} "
         f"({target['width']}x{target['height']})")

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1600, 980)
    registry = ActionRegistry(owner=dialog)
    workspace = registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    if not workspace.ok:
        raise SystemExit(workspace.message)
    step("workspace switched to ui_design")

    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    step("document handed to the canvas")

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    step("painter window shown")

    def open_umg() -> None:
        opened = registry.execute(
            "paint.ui.umg.widget_view.set",
            {"visible": True},
        )
        if not opened.ok:
            step(f"umg view failed: {opened.message}")
            return
        view = getattr(dialog, "_painter_umg_widget_view", None)
        if view is None:
            step("umg view missing after enable")
            return
        report = view.report()
        step(
            f"umg view open: counts={dict(report.get('counts') or {})} "
            f"reference={len(report.get('reference_object_ids') or [])}"
        )
        view.resize(1500, 900)
        view.show()
        view.raise_()
        view.activateWindow()
        QTimer.singleShot(200, view.fit_views)

    QTimer.singleShot(
        200,
        lambda: registry.execute("paint.ui.view.fit", {"mode": "artboard"}),
    )
    QTimer.singleShot(600, open_umg)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
