from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")


def run_ui_qa(output: Path) -> dict:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_figma_plugin_ui_dialog import PainterFigmaPluginUIDialog
    from app.painter_ui_figma_plugin_ui_session import PainterFigmaPluginUISession

    app = QApplication.instance() or QApplication([])
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            app.setFont(QFont(families[0], 10))
    output.mkdir(parents=True, exist_ok=True)
    source = """
figma.showUI(__html__,{width:420,height:240,title:'FP3 메시지 플러그인',themeColors:true});
figma.ui.postMessage({type:'boot',text:'Main worker 연결됨'});
figma.ui.onmessage=(message)=>figma.ui.postMessage({type:'echo',text:`UI 응답 ${message.value}`});
"""
    html = """
<style>
body{font-family:system-ui;margin:0;padding:24px;background:var(--figma-color-bg);color:var(--figma-color-text)}
.card{border:1px solid var(--figma-color-border);border-radius:10px;padding:18px}
button{margin-top:16px;padding:9px 14px;border:0;border-radius:6px;background:var(--figma-color-bg-brand);color:white}
</style>
<div class="card"><h2>Figma Plugin UI</h2><div id="status">브리지 대기 중</div><button id="send">메시지 보내기</button></div>
<script>
onmessage=(event)=>{document.getElementById('status').textContent=event.data.pluginMessage.text};
document.getElementById('send').onclick=()=>parent.postMessage({pluginMessage:{type:'ping',value:7}},'*');
</script>
"""
    session = PainterFigmaPluginUISession(source, html, plugin_name="FP3 QA")
    dialog = PainterFigmaPluginUIDialog(session, dark=True)
    dialog.show()
    capture = output / "figma_plugin_ui_bridge.png"

    def click_button() -> None:
        dialog.view.page().runJavaScript("document.getElementById('send').click()")

    def finish() -> None:
        dialog.grab().save(str(capture))
        app.quit()

    dialog.view.loadFinished.connect(
        lambda ok: QTimer.singleShot(250, click_button) if ok else None
    )
    QTimer.singleShot(2200, finish)
    app.exec()
    report = {
        "schema": "tigercapture.painter.figma_plugin_ui_product_qa.v1",
        "capture": str(capture),
        "ui_messages": dialog.ui_messages,
        "main_messages": dialog.main_messages,
        "session_ui": session.ready["ui"],
    }
    report["passed"] = bool(
        capture.exists()
        and dialog.ui_messages == [{"type": "ping", "value": 7}]
        and dialog.main_messages == [
            {"type": "boot", "text": "Main worker 연결됨"},
            {"type": "echo", "text": "UI 응답 7"},
        ]
    )
    dialog.close()
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_ui"),
    )
    args = parser.parse_args()
    report = run_ui_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
