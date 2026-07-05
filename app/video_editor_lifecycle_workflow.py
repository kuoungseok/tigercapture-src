from __future__ import annotations

import os
import time

from PySide6.QtWidgets import QApplication


def _record_editor_action(self, event: str, **data) -> None:
    if not str(event or "").startswith(("autosave.", "recovery.")):
        try:
            self._autosave_dirty = True
        except Exception:
            pass
    try:
        from app.crash_reporter import record_action

        record_action(event, **data)
    except Exception:
        pass


def _yield_startup_ui(self, phase: str) -> None:
    """Trace editor bootstrap phases without pumping Qt events by default.

    The startup trace showed that calling ``processEvents()`` while the
    editor tree was half-built let unattached Qt widgets become visible
    top-level windows. Keep this as an opt-in diagnostic hook only.
    """
    try:
        from app.startup_trace import cleanup_hidden_qt_orphan_windows

        cleanup_hidden_qt_orphan_windows(self, f"video_editor.startup_yield.{phase}")
    except Exception:
        pass
    now = time.monotonic()
    last = float(getattr(self, "_startup_ui_yield_last_at", 0.0) or 0.0)
    if now - last < 0.12:
        return
    self._startup_ui_yield_last_at = now
    try:
        from app.startup_trace import log_startup_trace

        log_startup_trace("video_editor.startup_yield", phase=phase)
    except Exception:
        pass
    if str(os.environ.get("TIGERCAPTURE_STARTUP_YIELD") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }:
        return
    app = QApplication.instance()
    if app is not None:
        try:
            app.processEvents()
        except Exception:
            pass


def closeEvent(self, event) -> None:
    try:
        self._end_window_move_guard()
    except Exception:
        pass
    try:
        self._do_autosave("close")
    except Exception:
        pass
    try:
        self._autosave_timer.stop()
    except Exception:
        pass
    try:
        from app.crash_reporter import record_action, set_emergency_autosave_callback
        record_action("editor.close")
        set_emergency_autosave_callback(None)
    except Exception:
        pass
    thumbnail_extractors = [
        *list(self._extractors.values()),
        *list(getattr(self, "_clip_extractors", {}).values()),
        *list(getattr(self, "_retired_thumbnail_extractors", [])),
    ]
    for ex in thumbnail_extractors:
        ex.stop()
    for ex in thumbnail_extractors:
        try:
            ex.wait(300)
        except Exception:
            pass
    # Waveform + spectrum extractor threads are detached from the
    # main player. If we let them outlive this widget, Qt logs
    # "QThread: Destroyed while thread '' is still running" and
    # the process aborts on Windows. Drain them with a short wait
    # window ??the underlying ffmpeg pipe normally finishes well
    # inside this budget.
    for ex in list(getattr(self, "_waveform_extractors", {}).values()):
        try:
            ex.quit()
        except Exception:
            pass
    for ex in list(getattr(self, "_waveform_extractors", {}).values()):
        try:
            if not ex.wait(400):
                ex.terminate()
                ex.wait(100)
        except Exception:
            pass
    for ex in list(getattr(self, "_spectrum_map", {}).keys()):
        try:
            ex.quit()
        except Exception:
            pass
    for ex in list(getattr(self, "_spectrum_map", {}).keys()):
        try:
            if not ex.wait(400):
                ex.terminate()
                ex.wait(100)
        except Exception:
            pass
    # Also tear down any still-open per-clip sound editor windows ??
    # they hold their own spectrum extractor + media player.
    for se in list(getattr(self, "_sound_editors", []) or []):
        try:
            se.close()
        except Exception:
            pass
    try:
        self._shutdown_qwen_local_processes(reason="editor_close")
    except Exception:
        pass
    try:
        self._player.release()
    except Exception:
        pass
    super(type(self), self).closeEvent(event)

