from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.subtitles import Subtitle, SubtitleEditDialog, SubtitleLaneRow, SubtitlePanel


ProgressCallback = Callable[[int], None]
CommandRunner = Callable[..., Any]
FfmpegResolver = Callable[[], str]
TempWavFactory = Callable[[], str]


class WhisperTranscriptionError(RuntimeError):
    """Raised when audio extraction or Whisper transcription fails."""


def _noop_progress(_value: int) -> None:
    return None


def _default_ffmpeg_resolver() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def _default_hidden_subprocess_kwargs() -> dict[str, Any]:
    try:
        from app.subprocess_utils import hidden_subprocess_kwargs

        return dict(hidden_subprocess_kwargs())
    except Exception:
        return {}


def _default_temp_wav_factory() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    return tmp_path


def build_whisper_subprocess_script(wav_path: str, language: str, model_size: str) -> str:
    language_expr = repr(language or None)
    return (
        "import json, sys\n"
        "try:\n"
        "    from faster_whisper import WhisperModel\n"
        f"    model = WhisperModel({model_size!r}, device='cpu', compute_type='float32')\n"
        f"    segments, info = model.transcribe({wav_path!r}, language={language_expr}, beam_size=5, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))\n"
        "    out = [{'text': segment.text.strip(), 'start': segment.start, 'end': segment.end} for segment in segments if segment.text.strip()]\n"
        "    sys.stderr.write(f'detected_language={info.language} duration={info.duration:.1f}s segments={len(out)}\\n')\n"
        "except ImportError:\n"
        "    import whisper\n"
        f"    model = whisper.load_model({model_size!r})\n"
        f"    result = model.transcribe({wav_path!r}, language={language_expr})\n"
        "    out = [{'text': segment['text'].strip(), 'start': segment['start'], 'end': segment['end']} for segment in result.get('segments', []) if segment.get('text', '').strip()]\n"
        "print(json.dumps(out))\n"
    )


class WhisperTranscriptionService:
    """Extract a temporary WAV and run Whisper in an isolated subprocess.

    External execution points are constructor-injected so tests can assert the
    command contract without invoking ffmpeg, downloading models, or importing
    Whisper backends.
    """

    def __init__(
        self,
        *,
        ffmpeg_resolver: FfmpegResolver | None = None,
        command_runner: CommandRunner | None = None,
        temp_wav_factory: TempWavFactory | None = None,
        hidden_kwargs_factory: Callable[[], dict[str, Any]] | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._ffmpeg_resolver = ffmpeg_resolver or _default_ffmpeg_resolver
        self._command_runner = command_runner or subprocess.run
        self._temp_wav_factory = temp_wav_factory or _default_temp_wav_factory
        self._hidden_kwargs_factory = hidden_kwargs_factory or _default_hidden_subprocess_kwargs
        self._python_executable = python_executable or sys.executable

    def transcribe(
        self,
        video_path: Path | str,
        *,
        language: str = "",
        model_size: str = "small",
        progress: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        progress = progress or _noop_progress
        path = Path(video_path)
        ffmpeg = self._ffmpeg_resolver()
        tmp_path = self._temp_wav_factory()
        hidden_kwargs = self._hidden_kwargs_factory()
        try:
            progress(10)
            probe_result = self._command_runner(
                [ffmpeg, "-nostdin", "-v", "info", "-i", str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_kwargs,
            )
            if "Audio:" not in str(getattr(probe_result, "stderr", "") or ""):
                raise WhisperTranscriptionError(f"'{path.name}' has no audio stream.")

            result = self._command_runner(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "wav",
                    "-y",
                    tmp_path,
                ],
                capture_output=True,
                **hidden_kwargs,
            )
            if int(getattr(result, "returncode", 0) or 0) != 0:
                stderr = getattr(result, "stderr", b"")
                if isinstance(stderr, bytes):
                    stderr_text = stderr.decode("utf-8", errors="replace")
                else:
                    stderr_text = str(stderr or "")
                raise WhisperTranscriptionError(
                    f"Audio extraction failed (rc={getattr(result, 'returncode', 0)}):\n{stderr_text[-300:]}"
                )

            progress(30)
            script = build_whisper_subprocess_script(tmp_path, language, model_size)
            progress(50)
            proc = self._command_runner(
                [self._python_executable, "-c", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                **hidden_kwargs,
            )
            if int(getattr(proc, "returncode", 0) or 0) != 0:
                stderr = str(getattr(proc, "stderr", "") or "unknown error")
                raise WhisperTranscriptionError(
                    f"Whisper process failed (rc={getattr(proc, 'returncode', 0)}):\n{stderr[-400:]}"
                )
            stdout = str(getattr(proc, "stdout", "") or "").strip()
            if not stdout:
                diag = str(getattr(proc, "stderr", "") or "no output").strip()[-200:]
                raise WhisperTranscriptionError(f"Whisper returned no output.\n{diag}")
            decoded = json.loads(stdout)
            if not isinstance(decoded, list):
                raise WhisperTranscriptionError("Whisper returned an invalid segment payload.")
            progress(100)
            return [dict(segment) for segment in decoded if isinstance(segment, dict)]
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass


class WhisperTranscriber(QThread):
    """QThread wrapper around WhisperTranscriptionService."""

    ready = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(
        self,
        video_path: Path | str,
        language: str,
        model_size: str,
        parent: QObject | None = None,
        *,
        service: WhisperTranscriptionService | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = Path(video_path)
        self._language = language
        self._model_size = model_size
        self._service = service or WhisperTranscriptionService()

    def run(self) -> None:
        try:
            segments = self._service.transcribe(
                self._path,
                language=self._language,
                model_size=self._model_size,
                progress=self.progress.emit,
            )
            self.ready.emit(segments)
        except Exception as exc:
            self.failed.emit(str(exc))


class WhisperDialog(QDialog):
    """Modal settings and progress dialog for AI subtitle generation."""

    _LANGUAGES = [
        ("Auto detect", ""),
        ("Korean", "ko"),
        ("English", "en"),
        ("Japanese", "ja"),
        ("Chinese", "zh"),
        ("Spanish", "es"),
        ("French", "fr"),
        ("German", "de"),
    ]

    _MODELS = [
        ("tiny - fast / less accurate", "tiny"),
        ("base - balanced", "base"),
        ("small - recommended", "small"),
        ("medium - accurate", "medium"),
        ("large - best accuracy", "large-v3"),
    ]

    def __init__(
        self,
        video_path: Path | str,
        parent: QWidget | None = None,
        *,
        transcriber_factory: Callable[[Path, str, str, QObject | None], WhisperTranscriber] | None = None,
    ) -> None:
        super().__init__(parent)
        self._video_path = Path(video_path)
        self._worker: WhisperTranscriber | None = None
        self._transcriber_factory = transcriber_factory or (
            lambda path, language, model_size, parent_obj: WhisperTranscriber(path, language, model_size, parent_obj)
        )
        self.segments: list[dict[str, Any]] = []

        self.setWindowTitle("AI Subtitles")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        root.addWidget(QLabel("Model size"))
        self._model_combo = QComboBox()
        for label, _value in self._MODELS:
            self._model_combo.addItem(label)
        self._model_combo.setCurrentIndex(2)
        root.addWidget(self._model_combo)

        root.addWidget(QLabel("Language"))
        self._lang_combo = QComboBox()
        for label, _value in self._LANGUAGES:
            self._lang_combo.addItem(label)
        root.addWidget(self._lang_combo)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        root.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Generate subtitles")
        self._run_btn.setObjectName("PrimaryToolButton")
        self._run_btn.clicked.connect(self._start)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("ToolButton")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._cancel_btn)
        root.addLayout(btn_row)

    def _start(self) -> None:
        model_size = self._MODELS[self._model_combo.currentIndex()][1]
        language = self._LANGUAGES[self._lang_combo.currentIndex()][1]

        self._run_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.setText("Extracting audio...")

        self._worker = self._transcriber_factory(self._video_path, language, model_size, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, value: int) -> None:
        self._progress.setValue(value)
        if value < 30:
            self._status_label.setText("Extracting audio...")
        elif value < 50:
            self._status_label.setText("Loading model...")
        elif value < 100:
            self._status_label.setText("Transcribing...")
        else:
            self._status_label.setText("Done")

    def _on_ready(self, segments: list[dict[str, Any]]) -> None:
        self.segments = list(segments or [])
        self.accept()

    def _on_failed(self, reason: str) -> None:
        self._progress.hide()
        self._status_label.setText("Error occurred. Copy details and share them.")
        self._run_btn.setEnabled(True)
        print(f"[whisper] FAILED: {reason}", file=sys.stderr, flush=True)

        err_dlg = QDialog(self)
        err_dlg.setWindowTitle("AI Subtitle Error")
        err_dlg.resize(600, 300)
        layout = QVBoxLayout(err_dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(reason)
        text.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(err_dlg.accept)
        layout.addWidget(close_btn)
        err_dlg.exec()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().closeEvent(event)


@dataclass
class SubtitleSectionWidgets:
    host: QWidget
    header_row: QWidget
    panel: SubtitlePanel
    lane: SubtitleLaneRow
    ai_button: QPushButton
    srt_button: QPushButton
    toggle_button: QPushButton


class SubtitleSectionBuilder:
    """Build and wire the editor subtitle section using shared subtitle widgets."""

    def __init__(
        self,
        *,
        panel_cls: type[SubtitlePanel] = SubtitlePanel,
        lane_row_cls: type[SubtitleLaneRow] = SubtitleLaneRow,
    ) -> None:
        self._panel_cls = panel_cls
        self._lane_row_cls = lane_row_cls

    def build(
        self,
        *,
        parent: QWidget,
        root_layout: Any,
        tracks_layout: Any,
        timeline_ruler: Any,
        player: Any,
        px_per_sec: float,
        make_section_header: Callable[[str, str], QWidget],
        on_generate_ai_subtitles: Callable[[], None],
        on_import_srt_subtitles: Callable[[], None],
        on_subtitles_changed: Callable[[], None],
        on_subtitle_popout: Callable[[], None],
        on_subtitle_lane_edit: Callable[[int], None],
    ) -> SubtitleSectionWidgets:
        host = QWidget(parent)
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)

        header_row = QWidget(host)
        header_row.setObjectName("SubtitleHeaderRow")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 8, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(make_section_header(tr("veditor.section.subtitles"), "subtitles"), stretch=1)

        ai_button = QPushButton("AI Subtitles")
        ai_button.setObjectName("ToolButton")
        ai_button.setToolTip("Generate subtitles with Whisper.")
        ai_button.clicked.connect(on_generate_ai_subtitles)
        header_layout.addWidget(ai_button)

        srt_button = QPushButton("SRT")
        srt_button.setObjectName("ToolButton")
        srt_button.setToolTip("Import an SRT file using Screen Studio subtitle defaults.")
        srt_button.clicked.connect(on_import_srt_subtitles)
        header_layout.addWidget(srt_button)

        toggle_button = QPushButton("Show")
        toggle_button.setObjectName("SectionDisclosure")
        toggle_button.setCheckable(True)
        toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_button.setToolTip("Show or hide subtitle editor")
        header_layout.addWidget(toggle_button)
        host_layout.addWidget(header_row)

        panel = self._panel_cls(position_provider=lambda: int(player.position()))
        panel.subtitles_changed.connect(on_subtitles_changed)
        panel.popout_requested.connect(on_subtitle_popout)
        timeline_ruler.set_subtitle_layer(panel.layer)

        lane = self._lane_row_cls(panel.layer)
        lane.set_px_per_sec(px_per_sec)
        lane.request_edit.connect(on_subtitle_lane_edit)
        ruler_idx = tracks_layout.indexOf(timeline_ruler)
        if ruler_idx >= 0:
            tracks_layout.insertWidget(ruler_idx + 1, lane)
        else:
            tracks_layout.addWidget(lane)

        host_layout.addWidget(panel)

        def apply_panel_open(opened: bool) -> None:
            panel.setVisible(bool(opened))
            toggle_button.setText("Hide" if opened else "Show")

        toggle_button.toggled.connect(apply_panel_open)
        toggle_button.setChecked(False)
        apply_panel_open(False)

        root_layout.addWidget(host, stretch=1)
        return SubtitleSectionWidgets(
            host=host,
            header_row=header_row,
            panel=panel,
            lane=lane,
            ai_button=ai_button,
            srt_button=srt_button,
            toggle_button=toggle_button,
        )

    def install_on_editor(self, editor: Any) -> SubtitleSectionWidgets:
        widgets = self.build(
            parent=editor._right_dock_host,
            root_layout=editor._right_dock_layout,
            tracks_layout=editor._tracks_layout,
            timeline_ruler=editor._timeline_ruler,
            player=editor._player,
            px_per_sec=editor._px_per_sec,
            make_section_header=editor._make_section_header,
            on_generate_ai_subtitles=editor._generate_ai_subtitles,
            on_import_srt_subtitles=editor._import_screenstudio_srt_subtitles,
            on_subtitles_changed=editor._on_subtitles_changed,
            on_subtitle_popout=editor._toggle_subtitle_popout,
            on_subtitle_lane_edit=editor._on_subtitle_lane_edit,
        )
        editor._subtitle_section_host = widgets.host
        editor._subtitle_panel = widgets.panel
        editor._subtitle_lane = widgets.lane
        editor._subtitle_panel_toggle_btn = widgets.toggle_button
        editor._subtitle_root_layout = editor._right_dock_layout
        editor._subtitle_root_index = editor._right_dock_layout.count() - 1
        editor._subtitle_popout = None
        editor._subtitle_placeholder = None
        return widgets


@dataclass(frozen=True)
class SubtitleOverlayPlacement:
    x: int
    y: int
    width: int
    height: int


class SubtitleOverlayController:
    BOX_STYLE = (
        "QLabel { color: white; "
        "background-color: rgba(0, 0, 0, 180); "
        "padding: 6px 14px; border-radius: 4px; "
        "font-size: 18px; font-weight: 600; }"
    )
    TEXT_STYLE = (
        "QLabel { color: white; "
        "background-color: transparent; "
        "padding: 4px 10px; "
        "font-size: 20px; font-weight: 900; }"
    )

    def __init__(
        self,
        *,
        panel: SubtitlePanel,
        overlay: QLabel,
        preview_host: QWidget,
        player: Any | None = None,
        register_change: Callable[[str], None] | None = None,
    ) -> None:
        self.panel = panel
        self.overlay = overlay
        self.preview_host = preview_host
        self.player = player
        self.register_change = register_change

    def update(self, pos_ms: int) -> Subtitle | None:
        sub = self.panel.active_subtitle(pos_ms)
        if sub is None or not str(sub.text).strip():
            self.overlay.hide()
            return None
        self.overlay.setText(sub.text)
        self.overlay.setStyleSheet(self.BOX_STYLE if sub.show_box else self.TEXT_STYLE)
        self.reposition()
        self.overlay.show()
        return sub

    def reposition(self) -> SubtitleOverlayPlacement:
        host_size = self.preview_host.size()
        self.overlay.adjustSize()
        overlay_width = min(int(host_size.width() * 0.9), max(200, self.overlay.width()))
        overlay_height = self.overlay.heightForWidth(overlay_width)
        if overlay_height <= 0:
            overlay_height = self.overlay.height()
        x = (host_size.width() - overlay_width) // 2
        y = host_size.height() - overlay_height - 12
        x = max(0, x)
        y = max(0, y)
        self.overlay.setFixedWidth(overlay_width)
        self.overlay.move(x, y)
        return SubtitleOverlayPlacement(x=x, y=y, width=overlay_width, height=overlay_height)

    def on_subtitles_changed(self) -> None:
        pos_ms = 0
        if self.player is not None:
            try:
                pos_ms = int(self.player.position())
            except Exception:
                pos_ms = 0
        self.update(pos_ms)
        if self.register_change is not None:
            self.register_change("subtitle edit")


class SubtitleLaneEditController:
    """Open the shared subtitle edit dialog for a timeline-lane item."""

    def __init__(
        self,
        *,
        panel: SubtitlePanel,
        player: Any,
        parent: QWidget | None = None,
        changed_callback: Callable[[], None] | None = None,
        dialog_cls: type[SubtitleEditDialog] = SubtitleEditDialog,
    ) -> None:
        self.panel = panel
        self.player = player
        self.parent = parent
        self.changed_callback = changed_callback
        self.dialog_cls = dialog_cls

    def edit(self, idx: int) -> bool:
        layer = self.panel.layer
        items = layer.items()
        if idx < 0 or idx >= len(items):
            return False
        try:
            max_ms = max(int(self.player.duration()), 0)
        except Exception:
            max_ms = 0
        dialog = self.dialog_cls(self.parent, items[idx], max_ms)
        if dialog.exec():
            layer.replace_at(idx, dialog.result_subtitle())
            if self.changed_callback is not None:
                self.changed_callback()
            return True
        return False


class AISubtitleWorkflow:
    """Resolve source media, run WhisperDialog, and add generated subtitles."""

    def __init__(
        self,
        *,
        dialog_cls: type[WhisperDialog] = WhisperDialog,
        subtitle_plan_builder: Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]] | None = None,
        message_box: Any = QMessageBox,
        availability_checker: Callable[[], bool] | None = None,
    ) -> None:
        self.dialog_cls = dialog_cls
        self.message_box = message_box
        self.availability_checker = availability_checker or self.whisper_available
        self.subtitle_plan_builder = subtitle_plan_builder or self._default_plan_builder

    @staticmethod
    def whisper_available() -> bool:
        return (
            importlib.util.find_spec("faster_whisper") is not None
            or importlib.util.find_spec("whisper") is not None
        )

    @staticmethod
    def _default_plan_builder(project_settings: dict[str, Any], transcript_segments: list[dict[str, Any]]) -> dict[str, Any]:
        from app.screenstudio_parity import screenstudio_transcript_subtitle_plan

        return screenstudio_transcript_subtitle_plan(project_settings, transcript_segments)

    @staticmethod
    def resolve_video_path(editor: Any) -> Path | None:
        active_track_id = getattr(editor, "_active_track_id", None)
        if active_track_id is not None:
            find_track = getattr(editor, "_find_track", None)
            track = find_track(active_track_id) if callable(find_track) else None
            source_path = getattr(track, "source_path", None)
            if source_path:
                return Path(source_path)

        for track in list(getattr(editor, "_tracks", []) or []):
            source_path = getattr(track, "source_path", None)
            if source_path:
                return Path(source_path)

        for track in list(getattr(editor, "_tracks", []) or []):
            for clip in list(getattr(track, "clips", []) or []):
                source_path = getattr(clip, "source_path", None)
                if source_path:
                    return Path(source_path)
        return None

    @staticmethod
    def transcript_rows_from_segments(segments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for segment in segments:
            try:
                rows.append(
                    {
                        "text": str(segment.get("text") or ""),
                        "start_ms": int(float(segment.get("start", 0.0)) * 1000),
                        "end_ms": int(float(segment.get("end", 0.0)) * 1000),
                    }
                )
            except Exception:
                continue
        return rows

    @staticmethod
    def subtitle_from_row(row: dict[str, Any]) -> Subtitle:
        return Subtitle(
            text=str(row.get("text") or ""),
            start_ms=int(row.get("start_ms", 0) or 0),
            end_ms=int(row.get("end_ms", 0) or 0),
            show_box=bool(row.get("show_box", True)),
            style=dict(row.get("style", {}) or {}),
        )

    def apply_segments(self, editor: Any, segments: Iterable[dict[str, Any]]) -> int:
        transcript_segments = self.transcript_rows_from_segments(segments)
        if not transcript_segments:
            return 0
        plan = self.subtitle_plan_builder(dict(getattr(editor, "_project_settings", {}) or {}), transcript_segments)
        panel = getattr(editor, "_subtitle_panel", None)
        if panel is None:
            return 0
        layer = panel.layer
        count = 0
        for row in list(plan.get("subtitle_rows", []) or []):
            if not isinstance(row, dict):
                continue
            try:
                layer.add(self.subtitle_from_row(row))
                count += 1
            except Exception:
                continue
        try:
            panel._refresh_list()
        except Exception:
            pass
        try:
            panel.subtitles_changed.emit()
        except Exception:
            pass
        try:
            editor._on_subtitles_changed()
        except Exception:
            pass
        return count

    def generate_for_editor(self, editor: Any) -> int:
        if not self.availability_checker():
            self.message_box.warning(
                editor,
                "AI Subtitles",
                "Whisper is not installed. Install faster-whisper or openai-whisper before generating subtitles.",
            )
            return 0

        path = self.resolve_video_path(editor)
        if path is None:
            self.message_box.warning(editor, "AI Subtitles", "No source video is available for subtitle generation.")
            return 0

        dialog = self.dialog_cls(path, editor)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        count = self.apply_segments(editor, getattr(dialog, "segments", []) or [])
        if count:
            self.message_box.information(editor, "AI Subtitles", f"Generated {count} subtitle rows.")
        return count


class VideoEditorSubtitleWorkflow:
    """Editor-facing facade with method names matching the old window hooks."""

    def __init__(
        self,
        editor: Any,
        *,
        section_builder: SubtitleSectionBuilder | None = None,
        ai_workflow: AISubtitleWorkflow | None = None,
    ) -> None:
        self.editor = editor
        self.section_builder = section_builder or SubtitleSectionBuilder()
        self.ai_workflow = ai_workflow or AISubtitleWorkflow()

    def build_section(self) -> SubtitleSectionWidgets:
        return self.section_builder.install_on_editor(self.editor)

    def overlay_controller(self) -> SubtitleOverlayController:
        return SubtitleOverlayController(
            panel=self.editor._subtitle_panel,
            overlay=self.editor._subtitle_overlay,
            preview_host=self.editor._preview_host,
            player=self.editor._player,
            register_change=self.editor._register_change,
        )

    def update_overlay(self, pos_ms: int) -> Subtitle | None:
        return self.overlay_controller().update(pos_ms)

    def reposition_overlay(self) -> SubtitleOverlayPlacement:
        return self.overlay_controller().reposition()

    def on_subtitles_changed(self) -> None:
        self.overlay_controller().on_subtitles_changed()

    def on_subtitle_lane_edit(self, idx: int) -> bool:
        return SubtitleLaneEditController(
            panel=self.editor._subtitle_panel,
            player=self.editor._player,
            parent=self.editor,
            changed_callback=self.editor._on_subtitles_changed,
        ).edit(idx)

    def generate_ai_subtitles(self) -> int:
        return self.ai_workflow.generate_for_editor(self.editor)


def build_subtitle_section(editor: Any) -> SubtitleSectionWidgets:
    return VideoEditorSubtitleWorkflow(editor).build_section()


def update_subtitle_overlay(editor: Any, pos_ms: int) -> Subtitle | None:
    return VideoEditorSubtitleWorkflow(editor).update_overlay(pos_ms)


def reposition_subtitle_overlay(editor: Any) -> SubtitleOverlayPlacement:
    return VideoEditorSubtitleWorkflow(editor).reposition_overlay()


def on_subtitles_changed(editor: Any) -> None:
    VideoEditorSubtitleWorkflow(editor).on_subtitles_changed()


def on_subtitle_lane_edit(editor: Any, idx: int) -> bool:
    return VideoEditorSubtitleWorkflow(editor).on_subtitle_lane_edit(idx)


def generate_ai_subtitles(editor: Any) -> int:
    return VideoEditorSubtitleWorkflow(editor).generate_ai_subtitles()
