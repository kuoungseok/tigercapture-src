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


def run_lifecycle_qa(output: Path) -> dict:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_figma_plugin_ui_dialog import PainterFigmaPluginUIDialog
    from app.painter_ui_figma_plugin_ui_session import PainterFigmaPluginUISession

    app = QApplication.instance() or QApplication([])
    output.mkdir(parents=True, exist_ok=True)
    source = """
figma.showUI(__html__,{width:360,height:220,title:'Plugin UI 수명주기',themeColors:true});
figma.ui.onmessage=(message)=>{
  if(message==='resize') figma.ui.resize(560,300);
  if(message==='blink'){figma.ui.hide();setTimeout(()=>figma.ui.show(),120)}
  if(message==='close') figma.ui.close();
};
"""
    html = """
<style>
body{font-family:system-ui;margin:0;padding:22px;background:var(--figma-color-bg);color:var(--figma-color-text)}
.card{border:1px solid var(--figma-color-border);border-radius:10px;padding:16px}
button{margin:6px;padding:8px 12px;border:0;border-radius:6px;background:var(--figma-color-bg-brand);color:#fff}
</style>
<div class="card"><h2>Plugin UI 수명주기</h2><button id="resize">크기 변경</button><button id="blink">숨김·복귀</button><button id="close">닫기</button></div>
<script>
for(const id of ['resize','blink','close']) document.getElementById(id).onclick=()=>parent.postMessage({pluginMessage:id},'*');
</script>
"""
    session = PainterFigmaPluginUISession(source, html, plugin_name="Lifecycle QA")
    dialog = PainterFigmaPluginUIDialog(session, dark=True)
    dialog.show()
    initial_capture = output / "plugin_ui_initial.png"
    resized_capture = output / "plugin_ui_resized.png"
    restored_capture = output / "plugin_ui_restored_after_hide.png"
    observations: dict[str, object] = {}

    def capture_initial() -> None:
        dialog.grab().save(str(initial_capture))
        observations["initial_size"] = [dialog.width(), dialog.height()]
        dialog.view.page().runJavaScript("document.getElementById('resize').click()")
        QTimer.singleShot(250, capture_resized)

    def capture_resized() -> None:
        dialog.grab().save(str(resized_capture))
        observations["resized_size"] = [dialog.width(), dialog.height()]
        dialog.view.page().runJavaScript("document.getElementById('blink').click()")
        QTimer.singleShot(45, observe_hidden)
        QTimer.singleShot(350, capture_restored)

    def observe_hidden() -> None:
        observations["hidden"] = not dialog.isVisible()

    def capture_restored() -> None:
        observations["restored"] = dialog.isVisible()
        dialog.grab().save(str(restored_capture))
        dialog.view.page().runJavaScript("document.getElementById('close').click()")
        QTimer.singleShot(220, finish)

    def finish() -> None:
        observations["closed"] = not dialog.isVisible()
        app.quit()

    dialog.view.loadFinished.connect(
        lambda ok: QTimer.singleShot(220, capture_initial) if ok else app.quit()
    )
    QTimer.singleShot(4500, app.quit)
    app.exec()
    report = {
        "schema": "tigercapture.painter.figma_plugin_lifecycle_qa.v1",
        "captures": [str(initial_capture), str(resized_capture), str(restored_capture)],
        **observations,
    }
    report["passed"] = bool(
        all(path.exists() for path in (initial_capture, resized_capture, restored_capture))
        and observations.get("initial_size") == [360, 220]
        and observations.get("resized_size") == [560, 300]
        and observations.get("hidden") is True
        and observations.get("restored") is True
        and observations.get("closed") is True
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
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_lifecycle"),
    )
    args = parser.parse_args()
    report = run_lifecycle_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
