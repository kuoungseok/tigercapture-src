from __future__ import annotations

from pathlib import Path
from time import perf_counter

from PySide6.QtWidgets import QWidget

from app.video_editor_export_controls import (
    FPS_PRESETS as _EXPORT_FPS_PRESETS,
    RESOLUTION_PRESETS as _EXPORT_RESOLUTION_PRESETS,
)
from app.video_editor_window_delegates import install_video_editor_window_delegates
from app.video_editor_window_initializer import (
    build_editor_ui_and_finish_startup,
    init_actor_state,
    init_autosave,
    init_editor_state,
    init_editor_timers,
    init_player_and_audio,
    init_project_settings,
    init_window_shell,
    trace_video_editor_phase,
)


class VideoEditorWindow(QWidget):
    """Professional video editor shell.

    The behavior surface is installed by app.video_editor_window_delegates so
    the class stays small while the historical method names remain available.
    """

    _RESOLUTION_PRESETS = _EXPORT_RESOLUTION_PRESETS
    _FPS_PRESETS = _EXPORT_FPS_PRESETS

    def __init__(self, source_path: Path | None = None) -> None:
        super().__init__()
        self._startup_trace_begin = perf_counter()
        self._startup_trace_last = self._startup_trace_begin
        trace_video_editor_phase(
            self,
            "video_editor.init.begin",
            source_path=str(source_path) if source_path is not None else None,
        )
        init_editor_state(self)
        trace_video_editor_phase(self, "video_editor.init.state_done")
        init_editor_timers(self)
        trace_video_editor_phase(self, "video_editor.init.timers_done")
        init_autosave(self)
        trace_video_editor_phase(self, "video_editor.init.autosave_done")
        init_window_shell(self)
        trace_video_editor_phase(self, "video_editor.init.shell_done")
        init_player_and_audio(self)
        trace_video_editor_phase(self, "video_editor.init.player_audio_done")
        init_actor_state(self)
        trace_video_editor_phase(self, "video_editor.init.actor_state_done")
        init_project_settings(self)
        trace_video_editor_phase(self, "video_editor.init.project_settings_done")
        build_editor_ui_and_finish_startup(self, source_path)


install_video_editor_window_delegates(VideoEditorWindow)
