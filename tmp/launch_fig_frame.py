"""Open the Painter UI on one named frame of a .fig, for side-by-side review.

``tools/launch_painter_figma_sample.py`` fits whichever artboard the import
happened to leave active; this lands on the frame being compared against Figma.

    .venv/Scripts/python.exe tmp/launch_fig_frame.py <file.fig> "Auto Layout"
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
    dialog.resize(1600, 1900)
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
    report = dict(imported.result or {}).get("figma_import") or {}
    print(
        f"Imported {report.get('artboard_count', 0)} artboards and "
        f"{report.get('object_count', 0)} objects"
    )

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

    def _fit_then_zoom() -> None:
        r1 = registry.execute("paint.ui.view.fit", {"mode": "artboard"})
        print(f"fit: ok={r1.ok} err={r1.error!r}", flush=True)
        focus_name = sys.argv[3] if len(sys.argv) > 3 else ""
        if focus_name:
            objects = document.get("objects") or []
            focus_row = next(
                (
                    row
                    for row in objects
                    if str(row.get("name")) == focus_name
                    and row.get("artboard_id") == (target and target["id"])
                ),
                None,
            )
            if focus_row is not None:
                r2 = registry.execute(
                    "paint.ui.selection.set",
                    {"object_ids": [focus_row["id"]]},
                )
                print(f"select {focus_name!r}: ok={r2.ok} err={r2.error!r}", flush=True)

                def _fit_selection() -> None:
                    r3 = registry.execute("paint.ui.view.fit", {"mode": "selection"})
                    print(f"fit selection: ok={r3.ok} err={r3.error!r}", flush=True)

                QTimer.singleShot(200, _fit_selection)
            else:
                print(f"focus target {focus_name!r} not found", flush=True)

    QTimer.singleShot(150, _fit_then_zoom)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
