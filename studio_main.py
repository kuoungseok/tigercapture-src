from __future__ import annotations

import datetime
import faulthandler
import io
import os
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.paths import runtime_log_dir


LOG_DIR = runtime_log_dir()
LOG_FILE = LOG_DIR / "tigerstudio.log"


class _TeeStream(io.TextIOBase):
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
        for stream in (self._primary, self._secondary):
            try:
                stream.flush()
            except Exception:
                pass


def _install_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = open(LOG_FILE, "w", encoding="utf-8", errors="replace", buffering=1)
    log_fh.write(
        f"=== Tiger Studio session started {datetime.datetime.now().isoformat()} ===\n"
    )
    log_fh.flush()
    sys.stderr = _TeeStream(sys.stderr, log_fh)
    faulthandler.enable(file=log_fh, all_threads=True)

    def _on_unhandled(exc_type, exc_value, tb):
        print("=" * 60, file=sys.stderr, flush=True)
        print(
            f"UNHANDLED EXCEPTION at {datetime.datetime.now().isoformat()}:",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exception(exc_type, exc_value, tb, file=sys.stderr)
        print("=" * 60, file=sys.stderr, flush=True)

    from app.crash_reporter import install_crash_reporter, record_action

    install_crash_reporter(LOG_DIR, prior_excepthook=_on_unhandled)
    record_action("studio.session_start", log_file=str(LOG_FILE))
    try:
        from app.startup_trace import install_subprocess_trace

        install_subprocess_trace()
    except Exception:
        pass


def _consume_source_arg(argv: list[str]) -> Path | None:
    for raw in argv[1:]:
        if not raw or str(raw).startswith("-"):
            continue
        return Path(raw)
    return None


def _consume_option_path(argv: list[str], option: str) -> Path | None:
    try:
        index = argv.index(option)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    value = str(argv[index + 1] or "").strip()
    return Path(value) if value else None


def _load_project_after_show(editor, project_path: Path) -> None:
    try:
        from app.project_io import load_project, remember_last_project

        load_project(editor, project_path)
        editor._project_path = project_path
        remember_last_project(project_path)
        if hasattr(editor, "_refresh_window_title"):
            editor._refresh_window_title()
        if hasattr(editor, "_flash_status"):
            editor._flash_status(f"Opened project: {project_path.name}")
    except Exception as exc:
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(editor, "Open project failed", f"{project_path}\n\n{exc}")
        except Exception:
            print(f"[studio] project load failed: {project_path}: {exc}", file=sys.stderr)


def main() -> int:
    color_probe_path = _consume_option_path(sys.argv, "--color-runtime-probe")
    if color_probe_path is not None:
        from app.color_runtime_probe import write_color_runtime_probe_report

        report = write_color_runtime_probe_report(color_probe_path)
        return 0 if report.get("ok") else 1
    os.environ["TIGERCAPTURE_CAPTURE_TO_STUDIO"] = "1"
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

    QCoreApplication.setApplicationName("Tiger Studio")
    QCoreApplication.setOrganizationName("TigerCapture")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Tiger Studio")
    app.setOrganizationName("TigerCapture")

    from app.window_placement import install_global_window_placement

    install_global_window_placement(app)

    from app.font_fallback import apply_ui_font

    apply_ui_font(app)

    icon_path = Path(__file__).resolve().parent / "resources" / "tigercapture.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from app.i18n import initialize as init_i18n
    from app.style import APP_QSS
    from app.studio_startup_splash import StudioStartupSplash

    app.setStyleSheet(APP_QSS)
    init_i18n()

    source_arg = _consume_source_arg(sys.argv)
    project_path = source_arg if source_arg is not None and source_arg.suffix.lower() == ".tgp" else None
    source_path = None if project_path is not None else source_arg
    splash = StudioStartupSplash()
    splash.set_status(
        "Starting Tiger Studio...",
        "Loading the editor workspace and GPU preview surface.",
    )
    splash.show()
    splash.raise_()
    splash.activateWindow()
    app.processEvents()

    state: dict[str, object] = {"splash": splash}

    def _open_editor() -> None:
        try:
            splash.set_status(
                "Loading editor modules...",
                "Preparing media pool, timeline, preview, and automation actions.",
            )
            app.processEvents()
            from app.video_editor_window_core import VideoEditorWindow

            splash.set_status(
                "Building editor window...",
                "Initializing the timeline, player, audio mixer, and OpenGL preview.",
            )
            app.processEvents()
            editor = VideoEditorWindow(source_path=source_path)
            state["editor"] = editor
            editor.setWindowTitle("Tiger Studio")

            splash.set_status("Opening editor...", "Finalizing the visible workspace.")
            app.processEvents()
            editor.show()
            editor.raise_()
            editor.activateWindow()
            splash.close()
            if project_path is not None:
                QTimer.singleShot(0, lambda: _load_project_after_show(editor, project_path))
        except Exception as exc:
            print("[studio] startup failed:", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            splash.set_error(f"{type(exc).__name__}: {exc}")
            splash.show()
            splash.raise_()
            splash.activateWindow()

    QTimer.singleShot(0, _open_editor)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
