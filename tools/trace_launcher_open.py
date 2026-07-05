from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.pop("QT_QPA_PLATFORM", None)
    internal_trace = "--no-internal-trace" not in sys.argv
    if internal_trace:
        os.environ["TIGERCAPTURE_STARTUP_TRACE"] = "1"
    else:
        os.environ.pop("TIGERCAPTURE_STARTUP_TRACE", None)
        sys.argv = [arg for arg in sys.argv if arg != "--no-internal-trace"]

    # Never let the diagnostic harness leave a stuck GUI process behind.
    threading.Timer(11.0, lambda: os._exit(124)).start()

    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtWidgets import QApplication

    from app.controller import AppController
    from app.main_window import MainWindow
    from app.style import APP_QSS

    if internal_trace:
        from app.startup_trace import install_subprocess_trace, log_startup_trace, startup_trace_log_path

        install_subprocess_trace()
    else:
        def log_startup_trace(*_args, **_kwargs) -> None:
            return None

        def startup_trace_log_path() -> Path:
            return ROOT / "debugCapture" / "startup_trace_disabled.jsonl"
    QCoreApplication.setApplicationName("TigerCapture")
    QCoreApplication.setOrganizationName("TigerCapture")
    app = QApplication(sys.argv)
    app.setApplicationName("TigerCapture")
    app.setOrganizationName("TigerCapture")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)

    window = MainWindow()
    controller = AppController(window)
    _ = controller
    window.show()
    window.raise_()
    window.activateWindow()

    def _click_editor() -> None:
        log_startup_trace("trace_tool.click_editor.begin")
        window.pro_editor_btn.click()
        log_startup_trace("trace_tool.click_editor.done")

    def _finish() -> None:
        log_startup_trace("trace_tool.finish", trace_path=str(startup_trace_log_path()))
        # This is a diagnostic harness, not a real user shutdown path.
        # Closing the full editor can run teardown code and trigger DWM
        # "Ghost" windows that look like startup flicker in the external
        # trace. Exit hard after the final marker so the trace measures
        # launcher -> editor opening only.
        os._exit(0)

    click_timer = QTimer()
    click_timer.setSingleShot(True)
    click_timer.timeout.connect(_click_editor)
    finish_timer = QTimer()
    finish_timer.setSingleShot(True)
    finish_timer.timeout.connect(_finish)
    app._trace_launcher_timers = (click_timer, finish_timer)  # type: ignore[attr-defined]
    click_timer.start(800)
    finish_timer.start(9000)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
