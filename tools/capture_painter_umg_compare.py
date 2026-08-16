"""Import a Figma file scoped to one frame, open the UMG widget view, and
grab both as PNGs for side-by-side fidelity diffing. Exits automatically
once both captures are written (no interactive window needed).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--frame", required=True, help="artboard/frame name to scope to")
    parser.add_argument("--out-dir", default="tmp/umg_compare")
    parser.add_argument(
        "--images",
        default="",
        help="folder of archive image blobs named after their imageRef",
    )
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        parser.error(f"Figma source not found: {source}")
    fig_archive = source.suffix.casefold() in {".fig", ".jam"}
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
    workspace_result = registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    if not workspace_result.ok:
        raise RuntimeError(workspace_result.message)
    import_result = registry.execute(
        "paint.ui.figma.import",
        {
            "source": str(source),
            "json_snapshot": not fig_archive,
            "fig_archive": fig_archive,
            "image_dir": str(Path(args.images).expanduser()) if args.images else "",
            "mode": "replace",
        },
    )
    if not import_result.ok:
        raise RuntimeError(import_result.message)
    report = dict(import_result.result or {}).get("figma_import") or {}
    print(
        f"Imported {report.get('artboard_count', 0)} artboards and "
        f"{report.get('object_count', 0)} objects from {source.name}"
    )

    document = dialog._painter_ui_document
    artboards = (document or {}).get("artboards") or []
    target = args.frame.strip().casefold()
    match = next(
        (row for row in artboards if str(row.get("name", "")).strip().casefold() == target),
        None,
    )
    if match is None:
        names = sorted({str(row.get("name", "")) for row in artboards})
        raise SystemExit(f"No artboard named {args.frame!r} found. Available: {names}")
    artboard_id = str(match["id"])
    page_id = str(match.get("page_id") or "")

    if page_id:
        page_result = registry.execute("paint.ui.page.activate", {"page_id": page_id})
        if not page_result.ok:
            raise RuntimeError(page_result.message)
    activate_result = registry.execute("paint.ui.artboard.activate", {"artboard_id": artboard_id})
    if not activate_result.ok:
        raise RuntimeError(activate_result.message)
    scope_result = registry.execute("paint.ui.selection.scope.enter", {"object_id": artboard_id})
    if not scope_result.ok:
        raise RuntimeError(scope_result.message)
    print(f"Scoped to artboard {match.get('name')!r} ({artboard_id})")

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

    def _capture() -> None:
        registry.execute("paint.ui.view.fit", {"mode": "artboard"})
        umg_result = registry.execute("paint.ui.umg.widget_view.set", {"visible": True})
        if not umg_result.ok:
            raise RuntimeError(umg_result.message)

        def _grab_and_quit() -> None:
            app.processEvents()
            dialog.repaint()
            app.processEvents()
            painter_path = out_dir / "painter_ui.png"
            dialog.grab().save(str(painter_path))
            print(f"wrote {painter_path}")

            view = getattr(dialog, "_painter_umg_widget_view", None)
            if view is not None:
                view.repaint()
                app.processEvents()
                umg_path = out_dir / "umg_widget_view.png"
                view.grab().save(str(umg_path))
                print(f"wrote {umg_path}")
            else:
                print("warning: no _painter_umg_widget_view instance found")
            app.quit()

        QTimer.singleShot(2500, _grab_and_quit)

    QTimer.singleShot(300, _capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
