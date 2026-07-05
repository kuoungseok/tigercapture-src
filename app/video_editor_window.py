from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

from app.editor_observability import (
    append_ux_event as _append_ux_event,
    live2d_startup_warmup_enabled as _live2d_startup_warmup_enabled,
    probe_track_hdr_info as _probe_track_hdr_info,
)
from app.timeline_model import (
    build_zoom_ffmpeg_filter,
)
from app.timeline_ruler import (
    DEFAULT_PX_PER_SEC,
    MAX_PX_PER_SEC,
    MIN_PX_PER_SEC,
)
from app.timeline_track_row import (
    MIN_TRACK_WIDTH,
    TRACK_HEIGHT,
    TRACK_V_PADDING,
    TrackRow,
)
from app.video_editor_audio_widgets import AudioMixerPanel, AudioTrackRow, SoundEditorWindow
from app.video_editor_media_proxy import (
    _delete_proxy_for_source,
    _proxy_path_for,
    _proxy_state_for,
)
from app.video_editor_nested_sequence import cut_clip_window
from app.video_editor_popouts import PreviewPopoutWindow, VTuberBroadcastStudioWindow
from app.video_editor_preset_browser_widgets import (
    PresetPreviewSwatch as _PresetPreviewSwatch,
)
from app.video_editor_preset_cards import (
    EFFECT_PRESET_MIME_TYPE,
    EffectPresetCard,
    WorkflowPresetCard,
    WorkflowPresetPanel,
    _StudioPresetTile,
    _preset_query_score,
    _render_preset_ab_application_preview,
    _render_preset_application_frame_preview,
)
from app.video_editor_thumbnailing import probe_video_duration_ms
from app.video_editor_window_core import VideoEditorWindow
from app.video_editor_window_widgets import _AnimatedTimelineToolButton
from app.video_track_legacy import VideoTrack

SPEED_CHOICES = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0]

__all__ = [
    "AudioTrackRow",
    "AudioMixerPanel",
    "DEFAULT_PX_PER_SEC",
    "EFFECT_PRESET_MIME_TYPE",
    "EffectPresetCard",
    "MAX_PX_PER_SEC",
    "MIN_PX_PER_SEC",
    "MIN_TRACK_WIDTH",
    "PreviewPopoutWindow",
    "QApplication",
    "QFileDialog",
    "QImage",
    "QMessageBox",
    "QPixmap",
    "QProgressDialog",
    "SPEED_CHOICES",
    "SoundEditorWindow",
    "TRACK_HEIGHT",
    "TRACK_V_PADDING",
    "TrackRow",
    "VTuberBroadcastStudioWindow",
    "VideoEditorWindow",
    "VideoTrack",
    "WorkflowPresetCard",
    "WorkflowPresetPanel",
    "_AnimatedTimelineToolButton",
    "_PresetPreviewSwatch",
    "_StudioPresetTile",
    "_append_ux_event",
    "_delete_proxy_for_source",
    "_live2d_startup_warmup_enabled",
    "_preset_query_score",
    "_probe_track_hdr_info",
    "_proxy_path_for",
    "_proxy_state_for",
    "_render_preset_ab_application_preview",
    "_render_preset_application_frame_preview",
    "build_zoom_ffmpeg_filter",
    "cut_clip_window",
    "probe_video_duration_ms",
]


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _format_speed(p: float) -> str:
    if abs(p - round(p)) < 1e-3:
        return f"{int(round(p))}x"
    return f"{p:g}x"


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
