"""Open the UMG widget view on one named frame of a .fig, for side-by-side review.

``tmp/launch_fig_frame.py`` stops at the UI-mode canvas; this goes one step
further and raises the Painter/UMG comparison so the blocked-layer reference is
visible next to the source.

    .venv/Scripts/python.exe tmp/launch_umg_view.py <file.fig> "Auto Layout"
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
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
    imported = registry.execute(
        "paint.ui.figma.import",
        {
            "source": str(source),
            "json_snapshot": False,
            "fig_archive": True,
            "mode": "replace",
        },
    )
    if not imported.ok:
        raise SystemExit(imported.message)

    document = getattr(dialog, "_painter_ui_document", {}) or {}
    boards = document.get("artboards") or []
    target = next(
        (row for row in boards if str(row.get("name")) == wanted),
        None,
    )
    if target is None:
        print(f"frame {wanted!r} not found; showing the active artboard")
    else:
        print(f"showing {target['name']!r} ({target['width']}x{target['height']})")
        activated = registry.execute(
            "paint.ui.artboard.activate",
            {"artboard_id": target["id"]},
        )
        if not activated.ok:
            print(f"  activate failed: {activated.message}")

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

    def open_umg() -> None:
        opened = registry.execute(
            "paint.ui.umg.widget_view.set",
            {"visible": True},
        )
        if not opened.ok:
            print(f"umg view failed: {opened.message}")
            return
        report = dict(opened.result or {}).get("report") or {}
        counts = dict(report.get("counts") or {})
        references = list(report.get("reference_object_ids") or [])
        print(f"umg view counts={counts}  reference rows={len(references)}")
        view = getattr(dialog, "_painter_umg_widget_view", None)
        if view is not None:
            view.resize(1500, 900)
            view.raise_()
            view.activateWindow()
            QTimer.singleShot(120, view.fit_views)

    QTimer.singleShot(
        150,
        lambda: registry.execute("paint.ui.view.fit", {"mode": "artboard"}),
    )
    QTimer.singleShot(400, open_umg)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
