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


def run_recovery_qa(output: Path) -> dict:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_figma_plugin_ui_dialog import PainterFigmaPluginUIDialog
    from app.painter_ui_figma_plugin_ui_session import PainterFigmaPluginUISession

    app = QApplication.instance() or QApplication([])
    output.mkdir(parents=True, exist_ok=True)
    source = (
        "figma.showUI(__html__,{width:390,height:210,title:'복구 QA'});"
        "figma.ui.onmessage=()=>{while(true){}};"
    )
    html = """
<style>body{font-family:system-ui;margin:0;padding:24px}button{padding:9px 14px}</style>
<h2>응답 없는 플러그인</h2><button id="hang">실행</button>
<script>document.getElementById('hang').onclick=()=>parent.postMessage({pluginMessage:'hang'},'*')</script>
"""
    session = PainterFigmaPluginUISession(source, html, timeout_ms=100)
    dialog = PainterFigmaPluginUIDialog(session)
    failures: list[str] = []
    dialog.runtimeFailed.connect(failures.append)
    dialog.show()
    capture = output / "plugin_ui_timeout_recovered.png"

    def trigger() -> None:
        dialog.view.page().runJavaScript("document.getElementById('hang').click()")

    def finish() -> None:
        dialog.grab().save(str(capture))
        app.quit()

    dialog.view.loadFinished.connect(lambda ok: QTimer.singleShot(180, trigger) if ok else None)
    QTimer.singleShot(1300, finish)
    app.exec()
    report = {
        "schema": "tigercapture.painter.figma_plugin_recovery_qa.v1",
        "capture": str(capture),
        "failures": failures,
        "title": dialog.windowTitle(),
        "view_enabled": dialog.view.isEnabled(),
        "worker_stopped": session._process.poll() is not None,
    }
    report["passed"] = bool(
        capture.exists()
        and failures
        and "timed out" in failures[0]
        and "실행 오류" in dialog.windowTitle()
        and not dialog.view.isEnabled()
        and session._process.poll() is not None
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
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_recovery"),
    )
    args = parser.parse_args()
    report = run_recovery_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
