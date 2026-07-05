from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer

from app.audio_tracks import AudioMixer
from app.editor_observability import live2d_startup_warmup_enabled as _live2d_startup_warmup_enabled
from app.i18n import tr
from app.project_player import ProjectPlayer
from app.style import editor_scrollbar_qss
from app.video_editor_window_style import MEDIA_POOL_REFERENCE_QSS, VIDEO_EDITOR_EXTRA_QSS


def trace_video_editor_init(event: str, **payload) -> None:
    try:
        from app.startup_trace import log_startup_trace

        log_startup_trace(event, **payload)
    except Exception:
        pass


def init_editor_state(self) -> None:
    from app.history import HistoryStack

    self._tracks = []
    self._track_rows = {}
    self._audio_tracks = []
    self._audio_rows = {}
    from app.sound_editor_panel import SoundEditStateStore

    self._sound_edit_state_store = SoundEditStateStore()
    self._waveform_extractors = {}
    self._waveform_clip_map = {}
    self._waveform_job_key = {}
    self._waveform_source_jobs = {}
    self._waveform_job_seq = 1
    self._spectrum_source_jobs = {}
    self._preview_popout = None
    self._next_track_id = 1
    self._active_track_id = None
    self._current_segment_speed = 1.0
    self._jkl_transport_rate = 0.0
    self._extractors = {}
    self._retired_thumbnail_extractors = []
    self._clip_extractors = {}
    from app.timeline_ruler import DEFAULT_PX_PER_SEC

    self._px_per_sec = DEFAULT_PX_PER_SEC
    self._strokes = []
    self._bubbles = []
    self._bubble_items = []
    self._stickers = []
    self._sticker_items = []
    self._text_preview_label = None
    self._history = HistoryStack(max_undo_steps=10)
    self._history_suspended = False
    self._autosave_dirty = False
    self._selected_clips = []
    self._timeline_clipboard = None
    self._timeline_tool_mode = "select"
    self._next_nested_group_id = 1
    self._global_in_ms = -1
    self._global_out_ms = -1
    self._timeline_markers = []
    self._MARKER_COLORS = ["#f0a030", "#40c060", "#4090e0", "#e0d040"]
    self._node_grade_target = None
    self._last_good_preview_pixmap = None
    self._last_good_preview_rgb = None
    self._preview_tab_guard_until_ms = 0.0
    self._preview_black_recovery_until_ms = 0.0
    self._screenstudio_polish_dialog = None
    self._screenstudio_polish_dirty_since_register = False
    self._screenstudio_forced_media_path = None
    self._creator_assist_bundle = {}
    self._capcut_creator_package = {}
    self._capcut_short_ranges = []
    self._capcut_render_queue_jobs = []
    self._ai_script_edit_plan = None
    self._ai_script_edit_payload = {}
    self._localized_collapsible_headers = {}
    self._lut_data = None
    self._lut_strength = 1.0
    self._lut_path = ""
    self._proxy_mode = False
    self._proxy_dir = None
    self._proxy_threads = {}


def init_editor_timers(self) -> None:
    self._blade_dash_offset = 0
    self._blade_dash_timer = QTimer(self)
    self._blade_dash_timer.setInterval(80)
    self._blade_dash_timer.timeout.connect(self._tick_blade_dash)
    self._blade_dash_timer.start()
    self._window_move_guard_active = False
    self._window_move_guard_blade_was_active = False
    self._window_move_guard_started_at = 0.0
    self._window_move_guard_stats = {}
    self._window_move_guard_restore_timer = QTimer(self)
    self._window_move_guard_restore_timer.setSingleShot(True)
    self._window_move_guard_restore_timer.timeout.connect(self._end_window_move_guard)


def init_autosave(self) -> None:
    self._project_path = None
    self._last_autosave_path = None
    self._last_autosave_at = None
    self._autosave_timer = QTimer(self)
    try:
        self._autosave_interval_ms = max(
            30_000,
            int(os.environ.get("TIGERCAPTURE_AUTOSAVE_INTERVAL_MS", "120000")),
        )
    except Exception:
        self._autosave_interval_ms = 120_000
    self._autosave_timer.setInterval(self._autosave_interval_ms)
    self._autosave_timer.timeout.connect(self._do_autosave)
    self._autosave_timer.start()
    try:
        from app.crash_reporter import record_action, set_emergency_autosave_callback

        set_emergency_autosave_callback(lambda reason: self._do_autosave(reason))
        record_action("editor.open", autosave_interval_ms=self._autosave_interval_ms)
    except Exception:
        pass


def init_window_shell(self) -> None:
    self.setObjectName("EditorRoot")
    self.setWindowTitle(tr("veditor.title"))
    self.resize(1180, 780)
    self.setStyleSheet(
        VIDEO_EDITOR_EXTRA_QSS
        + MEDIA_POOL_REFERENCE_QSS
        + editor_scrollbar_qss()
    )
    self.setAcceptDrops(True)


def init_player_and_audio(self) -> None:
    self._player = ProjectPlayer(self)
    trace_video_editor_init("video_editor.init.player_created")
    self._player.frame_ready.connect(self._on_frame_ready)
    self._player.gpu_frame_ready.connect(self._on_gpu_frame_ready)
    self._player.position_changed.connect(self._on_position_changed)
    self._player.duration_changed.connect(self._on_duration_changed)
    self._player.state_changed.connect(self._on_playback_state_changed)
    self._player.error_occurred.connect(self._on_player_error)
    self._audio_mixer = AudioMixer(self)
    self._player.state_changed.connect(self._audio_mixer.on_state_changed)
    self._player.position_changed.connect(self._audio_mixer.on_position_changed)


def init_actor_state(self) -> None:
    self._spine_editor = None
    self._live2d_editor = None
    self._spine_actor_tracks = []
    self._actor_lane_rows = []
    self._next_actor_id = 1
    self._live2d_actor_tracks = []
    self._live2d_lane_rows = []
    self._next_live2d_id = 1
    self._ar_pbr_tracks = []
    self._ar_pbr_lane_rows = []
    self._next_ar_pbr_id = 1
    self._selected_ar_pbr_track_id = ""
    self._ar_pbr_gizmo_visible_track_id = ""
    self._ar_pbr_gizmo_drag = None
    self._ar_pbr_depth_cue_restore = {}
    self._mmd_tracks = []
    self._mmd_lane_rows = []
    self._next_mmd_id = 1
    self._selected_mmd_track_id = ""


def init_project_settings(self) -> None:
    try:
        self._project_settings = {
            "starter_template_id": "screen-recording-demo",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "fps": 60.0,
            "screenstudio_simple_mode": False,
            "screenstudio_simple_mode_ui": {"layout": "standard"},
            "screenstudio_advanced_visible": True,
        }
    except Exception:
        self._project_settings = {}


def build_editor_ui_and_finish_startup(self, source_path: Path | None) -> None:
    trace_video_editor_init("video_editor.init.build_ui_begin")
    self._build_ui()
    try:
        from app.startup_trace import cleanup_hidden_qt_orphan_windows, log_startup_trace

        log_startup_trace("video_editor.init.build_ui_done")
        cleanup_hidden_qt_orphan_windows(self, "video_editor.init.build_ui_done")
    except Exception:
        pass
    self._refresh_preview_qimage_mode()
    if source_path is not None:
        self._add_track_with_source(Path(source_path))
    from app.history import capture_editor_snapshot

    self._history.push(capture_editor_snapshot(self), label="initial")
    try:
        from app.preview_acceleration import schedule_editor_runtime_prewarm

        schedule_editor_runtime_prewarm(
            delay_ms=1100 if _live2d_startup_warmup_enabled() else 1400,
            status_callback=lambda msg: self._flash_status(msg),
        )
    except Exception:
        pass
    trace_video_editor_init("video_editor.init.done")
