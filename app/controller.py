from __future__ import annotations

import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from app.capture import capture_region
from app.countdown_overlay import CountdownOverlay
from app.exporter import GifExportThread, Mp4ExportThread
from app.foreground_tracker import ForegroundInfo, ForegroundTracker
from app.gif_editor_window import GifEditorWindow
from app.i18n import tr
from app.main_window import MainWindow
from app.modes import CaptureMode
from app.paths import default_save_dir
from app.recorder import FrameRecorder
from app.recording_bar import RecordingControlBar
from app.recording_border import RecordingBorderOverlay
from app.region_selector import RegionSelectorOverlay
from app.donation_dialog import DonationDialog
from app.screenshot_window import ScreenshotWindow
from app.settings_dialog import SettingsDialog


DEFAULT_GIF_FPS = 15
DEFAULT_VIDEO_FPS = 30
VideoEditorWindow = None


def _video_editor_window_class():
    patched_cls = globals().get("VideoEditorWindow")
    if patched_cls is not None:
        return patched_cls
    from app.video_editor_window_core import VideoEditorWindow

    return VideoEditorWindow


class AppController(QObject):
    """Coordinates the main window, region selection overlay, and capture flows."""

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self.main_window = main_window
        self._overlay: RegionSelectorOverlay | None = None
        self._pending_mode: CaptureMode | None = None
        self._pending_include_cursor: bool = True
        self._open_result_windows: list[QObject] = []
        self._video_editor_opening: bool = False
        self._last_video_editor_open_at: float = 0.0

        self._recorder: FrameRecorder | None = None
        self._border_overlay: RecordingBorderOverlay | None = None
        self._control_bar: RecordingControlBar | None = None
        self._recording_mode: CaptureMode | None = None
        self._recording_rect: QRect = QRect()
        self._recording_cancelled: bool = False
        self._pending_delay_seconds: int = 0
        self._countdown: CountdownOverlay | None = None
        self._active_editors: dict[CaptureMode, GifEditorWindow | None] = {
            CaptureMode.GIF: None,
            CaptureMode.VIDEO: None,
        }

        self._foreground = ForegroundTracker(
            is_own_window=self._is_own_hwnd, parent=self
        )
        self._foreground.changed.connect(self._on_foreground_changed)

        self.main_window.new_capture_requested.connect(self._on_new_capture_requested)
        self.main_window.open_settings_requested.connect(self._open_settings_dialog)
        self.main_window.open_video_editor_requested.connect(
            self._open_video_editor
        )
        self.main_window.open_project_requested.connect(
            self._open_project_from_startup
        )
        self.main_window.open_template_requested.connect(
            self._open_template_from_startup
        )
        self.main_window.open_sound_editor_requested.connect(
            self._open_sound_editor
        )
        self.main_window.open_donation_requested.connect(self._open_donation_dialog)
        self.main_window.open_gif_file_requested.connect(self._prompt_open_gif_file)

        # Keeps references to live WaveformExtractors launched from the
        # standalone Sound Editor flow. Keyed by clip id.
        self._standalone_waveform_extractors: dict[int, object] = {}
        # Keeps references to live standalone Sound Editor windows so
        # Qt doesn't GC them the moment this method returns.
        self._standalone_sound_editors: list[object] = []

    def _open_donation_dialog(self) -> None:
        dlg = DonationDialog(self.main_window)
        dlg.exec()

    def _prompt_open_gif_file(self, source_path: Path | None = None) -> None:
        """Open a GIF in the editor. When called with no ``source_path``
        (button / double-click), a file picker is shown; when called
        with a Path (from the main-window drop router), the GIF loads
        directly."""
        if source_path is None:
            from PySide6.QtWidgets import QFileDialog

            path, _ = QFileDialog.getOpenFileName(
                self.main_window,
                tr("main.mode.gif.open_dialog_title"),
                str(default_save_dir()),
                tr("main.mode.gif.open_dialog_filter"),
            )
            if not path:
                return
            source_path = Path(path)
        self.open_gif_editor_with_file(source_path)

    @staticmethod
    def _parse_video_editor_payload(payload: object) -> tuple[Path | None, str]:
        """Normalize launcher/editor-open payloads.

        Older call sites still emit a plain Path/None.  The launcher now
        emits a small dict so it can carry the chosen workspace mode too.
        """
        source: object = payload
        mode = "standard"
        if isinstance(payload, dict):
            source = payload.get("source_path")
            mode = str(payload.get("workspace_mode") or payload.get("mode") or "standard")
        source_path = Path(source) if source not in (None, "") else None
        mode = mode.lower().strip()
        if mode not in {"standard", "full", "simple"}:
            mode = "standard"
        if mode == "full":
            mode = "standard"
        return source_path, mode

    @staticmethod
    def _apply_video_editor_workspace_mode(editor, workspace_mode: str) -> None:
        try:
            if workspace_mode == "simple" and hasattr(editor, "_on_workspace_mode_selected"):
                editor._on_workspace_mode_selected(workspace_mode == "simple")
            elif (
                workspace_mode == "standard"
                and hasattr(editor, "_screenstudio_simple_mode_enabled")
                and editor._screenstudio_simple_mode_enabled()
                and hasattr(editor, "_on_workspace_mode_selected")
            ):
                editor._on_workspace_mode_selected(False)
        except Exception:
            pass

    @staticmethod
    def _note_startup_crash_report(editor) -> bool:
        """Keep crash reports discoverable without blocking startup."""
        try:
            from app.crash_reporter import has_unseen_crash_report, mark_crash_report_seen

            if not has_unseen_crash_report():
                return False
            if hasattr(editor, "_flash_status"):
                editor._flash_status("최근 크래시 리포트가 있습니다. Recovery/Health에서 확인할 수 있습니다.")
            mark_crash_report_seen()
            return True
        except Exception:
            return False

    def _open_video_editor(self, source_path: object = None) -> None:
        source_path, workspace_mode = self._parse_video_editor_payload(source_path)
        now = time.monotonic()
        opening = bool(getattr(self, "_video_editor_opening", False))
        last_open_at = float(getattr(self, "_last_video_editor_open_at", 0.0) or 0.0)
        if opening or (now - last_open_at) < 1.25:
            try:
                from app.startup_trace import log_startup_trace

                log_startup_trace(
                    "controller.open_video_editor.ignored_duplicate",
                    source_path=str(source_path) if source_path is not None else None,
                    workspace_mode=workspace_mode,
                    opening=opening,
                )
            except Exception:
                pass
            self._clear_launcher_busy_later()
            return
        self._video_editor_opening = True
        self._last_video_editor_open_at = now
        try:
            from app.startup_trace import log_startup_trace

            log_startup_trace(
                "controller.open_video_editor.begin",
                source_path=str(source_path) if source_path is not None else None,
                workspace_mode=workspace_mode,
            )
        except Exception:
            pass
        try:
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
            VideoEditorWindow = _video_editor_window_class()
            editor = VideoEditorWindow(source_path=source_path)
        finally:
            self._video_editor_opening = False
        try:
            from app.startup_trace import log_startup_trace

            log_startup_trace(
                "controller.open_video_editor.editor_constructed",
                source_path=str(source_path) if source_path is not None else None,
                workspace_mode=workspace_mode,
            )
        except Exception:
            pass
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._apply_video_editor_workspace_mode(editor, workspace_mode)
        try:
            from app.startup_trace import log_startup_trace

            log_startup_trace(
                "controller.open_video_editor.workspace_applied",
                workspace_mode=workspace_mode,
            )
        except Exception:
            pass
        editor.show()
        editor.raise_()
        editor.activateWindow()
        try:
            from app.startup_trace import log_startup_trace

            log_startup_trace(
                "controller.open_video_editor.shown",
                source_path=str(source_path) if source_path is not None else None,
                workspace_mode=workspace_mode,
            )
        except Exception:
            pass
        try:
            from app.startup_trace import cleanup_hidden_qt_orphan_windows

            cleanup_hidden_qt_orphan_windows(editor, "controller.open_video_editor.shown")
            QTimer.singleShot(
                250,
                lambda editor=editor: cleanup_hidden_qt_orphan_windows(
                    editor,
                    "controller.open_video_editor.post_show_250ms",
                ),
            )
        except Exception:
            pass
        self._track_result_window(editor)

        # Pure launcher → editor entry should be quiet and deterministic:
        # open the full editor shell only.  Project resume/open is now an
        # explicit user action; auto-resuming here made startup feel like
        # a chain of unrelated windows and could kick off media probes.
        if source_path is None:
            self._note_startup_crash_report(editor)
        self._clear_launcher_busy_later()

    def _open_project_from_startup(self, source_path: Path) -> None:
        from PySide6.QtWidgets import QMessageBox
        from app.project_io import load_project, remember_last_project

        VideoEditorWindow = _video_editor_window_class()
        editor = VideoEditorWindow(source_path=None)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self._track_result_window(editor)
        try:
            load_project(editor, source_path)
            editor._project_path = Path(source_path)
            remember_last_project(editor._project_path)
            if hasattr(editor, "_refresh_window_title"):
                editor._refresh_window_title()
            if hasattr(editor, "_flash_status"):
                editor._flash_status(f"Opened project: {Path(source_path).name}")
        except Exception as exc:
            QMessageBox.warning(
                self.main_window,
                "프로젝트 열기 실패",
                f"{source_path}\n\n{exc}",
            )
            editor.close()
        self.main_window.refresh_recent()
        self._clear_launcher_busy_later()

    def _open_template_from_startup(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        VideoEditorWindow = _video_editor_window_class()
        editor = VideoEditorWindow(source_path=None)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self._track_result_window(editor)
        try:
            editor.show_startup_template_hint(
                str(data.get("id", "") or ""),
                str(data.get("name", "") or "Template"),
            )
        except Exception:
            pass
        self._clear_launcher_busy_later()

    def _clear_launcher_busy_later(self) -> None:
        QTimer.singleShot(350, self.main_window.clear_startup_busy)

    def _maybe_offer_resume_last_project(self, editor) -> None:
        from PySide6.QtWidgets import QMessageBox
        from app.project_io import load_last_project_path, load_project, remember_last_project

        self._note_startup_crash_report(editor)

        last = load_last_project_path()
        if last is None:
            return
        reply = QMessageBox.question(
            editor,
            "이전 프로젝트 이어서?",
            f"전에 작업하던 프로젝트가 있습니다:\n\n{last.name}\n\n이어서 작업하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            load_project(editor, last)
            editor._project_path = last
            remember_last_project(last)
            if hasattr(editor, "_refresh_window_title"):
                editor._refresh_window_title()
        except Exception as exc:
            QMessageBox.warning(
                editor, "프로젝트 열기 실패",
                f"{last}\n\n{exc}",
            )

    def _open_sound_editor(self, source_path: Path | None = None) -> None:
        """Launch the Sound Editor standalone (no video editor parent).

        Called two ways: the main-window button (``source_path=None``,
        we show a picker) and drag-and-drop of an audio file
        (``source_path`` set). The editor receives an unparented
        ``AudioClip`` and falls back to its default track-volume-less
        behavior thanks to the ``parent() is None`` guards it already
        has for the tracks lookup."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from app.audio_tracks import (
            AUDIO_EXTS,
            AudioClip,
            WaveformExtractor,
            probe_audio_duration_ms,
        )
        from app.video_editor_window import SoundEditorWindow

        if source_path is None:
            filter_exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
            picked, _ = QFileDialog.getOpenFileName(
                self.main_window,
                tr("main.sound_editor.pick_title"),
                str(default_save_dir()),
                tr("main.sound_editor.pick_filter", exts=filter_exts),
            )
            if not picked:
                self._clear_launcher_busy_later()
                return
            source_path = Path(picked)

        duration_ms = probe_audio_duration_ms(source_path)
        if duration_ms <= 0:
            QMessageBox.warning(
                self.main_window,
                tr("main.sound_editor.decode_failed_title"),
                tr(
                    "main.sound_editor.decode_failed_body",
                    name=source_path.name,
                ),
            )
            self._clear_launcher_busy_later()
            return

        # Unique clip id: milliseconds since epoch. Safe because the
        # standalone flow never mingles with video-editor clips.
        import time as _time
        clip_id = int(_time.time() * 1000) & 0x7FFFFFFF

        clip = AudioClip(
            id=clip_id,
            source_path=source_path,
            duration_ms=duration_ms,
            trim_start_ms=0,
            trim_end_ms=duration_ms,
        )

        # Drag-drop another mp3 onto the title screen = "switch to this
        # file". Close any open standalone editor first so we don't
        # end up with two QMediaPlayer demuxer threads racing on Qt's
        # FFmpeg backend.
        for existing in list(self._standalone_sound_editors):
            try:
                existing.close()
            except Exception:
                pass

        editor = SoundEditorWindow(clip, parent=None)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.show()
        editor.raise_()
        editor.activateWindow()

        self._standalone_sound_editors.append(editor)

        def _on_closed(_event=None, ed=editor) -> None:
            try:
                self._standalone_sound_editors.remove(ed)
            except ValueError:
                pass
            # The matching WaveformExtractor cleans itself up via its
            # finished → deleteLater chain plus ``_on_ready /
            # _on_failed`` slots popping it from the dict.

        editor.destroyed.connect(lambda _obj=None, ed=editor: _on_closed(ed=ed))

        # Kick off the waveform extraction so the editor eventually
        # shows the peak view instead of the "loading…" placeholder.
        def _on_ready(cid: int, peaks) -> None:
            if cid == clip.id:
                clip.waveform = peaks
                try:
                    editor.refresh_waveform()
                except Exception:
                    pass
            self._standalone_waveform_extractors.pop(cid, None)

        def _on_failed(cid: int, _reason: str) -> None:
            self._standalone_waveform_extractors.pop(cid, None)

        from app.audio_tracks import get_cached_waveform

        cached = get_cached_waveform(clip.source_path)
        if cached is not None:
            clip.waveform = cached
            try:
                editor.refresh_waveform()
            except Exception:
                pass
            self._clear_launcher_busy_later()
            return

        ex = WaveformExtractor(clip.id, clip.source_path)
        ex.ready.connect(_on_ready)
        ex.failed.connect(_on_failed)
        ex.finished.connect(ex.deleteLater)
        self._standalone_waveform_extractors[clip.id] = ex
        ex.start()
        self._clear_launcher_busy_later()

    def open_gif_editor_with_file(self, path: Path) -> None:
        """Load an existing GIF / image sequence into the GIF editor."""
        from PySide6.QtWidgets import QMessageBox

        try:
            img = Image.open(str(path))
            frames: list[Image.Image] = []
            fps_guess = DEFAULT_GIF_FPS
            try:
                n = getattr(img, "n_frames", 1)
            except Exception:
                n = 1
            durations = []
            for i in range(n):
                try:
                    img.seek(i)
                except EOFError:
                    break
                frames.append(img.convert("RGB").copy())
                d = img.info.get("duration")
                if d:
                    durations.append(d)
            if durations:
                avg_d = sum(durations) / len(durations)
                if avg_d > 0:
                    fps_guess = max(1, min(60, int(round(1000 / avg_d))))
            if not frames:
                raise RuntimeError("No frames decoded from file.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self.main_window,
                tr("editor.dialog.save_fail_title"),
                str(exc),
            )
            self._clear_launcher_busy_later()
            return

        self._open_editor(frames, fps_guess, CaptureMode.GIF)
        self._clear_launcher_busy_later()

    def _is_own_hwnd(self, hwnd: int) -> bool:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False
        for w in app.topLevelWidgets():
            try:
                if int(w.winId()) == hwnd:
                    return True
            except Exception:
                continue
        return False

    def _on_foreground_changed(self, info: ForegroundInfo | None) -> None:
        for ed in self._active_editors.values():
            if ed is not None:
                try:
                    ed.update_quick_paste_target(info)
                except Exception:
                    pass
        # Screenshot windows too
        for w in self._open_result_windows:
            fn = getattr(w, "update_quick_paste_target", None)
            if fn:
                try:
                    fn(info)
                except Exception:
                    pass

    def get_paste_target(self) -> ForegroundInfo | None:
        return self._foreground.last_other()

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.main_window)
        dlg.language_changed.connect(self._on_language_changed)
        dlg.exec()

    def _on_language_changed(self, _code: str) -> None:
        """Reapply translated strings live without recreating the window."""
        self.main_window.retranslate()

    def _on_new_capture_requested(
        self, mode: CaptureMode, delay_seconds: int, include_cursor: bool
    ) -> None:
        if mode in (CaptureMode.GIF, CaptureMode.VIDEO):
            if not self._ensure_no_active_editor_for(mode):
                return
        self._pending_mode = mode
        self._pending_include_cursor = include_cursor
        self._pending_delay_seconds = max(0, int(delay_seconds))
        self._start_region_selection()

    def _ensure_no_active_editor_for(self, mode: CaptureMode) -> bool:
        """If an editor of the same mode is open and has unsaved frames,
        prompt the user. Returns False if the user cancelled.
        """
        ed = self._active_editors.get(mode)
        if ed is None or not ed.isVisible():
            self._active_editors[mode] = None
            return True

        has_unsaved = bool(getattr(ed, "_frames", None)) and ed._last_saved_path is None
        if has_unsaved:
            title_key = (
                "ctrl.unsaved.gif_title"
                if mode is CaptureMode.GIF
                else "ctrl.unsaved.video_title"
            )
            label = tr("mode.gif") if mode is CaptureMode.GIF else tr("mode.video")
            ans = QMessageBox.question(
                ed,
                tr(title_key),
                tr("ctrl.unsaved.body", label=label),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ans != QMessageBox.StandardButton.Ok:
                ed.raise_()
                ed.activateWindow()
                return False

        ed.close()
        self._active_editors[mode] = None
        return True

    def _start_region_selection(self) -> None:
        self.main_window.hide()
        QTimer.singleShot(120, self._show_overlay)

    def _show_overlay(self) -> None:
        overlay = RegionSelectorOverlay()
        overlay.region_selected.connect(self._on_region_selected)
        overlay.cancelled.connect(self._on_region_cancelled)
        overlay.start()
        self._overlay = overlay

    def _on_region_selected(self, rect: QRect) -> None:
        self._overlay = None
        mode = self._pending_mode
        include_cursor = self._pending_include_cursor
        delay = self._pending_delay_seconds
        self._pending_mode = None
        self._pending_delay_seconds = 0

        if mode is None:
            return

        if delay > 0:
            countdown = CountdownOverlay(delay)
            countdown.finished.connect(
                lambda m=mode, r=rect, c=include_cursor: self._dispatch_capture(m, r, c)
            )
            countdown.start()
            self._countdown = countdown
        else:
            self._dispatch_capture(mode, rect, include_cursor)

    def _dispatch_capture(
        self, mode: CaptureMode, rect: QRect, include_cursor: bool
    ) -> None:
        self._countdown = None
        if mode is CaptureMode.SCREENSHOT:
            self._handle_screenshot(rect, include_cursor)
        elif mode is CaptureMode.GIF:
            self._start_recording(rect, CaptureMode.GIF, DEFAULT_GIF_FPS, include_cursor)
        elif mode is CaptureMode.VIDEO:
            self._start_recording(rect, CaptureMode.VIDEO, DEFAULT_VIDEO_FPS, include_cursor)

    def _on_region_cancelled(self) -> None:
        self._overlay = None
        self._pending_mode = None
        self._pending_delay_seconds = 0
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _handle_screenshot(self, rect: QRect, include_cursor: bool) -> None:
        try:
            image = capture_region(rect, include_cursor=include_cursor)
        except Exception as exc:
            QMessageBox.critical(
                None,
                tr("ctrl.capture_fail.title"),
                tr("ctrl.capture_fail.body", exc=str(exc)),
            )
            self.main_window.show()
            return

        # Show main window FIRST so the result window can land on top
        # after its own raise/activate. Otherwise Windows puts the
        # most-recently-shown window (main) above the result.
        self.main_window.show()
        window = ScreenshotWindow(image, default_save_dir())
        window.show()
        window.raise_()
        window.activateWindow()
        self._track_result_window(window)

    def _track_result_window(self, window: QObject) -> None:
        self._open_result_windows.append(window)
        window.destroyed.connect(
            lambda _obj, w=window: self._open_result_windows.remove(w)
            if w in self._open_result_windows
            else None
        )

    def _start_recording(
        self, rect: QRect, mode: CaptureMode, fps: int, include_cursor: bool
    ) -> None:
        self._recording_mode = mode
        self._recording_rect = rect
        self._recording_cancelled = False

        self._border_overlay = RecordingBorderOverlay(rect)

        bar = RecordingControlBar(rect, fps)
        bar.pause_requested.connect(lambda: self._set_paused(True))
        bar.resume_requested.connect(lambda: self._set_paused(False))
        bar.stop_requested.connect(self._stop_recording)
        bar.cancel_requested.connect(self._cancel_recording)
        bar.show()
        self._control_bar = bar

        recorder = FrameRecorder(rect, fps, include_cursor=include_cursor)
        recorder.frame_captured.connect(bar.update_progress)
        # Legacy signal — still wired for the macOS recorder which
        # buffers a frame list. Windows recorder emits the streamed
        # signal below instead.
        recorder.finished_recording.connect(self._on_recording_finished)
        recorder.finished_recording_streamed.connect(
            self._on_recording_finished_streamed,
        )
        recorder.error.connect(self._on_recording_error)
        self._recorder = recorder
        recorder.start()

    def _set_paused(self, paused: bool) -> None:
        if self._recorder is not None:
            self._recorder.set_paused(paused)

    def _stop_recording(self) -> None:
        if self._recorder is not None and self._recorder.isRunning():
            self._recorder.request_stop()

    def _cancel_recording(self) -> None:
        self._recording_cancelled = True
        self._stop_recording()

    def _on_recording_finished_streamed(
        self, temp_mp4: str, actual_fps: int, total_ms: int,
    ) -> None:
        """Streaming recorder result: ffmpeg already encoded every
        frame to ``temp_mp4`` while the capture was running.

        For VIDEO mode we now skip the decode-back path entirely —
        move the temp .mp4 to the user's save directory and route
        straight into the Pro video editor (which is file-source
        based, no frame-list memory peak). GIF mode still decodes
        back because the GIF editor consumes a frame list.
        """
        mode = self._recording_mode
        cancelled = self._recording_cancelled
        if cancelled or not temp_mp4:
            # Recording cancelled or encoder produced nothing —
            # delete the temp file (if any) and fall through to the
            # legacy handler with an empty frame list so all the
            # cleanup (recorder dispose, control bar close, main
            # window show) happens in one place.
            if temp_mp4:
                try:
                    Path(temp_mp4).unlink()
                except OSError:
                    pass
            self._on_recording_finished([], actual_fps, total_ms)
            return

        if mode is CaptureMode.VIDEO:
            saved = self._move_temp_capture_to_save_dir(Path(temp_mp4))
            if saved is not None:
                # Tear down recorder UI then open the Pro editor with
                # the freshly captured file as the initial source.
                self._teardown_recording_ui()
                self._recording_mode = None
                self._recording_cancelled = False
                self.main_window.show()
                self._open_video_editor(saved)
                return
            # Fallback: move failed, drop through to decode-back
            # path so the user still gets *some* editor.

        # GIF mode (or VIDEO fallback) — decode the temp .mp4 back
        # into a PIL frame list. Run in a background thread so the UI
        # stays responsive during long recordings.
        self._decode_gif_async(temp_mp4, actual_fps, total_ms)

    def _teardown_recording_ui(self) -> None:
        """Shared cleanup the Pro-editor route uses without going
        through ``_on_recording_finished``."""
        if self._recorder is not None:
            self._recorder.deleteLater()
            self._recorder = None
        if self._border_overlay is not None:
            self._border_overlay.close()
            self._border_overlay = None
        if self._control_bar is not None:
            self._control_bar.close()
            self._control_bar.deleteLater()
            self._control_bar = None

    def _decode_gif_async(self, temp_mp4: str, actual_fps: int, total_ms: int) -> None:
        """Decode temp MP4 → PIL frames in background thread."""
        from PySide6.QtCore import QThread, Signal as _Signal
        from PySide6.QtWidgets import QProgressDialog, QApplication

        class _Worker(QThread):
            done = _Signal(list)
            progress = _Signal(int)

            def __init__(self, path):
                super().__init__()
                self._path = path

            def run(self):
                frames = []
                try:
                    import imageio.v2 as _ii
                    reader = _ii.get_reader(self._path)
                    meta = reader.get_meta_data()
                    total = meta.get("nframes", 0)
                    for i, arr in enumerate(reader):
                        frames.append(Image.fromarray(arr))
                        if total > 0:
                            self.progress.emit(int(i * 100 / total))
                    reader.close()
                except Exception as e:
                    import sys
                    print(f"[decode] {e}", file=sys.stderr)
                try:
                    Path(self._path).unlink()
                except OSError:
                    pass
                self.done.emit(frames)

        dlg = QProgressDialog("GIF 디코딩 중...", None, 0, 100,
                              self.main_window)
        dlg.setWindowTitle("처리 중")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(300)
        dlg.setValue(0)

        worker = _Worker(temp_mp4)
        worker.progress.connect(dlg.setValue)

        def _on_done(frames):
            dlg.close()
            worker.deleteLater()
            self._on_recording_finished(frames, actual_fps, total_ms)

        worker.done.connect(_on_done)
        worker.start()

    def _move_temp_capture_to_save_dir(self, temp_path: Path) -> Path | None:
        """Move the streaming temp .mp4 into the default save dir
        with a timestamped name so it survives the OS temp cleanup
        and the user can find it again. Returns the new path on
        success, ``None`` on failure (caller falls back to decode)."""
        import datetime
        import shutil
        save_dir = default_save_dir()
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        target = save_dir / f"tigercapture-{ts}.mp4"
        n = 1
        while target.exists():
            target = save_dir / f"tigercapture-{ts}-{n}.mp4"
            n += 1
        try:
            shutil.move(str(temp_path), str(target))
            sidecar = Path(str(temp_path) + ".cursor.json")
            if sidecar.is_file():
                try:
                    shutil.move(str(sidecar), str(Path(str(target) + ".cursor.json")))
                except Exception as exc:
                    print(
                        f"[controller] cursor sidecar move failed: {exc}",
                        file=__import__("sys").stderr, flush=True,
                    )
            return target
        except Exception as exc:
            print(
                f"[controller] move of streaming temp mp4 to save dir failed: {exc}",
                file=__import__("sys").stderr, flush=True,
            )
            return None

    def _on_recording_finished(
        self, frames: list[Image.Image], actual_fps: int, total_ms: int
    ) -> None:
        if self._recorder is not None:
            self._recorder.deleteLater()
            self._recorder = None

        if self._border_overlay is not None:
            self._border_overlay.close()
            self._border_overlay = None
        if self._control_bar is not None:
            self._control_bar.close()
            self._control_bar.deleteLater()
            self._control_bar = None

        mode = self._recording_mode
        cancelled = self._recording_cancelled
        self._recording_mode = None
        self._recording_cancelled = False

        if cancelled or not frames:
            self.main_window.show()
            return

        duration_s = total_ms / 1000.0 if total_ms else len(frames) / max(actual_fps, 1)
        _ = duration_s
        # Same ordering trick as screenshot: main first, then the editor
        # raises itself on top — so the user lands on the editor, not
        # the main window.
        self.main_window.show()
        if mode in (CaptureMode.GIF, CaptureMode.VIDEO):
            self._open_editor(frames, actual_fps, mode)

    def _open_editor(
        self, frames: list[Image.Image], fps: int, mode: CaptureMode
    ) -> None:
        existing = self._active_editors.get(mode)
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass
            self._active_editors[mode] = None

        editor = GifEditorWindow(
            frames, fps, default_save_dir(), mode=mode, controller=self
        )
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.update_quick_paste_target(self._foreground.last_other())
        if mode is CaptureMode.VIDEO:
            editor.save_mp4_requested.connect(
                lambda fr, opts, w=editor: self._save_mp4(fr, opts, w)
            )
            editor.send_to_pro_editor_requested.connect(
                lambda _fr, opts: self._open_video_editor(opts.get("output_path"))
            )
        else:
            editor.save_requested.connect(
                lambda fr, opts, w=editor: self._save_gif(fr, opts, w)
            )
        editor.destroyed.connect(lambda *_args, m=mode: self._on_editor_destroyed(m))
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self._active_editors[mode] = editor
        self._track_result_window(editor)

    def _on_editor_destroyed(self, mode: CaptureMode) -> None:
        self._active_editors[mode] = None

    def _save_mp4(
        self,
        frames: list[Image.Image],
        options: dict,
        editor: GifEditorWindow,
    ) -> None:
        out: Path = options["output_path"]
        fps = int(options["fps"])
        scale = float(options["scale"])

        thread = Mp4ExportThread(frames, out, fps, scale)
        editor.begin_export_progress(len(frames), kind="mp4")

        thread.progress.connect(editor.update_export_progress)
        thread.stage.connect(editor.update_export_stage)
        thread.finished_success.connect(lambda p, _size: editor.notify_saved(p))
        thread.finished_error.connect(lambda msg: editor.notify_save_failed(msg))
        thread.finished.connect(thread.deleteLater)

        existing = getattr(self, "_export_threads", None)
        if existing is None:
            existing = []
            self._export_threads = existing
        existing.append(thread)
        thread.finished.connect(
            lambda t=thread: (existing.remove(t) if t in existing else None)
        )

        thread.start()

    def _save_gif(
        self,
        frames: list[Image.Image],
        options: dict,
        editor: GifEditorWindow,
    ) -> None:
        out: Path = options["output_path"]
        fps = int(options["fps"])
        scale = float(options["scale"])
        # New compression knobs — fall back to historical defaults so any
        # caller that doesn't know about them keeps shipping 256 colours
        # with the gifsicle --lossy=60 post-pass TigerCapture has used since 1.0.
        max_colors = int(options.get("max_colors", 256))
        lossy = int(options.get("lossy", 60))

        thread = GifExportThread(frames, out, fps, scale, max_colors, lossy)
        editor.begin_export_progress(len(frames))

        thread.progress.connect(editor.update_export_progress)
        thread.stage.connect(editor.update_export_stage)
        thread.finished_success.connect(lambda p, _size: editor.notify_saved(p))
        thread.finished_error.connect(lambda msg: editor.notify_save_failed(msg))
        thread.finished.connect(thread.deleteLater)

        existing = getattr(self, "_export_threads", None)
        if existing is None:
            existing = []
            self._export_threads = existing
        existing.append(thread)
        thread.finished.connect(
            lambda t=thread: (existing.remove(t) if t in existing else None)
        )

        thread.start()

    def _on_recording_error(self, message: str) -> None:
        if self._border_overlay is not None:
            self._border_overlay.close()
            self._border_overlay = None
        if self._control_bar is not None:
            self._control_bar.close()
            self._control_bar = None
        if self._recorder is not None:
            self._recorder.deleteLater()
            self._recorder = None

        QMessageBox.critical(
            None,
            tr("ctrl.rec_error.title"),
            tr("ctrl.rec_error.body", message=message),
        )
        self.main_window.show()
