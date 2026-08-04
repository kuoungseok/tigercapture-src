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


def run_ui_document_qa(output: Path) -> dict:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
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
    (package / "code.js").write_text(
        "figma.showUI(__html__,{width:360,height:190,title:'문서 생성 플러그인',themeColors:true});"
        "figma.ui.onmessage=msg=>{const n=figma.createRectangle();n.name=msg.name;"
        "n.x=32;n.y=48;n.resize(180,96);n.fills=[{type:'SOLID',color:{r:0.1,g:0.55,b:0.95}}];"
        "figma.currentPage.selection=[n];figma.ui.postMessage({text:'생성 완료'});};",
        encoding="utf-8",
    )
    (package / "ui.html").write_text(
        "<style>body{font-family:system-ui;padding:20px;background:var(--figma-color-bg);color:var(--figma-color-text)}"
        "button{padding:9px 14px;background:var(--figma-color-bg-brand);color:white;border:0;border-radius:6px}</style>"
        "<h2>Painter 문서 플러그인</h2><div id='status'>대기 중</div><button id='create'>사각형 생성</button>"
        "<script>onmessage=e=>status.textContent=e.data.pluginMessage.text;"
        "create.onclick=()=>parent.postMessage({pluginMessage:{name:'UI Plugin card'}},'*');</script>",
        encoding="utf-8",
    )
    (package / "manifest.json").write_text(json.dumps({
        "name": "UI Document QA", "id": "qa.ui.document", "api": "1.0.0",
        "editorType": ["figma"], "main": "code.js", "ui": "ui.html",
        "documentAccess": "dynamic-page", "networkAccess": {"allowedDomains": ["none"]},
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
    ui_dialog.view.loadFinished.connect(
        lambda ok: QTimer.singleShot(
            250,
            lambda: ui_dialog.view.page().runJavaScript(
                "document.getElementById('create').click()"
            ),
        ) if ok else None
    )
    QTimer.singleShot(1800, loop.quit)
    loop.exec()
    owner._fit_painter_ui_view("selection")
    app.processEvents()
    after_run = output / "painter_ui_plugin_after_run.png"
    owner.grab().save(str(after_run))
    object_names = [row["name"] for row in owner._painter_ui_document["objects"]]
    undo_labels = list(owner._undo_labels)
    owner._undo()
    owner._fit_painter_ui_view("artboard")
    app.processEvents()
    after_undo = output / "painter_ui_plugin_after_undo.png"
    owner.grab().save(str(after_undo))
    after_undo_count = len(owner._painter_ui_document["objects"])
    ui_dialog.close()
    manager.close()
    owner.close()
    report = {
        "schema": "tigercapture.painter.figma_plugin_ui_document_qa.v1",
        "run_returned": bool(run_ok),
        "object_names": object_names,
        "undo_labels": undo_labels,
        "object_count_after_undo": after_undo_count,
        "after_run_capture": str(after_run),
        "after_undo_capture": str(after_undo),
    }
    report["passed"] = bool(
        run_ok
        and object_names == ["UI Plugin card"]
        and undo_labels == ["Run Figma UI plugin"]
        and after_undo_count == 0
        and after_run.exists()
        and after_undo.exists()
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_ui_document"),
    )
    args = parser.parse_args()
    report = run_ui_document_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
