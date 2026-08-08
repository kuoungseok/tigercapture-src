import datetime
import faulthandler
import io
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


# Mirror stderr to the per-user runtime log directory so each run leaves a
# readable trail without dirtying the source checkout. The file is truncated on
# launch so "latest run" is always at the top.
from app.paths import runtime_log_dir

LOG_DIR = runtime_log_dir()
LOG_FILE = LOG_DIR / "tigercapture.log"


def _consume_studio_flag(argv: list[str]) -> bool:
    studio_flags = {"--studio", "--tiger-studio", "/studio"}
    found = any(str(arg).strip().lower() in studio_flags for arg in argv[1:])
    if found:
        argv[:] = [argv[0], *[arg for arg in argv[1:] if str(arg).strip().lower() not in studio_flags]]
    return found


class _TeeStream(io.TextIOBase):
    """Write-only duplicator: each ``write`` goes to both the original
    stream and a second one. Used to copy stderr into a file while
    still showing it in the console."""

    def __init__(self, primary, secondary):
        self._primary = primary
        self._secondary = secondary

    def write(self, data):
        try:
            n = self._primary.write(data)
        except Exception:
            n = len(data) if isinstance(data, str) else 0
        try:
            self._secondary.write(data)
            self._secondary.flush()
        except Exception:
            pass
        return n

    def flush(self):
        for s in (self._primary, self._secondary):
            try:
                s.flush()
            except Exception:
                pass


def _install_logging() -> None:
    """Set up a persistent-file stderr mirror + faulthandler + Python
    excepthook. Crashes that weren't making it into the background-task
    wrapper now land in the runtime ``tigercapture.log`` reliably."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_FILE, "w", encoding="utf-8", errors="replace", buffering=1)
    log_fh.write(
        f"=== TigerCapture session started {datetime.datetime.now().isoformat()} ===\n"
    )
    log_fh.flush()
    sys.stderr = _TeeStream(sys.stderr, log_fh)

    # Native crashes (Qt C++ / Python interpreter faults). Writes
    # directly to the raw file handle, not through our tee, so a
    # segfault in sys.stderr teardown can't swallow the trace.
    faulthandler.enable(file=log_fh, all_threads=True)

    def _on_unhandled(exc_type, exc_value, tb):
        print("=" * 60, file=sys.stderr, flush=True)
        print(
            f"UNHANDLED EXCEPTION at {datetime.datetime.now().isoformat()}:",
            file=sys.stderr, flush=True,
        )
        traceback.print_exception(exc_type, exc_value, tb, file=sys.stderr)
        print("=" * 60, file=sys.stderr, flush=True)

    from app.crash_reporter import install_crash_reporter, record_action

    install_crash_reporter(LOG_DIR, prior_excepthook=_on_unhandled)
    record_action("app.session_start", log_file=str(LOG_FILE))
    try:
        from app.startup_trace import install_subprocess_trace

        install_subprocess_trace()
    except Exception:
        pass


def main() -> int:
    if _consume_studio_flag(sys.argv):
        from studio_main import main as studio_main

        return studio_main()
    _install_logging()
    try:
        from app.preview_acceleration import configure_preview_acceleration_defaults

        configure_preview_acceleration_defaults()
    except Exception:
        pass
    try:
        from app.qt_opengl_policy import configure_qt_opengl_application_attributes

        configure_qt_opengl_application_attributes()
    except Exception:
        pass
    QCoreApplication.setApplicationName("TigerCapture")
    QCoreApplication.setOrganizationName("TigerCapture")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("TigerCapture")
    app.setOrganizationName("TigerCapture")

    from app.window_placement import install_global_window_placement

    install_global_window_placement(app)

    from app.font_fallback import apply_ui_font
    apply_ui_font(app)

    # Window/taskbar icon when running from source (PyInstaller builds
    # also pick this up via the spec's ``icon=`` field).
    _icon_path = Path(__file__).resolve().parent / "resources" / "tigercapture.ico"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    # Global dark theme — applies to every widget that doesn't set its own.
    from app.style import APP_QSS
    app.setStyleSheet(APP_QSS)

    from app.i18n import initialize as init_i18n

    init_i18n()

    from app.controller import AppController
    from app.main_window import MainWindow

    window = MainWindow()
    controller = AppController(window)
    _ = controller
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
