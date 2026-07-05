from __future__ import annotations

from pathlib import Path

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
    trace_video_editor_init,
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
        trace_video_editor_init(
            "video_editor.init.begin",
            source_path=str(source_path) if source_path is not None else None,
        )
        init_editor_state(self)
        init_editor_timers(self)
        init_autosave(self)
        init_window_shell(self)
        init_player_and_audio(self)
        init_actor_state(self)
        init_project_settings(self)
        build_editor_ui_and_finish_startup(self, source_path)


install_video_editor_window_delegates(VideoEditorWindow)
