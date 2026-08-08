from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")


def run_svg_drop_qa(output: Path) -> dict:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPixmap
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog
    from app.painter_ui_figma_plugin_manager_dialog import PainterFigmaPluginManagerDialog
    from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry

    app = QApplication.instance() or QApplication([])
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            app.setFont(QFont(families[0], 10))
    output.mkdir(parents=True, exist_ok=True)
    package = output / "package"
    registry_root = output / "registry"
    for path in (package, registry_root):
        if path.exists():
            shutil.rmtree(path)
    package.mkdir()
    official = ROOT / "external" / "tools" / "figma-plugin-samples" / "icon-drag-and-drop"
    (package / "code.js").write_text(
        (official / "code.ts").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (package / "ui.html").write_text(
        (official / "ui.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (package / "manifest.json").write_text(json.dumps({
        "name": "Official Icon Drop QA",
        "id": "qa.official.icon.drop",
        "api": "1.0.0",
        "editorType": ["figma"],
        "main": "code.js",
        "ui": "ui.html",
        "documentAccess": "dynamic-page",
        "networkAccess": {"allowedDomains": ["none"]},
    }), encoding="utf-8")
    registry = PainterFigmaPluginRegistry([registry_root], install_root=registry_root)
    registry.install(package / "manifest.json")
    canvas = QPixmap(960, 600)
    canvas.fill(QColor("#F5F5F5"))
    owner = PaintDialog(canvas, [], 0, standalone=True)
    owner.resize(1180, 760)
    owner._set_canvas_workspace_mode("ui_design")
    owner.show()
    manager = PainterFigmaPluginManagerDialog(owner, registry=registry)
    manager.show()
    app.processEvents()
    run_ok = manager._run_current_ui()
    ui_dialog = manager._plugin_ui_dialogs[0]
    loop = QEventLoop()

    def trigger_drop() -> None:
        overlay = owner._painter_ui_overlay
        active = owner._painter_ui_document["active_artboard_id"]
        artboard = next(
            row for row in owner._painter_ui_document["artboards"] if row["id"] == active
        )
        viewport, _scale = overlay._artboard_viewport(artboard)
        QCursor.setPos(overlay.mapToGlobal(viewport.center().toPoint()))
        ui_dialog.view.page().runJavaScript("""
const svg=document.querySelector('.icon svg').outerHTML;
const file=new File([svg],'content.svg',{type:'image/svg+xml'});
window.parent.postMessage({pluginDrop:{clientX:240,clientY:180,files:[file],dropMetadata:{parentingStrategy:'page'}}},'*');
""")

    ui_dialog.view.loadFinished.connect(
        lambda ok: QTimer.singleShot(300, trigger_drop) if ok else None
    )
    QTimer.singleShot(2200, loop.quit)
    loop.exec()
    owner._fit_painter_ui_view("selection")
    app.processEvents()
    after_drop = output / "painter_ui_official_svg_drop.png"
    owner.grab().save(str(after_drop))
    rows = list(owner._painter_ui_document["objects"])
    hierarchy = [
        {"id": row["id"], "name": row["name"], "kind": row["kind"], "parent_id": row["parent_id"]}
        for row in rows
    ]
    undo_labels = list(owner._undo_labels)
    vector = next((row for row in rows if row["kind"] == "path"), None)
    vector_capture = output / "painter_ui_official_svg_vector_selected.png"
    if vector is not None:
        owner._set_painter_ui_selection([vector["id"]], vector["id"])
        owner._fit_painter_ui_view("selection")
        app.processEvents()
        owner.grab().save(str(vector_capture))
    owner._undo()
    after_undo_count = len(owner._painter_ui_document["objects"])
    ui_dialog.close()
    manager.close()
    owner.close()
    frame = next((row for row in rows if row["kind"] == "frame"), None)
    report = {
        "schema": "tigercapture.painter.figma_plugin_svg_drop_qa.v1",
        "run_returned": bool(run_ok),
        "hierarchy": hierarchy,
        "undo_labels": undo_labels,
        "object_count_after_undo": after_undo_count,
        "capture": str(after_drop),
        "vector_capture": str(vector_capture),
    }
    report["passed"] = bool(
        run_ok
        and frame is not None
        and vector is not None
        and vector["parent_id"] == frame["id"]
        and undo_labels == ["Run Figma UI plugin"]
        and after_undo_count == 0
        and after_drop.exists()
        and vector_capture.exists()
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_svg_drop"),
    )
    args = parser.parse_args()
    report = run_svg_drop_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
