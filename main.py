import datetime
import faulthandler
import io
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication


# Mirror stderr to ``logs/bitdam.log`` next to main.py so each run
# leaves a readable trail (timestamps + stderr lines + tracebacks). The
# file is truncated on launch so "latest run" is always at the top.
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "bitdam.log"


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
    wrapper now land in ``logs/bitdam.log`` reliably."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_FILE, "w", encoding="utf-8", errors="replace", buffering=1)
    log_fh.write(
        f"=== Bitdam session started {datetime.datetime.now().isoformat()} ===\n"
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

    sys.excepthook = _on_unhandled


def main() -> int:
    _install_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Bitdam")
    app.setOrganizationName("Bitdam")

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
