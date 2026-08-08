from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Thread


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"value": "허용 OK"}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def run_network_qa(output: Path) -> dict:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_figma_plugin_ui_dialog import PainterFigmaPluginUIDialog
    from app.painter_ui_figma_plugin_ui_session import PainterFigmaPluginUISession

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    app = QApplication.instance() or QApplication([])
    output.mkdir(parents=True, exist_ok=True)
    source = "figma.showUI(__html__,{width:430,height:220,title:'도메인 권한 QA'});"
    html = f"""
<style>
body{{font-family:system-ui;margin:0;padding:24px;background:#fff;color:#1e1e1e}}
.card{{border:1px solid #ddd;border-radius:10px;padding:18px}}
#status{{font-weight:650;margin-top:14px}}
</style>
<div class="card"><h2>Plugin UI 네트워크</h2><div id="status">검증 중…</div></div>
<script>
(async()=>{{
  const status=document.getElementById('status');
  try {{
    const value=await fetch('http://127.0.0.1:{port}/allowed').then(r=>r.json());
    let blocked=false;
    try {{ await fetch('http://localhost:{port}/blocked'); }} catch (_) {{ blocked=true; }}
    status.textContent=value.value+' / '+(blocked?'미승인 차단 OK':'미승인 차단 실패');
  }} catch (error) {{ status.textContent='허용 요청 실패: '+error; }}
}})();
</script>
"""
    session = PainterFigmaPluginUISession(source, html, plugin_name="Network QA")
    dialog = PainterFigmaPluginUIDialog(
        session,
        allowed_domains=(f"http://127.0.0.1:{port}/",),
    )
    dialog.show()
    capture = output / "figma_plugin_network_permission.png"
    result: dict[str, str] = {"text": ""}

    def finish() -> None:
        dialog.view.page().runJavaScript(
            "document.getElementById('status').textContent",
            lambda value: result.update(text=str(value or "")),
        )
        QTimer.singleShot(150, save_and_quit)

    def save_and_quit() -> None:
        dialog.grab().save(str(capture))
        app.quit()

    QTimer.singleShot(1800, finish)
    app.exec()
    dialog.close()
    server.shutdown()
    server.server_close()
    report = {
        "schema": "tigercapture.painter.figma_plugin_network_qa.v1",
        "capture": str(capture),
        "status": result["text"],
        "allowed_pattern": f"http://127.0.0.1:{port}/",
    }
    report["passed"] = bool(
        capture.exists() and result["text"] == "허용 OK / 미승인 차단 OK"
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_network"),
    )
    args = parser.parse_args()
    report = run_network_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
