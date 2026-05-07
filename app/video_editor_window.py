from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMimeData, QObject, QPoint, QRect, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.audio_tracks import (
    AUDIO_EXTS,
    VIDEO_EXTS,
    AudioClip,
    AudioMixer,
    AudioTrack,
    WaveformExtractor,
    is_audio_path,
    is_video_path,
    probe_audio_duration_ms,
)
from app.drawing import (
    DrawingCanvas,
    SpeechBubble,
    SpeechBubbleItem,
    Stroke,
    compose_pil_bubbles,
)
from app.typography import (
    TEXT_CLIP_MIME,
    AnimationConfig,
    TextClip,
    TextStyle,
    TextTrack,
)
from app.i18n import tr
from app.project_player import ProjectPlayer
from app.simple_video_player import PlayerState
from app.workbench_panel import WorkbenchPanel
from app.media_pool import MediaPool
from app.pg_scopes import ScopesPanelPG
from app.subtitles import Subtitle, SubtitleLaneRow, SubtitlePanel
from app.video_exporter import (
    VideoExportThread,
    build_segments,
    build_segments_from_clips,
)


SPEED_CHOICES = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0]
THUMB_H = 48                  # thumbnail extract/display height in pixels
THUMB_SECONDS_PER_TILE = 4.0  # target seconds between thumbnails
MIN_THUMBS = 10
MAX_THUMBS = 60
TRACK_HEIGHT = 70
TRACK_V_PADDING = 8
DEFAULT_PX_PER_SEC = 40.0
MIN_PX_PER_SEC = 4.0
MAX_PX_PER_SEC = 300.0
MIN_TRACK_WIDTH = 300

# MIME types moved to app.effect_cards. Re-imported below at the
# unified card-import block so the constants stay accessible at the
# editor-module level for TrackRow's drop handlers without churning
# any callers.
from app.effect_cards import (  # noqa: E402, F401
    FADE_MIME_TYPE,
    SPEED_MIME_TYPE,
    ZOOM_MIME_TYPE,
    FadeCard,
    SpeedCard,
    TypographyCard,
    ZoomCard,
)

# MIME type for DaVinci-style clip-boundary transition cards.
# Distinct from FADE_MIME_TYPE (which creates FadeSegment actors on
# the timeline). This one sets clip.transition_out_type / _ms on a
# specific clip's right edge via drag-drop.
TRANSITION_MIME_TYPE = "application/x-tigercapture-clip-transition"

# MIME type for title/typography animation preset cards dragged onto tracks.
TITLE_PRESET_MIME_TYPE = "application/x-tigercapture-title-preset"

# ---------------------------------------------------------------------------
#  Title animation presets — drag-and-drop source cards for the left dock.
# ---------------------------------------------------------------------------

TITLE_PRESETS = [
    {
        "id": "lower_third",
        "name": "하단 자막",
        "icon": "▬",
        "text": "하단 자막 텍스트",
        "font_size": 42,
        "color": "#ffffff",
        "bg_color": "#1a1a1aaa",
        "x_norm": 0.05,
        "y_norm": 0.82,
        "preset_id_in": "slide-right-in",
        "preset_id_out": "slide-left-out",
        "duration_ms": 3000,
        "desc": "하단 슬라이드 인",
    },
    {
        "id": "main_title",
        "name": "메인 타이틀",
        "icon": "T",
        "text": "메인 타이틀",
        "font_size": 72,
        "color": "#ffffff",
        "bg_color": "",
        "x_norm": 0.5,
        "y_norm": 0.45,
        "preset_id_in": "fade-in",
        "preset_id_out": "fade-out",
        "duration_ms": 4000,
        "desc": "중앙 페이드",
    },
    {
        "id": "subtitle",
        "name": "자막",
        "icon": "—",
        "text": "자막 텍스트",
        "font_size": 36,
        "color": "#fffde7",
        "bg_color": "#00000088",
        "x_norm": 0.5,
        "y_norm": 0.88,
        "preset_id_in": "fade-in",
        "preset_id_out": "fade-out",
        "duration_ms": 2500,
        "desc": "중앙 하단",
    },
    {
        "id": "kinetic",
        "name": "키네틱",
        "icon": "K",
        "text": "키네틱 텍스트",
        "font_size": 56,
        "color": "#ffeb3b",
        "bg_color": "",
        "x_norm": 0.5,
        "y_norm": 0.5,
        "preset_id_in": "bounce-in",
        "preset_id_out": "zoom-out",
        "duration_ms": 3000,
        "desc": "바운스 인",
    },
    {
        "id": "corner_tag",
        "name": "코너 태그",
        "icon": "◼",
        "text": "태그",
        "font_size": 28,
        "color": "#ffffff",
        "bg_color": "#e53935cc",
        "x_norm": 0.88,
        "y_norm": 0.05,
        "preset_id_in": "pop-in",
        "preset_id_out": "pop-out",
        "duration_ms": 2000,
        "desc": "우상단 팝",
    },
    {
        "id": "typewriter",
        "name": "타이프라이터",
        "icon": "|_",
        "text": "타이프라이터 효과",
        "font_size": 48,
        "color": "#e8f5e9",
        "bg_color": "",
        "x_norm": 0.5,
        "y_norm": 0.5,
        "preset_id_in": "typewriter-in",
        "preset_id_out": "fade-out",
        "duration_ms": 4000,
        "desc": "타이핑 효과",
    },
]


from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_BLUE_HOVER,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_ORANGE,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_BG_L1,
    COLOR_BG_L2,
    COLOR_BG_L3,
    COLOR_BG_L4,
    COLOR_BG_L5,
    COLOR_BG_L6,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_FOCUS,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)


VIDEO_EDITOR_EXTRA_QSS = f"""
/* ── Global font override for editor chrome ───────────────────────────── */
* {{
    font-family: "Segoe UI Variable", "Segoe UI", "Pretendard", "Malgun Gothic",
                 system-ui, -apple-system, sans-serif;
    letter-spacing: 0.1px;
}}

QWidget#EditorRoot {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}

/* ── Left / Right dock columns ─────────────────────────────────────────── */
QWidget#LeftDockColumn, QWidget#RightDockColumn {{
    background-color: #1a1a22;
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

/* ── ToolButton — compact, professional toolbar look ───────────────────── */
QPushButton#ToolButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 5px 9px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 500;
}}
QPushButton#ToolButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: #4a4a52;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ToolButton:pressed {{
    background-color: {COLOR_BG_L4};
    border-color: #3a3a42;
}}
QPushButton#ToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
    background-color: {COLOR_BG_L3};
}}
QPushButton#ToolButton:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border-color: {COLOR_ACCENT_BLUE};
}}

/* ── PrimaryToolButton ─────────────────────────────────────────────────── */
QPushButton#PrimaryToolButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border: 1px solid {COLOR_ACCENT_BLUE};
    border-radius: 6px;
    padding: 5px 16px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
    border-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
    border-color: {COLOR_ACCENT_PRESSED};
}}

/* ── SpeedActive ────────────────────────────────────────────────────────── */
QPushButton#SpeedActive {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_ACCENT_BLUE};
    border-radius: 6px;
    padding: 5px 11px;
    font-weight: 700;
}}

/* ── Section headers — all variants share height / font ──────────────────
   Accent bar changes per panel identity (preview / timeline / subtitles).
   Height is held at 28px (line-height + padding) for vertical rhythm.    */
QLabel[sectionHeader="true"] {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 0px 12px;
    min-height: 28px;
    max-height: 28px;
    background-color: {COLOR_BG_L4};
    border-left: 3px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="preview"] {{
    border-left: 3px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="timeline"] {{
    border-left: 3px solid {COLOR_ACCENT_ORANGE};
}}
QLabel[sectionHeader="true"][accent="subtitles"] {{
    border-left: 3px solid {COLOR_ACCENT_GREEN};
}}

/* ── Preview section header (custom widget wrapping label + pop-out btn) */
QWidget#PreviewSectionHeader {{
    background-color: {COLOR_BG_L4};
    border-left: 3px solid {COLOR_ACCENT_BLUE};
    min-height: 28px;
    max-height: 28px;
}}
QLabel#PreviewSectionTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 0px 12px;
    min-height: 28px;
    background: transparent;
}}
QPushButton#PreviewPopoutIcon {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 15px;
    padding: 0;
}}
QPushButton#PreviewPopoutIcon:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_DEFAULT};
}}
QPushButton#PreviewPopoutIcon:pressed {{
    background-color: {COLOR_BG_L2};
}}
QPushButton#PreviewPopoutIcon[popped="true"] {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT_BLUE};
}}

/* ── Preview + play area ────────────────────────────────────────────────── */
QWidget#PreviewHost {{
    background-color: {COLOR_BG_L1};
    border: none;
}}

QWidget#PlayBar {{
    background-color: {COLOR_BG_L4};
    border-top: 2px solid {COLOR_BG_L1};
    border-bottom: 2px solid {COLOR_BG_L1};
}}

QWidget#ControlsBar {{
    background-color: {COLOR_BG_L3};
    border-top: 2px solid {COLOR_BG_L1};
}}

/* ── Mono labels (time / zoom readouts) ──────────────────────────────────
   JetBrains Mono → Cascadia Code → Consolas — consistent digit width.   */
QLabel#TimeLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0px;
}}
QLabel#SpeedLabel {{
    color: {COLOR_ACCENT_BLUE};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-weight: 700;
    letter-spacing: 0px;
}}
QLabel#ZoomLabel {{
    color: {COLOR_TEXT_TERTIARY};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    letter-spacing: 0px;
}}

/* ── Play button ─────────────────────────────────────────────────────────*/
QPushButton#PlayButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 19px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#PlayButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}

/* ── Scroll areas + scrollbars ─────────────────────────────────────────── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border: none;
    margin: 1px;
}}
QScrollBar::handle:horizontal {{
    background: #38383e;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #48484e;
}}
QScrollBar::handle:horizontal:pressed {{
    background: {COLOR_ACCENT_BLUE};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
    margin: 1px;
}}
QScrollBar::handle:vertical {{
    background: #38383e;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #48484e;
}}
QScrollBar::handle:vertical:pressed {{
    background: {COLOR_ACCENT_BLUE};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

/* ── Separator lines ─────────────────────────────────────────────────────
   QFrame with HLine(4)/VLine(5) shape used as dividers.                  */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: #2a2a38;
    max-height: 1px;
    border: none;
}}

/* ── List widget ─────────────────────────────────────────────────────────*/
QListWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 4px;
    alternate-background-color: {COLOR_BG_L3};
    outline: none;
}}
QListWidget::item {{
    padding: 4px 8px;
    border-radius: 3px;
}}
QListWidget::item:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}
QListWidget::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border-left: 2px solid {COLOR_ACCENT_BLUE_HOVER};
}}
"""


# Phase 1: SpeedSegment / CutSegment / FadeSegment / ZoomActor and
# the zoom helper functions live in app.timeline_model now. They are
# re-exported below so existing imports
# (from app.video_editor_window import FadeSegment, find_active_zoom, ...)
# keep working until call sites migrate to timeline_model directly.
from app.timeline_model import (  # noqa: E402, F401
    CutSegment,
    FadeSegment,
    SpeedSegment,
    ZoomActor,
    _map_source_to_output_seconds,
    _zoom_ease,
    build_zoom_ffmpeg_filter,
    find_active_zoom,
    zoom_window_at,
)


from app.timeline_model import NodeGraph as _NodeGraph
from app.timeline_model import build_legacy_clips_view as _build_legacy_clips_view


def _new_node_graph():
    """Lazy default factory for the per-track ``NodeGraph`` — wraps a
    fresh ``ColorGrade`` in a ``ColorNode``. Phase 2 introduces this
    indirection so Phase 1.5b/c can move the graph from track-level to
    clip-level without breaking the 16 sites that read ``color_grade``."""
    return _NodeGraph.default()


# ---------------------------------------------------------------------------
#  3D LUT support (.cube format)
# ---------------------------------------------------------------------------

def parse_cube_lut(path: str):
    """Parse an Adobe .cube 3D LUT file.

    Returns a numpy array of shape ``(size, size, size, 3)`` float32 on
    success, or ``None`` if the file is not a valid 3D LUT."""
    import numpy as np
    size = None
    data = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("LUT_3D_SIZE"):
                try:
                    size = int(line.split()[-1])
                except (ValueError, IndexError):
                    pass
            elif (
                line
                and not line.startswith("#")
                and not line.startswith("TITLE")
                and not line.startswith("DOMAIN")
                and not line.startswith("LUT")
            ):
                parts = line.split()
                if len(parts) == 3:
                    try:
                        data.append([float(p) for p in parts])
                    except ValueError:
                        pass
    if size is None or len(data) < size ** 3:
        return None
    arr = np.array(data[: size ** 3], dtype=np.float32).reshape(size, size, size, 3)
    return arr


def apply_lut(rgb_u8, lut, strength: float = 1.0):
    """Apply a 3D LUT to an RGB uint8 image using trilinear interpolation.

    Parameters
    ----------
    rgb_u8 : np.ndarray, shape (H, W, 3), dtype uint8
    lut    : np.ndarray, shape (S, S, S, 3), dtype float32  — values 0..1
    strength : float 0..1 — blend factor between original and graded

    Returns uint8 (H, W, 3) array.
    """
    import numpy as np
    size = lut.shape[0]
    scale = (size - 1) / 255.0
    r = rgb_u8[:, :, 0].astype(np.float32) * scale
    g = rgb_u8[:, :, 1].astype(np.float32) * scale
    b = rgb_u8[:, :, 2].astype(np.float32) * scale
    r0 = np.clip(r.astype(np.int32), 0, size - 2)
    g0 = np.clip(g.astype(np.int32), 0, size - 2)
    b0 = np.clip(b.astype(np.int32), 0, size - 2)
    rf = r - r0
    gf = g - g0
    bf = b - b0
    c000 = lut[b0, g0, r0]
    c001 = lut[b0, g0, r0 + 1]
    c010 = lut[b0, g0 + 1, r0]
    c011 = lut[b0, g0 + 1, r0 + 1]
    c100 = lut[b0 + 1, g0, r0]
    c101 = lut[b0 + 1, g0, r0 + 1]
    c110 = lut[b0 + 1, g0 + 1, r0]
    c111 = lut[b0 + 1, g0 + 1, r0 + 1]
    rf = rf[:, :, np.newaxis]
    gf = gf[:, :, np.newaxis]
    bf = bf[:, :, np.newaxis]
    result = (
        c000 * (1 - rf) * (1 - gf) * (1 - bf)
        + c001 * rf * (1 - gf) * (1 - bf)
        + c010 * (1 - rf) * gf * (1 - bf)
        + c011 * rf * gf * (1 - bf)
        + c100 * (1 - rf) * (1 - gf) * bf
        + c101 * rf * (1 - gf) * bf
        + c110 * (1 - rf) * gf * bf
        + c111 * rf * gf * bf
    )
    result = np.clip(result * 255, 0, 255).astype(np.uint8)
    if strength < 1.0:
        result = (rgb_u8 * (1.0 - strength) + result * strength).astype(np.uint8)
    return result


def _ensure_video_clips(track, *, force: bool = False) -> None:
    """First-time sync of ``track.clips`` from the legacy fields. By
    default this is *idempotent* — once a track has clips, the user's
    in-place edits (Step B drags, Step C splits) are preserved.

    Callers:
    - Video-track load (after duration is known)  — ``force=False``
    - ``ProjectPlayer.refresh_tracks`` defensive fallback             — ``force=False``
    - Reset / project reload paths that explicitly want a rebuild     — ``force=True``

    Phase 1.5d Step C (cut-as-split) mutates ``track.clips`` directly
    instead of going through this helper, so user-positioned clips
    survive subsequent track refreshes."""
    if track.clips and not force:
        # Already populated; just ensure the explicit flag is set so
        # ProjectPlayer.refresh_tracks doesn't fall back to _build_clips_view.
        track.clips_explicit = True
        return
    track.clips = _build_legacy_clips_view(track)
    # Mark as initialised so ProjectPlayer knows the empty list is intentional
    # (e.g. source has no frames) rather than "not yet set up".
    track.clips_explicit = True


def cut_clip_window(
    clips: list, cut_start_source_ms: int, cut_end_source_ms: int,
    track_offset_ms: int,
):
    """Pure clip-list mutation for Phase 1.5d Step C: drop the source
    window ``[cut_start_source_ms, cut_end_source_ms)`` from every
    clip in ``clips`` (interpreted as track-local source ms — the same
    coordinate system ``track.selection_*_ms`` uses today). Each clip
    contributes 0 / 1 / 2 surviving pieces. Returns a new list sorted
    by ``timeline_in_ms``; does not mutate the input.

    Extracted so the editor's ``_cut_selection_in_track`` is a thin
    wrapper that handles only the GUI side (selection state, repaint,
    player refresh) and the clip math is unit-testable headless."""
    from app.timeline_model import VideoClip
    s = int(cut_start_source_ms)
    e = int(cut_end_source_ms)
    out: list = []
    for clip in clips:
        cs = clip.source_in_ms
        ce = clip.effective_source_out_ms
        if ce <= s or cs >= e:
            out.append(clip)
            continue
        if cs < s:
            left_end = min(ce, s)
            out.append(VideoClip(
                id=clip.id,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=clip.timeline_in_ms,
                source_in_ms=cs,
                source_out_ms=left_end,
                speed_segments=list(clip.speed_segments),
                fades=[f for f in clip.fades if f.start_ms < left_end],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.start_ms < left_end
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "start_ms", 0) < left_end
                ],
                node_graph=clip.node_graph,
            ))
        if ce > e:
            right_start = max(cs, e)
            out.append(VideoClip(
                id=clip.id + 1,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=int(track_offset_ms) + right_start,
                source_in_ms=right_start,
                source_out_ms=ce,
                speed_segments=list(clip.speed_segments),
                fades=[f for f in clip.fades if f.end_ms > right_start],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.end_ms > right_start
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "end_ms", 0) > right_start
                ],
                node_graph=clip.node_graph,
            ))
    out.sort(key=lambda c: c.timeline_in_ms)
    return out


@dataclass
class VideoTrack:
    id: int
    source_path: Path | None = None
    # Proxy support: stores the original source path so _toggle_proxy_mode
    # can restore it after swapping in a proxy. None until a proxy is applied.
    _original_source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0  # where this clip starts on the project timeline
    speed_segments: list[SpeedSegment] = field(default_factory=list)
    cuts: list[CutSegment] = field(default_factory=list)
    fades: list[FadeSegment] = field(default_factory=list)
    thumbnails: list[QPixmap] = field(default_factory=list)
    selection_start_ms: int = -1
    selection_end_ms: int = -1
    # Typography actors placed directly on this track's strip. They
    # overlay the video at their time windows; each actor carries its
    # own text, style, and (future) animation config. Times are track-
    # local source ms (the TrackRow paints them in project time via the
    # offset + speed mapping the row already knows).
    typography_actors: list = field(default_factory=list)  # list[TextClip]
    # Per-track effects graph. Phase 2 only owns the colour node; Phase
    # 1.5b will move this onto each VideoClip so colour grades become
    # per-clip. The ``color_grade`` property below preserves backwards
    # compatibility with the 16 sites that still read / write a flat
    # ``track.color_grade``.
    node_graph: object = field(default_factory=_new_node_graph)
    # Zoom-in actors (multiple per track allowed; should not overlap).
    zoom_actors: list[ZoomActor] = field(default_factory=list)

    # Phase 1.5d: stored clip-list field (was a property in Phase
    # 1.5c). Phase 1.5d Step A keeps this in lockstep with the legacy
    # ``source_path`` / ``duration_ms`` / ``cuts`` / ``offset_ms``
    # fields via ``_ensure_video_clips`` — so reading ``track.clips``
    # is identical to today's clip view and writers (cut handler,
    # video-load entry points) call the helper to refresh. Step B
    # will start using this as a *real* per-clip store, at which
    # point the rebuild on cut goes away.
    clips: list = field(default_factory=list)  # list[VideoClip]
    # Set to True once track.clips has been initialised (via
    # ``_ensure_video_clips``) or explicitly mutated by the user (blade,
    # ripple-delete, cut, project-load).  ``ProjectPlayer.refresh_tracks``
    # uses this to skip the ``_build_clips_view`` fallback so that an
    # intentionally-empty clip list (all clips deleted) is NOT
    # silently rebuilt from the source file.
    clips_explicit: bool = False
    # Phase 2D — saved snapshot of the workbench's NodeGraphScene so
    # selecting back to this track restores the same graph layout.
    # ``None`` until the user touches the node graph for the first
    # time. Format: see app/workbench/node_graph/scene.py::to_data.
    node_graph_view_data: dict | None = None
    # PIP compositing fields — mirror timeline_model.VideoTrack so the
    # legacy track path and the new path share the same attribute names.
    pip_enabled: bool = False
    pip_x: float = 0.5        # centre x, normalised 0-1
    pip_y: float = 0.5        # centre y, normalised 0-1
    pip_scale: float = 0.3    # scale factor (fraction of base frame width)
    pip_opacity: float = 1.0  # opacity 0-1
    pip_keyframes: list = field(default_factory=list)
    # Each keyframe dict: {"ms": int, "x": float, "y": float, "scale": float, "opacity": float}

    @property
    def display_name(self) -> str:
        if self.source_path is None:
            # Multi-source track: derive name from clips.
            clip_paths = {
                c.source_path for c in self.clips
                if getattr(c, "source_path", None) is not None
            }
            if not clip_paths:
                return tr("veditor.track.empty")
            if len(clip_paths) == 1:
                return next(iter(clip_paths)).name
            return f"{len(self.clips)} clips"
        return self.source_path.name

    # ---- Phase 2 backwards-compat ----

    @property
    def color_grade(self):
        """Delegate to ``node_graph.color.grade``. Existing callers
        (project_player, video_exporter, the colour panel handlers)
        keep using ``track.color_grade`` and don't need to know about
        the wrapping ``NodeGraph``."""
        ng = self.node_graph
        if ng is None:
            return None
        return getattr(ng, "color", None) and ng.color.grade

    @color_grade.setter
    def color_grade(self, value) -> None:
        # ``_active_color_grade`` re-assigns when it finds None; route
        # the new ColorGrade into the existing node graph so the rest
        # of the structure (future LUT / blur nodes, when they come)
        # isn't lost.
        from app.timeline_model import ColorNode
        ng = self.node_graph
        if ng is None or getattr(ng, "color", None) is None:
            self.node_graph = _NodeGraph(color=ColorNode(grade=value))
        else:
            ng.color.grade = value


def probe_video_duration_ms(path: Path) -> int:
    """Return duration of the video at ``path`` in milliseconds using cv2.
    Returns 0 if the file cannot be opened or has no duration information."""
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return 0
        fps = float(cap.get(_cv2.CAP_PROP_FPS) or 0)
        total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        if fps > 0 and total > 0:
            return int(total / fps * 1000)
    except Exception:
        pass
    return 0


class ThumbnailExtractor(QThread):
    """Extracts evenly-spaced thumbnail frames for a track's video using
    OpenCV. The count is chosen dynamically from video duration so that one
    thumbnail roughly represents ``THUMB_SECONDS_PER_TILE`` of footage,
    clamped to [MIN_THUMBS, MAX_THUMBS].

    When ``clip_id`` is given the extractor is operating in per-clip mode:
    ``clip_thumb_ready`` and ``clip_count_determined`` are emitted instead
    of (or in addition to) the track-level signals, letting the editor store
    thumbnails on the individual ``VideoClip`` rather than the track.
    """

    count_determined = Signal(int, int)        # track_id, count
    thumb_ready = Signal(int, int, QPixmap)    # track_id, index, pixmap
    finished_extracting = Signal(int)          # track_id
    # Per-clip variants (only emitted when clip_id is set)
    clip_count_determined = Signal(int, int, int)       # track_id, clip_id, count
    clip_thumb_ready = Signal(int, int, int, QPixmap)   # track_id, clip_id, idx, pixmap

    def __init__(
        self,
        track_id: int,
        path: Path,
        thumb_height: int,
        clip_id: int = -1,
    ) -> None:
        super().__init__()
        self._track_id = track_id
        self._path = Path(path)
        self._thumb_h = max(16, int(thumb_height))
        self._stop = False
        self._clip_id = clip_id

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        cap = None
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(str(self._path))
            if not cap.isOpened():
                return
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total_frames <= 0:
                return
            duration_s = total_frames / fps if fps > 0 else 0
            count = max(
                MIN_THUMBS,
                min(MAX_THUMBS, int(round(duration_s / THUMB_SECONDS_PER_TILE))),
            )
            self.count_determined.emit(self._track_id, count)
            if self._clip_id >= 0:
                self.clip_count_determined.emit(self._track_id, self._clip_id, count)

            for i in range(count):
                if self._stop:
                    return
                frame_idx = min(
                    total_frames - 1,
                    int((i + 0.5) * total_frames / count),
                )
                # Seek to the nearest keyframe and read — O(1) after cap is open
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, bgr = cap.read()
                if not ret or bgr is None:
                    continue

                h, w = bgr.shape[:2]
                if h != self._thumb_h:
                    new_w = max(1, int(round(w * self._thumb_h / h)))
                    bgr = cv2.resize(
                        bgr, (new_w, self._thumb_h), interpolation=cv2.INTER_AREA
                    )
                    h, w = bgr.shape[:2]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                contig = np.ascontiguousarray(rgb)
                qimg = QImage(
                    contig.data, w, h, contig.strides[0], QImage.Format.Format_RGB888
                ).copy()
                pixmap = QPixmap.fromImage(qimg)
                self.thumb_ready.emit(self._track_id, i, pixmap)
                if self._clip_id >= 0:
                    self.clip_thumb_ready.emit(self._track_id, self._clip_id, i, pixmap)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            self.finished_extracting.emit(self._track_id)


# ---------------------------------------------------------------------------
# Proxy generation helpers
# ---------------------------------------------------------------------------

def _generate_proxy(path: Path) -> "Path | None":
    """Generate a 540p proxy for the given video. Returns proxy path or None on failure."""
    import sys
    import subprocess
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        return None
    proxy_dir = path.parent / "proxies"
    try:
        proxy_dir.mkdir(exist_ok=True)
    except Exception:
        return None
    proxy_path = proxy_dir / (path.stem + "_proxy.mp4")
    if proxy_path.exists():
        return proxy_path  # already generated
    cmd = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
        "-vf", "scale=-2:540",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-y", str(proxy_path),
    ]
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            cmd, capture_output=True, creationflags=creationflags
        )
        return proxy_path if result.returncode == 0 else None
    except Exception:
        return None


def _is_high_resolution(path: Path) -> bool:
    """Return True if the video is high-resolution (>1920x1080 or >500 MB)."""
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 500:
            return True
    except Exception:
        pass
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if cap.isOpened():
            w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if w > 1920 or h > 1080:
                return True
    except Exception:
        pass
    return False


def _probe_video_dimensions(path: Path) -> tuple:
    """Return (width, height) of the video, or (0, 0) on failure."""
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if cap.isOpened():
            w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            return (w, h)
    except Exception:
        pass
    return (0, 0)


class ProxyGeneratorThread(QThread):
    """Background thread: generates a 540p proxy for a video file."""

    done = Signal(str, str)    # original_path, proxy_path
    failed = Signal(str, str)  # original_path, reason
    progress = Signal(int)     # 0-100 (coarse; 10 = started, 100 = done)

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        self._path = Path(path)

    def run(self) -> None:
        self.progress.emit(10)
        proxy = _generate_proxy(self._path)
        if proxy is not None:
            self.progress.emit(100)
            self.done.emit(str(self._path), str(proxy))
        else:
            self.failed.emit(str(self._path), "ffmpeg proxy generation failed")


# TimelineRuler moved to app/timeline_ruler.py — re-exported here so
# any caller that imports it from this module keeps working.
from app.timeline_ruler import TimelineRuler  # noqa: E402, F401


class TrackRow(QWidget):
    """Single horizontal track with label row + timeline row."""

    clicked = Signal(int)  # track_id
    position_requested = Signal(int, int)  # track_id, ms
    selection_changed = Signal(int, int, int)  # track_id, start, end
    context_menu = Signal(int, QPoint)  # track_id, global_pos

    MARGIN = 10
    # Slim header strip — paints the active dot + track name above the
    # timeline body. Trimmed from 18 → 14 to narrow the visual gap
    # between the subtitle lane and the first track (users were trying
    # to drop clips into the header area and missing).
    LABEL_H = 14
    TIMELINE_H = TRACK_HEIGHT
    FADE_EDGE_GRAB_PX = 6  # resize handle hit area in pixels
    TYPO_EDGE_GRAB_PX = 8
    TYPO_CHIP_H = 22             # height of the typography chip strip
    ZOOM_CHIP_H = 18             # height of the zoom actor strip
    ZOOM_EDGE_GRAB_PX = 8        # left/right edge zone for resize on zoom actor
    ZOOM_MIN_DURATION_MS = 200   # can't shrink below this
    TYPO_MIN_DURATION_MS = 200
    SPEED_EDGE_GRAB_PX = 8
    SPEED_MIN_DURATION_MS = 200
    CLIP_EDGE_GRAB_PX = 8        # clip trim / roll edit handle hit area
    CLIP_MIN_DURATION_MS = 100   # minimum clip duration after trim

    offset_changed = Signal(int, int)  # track_id, new_offset_ms
    drag_committed = Signal(int)       # track_id — emitted ONLY on mouseRelease
    # Emitted during clip drag so the editor can sync linked audio.
    # Carries (track_id, clip_id, new_timeline_in_ms, delta_ms).
    clip_drag_delta = Signal(int, int, int, int)
    # Option C — clip-level selection. ``shift_held`` lets the
    # editor decide between "replace selection" and "toggle".
    clip_clicked = Signal(int, int, bool)  # track_id, clip_id, shift
    empty_area_clicked = Signal(int)       # track_id — clears selection
    fades_changed = Signal(int)  # track_id — fade segments added / resized
    speed_changed = Signal(int)  # track_id — speed segments added / changed
    media_dropped = Signal(int, object)  # track_id, Path — any media file
    typography_double_clicked = Signal(int, int)    # track_id, clip_id
    typography_context_menu = Signal(int, int, object)   # track_id, clip_id, global pos
    typography_changed = Signal(int)                # track_id — add/move/resize
    typography_actor_selected = Signal(int, int)    # track_id, actor_id (0=deselect)
    zoom_double_clicked = Signal(int, int)          # track_id, zoom_actor_id
    zoom_context_menu = Signal(int, int, object)    # track_id, zoom_actor_id, global pos
    zoom_changed = Signal(int)                      # track_id — add/move/resize
    clip_context_menu = Signal(int, int, object)    # track_id, clip_id, global pos

    def __init__(self, track: VideoTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._position_ms: int = 0  # project time
        self._march_offset: int = 0   # marching-ants selection animation offset
        self._dragging_playhead: bool = False
        self._dragging_offset: bool = False
        self._resizing_fade: FadeSegment | None = None
        self._resize_side: str = ""  # "left" or "right"
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._drag_start_ms: int = 0
        self._drag_start_x: int = 0
        self._drag_start_offset_ms: int = 0
        # Phase 1.5d Step B: which clip the user grabbed and where it
        # started — populated by ``mousePressEvent`` and consumed in
        # ``mouseMoveEvent``. ``_drag_clip_id`` is None when the press
        # didn't land on a clip body.
        self._drag_clip_id: int | None = None
        self._drag_start_clip_in_ms: int = 0
        # Option C: per-row "currently selected" clip IDs, set by
        # the editor via ``set_selected_clip_ids`` so paintEvent can
        # paint the Tiger Orange selection border.
        self._selected_clip_ids: set[int] = set()
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        # Typography-actor drag state
        self._typo_drag_mode: str | None = None
        self._typo_drag_actor_id: int | None = None
        self._typo_drag_anchor_ms: int = 0
        self._typo_drag_orig_start_ms: int = 0
        self._typo_drag_orig_end_ms: int = 0
        # Zoom-actor drag state
        self._zoom_drag_mode: str | None = None
        self._zoom_drag_actor_id: int | None = None
        self._zoom_drag_anchor_ms: int = 0
        self._zoom_drag_orig_start_ms: int = 0
        self._zoom_drag_orig_end_ms: int = 0
        self._zoom_drag_orig_in_ms: int = 0
        self._zoom_drag_orig_out_ms: int = 0
        # Hover tracking for edge-handle highlighting
        self._hover_fade: FadeSegment | None = None
        self._hover_fade_side: str = ""
        self._hover_typo_actor_id: int | None = None
        self._hover_typo_side: str = ""
        self._hover_speed_seg: SpeedSegment | None = None
        self._hover_speed_side: str = ""
        # Speed-segment drag state
        self._speed_drag_mode: str | None = None
        self._speed_drag_seg: SpeedSegment | None = None
        self._speed_drag_anchor_ms: int = 0
        self._speed_drag_orig_start: int = 0
        self._speed_drag_orig_end: int = 0
        # Extra snap targets (ms) passed from the editor — playhead +
        # timeline markers. Updated by VideoEditorWindow whenever the
        # marker list or playhead changes.
        self._extra_snap_targets: list[int] = []
        # Clip edge trim / roll-edit drag state.
        # ``_clip_trim_clip`` is the clip being trimmed (left or right edge).
        # ``_clip_trim_side`` is "left" or "right".
        # ``_clip_trim_orig_src_in/out`` are the original source timestamps.
        # ``_clip_trim_orig_tl_in`` is the original timeline_in_ms.
        # ``_clip_trim_anchor_ms`` is the project-time ms where the drag began.
        # ``_clip_trim_mode`` is "trim_r", "trim_l", "ripple_r", "ripple_l",
        # or "roll" to distinguish the different edit types.
        # ``_clip_trim_roll_right`` is clip B for roll edits.
        self._clip_trim_clip = None       # VideoClip | None
        self._clip_trim_side: str = ""    # "left" or "right"
        self._clip_trim_mode: str = ""    # "trim_r" / "trim_l" / "ripple_r" / "ripple_l" / "roll"
        self._clip_trim_orig_src_in: int = 0
        self._clip_trim_orig_src_out: int = 0
        self._clip_trim_orig_tl_in: int = 0
        self._clip_trim_anchor_ms: int = 0
        self._clip_trim_roll_right = None  # VideoClip | None (roll edit only)
        self._clip_trim_roll_orig_src_in: int = 0
        self._clip_trim_roll_orig_tl_in: int = 0
        # Transition drag-drop state — clip ID that is the current drop
        # target (its right edge highlighted with an orange line while a
        # TransitionCard is dragged over the row).
        self._drop_target_clip_id: int | None = None
        # CapCut-style transition block interaction state.
        self._hovered_transition_clip_id: int | None = None
        self._dragging_transition: bool = False
        self._drag_transition_clip = None   # VideoClip | None
        self._drag_transition_side: str = ""   # "left" or "right"
        self._drag_transition_start_ms: int = 0  # original ms before drag
        self._drag_transition_start_x: int = 0   # mouse x at drag start

        self.setFixedHeight(self.LABEL_H + self.TIMELINE_H + TRACK_V_PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setAcceptDrops(True)
        self._recalc_width()

    def set_selected_clip_ids(self, ids: set[int]) -> None:
        self._selected_clip_ids = set(int(i) for i in ids)
        self.update()

    def set_extra_snap_targets(self, targets: list[int]) -> None:
        """Extra project-ms snap targets (playhead + markers) injected by
        the editor so clip drags also snap to these positions."""
        self._extra_snap_targets = list(targets)

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()

    def _preferred_width(self) -> int:
        """Content-driven width before any stretching. Spans up to the
        rightmost edge of either the legacy ``offset+duration`` or any
        clip on the track — multi-clip drags can push a clip past the
        legacy span, so the row needs to keep up."""
        if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
            return MIN_TRACK_WIDTH
        legacy_end = self.track.offset_ms + self.track.duration_ms
        clip_end = 0
        for c in getattr(self.track, "clips", ()):
            if c.timeline_out_ms > clip_end:
                clip_end = c.timeline_out_ms
        span_ms = max(legacy_end, clip_end)
        w = int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        return max(MIN_TRACK_WIDTH, w)

    def _recalc_width(self) -> None:
        # Set the content-driven minimum; the editor will stretch every row
        # to the widest common width via _update_tracks_host_width.
        self.setFixedWidth(self._preferred_width())
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = ms
        self.update()

    def _track_span_ms(self) -> int:
        """Total occupied span on the project timeline in ms.

        For single-source tracks this equals ``track.offset_ms +
        track.duration_ms``.  For multi-source tracks (``source_path``
        is None, clips carried in ``track.clips``) the legacy
        ``duration_ms`` stays 0, so we derive the span from the clip
        list instead.  Returns 0 when there is no content."""
        legacy_end = self.track.offset_ms + self.track.duration_ms
        clip_end = max(
            (int(c.timeline_out_ms) for c in getattr(self.track, "clips", ())),
            default=0,
        )
        return max(legacy_end, clip_end)

    def _timeline_rect(self) -> QRect:
        """Rect of the WHOLE track strip (clip + gaps) in widget coords.
        Used for hit-testing the strip and clipping thumbnails — the
        actual clip body fill happens per-clip inside ``paintEvent``.

        Always derived from the clip list when clips are present so that
        appended clips (via ``_append_clip_to_track``) are included even
        when ``track.duration_ms`` still reflects only the original source.
        Falls back to the legacy ``offset_ms + duration_ms`` span when
        there are no clips yet."""
        clips = list(getattr(self.track, "clips", ()))
        if clips:
            # Bounding box across ALL clips (single-source or multi-source).
            left_ms = min(int(c.timeline_in_ms) for c in clips)
            right_ms = max(int(c.timeline_out_ms) for c in clips)
            x = int(self.MARGIN + left_ms / 1000.0 * self._px_per_sec)
            w = max(0, int((right_ms - left_ms) / 1000.0 * self._px_per_sec))
        else:
            offset_px = int(self.track.offset_ms / 1000.0 * self._px_per_sec)
            duration_px = int(self.track.duration_ms / 1000.0 * self._px_per_sec)
            x = self.MARGIN + offset_px
            w = max(0, duration_px)
        return QRect(x, self.LABEL_H, w, self.TIMELINE_H)

    def _clip_rect(self, clip) -> QRect:
        """Phase 1.5c: rect of a single clip's body in widget coords.
        Returns an empty rect if the clip has zero / negative width."""
        x1 = self._project_ms_to_x(int(clip.timeline_in_ms))
        x2 = self._project_ms_to_x(int(clip.timeline_out_ms))
        return QRect(x1, self.LABEL_H, max(0, x2 - x1), self.TIMELINE_H)

    def _hit_test_clip(self, pos: QPoint):
        """Phase 1.5d Step B: return the ``VideoClip`` whose body rect
        contains the cursor, or ``None``. Iterates in clip-list order
        — for overlapping clips the first match wins, but the cut /
        split paths keep clips disjoint so this isn't an issue today."""
        for clip in getattr(self.track, "clips", ()):
            if self._clip_rect(clip).contains(pos):
                return clip
        return None

    def _find_clip_by_id(self, clip_id: int):
        for clip in getattr(self.track, "clips", ()):
            if int(clip.id) == int(clip_id):
                return clip
        return None

    def _clip_edge_at(self, pos: "QPoint") -> "tuple | None":
        """Return ``(clip, side, roll_neighbour)`` if the cursor is within
        ``CLIP_EDGE_GRAB_PX`` of a clip's left or right edge inside the
        timeline strip, otherwise ``None``.

        ``roll_neighbour`` is the adjacent clip when the cursor sits exactly
        on the shared boundary of two clips; ``None`` for ordinary trim.
        ``side`` is ``"left"`` or ``"right"`` (relative to the target clip).
        """
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        clips = sorted(
            getattr(self.track, "clips", []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for i, clip in enumerate(clips):
            x1 = self._project_ms_to_x(int(clip.timeline_in_ms))
            x2 = self._project_ms_to_x(int(clip.timeline_out_ms))
            x = pos.x()
            # Right edge hit
            if abs(x - x2) <= self.CLIP_EDGE_GRAB_PX:
                # Check if right neighbour shares this boundary (roll edit)
                roll_right = None
                if i + 1 < len(clips):
                    nxt = clips[i + 1]
                    if abs(int(nxt.timeline_in_ms) - int(clip.timeline_out_ms)) <= 1:
                        roll_right = nxt
                return (clip, "right", roll_right)
            # Left edge hit
            if abs(x - x1) <= self.CLIP_EDGE_GRAB_PX:
                # Check if left neighbour shares this boundary (roll edit)
                roll_left = None
                if i - 1 >= 0:
                    prv = clips[i - 1]
                    if abs(int(clip.timeline_in_ms) - int(prv.timeline_out_ms)) <= 1:
                        roll_left = prv
                return (clip, "left", roll_left)
        return None

    def _project_ms_to_x(self, project_ms: int) -> int:
        """Project-timeline ms → widget x."""
        return int(self.MARGIN + project_ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _ms_to_x(self, ms: int) -> int:
        """Track-local ms → widget x (accounts for offset)."""
        return self._project_ms_to_x(self.track.offset_ms + ms)

    def _x_to_ms(self, x: int) -> int:
        """Widget x → track-local ms (clamped to duration).

        For multi-source tracks (source_path=None, duration_ms=0) the
        effective duration is derived from the clip list so that zoom /
        typography actor drags work correctly even before
        ``ProjectPlayer.refresh_tracks`` has had a chance to back-fill
        ``track.duration_ms``."""
        eff_dur = self.track.duration_ms
        if eff_dur <= 0:
            # Fall back to the clip-list span so multi-source tracks
            # don't return 0 for every x-position.
            eff_dur = max(
                (int(c.timeline_out_ms) for c in getattr(self.track, "clips", ())),
                default=0,
            )
        if eff_dur <= 0:
            return 0
        local = self._x_to_project_ms(x) - self.track.offset_ms
        return max(0, min(eff_dur, local))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Active indicator dot + ▶ icon + track label
        if self._is_active:
            label_color = QColor("#7090d0")   # actual blue (COLOR_ACCENT_BLUE = orange!)
            status_color = QColor("#50c070")  # actual green
        else:
            label_color = QColor(COLOR_TEXT_TERTIARY)
            status_color = QColor(COLOR_TEXT_DISABLED)
        painter.save()
        label_font = painter.font()
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(status_color)
        painter.drawText(
            QRect(self.MARGIN, 0, 14, self.LABEL_H),
            Qt.AlignmentFlag.AlignVCenter,
            "●" if self._is_active else "○",
        )
        label_font.setPixelSize(10)
        label_font.setBold(False)
        painter.setFont(label_font)
        painter.setPen(label_color)
        painter.drawText(
            QRect(self.MARGIN + 16, 0, self.width() - 2 * self.MARGIN - 16, self.LABEL_H),
            Qt.AlignmentFlag.AlignVCenter,
            f"▶  {self.track.display_name}",
        )
        painter.restore()

        rect = self._timeline_rect()

        # Multi-source tracks (source_path=None, clips=[…]) must fall
        # through to the clip-rendering else-branch below.  Only a truly
        # empty slot (no source AND no clips) shows the "no source" placeholder.
        _has_clips = bool(getattr(self.track, "clips", None))
        if self.track.source_path is None and not _has_clips:
            # Empty slot: BRIGHTER diagonal stripes than the host background,
            # with a dashed border — matches the 3-level hierarchy
            # (timeline host = darkest, loaded clip = middle, empty = lightest).
            self._paint_empty_slot_pattern(painter, rect)
            # Large watermark icon — ▶ centred in the empty strip
            painter.save()
            _wm_font = painter.font()
            _wm_font.setPixelSize(min(48, max(24, self.TIMELINE_H - 8)))
            painter.setFont(_wm_font)
            painter.setPen(QColor(180, 180, 220, 45))
            painter.drawText(
                QRect(0, self.LABEL_H, self.width(), self.TIMELINE_H),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "▶  ",
            )
            painter.restore()
            painter.setPen(QColor("#8a8a92"))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter,
                tr("veditor.track.no_source"),
            )
        else:
            # Loaded clip — Phase 1.5c paints each clip's body
            # separately so cut regions naturally show as gaps. For
            # single-clip tracks (the legacy default) this collapses
            # to one rect identical to before; for tracks with cuts
            # the cut overlay below paints over the gap to keep the
            # visual cue users expect.
            #
            # Robustness: if ``track.clips`` is momentarily empty
            # (source loaded, ``_ensure_video_clips`` hasn't run yet,
            # or a paint event slipped between the two), fall back to
            # painting the legacy ``_timeline_rect`` so the row is
            # never blank. Without this, a paint event that fires in
            # the gap leaves the user staring at an empty track row.
            clips_list = list(getattr(self.track, "clips", ()) or ())
            # 1) 80% stripes across full widget width
            full_strip = QRect(0, self.LABEL_H, self.width(), self.TIMELINE_H)
            StripedHost._draw_stripes(
                painter, full_strip,
                StripedHost.BG_80, StripedHost.STRIPE_80,
            )
            # Faint watermark ▶ centred in the full track width
            painter.save()
            _wm_font = painter.font()
            _wm_font.setPixelSize(min(48, max(24, self.TIMELINE_H - 8)))
            painter.setFont(_wm_font)
            painter.setPen(QColor(180, 180, 220, 30))
            painter.drawText(
                QRect(0, self.LABEL_H, self.width(), self.TIMELINE_H),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "▶  ",
            )
            painter.restore()
            # 2) 50% darkness over the clip's timeline extent — always,
            #    regardless of whether per-clip objects are ready.
            #    _timeline_rect() is robust: falls back to duration_ms when
            #    clips list is empty, so the dark area appears on first paint.
            if rect.width() > 0:
                painter.fillRect(rect, QColor("#1b1b22"))
            if not clips_list and rect.width() > 0:
                pen = QPen(QColor("#3e3e4a"))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect.adjusted(0, 0, -1, -1))
            # Render each clip with a 2 px gap on its right edge when
            # another clip starts immediately after — the gap is the
            # visible blade-cut indicator. Without it, two clips that
            # touch at a split point look like one continuous block
            # and users think Blade did nothing.
            sorted_clips = sorted(
                clips_list, key=lambda c: int(c.timeline_in_ms),
            )
            BLADE_GAP_PX = 2
            for i, clip in enumerate(sorted_clips):
                clip_rect = self._clip_rect(clip)
                if clip_rect.width() <= 0:
                    continue
                # Trim the right edge if the next clip butts directly
                # against this one (boundary within 1 ms — split, not
                # a real gap the user authored).
                if i + 1 < len(sorted_clips):
                    nxt = sorted_clips[i + 1]
                    if int(nxt.timeline_in_ms) - int(clip.timeline_out_ms) <= 1:
                        new_w = max(1, clip_rect.width() - BLADE_GAP_PX)
                        clip_rect = QRect(
                            clip_rect.x(), clip_rect.y(),
                            new_w, clip_rect.height(),
                        )
                # Clip body → 50% brightness solid (thumbnails on top)
                # 50% of StripedHost.BG (#373744) = #1b1b22
                painter.fillRect(clip_rect, QColor("#1b1b22"))
                pen = QPen(QColor("#2a2a35"))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(clip_rect.adjusted(0, 0, -1, -1))
                # Selection border moved to the END of paintEvent so
                # thumbnails / actors / blade markers no longer paint
                # over it (was the cause of "I clicked but nothing
                # turned orange" reports).

            # Thumbnails — fixed native aspect, centered on their time
            # position. Clip to the UNION of every clip's rect so any
            # area the user has ripple-deleted goes blank instead of
            # continuing to show stale thumbnails (was the cause of
            # "I deleted the clip but it didn't disappear").
            # Multi-source: some clips may have their own ``clip.thumbnails``
            # list (extracted per-source); fall back to ``track.thumbnails``
            # for clips that don't (legacy single-source path).
            has_any_thumbs = bool(self.track.thumbnails) or any(
                getattr(c, "thumbnails", None) for c in sorted_clips
            )
            if has_any_thumbs and self.track.duration_ms > 0:
                from PySide6.QtGui import QRegion
                track_thumbs = self.track.thumbnails
                n_track = len(track_thumbs)
                track_h = rect.height()
                src_dur = max(1, int(self.track.duration_ms))
                painter.save()
                # Clip thumbnails to the union of every current clip's
                # rect so deleted / dragged-away regions stay blank.
                clip_region = QRegion()
                for c in sorted_clips:
                    cr = self._clip_rect(c)
                    if cr.width() > 0:
                        clip_region = clip_region.united(QRegion(cr))
                if clip_region.isEmpty():
                    painter.setClipRect(rect)
                else:
                    painter.setClipRegion(clip_region)

                # Draw one row of thumbnails PER CLIP, mapped from
                # each clip's source range to its project-time
                # position. Prefer per-clip thumbnails (multi-source);
                # fall back to track-level thumbnails (single-source).
                for clip in sorted_clips:
                    src_in = int(clip.source_in_ms)
                    src_out = int(clip.effective_source_out_ms)
                    ti = int(clip.timeline_in_ms)
                    if src_out <= src_in:
                        continue
                    clip_thumbs = getattr(clip, "thumbnails", None) or []
                    # Use per-clip thumbnails when available (multi-source);
                    # otherwise use track-level thumbnails.
                    if clip_thumbs:
                        thumb_list = clip_thumbs
                        n = len(clip_thumbs)
                        clip_src_dur = max(1, int(
                            getattr(clip, "source_duration_ms", src_dur) or src_dur
                        ))
                    else:
                        thumb_list = track_thumbs
                        n = n_track
                        clip_src_dur = src_dur
                    for i, pm in enumerate(thumb_list):
                        if pm is None or pm.isNull():
                            continue
                        # Source-ms position this thumbnail represents.
                        thumb_src_ms = int((i + 0.5) * clip_src_dur / n)
                        if not (src_in <= thumb_src_ms < src_out):
                            continue
                        if pm.height() > 0:
                            tw = max(1, int(round(pm.width() * track_h / pm.height())))
                        else:
                            tw = 80
                        # Project x = clip's project position +
                        # (source_ms within clip).
                        proj_ms = ti + (thumb_src_ms - src_in)
                        center_x = self._project_ms_to_x(proj_ms)
                        x = center_x - tw // 2
                        painter.drawPixmap(x, rect.top(), tw, track_h, pm)
                painter.restore()
            else:
                painter.setPen(QColor(COLOR_TEXT_TERTIARY))
                painter.drawText(
                    rect, Qt.AlignmentFlag.AlignCenter,
                    tr("veditor.track.loading"),
                )

        # Speed segments overlay
        for seg in self.track.speed_segments:
            x1 = self._ms_to_x(seg.start_ms)
            x2 = self._ms_to_x(seg.end_ms)
            seg_w = max(1, x2 - x1)
            color = self._color_for_speed(seg.speed)
            painter.fillRect(x1, rect.top(), seg_w, rect.height(), color)
            self._draw_speed_label(
                painter, seg.speed, x1, rect.top(), seg_w, rect.height(),
                frame_blend=getattr(seg, "frame_blend", False),
            )
            # Edge trim handles (blue — matches the SpeedCard accent).
            is_hover = self._hover_speed_seg is seg
            is_drag = self._speed_drag_seg is seg
            self._paint_edge_handles(
                painter,
                rect_top=rect.top(),
                rect_h=rect.height(),
                x_left=x1,
                x_right=x2,
                left_hot=(is_hover and self._hover_speed_side == "left")
                    or (is_drag and self._speed_drag_mode == "resize_l"),
                right_hot=(is_hover and self._hover_speed_side == "right")
                    or (is_drag and self._speed_drag_mode == "resize_r"),
                dragging=is_drag,
                base_color=QColor(216, 90, 48, 220),
                accent_color=QColor("#ff7a4a"),
            )

        # Cut segments (dark overlay)
        for cut in self.track.cuts:
            x1 = self._ms_to_x(cut.start_ms)
            x2 = self._ms_to_x(cut.end_ms)
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(),
                QColor(30, 30, 30, 200),
            )
            if x2 - x1 > 24:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(
                    QRect(x1, rect.top(), x2 - x1, rect.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    tr("veditor.cut_label"),
                )

        # Fade segments — orange gradient "actors", resizable via edge drag.
        for fade in self.track.fades:
            self._paint_fade_segment(painter, fade, rect)

        # Typography actors — orange→pink gradient chips at the top of the
        # track strip. Draw AFTER fades so they always read on top.
        for actor in getattr(self.track, "typography_actors", []):
            self._paint_typography_actor(painter, actor, rect)

        # Zoom actors — blue tinted strip with a 🔍 marker. Drawn last so
        # they read on top of fades and speed but below selection / cuts.
        for zactor in getattr(self.track, "zoom_actors", []):
            self._paint_zoom_actor(painter, zactor, rect)

        # Blade-cut markers — drawn AFTER thumbnails / actors so they
        # always read on top. Static white + Tiger Orange line with a
        # small white triangle notch at the top so the cut is obvious
        # even in screenshots. The marching-ants animation remains in
        # _tick_blade_dash + _blade_dash_offset on the editor for
        # future selection-region overlays.
        clips_for_marks = list(getattr(self.track, "clips", ()) or ())
        if len(clips_for_marks) >= 2:
            painter.save()
            sorted_for_marks = sorted(
                clips_for_marks, key=lambda c: int(c.timeline_in_ms),
            )
            from PySide6.QtGui import QPolygon
            top = rect.top()
            bot = rect.bottom()
            for i in range(len(sorted_for_marks) - 1):
                left_clip = sorted_for_marks[i]
                right_clip = sorted_for_marks[i + 1]
                gap_ms = (
                    int(right_clip.timeline_in_ms)
                    - int(left_clip.timeline_out_ms)
                )
                if gap_ms > 1:
                    continue
                cut_x = self._project_ms_to_x(int(left_clip.timeline_out_ms))

                # 3 px wide marker: white outer pixels + Tiger Orange
                # core. High contrast against any thumbnail underneath
                # so the cut is unmistakable.
                painter.fillRect(cut_x - 1, top, 1, bot - top + 1,
                                 QColor(240, 240, 240))
                painter.fillRect(cut_x + 1, top, 1, bot - top + 1,
                                 QColor(240, 240, 240))
                painter.fillRect(cut_x, top, 1, bot - top + 1,
                                 QColor(COLOR_ACCENT_ORANGE))

                # White triangle notch at the very top — static
                # affordance for "this was cut here", complements the
                # vertical line below.
                painter.setBrush(QColor(240, 240, 240))
                painter.setPen(Qt.PenStyle.NoPen)
                notch = QPolygon([
                    QPoint(cut_x - 4, top),
                    QPoint(cut_x + 4, top),
                    QPoint(cut_x, top + 5),
                ])
                painter.drawPolygon(notch)
            painter.restore()

        # CapCut-style transition blocks — drawn after blade markers, before
        # selection borders. Each clip with transition_out_type != "" shows a
        # dark rectangular block centred on the clip boundary, spanning half
        # the transition width into each adjacent clip. The block has:
        #   • semi-transparent dark background (#1a1a2e, alpha 200)
        #   • centred ◇ label with the transition name
        #   • left + right edge handle bars (vertical lines)
        #   • orange border when being dragged
        from PySide6.QtGui import QPolygon as _QPolygonT
        sorted_clips_for_tr = sorted(
            (getattr(self.track, "clips", None) or []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for idx_t, clip in enumerate(sorted_clips_for_tr):
            ttype = getattr(clip, "transition_out_type", "")
            if not ttype:
                continue
            t_ms = max(100, int(getattr(clip, "transition_out_ms", 500)))
            t_rect = self._transition_rect(clip, sorted_clips_for_tr)
            if t_rect is None or t_rect.width() < 4:
                continue
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

            # Background block
            is_dragging = (self._drag_transition_clip is clip and self._dragging_transition)
            bg_color = QColor(26, 26, 46, 200)
            painter.fillRect(t_rect, bg_color)

            # Border — orange when dragging, else subdued blue-grey
            border_pen = QPen(
                QColor(COLOR_ACCENT_ORANGE) if is_dragging else QColor(100, 100, 160, 200),
                2,
            )
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(t_rect.adjusted(1, 1, -1, -1))

            # Centre label — transition type name abbreviation
            _TR_LABELS = {
                "dissolve":   "◇ Cross",
                "fade_black": "◇ Black",
                "fade_white": "◇ White",
                "slide_left": "◇ Slide",
                "wipe_left":  "◇ Wipe",
                "zoom_in":    "◇ ZoomIn",
                "zoom_out":   "◇ ZoomOut",
                "dip_white":  "◇ Dip",
            }
            label_text = _TR_LABELS.get(ttype, f"◇ {ttype}")
            lbl_font = painter.font()
            lbl_font.setPixelSize(9)
            painter.setFont(lbl_font)
            painter.setPen(QColor(200, 200, 220, 220))
            painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, label_text)

            # Left and right edge handle bars (resize affordance)
            handle_w = 4
            handle_color = QColor(160, 160, 220, 200) if not is_dragging else QColor(COLOR_ACCENT_ORANGE)
            painter.fillRect(
                t_rect.left(), t_rect.top(), handle_w, t_rect.height(), handle_color,
            )
            painter.fillRect(
                t_rect.right() - handle_w + 1, t_rect.top(), handle_w, t_rect.height(), handle_color,
            )

            painter.restore()

        # Transition drop-target indicator — bright orange vertical line at
        # the right edge of the target clip during a TransitionCard drag.
        if self._drop_target_clip_id is not None:
            for clip in (getattr(self.track, "clips", None) or []):
                if int(clip.id) != self._drop_target_clip_id:
                    continue
                cr = self._clip_rect(clip)
                if cr.width() <= 0:
                    break
                drop_x = cr.right()
                painter.save()
                # Bright orange 3-px line with white fill at the centre
                painter.fillRect(drop_x - 1, cr.top(), 3, cr.height(),
                                 QColor(255, 255, 255, 120))
                painter.fillRect(drop_x, cr.top(), 2, cr.height(),
                                 QColor(255, 120, 30, 230))
                painter.restore()
                break

        # Clip selection — marching ants (only when video owns the selection)
        if self._selected_clip_ids and _ANTS_OWNER == "video":
            painter.save()
            march_off = getattr(self, "_march_offset", 0)
            for clip in (getattr(self.track, "clips", None) or []):
                if int(clip.id) not in self._selected_clip_ids:
                    continue
                cr = self._clip_rect(clip)
                if cr.width() <= 0:
                    continue
                _draw_marching_ants(painter, cr, march_off)
            painter.restore()

        # Active track: subtle left-edge bar only (no full border)
        if self._is_active:
            painter.fillRect(0, 0, 3, self.height(), QColor(80, 120, 200, 180))

        # Playhead — orange, drawn on every track at project time.
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        px = self._project_ms_to_x(self._position_ms)
        painter.drawLine(
            px, self.LABEL_H - 2, px, self.LABEL_H + self.TIMELINE_H + 2
        )

        # Proxy badge — small "P" pill in the top-right corner of the label
        # area when the track is currently playing a proxy file.
        _sp = self.track.source_path
        if _sp is not None and str(_sp).endswith("_proxy.mp4"):
            painter.save()
            badge_font = painter.font()
            badge_font.setPixelSize(9)
            badge_font.setBold(True)
            painter.setFont(badge_font)
            badge_text = "P"
            badge_w, badge_h = 14, 12
            badge_x = self.width() - self.MARGIN - badge_w
            badge_y = 0
            painter.setBrush(QColor(COLOR_ACCENT_ORANGE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRect(badge_x, badge_y, badge_w, badge_h),
                Qt.AlignmentFlag.AlignCenter,
                badge_text,
            )
            painter.restore()

        # PIP badge — small "PIP" pill when the track has pip_enabled=True.
        if getattr(self.track, "pip_enabled", False):
            painter.save()
            pip_badge_font = painter.font()
            pip_badge_font.setPixelSize(8)
            pip_badge_font.setBold(True)
            painter.setFont(pip_badge_font)
            _proxy_offset = 18 if (_sp is not None and str(_sp).endswith("_proxy.mp4")) else 0
            pip_badge_w, pip_badge_h = 24, 12
            pip_badge_x = self.width() - self.MARGIN - pip_badge_w - _proxy_offset
            pip_badge_y = 0
            painter.setBrush(QColor("#3a7bd5"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pip_badge_x, pip_badge_y, pip_badge_w, pip_badge_h, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRect(pip_badge_x, pip_badge_y, pip_badge_w, pip_badge_h),
                Qt.AlignmentFlag.AlignCenter,
                "PIP",
            )
            painter.restore()

            # 🔗 Linked-audio badge on clips that have linked_audio_id set
            for clip in (getattr(self.track, "clips", None) or []):
                if getattr(clip, "linked_audio_id", None) is not None:
                    cr = self._clip_rect(clip)
                    if cr.width() > 14:
                        painter.save()
                        lf = painter.font(); lf.setPixelSize(9); painter.setFont(lf)
                        painter.setPen(QColor("#66aaff"))
                        painter.drawText(
                            QRect(cr.x() + 2, self.LABEL_H + 2, 14, 11),
                            Qt.AlignmentFlag.AlignCenter, "🔗",
                        )
                        painter.restore()

            # PIP keyframe markers — small ◇ diamonds at each keyframe position.
            kfs = getattr(self.track, "pip_keyframes", [])
            if kfs:
                painter.save()
                kf_y = self.LABEL_H + self.TIMELINE_H // 2
                for kf in kfs:
                    kf_ms = int(kf.get("ms", 0))
                    kf_x = self._project_ms_to_x(kf_ms)
                    # Diamond shape
                    from PySide6.QtGui import QPolygon as _QPolygon
                    from PySide6.QtCore import QPoint as _QPoint
                    d = 5
                    diamond = _QPolygon([
                        _QPoint(kf_x, kf_y - d),
                        _QPoint(kf_x + d, kf_y),
                        _QPoint(kf_x, kf_y + d),
                        _QPoint(kf_x - d, kf_y),
                    ])
                    painter.setBrush(QColor("#f5a623"))
                    painter.setPen(QPen(QColor("#ffffff"), 1))
                    painter.drawPolygon(diamond)
                painter.restore()

        # Separator between track rows — dark groove against the bright host
        # stripes so adjacent tracks read as distinct lanes.
        pen = QPen(QColor("#0f0f14"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(
            0, self.height() - 1, self.width(), self.height() - 1,
        )

    @staticmethod
    def _color_for_speed(speed: float) -> QColor:
        if speed < 1.0:
            t = min(1.0, (1.0 - speed) / 0.75)
            return QColor(int(120 + 80 * t), int(180 - 80 * t), 255, 160)
        if speed > 1.0:
            t = min(1.0, (speed - 1.0) / 15.0)
            return QColor(255, int(180 - 130 * t), int(120 - 100 * t), 160)
        return QColor(150, 150, 150, 100)

    def _paint_fade_segment(
        self, painter: QPainter, fade: FadeSegment, rect: QRect
    ) -> None:
        """Draw a FadeSegment as an orange/black gradient. Shape depends on
        ``fade.kind``: ``in`` = black→content, ``out`` = content→black,
        ``both`` = content→black→content (two halves). Resize handles on
        each edge; right-click menu toggles the kind."""
        from PySide6.QtGui import QLinearGradient, QBrush
        fx1 = self._ms_to_x(fade.start_ms)
        fx2 = self._ms_to_x(fade.end_ms)
        if fx2 - fx1 < 2:
            return

        painter.save()
        painter.setClipRect(
            rect.intersected(QRect(fx1, rect.top(), fx2 - fx1, rect.height()))
        )
        if fade.kind == "in":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 220))
            g.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), QBrush(g))
        elif fade.kind == "out":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(216, 90, 48, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), QBrush(g))
        else:  # both — two-half pattern
            mid = (fx1 + fx2) // 2
            g_out = QLinearGradient(fx1, 0, mid, 0)
            g_out.setColorAt(0.0, QColor(216, 90, 48, 0))
            g_out.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, rect.top(), mid - fx1, rect.height(), QBrush(g_out))
            g_in = QLinearGradient(mid, 0, fx2, 0)
            g_in.setColorAt(0.0, QColor(0, 0, 0, 220))
            g_in.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(mid, rect.top(), fx2 - mid, rect.height(), QBrush(g_in))
        painter.restore()

        # Outer frame — subtle, not orange (orange is reserved for selection)
        pen = QPen(QColor(180, 100, 60, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, rect.top(), max(1, fx2 - fx1), rect.height())

        # Edge trim handles — always visible (invites resizing), widen +
        # brighten on hover, light up with accent during active drag.
        self._paint_edge_handles(
            painter,
            rect_top=rect.top(),
            rect_h=rect.height(),
            x_left=fx1,
            x_right=fx2,
            left_hot=(self._hover_fade is fade and self._hover_fade_side == "left")
                or (self._resizing_fade is fade and self._resize_side == "left"),
            right_hot=(self._hover_fade is fade and self._hover_fade_side == "right")
                or (self._resizing_fade is fade and self._resize_side == "right"),
            dragging=(self._resizing_fade is fade),
            base_color=QColor(255, 150, 80),
            accent_color=QColor("#ff7a4a"),
        )

    def _paint_edge_handles(
        self,
        painter: QPainter,
        *,
        rect_top: int,
        rect_h: int,
        x_left: int,
        x_right: int,
        left_hot: bool,
        right_hot: bool,
        dragging: bool,
        base_color: QColor,
        accent_color: QColor,
    ) -> None:
        """Draw two trim handles at the actor's edges. Each handle
        widens when hovered (6px) or being dragged (8px), and uses the
        accent color during drag."""
        def _one(x: int, hot: bool) -> None:
            if dragging and hot:
                w = 8
                color = accent_color
            elif hot:
                w = 6
                color = QColor(accent_color)
                color.setAlpha(255)
            else:
                w = 4
                color = QColor(base_color)
                color.setAlpha(210)
            painter.fillRect(x - w // 2, rect_top, w, rect_h, color)
            # Small notch marks top + bottom so the handle reads as a
            # "grabbable bar" rather than a color stripe.
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            notch = max(2, w - 2)
            painter.drawLine(
                x - notch // 2, rect_top + 2,
                x + notch // 2, rect_top + 2,
            )
            painter.drawLine(
                x - notch // 2, rect_top + rect_h - 3,
                x + notch // 2, rect_top + rect_h - 3,
            )

        _one(x_left, left_hot)
        _one(x_right, right_hot)

    @staticmethod
    def _paint_empty_slot_pattern(painter: QPainter, rect: QRect) -> None:
        """Empty-track slot: 80% brightness diagonal stripes + subtle border."""
        painter.save()
        StripedHost._draw_stripes(
            painter, rect,
            StripedHost.BG_80, StripedHost.STRIPE_80,
        )
        border = QPen(QColor("#3e3e4a"))
        border.setWidth(1)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.restore()

    @staticmethod
    def _draw_speed_label(
        painter: QPainter, speed: float, x: int, y: int, w: int, h: int,
        frame_blend: bool = False,
    ) -> None:
        """Draw a bold ×speed badge clamped inside the segment rect. Picks a
        font size proportional to the segment box, capped so it never spills
        outside the track frame.  When ``frame_blend`` is True a tilde suffix
        (``~``) is appended to hint that smooth interpolation is active."""
        if w < 14:
            return
        label = f"×{speed:g}" + ("~" if frame_blend else "")
        # Font size scales with the smaller of segment width / track height,
        # so very narrow segments get a small readable label instead of an
        # oversized clipped one.
        target_h = min(h - 4, int(w * 0.55))
        font_px = max(11, min(36, target_h))
        font = painter.font()
        font.setPixelSize(font_px)
        font.setBold(True)
        painter.setFont(font)

        # White text with a dark outline for legibility on any speed color.
        clip_rect = QRect(x, y, w, h)
        painter.save()
        painter.setClipRect(clip_rect)
        # Shadow / outline via 1px offsets
        painter.setPen(QColor(0, 0, 0, 220))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(
                clip_rect.adjusted(dx, dy, dx, dy),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(clip_rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        # Multi-source tracks have duration_ms == 0 (clips list carries
        # the content).  Guard against truly empty tracks only.
        if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
            return
        pos = event.position().toPoint()
        x = pos.x()
        mods = event.modifiers()
        rect = self._timeline_rect()

        # Zoom actor — drag (move / resize / fade-in / fade-out) takes
        # priority; the modal opens on double-click only.
        zactor, zoom_zone = self._zoom_at(pos)
        if zactor is not None:
            self._zoom_drag_actor_id = zactor.id
            self._zoom_drag_anchor_ms = self._x_to_ms(x)
            self._zoom_drag_orig_start_ms = int(zactor.start_ms)
            self._zoom_drag_orig_end_ms = int(zactor.end_ms)
            self._zoom_drag_orig_in_ms = int(zactor.zoom_in_ms)
            self._zoom_drag_orig_out_ms = int(zactor.zoom_out_ms)
            if zoom_zone == "left":
                self._zoom_drag_mode = "resize_l"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif zoom_zone == "right":
                self._zoom_drag_mode = "resize_r"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif zoom_zone == "fade_in":
                self._zoom_drag_mode = "fade_in"
                self.setCursor(Qt.CursorShape.SplitHCursor)
            elif zoom_zone == "fade_out":
                self._zoom_drag_mode = "fade_out"
                self.setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self._zoom_drag_mode = "move"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return

        # Typography actor interactions take priority over everything
        # else — they sit at the top of the strip and must be movable
        # / resizable without triggering the clip body's drag-to-move.
        typo_actor, typo_zone = self._typography_at(pos)
        if typo_actor is not None:
            self._typo_drag_actor_id = typo_actor.id
            self._typo_drag_anchor_ms = self._x_to_ms(x)
            self._typo_drag_orig_start_ms = int(typo_actor.start_ms)
            self._typo_drag_orig_end_ms = int(typo_actor.end_ms)
            if typo_zone == "left":
                self._typo_drag_mode = "resize_l"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif typo_zone == "right":
                self._typo_drag_mode = "resize_r"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self._typo_drag_mode = "move"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            # Notify editor that this actor is selected (for Delete key)
            self.typography_actor_selected.emit(self.track.id, typo_actor.id)
            self.update()
            return

        # CapCut-style transition block: left-click on an existing
        # transition block starts a drag to resize it.
        tr_clip, tr_side = self._transition_handle_at(pos)
        if tr_clip is not None:
            self._dragging_transition = True
            self._drag_transition_clip = tr_clip
            self._drag_transition_side = tr_side
            self._drag_transition_start_ms = int(tr_clip.transition_out_ms)
            self._drag_transition_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # CapCut-style transition: left-click at the boundary between
        # two adjacent clips inserts a transition using the currently
        # selected type from the TransitionsPanel.
        # Guard: only fire when the click is NOT on any clip body —
        # if the cursor is already on a clip, the clip-drag path below
        # should win (otherwise short clips and boundary-adjacent clicks
        # silently insert a transition instead of selecting / dragging
        # the second clip).
        boundary_clip = self._clip_at_boundary(pos)
        if boundary_clip is not None and self._hit_test_clip(pos) is None:
            ttype, tms = self._get_current_transition_type()
            boundary_clip.transition_out_type = ttype
            boundary_clip.transition_out_ms = tms
            self.update()
            return

        # Fade edge resize takes priority over everything else (audio
        # FadeSegments on video tracks — keep this for track.fades list).
        fade, side = self._fade_edge_at(x, pos.y())
        if fade is not None:
            self._resizing_fade = fade
            self._resize_side = side
            self._resize_orig_start = fade.start_ms
            self._resize_orig_end = fade.end_ms
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Speed edge resize (after fades — when a fade and a speed
        # segment share an edge pixel, fade wins; rare in practice).
        seg, s_side = self._speed_edge_at(x, pos.y())
        if seg is not None:
            self._speed_drag_seg = seg
            self._speed_drag_mode = "resize_l" if s_side == "left" else "resize_r"
            self._speed_drag_anchor_ms = self._x_to_ms(x)
            self._speed_drag_orig_start = int(seg.start_ms)
            self._speed_drag_orig_end = int(seg.end_ms)
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Clip edge trim / roll edit. Detected AFTER actor/fade/speed
        # handles so those take priority at shared pixels.
        clip_edge_hit = self._clip_edge_at(pos)
        if clip_edge_hit is not None:
            hit_clip, edge_side, roll_neighbour = clip_edge_hit
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            self._clip_trim_clip = hit_clip
            self._clip_trim_side = edge_side
            self._clip_trim_orig_src_in = int(hit_clip.source_in_ms)
            self._clip_trim_orig_src_out = int(hit_clip.effective_source_out_ms)
            self._clip_trim_orig_tl_in = int(hit_clip.timeline_in_ms)
            self._clip_trim_anchor_ms = self._x_to_project_ms(x)
            if ctrl and roll_neighbour is not None:
                # Roll edit — boundary between two clips, Ctrl held.
                self._clip_trim_mode = "roll"
                self._clip_trim_roll_right = roll_neighbour
                self._clip_trim_roll_orig_src_in = int(roll_neighbour.source_in_ms)
                self._clip_trim_roll_orig_tl_in = int(roll_neighbour.timeline_in_ms)
            elif shift and edge_side == "right":
                self._clip_trim_mode = "ripple_r"
                self._clip_trim_roll_right = None
            elif shift and edge_side == "left":
                self._clip_trim_mode = "ripple_l"
                self._clip_trim_roll_right = None
            elif edge_side == "right":
                self._clip_trim_mode = "trim_r"
                self._clip_trim_roll_right = None
            else:
                self._clip_trim_mode = "trim_l"
                self._clip_trim_roll_right = None
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Option C: legacy Shift+drag range-select removed. Industry-
        # standard NLEs (DaVinci/Premiere/FCP) use click-to-select on
        # clips and Shift+click for multi-clip add. The Shift modifier
        # is now consumed by the clip-click branch below as the
        # "add to selection" toggle.

        # Drag on the clip body = move the clip on the project timeline
        # (Premiere/DaVinci style). Scrubbing moved to the timeline ruler.
        # Phase 1.5d Step B: hit-test which CLIP the cursor is on so a
        # split (multi-clip) track lets each piece be dragged
        # independently. Single-clip tracks behave identically to before.
        # Option C: emit ``clip_clicked`` / ``empty_area_clicked`` so the
        # editor maintains the project-wide clip selection set.
        if rect.contains(pos):
            hit_clip = self._hit_test_clip(pos)
            shift_held = bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            if hit_clip is not None:
                self.clip_clicked.emit(
                    self.track.id, int(hit_clip.id), shift_held,
                )
                self._dragging_offset = True
                self._drag_start_x = x
                self._drag_clip_id = int(hit_clip.id)
                self._drag_start_clip_in_ms = int(hit_clip.timeline_in_ms)
                self._drag_start_offset_ms = self.track.offset_ms
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self.empty_area_clicked.emit(self.track.id)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Multi-source tracks have duration_ms == 0 (clips list carries
        # the content).  Guard against truly empty tracks only.
        if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
            return
        pos = event.position().toPoint()
        x = pos.x()

        # Typography drag — active
        if self._typo_drag_mode is not None and self._typo_drag_actor_id is not None:
            actor = None
            for a in self.track.typography_actors:
                if a.id == self._typo_drag_actor_id:
                    actor = a
                    break
            if actor is None:
                self._typo_drag_mode = None
            else:
                delta_ms = self._x_to_ms(x) - self._typo_drag_anchor_ms
                if self._typo_drag_mode == "move":
                    new_start = max(0, self._typo_drag_orig_start_ms + delta_ms)
                    duration = self._typo_drag_orig_end_ms - self._typo_drag_orig_start_ms
                    if new_start + duration > self.track.duration_ms:
                        new_start = max(0, self.track.duration_ms - duration)
                    actor.start_ms = new_start
                    actor.end_ms = new_start + duration
                elif self._typo_drag_mode == "resize_l":
                    new_start = max(0, self._typo_drag_orig_start_ms + delta_ms)
                    new_start = min(
                        new_start, actor.end_ms - self.TYPO_MIN_DURATION_MS
                    )
                    actor.start_ms = new_start
                elif self._typo_drag_mode == "resize_r":
                    new_end = max(
                        actor.start_ms + self.TYPO_MIN_DURATION_MS,
                        self._typo_drag_orig_end_ms + delta_ms,
                    )
                    new_end = min(new_end, self.track.duration_ms)
                    actor.end_ms = new_end
                self.update()
                self.typography_changed.emit(self.track.id)
                return

        # Zoom actor drag (move / resize_l / resize_r) — same shape as
        # typography above; just operates on track.zoom_actors.
        if self._zoom_drag_mode is not None and self._zoom_drag_actor_id is not None:
            zactor = None
            for z in self.track.zoom_actors:
                if z.id == self._zoom_drag_actor_id:
                    zactor = z
                    break
            if zactor is None:
                self._zoom_drag_mode = None
            else:
                delta_ms = self._x_to_ms(x) - self._zoom_drag_anchor_ms
                if self._zoom_drag_mode == "move":
                    new_start = max(0, self._zoom_drag_orig_start_ms + delta_ms)
                    duration = self._zoom_drag_orig_end_ms - self._zoom_drag_orig_start_ms
                    if new_start + duration > self.track.duration_ms:
                        new_start = max(0, self.track.duration_ms - duration)
                    zactor.start_ms = new_start
                    zactor.end_ms = new_start + duration
                elif self._zoom_drag_mode == "resize_l":
                    new_start = max(0, self._zoom_drag_orig_start_ms + delta_ms)
                    new_start = min(
                        new_start, zactor.end_ms - self.ZOOM_MIN_DURATION_MS
                    )
                    zactor.start_ms = new_start
                elif self._zoom_drag_mode == "resize_r":
                    new_end = max(
                        zactor.start_ms + self.ZOOM_MIN_DURATION_MS,
                        self._zoom_drag_orig_end_ms + delta_ms,
                    )
                    new_end = min(new_end, self.track.duration_ms)
                    zactor.end_ms = new_end
                elif self._zoom_drag_mode == "fade_in":
                    # Drag the inner-left handle: zoom_in_ms is the
                    # distance from start to where the cursor sits.
                    new_in = self._x_to_ms(x) - zactor.start_ms
                    new_in = max(0, new_in)
                    span = max(0, zactor.end_ms - zactor.start_ms)
                    new_in = min(new_in, max(0, span - zactor.zoom_out_ms))
                    zactor.zoom_in_ms = new_in
                elif self._zoom_drag_mode == "fade_out":
                    # Drag the inner-right handle: zoom_out_ms is the
                    # distance from end back to where the cursor sits.
                    new_out = zactor.end_ms - self._x_to_ms(x)
                    new_out = max(0, new_out)
                    span = max(0, zactor.end_ms - zactor.start_ms)
                    new_out = min(new_out, max(0, span - zactor.zoom_in_ms))
                    zactor.zoom_out_ms = new_out
                # Outer-resize modes can shrink the span; clamp ramps
                # so they always fit inside the new window.
                if self._zoom_drag_mode in ("resize_l", "resize_r", "move"):
                    span = max(0, zactor.end_ms - zactor.start_ms)
                    zactor.zoom_in_ms = min(zactor.zoom_in_ms, span)
                    zactor.zoom_out_ms = min(
                        zactor.zoom_out_ms, max(0, span - zactor.zoom_in_ms)
                    )
                self.update()
                self.zoom_changed.emit(self.track.id)
                return

        # Speed edge resize — active drag
        if self._speed_drag_mode is not None and self._speed_drag_seg is not None:
            seg = self._speed_drag_seg
            mouse_ms = self._x_to_ms(x)
            delta = mouse_ms - self._speed_drag_anchor_ms
            # Compute adjacent-segment bounds so we can't cross into
            # a neighbouring speed segment.
            neighbours = [s for s in self.track.speed_segments if s is not seg]
            if self._speed_drag_mode == "resize_l":
                # Max start = current end - MIN. Min start = closest
                # left neighbour's end (or 0).
                left_cap = max(
                    (s.end_ms for s in neighbours if s.end_ms <= self._speed_drag_orig_start),
                    default=0,
                )
                new_start = max(
                    left_cap,
                    min(seg.end_ms - self.SPEED_MIN_DURATION_MS,
                        self._speed_drag_orig_start + delta),
                )
                seg.start_ms = int(new_start)
            else:  # resize_r
                right_cap = min(
                    (s.start_ms for s in neighbours if s.start_ms >= self._speed_drag_orig_end),
                    default=self.track.duration_ms,
                )
                new_end = min(
                    right_cap,
                    max(seg.start_ms + self.SPEED_MIN_DURATION_MS,
                        self._speed_drag_orig_end + delta),
                )
                seg.end_ms = int(new_end)
            self.update()
            self.speed_changed.emit(self.track.id)
            return

        # CapCut-style transition block drag — resize transition_out_ms.
        if self._dragging_transition and self._drag_transition_clip is not None:
            clip = self._drag_transition_clip
            delta_px = x - self._drag_transition_start_x
            delta_ms = int(delta_px / max(1.0, self._px_per_sec) * 1000)
            if self._drag_transition_side == "right":
                new_ms = max(100, min(3000, self._drag_transition_start_ms + delta_ms))
            else:  # "left" — dragging left handle shrinks from left
                new_ms = max(100, min(3000, self._drag_transition_start_ms - delta_ms))
            clip.transition_out_ms = new_ms
            self.update()
            return

        # Clip edge trim / roll / ripple trim — active drag.
        if self._clip_trim_clip is not None and self._clip_trim_mode:
            clip = self._clip_trim_clip
            mouse_ms = self._x_to_project_ms(x)
            delta = mouse_ms - self._clip_trim_anchor_ms
            mode = self._clip_trim_mode

            if mode == "trim_r":
                # Ordinary right trim: extend/shrink source_out_ms.
                new_src_out = max(
                    self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                    self._clip_trim_orig_src_out + delta,
                )
                if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                    new_src_out = min(new_src_out, int(clip.source_duration_ms))
                clip.source_out_ms = int(new_src_out)
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return

            elif mode == "trim_l":
                # Ordinary left trim: extend/shrink source_in_ms + move timeline_in_ms.
                new_src_in = min(
                    self._clip_trim_orig_src_out - self.CLIP_MIN_DURATION_MS,
                    self._clip_trim_orig_src_in + delta,
                )
                new_src_in = max(0, new_src_in)
                clip.source_in_ms = int(new_src_in)
                clip.timeline_in_ms = max(0, self._clip_trim_orig_tl_in + delta)
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return

            elif mode == "ripple_r":
                # Ripple right trim: change duration AND shift all subsequent clips.
                new_src_out = max(
                    self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                    self._clip_trim_orig_src_out + delta,
                )
                if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                    new_src_out = min(new_src_out, int(clip.source_duration_ms))
                actual_delta = new_src_out - self._clip_trim_orig_src_out
                clip.source_out_ms = int(new_src_out)
                old_end = self._clip_trim_orig_tl_in + (
                    self._clip_trim_orig_src_out - self._clip_trim_orig_src_in
                )
                for other in getattr(self.track, "clips", []):
                    if other is clip:
                        continue
                    if int(other.timeline_in_ms) >= old_end - 1:
                        other.timeline_in_ms = max(0, int(other.timeline_in_ms) + actual_delta)
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return

            elif mode == "ripple_l":
                # Ripple left trim: change source_in_ms + shift this and all subsequent
                # clips left/right by the same delta (but NOT clips to the left).
                new_src_in = min(
                    self._clip_trim_orig_src_out - self.CLIP_MIN_DURATION_MS,
                    self._clip_trim_orig_src_in + delta,
                )
                new_src_in = max(0, new_src_in)
                actual_delta = new_src_in - self._clip_trim_orig_src_in
                clip.source_in_ms = int(new_src_in)
                clip.timeline_in_ms = max(0, self._clip_trim_orig_tl_in + actual_delta)
                for other in getattr(self.track, "clips", []):
                    if other is clip:
                        continue
                    if int(other.timeline_in_ms) >= self._clip_trim_orig_tl_in - 1:
                        other.timeline_in_ms = max(0, int(other.timeline_in_ms) + actual_delta)
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return

            elif mode == "roll":
                # Roll edit: clip A's right edge moves +delta,
                # clip B's left edge moves +delta.  Total duration unchanged.
                roll_b = self._clip_trim_roll_right
                if roll_b is not None:
                    new_a_src_out = max(
                        self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                        min(
                            self._clip_trim_orig_src_out + delta,
                            self._clip_trim_orig_src_out
                            + (int(roll_b.effective_source_out_ms) - self._clip_trim_roll_orig_src_in)
                            - self.CLIP_MIN_DURATION_MS,
                        ),
                    )
                    if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                        new_a_src_out = min(new_a_src_out, int(clip.source_duration_ms))
                    roll_delta = new_a_src_out - self._clip_trim_orig_src_out
                    clip.source_out_ms = int(new_a_src_out)
                    new_b_src_in = max(
                        0, self._clip_trim_roll_orig_src_in + roll_delta
                    )
                    roll_b.source_in_ms = int(new_b_src_in)
                    roll_b.timeline_in_ms = max(
                        0, self._clip_trim_roll_orig_tl_in + roll_delta
                    )
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return

        # Fade edge resize — active drag
        if self._resizing_fade is not None:
            delta_ms = int((x - self._drag_start_x) / self._px_per_sec * 1000)
            fade = self._resizing_fade
            if self._resize_side == "left":
                new_start = max(0, min(
                    fade.end_ms - 100,
                    self._resize_orig_start + delta_ms,
                ))
                fade.start_ms = new_start
            else:  # "right"
                new_end = min(self.track.duration_ms, max(
                    fade.start_ms + 100,
                    self._resize_orig_end + delta_ms,
                ))
                fade.end_ms = new_end
            self.update()
            self.fades_changed.emit(self.track.id)
            return

        # Idle hover — swap cursor when the pointer is over a fade edge
        # or typography actor so the user discovers the affordances.
        # Also update hover-state fields so paint can thicken the edge
        # handles on the thing under the cursor.
        if not (self._dragging_offset or self._dragging_playhead):
            typo_actor, typo_zone = self._typography_at(pos)

            prev_typo_id = self._hover_typo_actor_id
            prev_typo_side = self._hover_typo_side
            prev_fade = self._hover_fade
            prev_fade_side = self._hover_fade_side
            prev_speed = self._hover_speed_seg
            prev_speed_side = self._hover_speed_side

            if typo_actor is not None:
                self._hover_typo_actor_id = typo_actor.id
                self._hover_typo_side = typo_zone if typo_zone in ("left", "right") else ""
                self._hover_fade = None
                self._hover_fade_side = ""
                self._hover_speed_seg = None
                self._hover_speed_side = ""
                self.setCursor(
                    Qt.CursorShape.SizeHorCursor if typo_zone in ("left", "right")
                    else Qt.CursorShape.OpenHandCursor
                )
            else:
                self._hover_typo_actor_id = None
                self._hover_typo_side = ""
                # CapCut-style: show resize cursor when over a transition block
                tr_clip, _tr_side = self._transition_handle_at(pos)
                if tr_clip is not None:
                    self._hover_fade = None
                    self._hover_fade_side = ""
                    self._hover_speed_seg = None
                    self._hover_speed_side = ""
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    fade, side = self._fade_edge_at(x, pos.y())
                    if fade is not None:
                        self._hover_fade = fade
                        self._hover_fade_side = side
                        self._hover_speed_seg = None
                        self._hover_speed_side = ""
                        self.setCursor(Qt.CursorShape.SizeHorCursor)
                    else:
                        self._hover_fade = None
                        self._hover_fade_side = ""
                        seg, s_side = self._speed_edge_at(x, pos.y())
                        if seg is not None:
                            self._hover_speed_seg = seg
                            self._hover_speed_side = s_side
                            self.setCursor(Qt.CursorShape.SizeHorCursor)
                        else:
                            self._hover_speed_seg = None
                            self._hover_speed_side = ""
                            # Show PointingHandCursor near clip boundaries
                            # (teaches users they can click to insert transition)
                            # but only when NOT on a clip body itself — if the
                            # cursor is already on a clip, OpenHandCursor wins
                            # (clip drag takes priority over transition insert).
                            bnd = self._clip_at_boundary(pos)
                            on_clip = self._hit_test_clip(pos) is not None
                            self.setCursor(
                                Qt.CursorShape.PointingHandCursor if (bnd is not None and not on_clip)
                                else Qt.CursorShape.OpenHandCursor
                            )

            if (
                prev_typo_id != self._hover_typo_actor_id
                or prev_typo_side != self._hover_typo_side
                or prev_fade is not self._hover_fade
                or prev_fade_side != self._hover_fade_side
                or prev_speed is not self._hover_speed_seg
                or prev_speed_side != self._hover_speed_side
            ):
                self.update()

        if self._dragging_offset:
            delta_px = x - self._drag_start_x
            delta_ms = int(delta_px / self._px_per_sec * 1000)
            new_clip_in = max(0, self._drag_start_clip_in_ms + delta_ms)
            # Phase 1.5d Step B: move the specific clip the user grabbed.
            # When this is the only clip on the track we also keep the
            # legacy ``track.offset_ms`` in lockstep so the export path
            # (which still consults offset + cuts + duration) stays
            # consistent. Multi-clip tracks (post-cut) move just the
            # one clip.
            clip = self._find_clip_by_id(self._drag_clip_id) if self._drag_clip_id is not None else None
            if clip is None:
                # Fallback: clip went away mid-drag (e.g. another cut
                # racing). Keep the old behaviour so the gesture still
                # does something sensible.
                new_offset = max(0, self._drag_start_offset_ms + delta_ms)
                if new_offset != self.track.offset_ms:
                    self.track.offset_ms = new_offset
                    self._recalc_width()
                    self.offset_changed.emit(self.track.id, self.track.offset_ms)
                return
            # Phase 1.5d post-work: snap to other clip edges + 0 +
            # extra targets (playhead, markers), then refuse drops that
            # would overlap. ``snap_ms`` derives from a fixed pixel
            # tolerance so the stickiness is the same physical width
            # regardless of zoom.
            from app.timeline_model import apply_drag_constraints
            snap_px = 8
            snap_ms = max(40, int(snap_px / max(1.0, self._px_per_sec) * 1000))
            # Pre-snap to extra targets (playhead + markers) before the
            # full constraint pass so those also benefit from collision.
            if self._extra_snap_targets:
                clip_len = int(getattr(clip, "effective_length_ms", 0) or 0)
                clip_out = new_clip_in + clip_len
                best_extra_delta = snap_ms + 1
                best_extra_pos: int | None = None
                for t in self._extra_snap_targets:
                    d_in = abs(t - new_clip_in)
                    if d_in < best_extra_delta:
                        best_extra_delta = d_in
                        best_extra_pos = t
                    d_out = abs(t - clip_out)
                    if d_out < best_extra_delta:
                        best_extra_delta = d_out
                        best_extra_pos = max(0, t - clip_len)
                if best_extra_pos is not None:
                    new_clip_in = best_extra_pos
            new_clip_in = apply_drag_constraints(
                self.track.clips, clip, new_clip_in, snap_ms=snap_ms,
            )
            if int(clip.timeline_in_ms) != new_clip_in:
                old_clip_in = int(clip.timeline_in_ms)
                clip.timeline_in_ms = new_clip_in
                # source_in/out are untouched — only the project-time
                # position moves. ``effective_length_ms`` is derived from
                # source_in/out so it stays the same automatically.
                if len(self.track.clips) <= 1:
                    self.track.offset_ms = new_clip_in
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
                # Notify editor about clip drag so linked audio can be synced.
                if getattr(clip, "linked_audio_id", None) is not None:
                    delta_ms = new_clip_in - old_clip_in
                    self.clip_drag_delta.emit(self.track.id, clip.id, new_clip_in, delta_ms)
            return
        if self._dragging_playhead:
            project_ms = self._x_to_project_ms(x)
            self.position_requested.emit(self.track.id, project_ms)

    def leaveEvent(self, _event) -> None:
        # Clear hover state when the cursor exits the widget, otherwise
        # the last-hovered handle stays "hot" forever. Qt fires an
        # early leaveEvent during construction (before the hover fields
        # are set) when the host invalidates layout right after
        # insertWidget — guard with getattr so the widget doesn't crash
        # mid-build.
        if (getattr(self, "_hover_fade", None) is not None
                or getattr(self, "_hover_typo_actor_id", None) is not None
                or getattr(self, "_hover_speed_seg", None) is not None):
            self._hover_fade = None
            self._hover_fade_side = ""
            self._hover_typo_actor_id = None
            self._hover_typo_side = ""
            self._hover_speed_seg = None
            self._hover_speed_side = ""
            self.update()

    def wheelEvent(self, event) -> None:
        """Scroll wheel over a speed segment cycles through preset
        rates — gives users a quick way to tweak the speed in place
        without opening the context menu."""
        pos = event.position().toPoint()
        seg = self._speed_segment_under(pos)
        if seg is None:
            super().wheelEvent(event)
            return
        try:
            idx = SpeedCard.PRESETS.index(
                min(SpeedCard.PRESETS, key=lambda p: abs(p - seg.speed))
            )
        except ValueError:
            idx = SpeedCard.PRESETS.index(SpeedCard.DEFAULT_SPEED)
        delta_y = event.angleDelta().y()
        step = 1 if delta_y > 0 else -1
        new_idx = max(0, min(len(SpeedCard.PRESETS) - 1, idx + step))
        seg.speed = float(SpeedCard.PRESETS[new_idx])
        self.update()
        self.speed_changed.emit(self.track.id)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._speed_drag_mode is not None:
            # Keep segments ordered for subsequent hit-tests / painting.
            self.track.speed_segments.sort(key=lambda s: s.start_ms)
            self._speed_drag_mode = None
            self._speed_drag_seg = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.speed_changed.emit(self.track.id)
            self.update()
        if self._typo_drag_mode is not None:
            # Re-sort by start_ms so paint + hit-testing stay consistent.
            self.track.typography_actors.sort(key=lambda c: c.start_ms)
            self._typo_drag_mode = None
            self._typo_drag_actor_id = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.typography_changed.emit(self.track.id)
            self.update()
        if self._zoom_drag_mode is not None:
            self.track.zoom_actors.sort(key=lambda z: z.start_ms)
            self._zoom_drag_mode = None
            self._zoom_drag_actor_id = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.zoom_changed.emit(self.track.id)
            self.update()
        if self._dragging_transition:
            self._dragging_transition = False
            self._drag_transition_clip = None
            self._drag_transition_side = ""
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
        if self._resizing_fade is not None:
            self._resizing_fade = None
            self._resize_side = ""
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.fades_changed.emit(self.track.id)
        if self._clip_trim_clip is not None:
            # Re-sort clips so timeline order is consistent after trim / roll.
            if hasattr(self.track, "clips"):
                self.track.clips.sort(key=lambda c: int(c.timeline_in_ms))
            self._clip_trim_clip = None
            self._clip_trim_mode = ""
            self._clip_trim_roll_right = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            self.drag_committed.emit(self.track.id)
            self.update()
        if self._dragging_offset:
            self._dragging_offset = False
            self._drag_clip_id = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            # ``drag_committed`` is the user-gesture-end pulse the
            # editor's history stack hooks. Live ``offset_changed``
            # ticks during the drag are intentionally NOT a savepoint.
            self.drag_committed.emit(self.track.id)
        self._dragging_playhead = False

    def _on_context_menu(self, local_pos: QPoint) -> None:
        # Zoom actor right-click: edit / delete menu.
        zactor, _zone = self._zoom_at(local_pos)
        if zactor is not None:
            self.zoom_context_menu.emit(
                self.track.id, zactor.id, self.mapToGlobal(local_pos)
            )
            return
        # Typography actors have priority — they sit visually on top
        # of the timeline strip.
        typo_actor, _zone = self._typography_at(local_pos)
        if typo_actor is not None:
            self.typography_context_menu.emit(
                self.track.id, typo_actor.id, self.mapToGlobal(local_pos)
            )
            return
        # If the click is on a fade actor, open the fade-type / delete menu
        # instead of the generic track menu.
        fade = self._fade_under(local_pos)
        if fade is not None:
            self._show_fade_menu(fade, self.mapToGlobal(local_pos))
            return
        # Speed segment right-click: rate picker + delete.
        seg = self._speed_segment_under(local_pos)
        if seg is not None:
            self._show_speed_menu(seg, self.mapToGlobal(local_pos))
            return
        # CapCut-style transition block right-click: show transition menu
        # if the cursor is inside any existing transition block.
        trans_clip, _side = self._transition_handle_at(local_pos)
        if trans_clip is None:
            # Also fall back to old proximity check for backwards compat
            trans_clip = self._transition_clip_at(local_pos)
        if trans_clip is not None:
            self._show_transition_menu(trans_clip, self.mapToGlobal(local_pos))
            return
        # Video clip right-click → emit clip_context_menu
        _rclip = self._clip_at(local_pos)
        if _rclip is not None:
            self.clip_context_menu.emit(
                self.track.id, _rclip.id, self.mapToGlobal(local_pos)
            )
            return
        self.context_menu.emit(self.track.id, self.mapToGlobal(local_pos))

    def _speed_segment_under(self, pos: QPoint) -> "SpeedSegment | None":
        """Return the SpeedSegment under ``pos``, or None."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        ms = self._x_to_ms(pos.x())
        for seg in self.track.speed_segments:
            if seg.start_ms <= ms < seg.end_ms:
                return seg
        return None

    def _speed_edge_at(self, x: int, y: int) -> "tuple[SpeedSegment | None, str]":
        """Return (seg, 'left'/'right') if the cursor is on a speed
        segment's resize edge, (None, '') otherwise."""
        if y < self.LABEL_H or y > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        for seg in self.track.speed_segments:
            sx1 = self._ms_to_x(seg.start_ms)
            sx2 = self._ms_to_x(seg.end_ms)
            if abs(x - sx1) <= self.SPEED_EDGE_GRAB_PX:
                return seg, "left"
            if abs(x - sx2) <= self.SPEED_EDGE_GRAB_PX:
                return seg, "right"
        return None, ""

    def _show_speed_menu(self, seg: "SpeedSegment", global_pos) -> None:
        """Preset rate picker + Frame Blend toggle + delete action for a placed SpeedSegment."""
        menu = QMenu(self)
        # Header (disabled action showing current speed)
        hdr = menu.addAction(tr("veditor.speed_menu.current", speed=_format_speed(seg.speed)))
        hdr.setEnabled(False)
        menu.addSeparator()
        preset_actions: list = []
        for p in SpeedCard.PRESETS:
            a = menu.addAction(SpeedCard._format_preset(p))
            a.setCheckable(True)
            a.setChecked(abs(seg.speed - p) < 1e-3)
            preset_actions.append((a, p))
        menu.addSeparator()
        # Frame blend toggle (only meaningful for slow-motion; shown always for simplicity)
        act_blend = menu.addAction(tr("veditor.speed_menu.frame_blend"))
        act_blend.setCheckable(True)
        act_blend.setChecked(getattr(seg, "frame_blend", False))
        # Blend mode sub-menu
        blend_sub = menu.addMenu(tr("veditor.speed_menu.blend_mode"))
        act_linear = blend_sub.addAction(tr("veditor.speed_menu.blend_linear"))
        act_linear.setCheckable(True)
        act_flow = blend_sub.addAction(tr("veditor.speed_menu.blend_optical_flow"))
        act_flow.setCheckable(True)
        current_mode = getattr(seg, "blend_mode", "linear")
        act_linear.setChecked(current_mode == "linear")
        act_flow.setChecked(current_mode == "optical_flow")
        menu.addSeparator()
        # Ease in/out sub-menu (Bezier speed ramp)
        ease_sub = menu.addMenu("⟳ Speed Ramp (Ease)")
        def _ease_act(label, ein, eout):
            a = ease_sub.addAction(label)
            a.setData((ein, eout))
            return a
        _ease_act("None (constant)", 0.0, 0.0)
        _ease_act("Ease In", 0.6, 0.0)
        _ease_act("Ease Out", 0.0, 0.6)
        _ease_act("Ease In+Out", 0.6, 0.6)
        _ease_act("S-Curve (full)", 1.0, 1.0)
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.speed_menu.delete"))
        chosen = menu.exec(global_pos)
        # Handle ease actions
        if chosen is not None and chosen.data() is not None:
            ein, eout = chosen.data()
            seg.ease_in  = float(ein)
            seg.ease_out = float(eout)
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        if chosen is act_del:
            try:
                self.track.speed_segments.remove(seg)
            except ValueError:
                pass
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        if chosen is act_blend:
            seg.frame_blend = not getattr(seg, "frame_blend", False)
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        if chosen is act_linear:
            seg.blend_mode = "linear"
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        if chosen is act_flow:
            seg.blend_mode = "optical_flow"
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        for a, p in preset_actions:
            if chosen is a:
                seg.speed = float(p)
                self.update()
                self.speed_changed.emit(self.track.id)
                return

    # ---- Transition helpers ----

    _TRANSITION_EDGE_PX = 20  # px from right edge of clip to trigger transition menu

    def _transition_clip_at(self, pos: QPoint):
        """Return the VideoClip whose right edge is within
        ``_TRANSITION_EDGE_PX`` of ``pos``, or None."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        for clip in (getattr(self.track, "clips", None) or []):
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                continue
            right_x = cr.right()
            if abs(pos.x() - right_x) <= self._TRANSITION_EDGE_PX and cr.top() <= pos.y() <= cr.bottom():
                return clip
        return None

    # ---- CapCut-style transition helpers ----

    _BOUNDARY_HIT_PX = 10   # px either side of a clip boundary to detect click
    _TRANSITION_HANDLE_PX = 8  # px from edge of transition block for handle grab

    def _clip_at_boundary(self, pos: QPoint):
        """Return the LEFT VideoClip if ``pos`` is at the boundary (gap ≤ 5 px)
        between two adjacent clips AND that clip has no transition yet.
        Returns None otherwise."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        clips = sorted(
            (getattr(self.track, "clips", None) or []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for i in range(len(clips) - 1):
            left_clip = clips[i]
            right_clip = clips[i + 1]
            gap_ms = int(right_clip.timeline_in_ms) - int(left_clip.timeline_out_ms)
            if gap_ms > 5:
                # More than 5 ms gap — not adjacent, skip
                continue
            boundary_x = self._project_ms_to_x(int(left_clip.timeline_out_ms))
            if abs(pos.x() - boundary_x) <= self._BOUNDARY_HIT_PX:
                # Don't insert if the clip already has a transition block
                if getattr(left_clip, "transition_out_type", ""):
                    return None
                return left_clip
        return None

    def _transition_rect(self, clip, sorted_clips=None):
        """Return the QRect of the transition block for ``clip`` if it has
        ``transition_out_type != ""``, spanning half the block into this clip
        and half into the next adjacent clip. Returns None if no transition or
        no adjacent next clip."""
        ttype = getattr(clip, "transition_out_type", "")
        if not ttype:
            return None
        t_ms = max(100, int(getattr(clip, "transition_out_ms", 500)))
        t_px = max(16, int(t_ms / 1000.0 * self._px_per_sec))
        half = t_px // 2

        boundary_x = self._project_ms_to_x(int(clip.timeline_out_ms))
        y_top = self.LABEL_H
        h_px = self.TIMELINE_H
        return QRect(boundary_x - half, y_top, t_px, h_px)

    def _transition_handle_at(self, pos: QPoint):
        """Return (clip, 'left' | 'right') if ``pos`` is on the left or right
        edge handle of an existing transition block, (None, '') otherwise."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        clips = sorted(
            (getattr(self.track, "clips", None) or []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for clip in clips:
            t_rect = self._transition_rect(clip, clips)
            if t_rect is None:
                continue
            if not t_rect.contains(pos):
                continue
            # Determine which handle: left or right based on x position
            mid_x = t_rect.left() + t_rect.width() // 2
            if pos.x() <= mid_x:
                return clip, "left"
            else:
                return clip, "right"
        return None, ""

    def _get_current_transition_type(self) -> tuple:
        """Return (type_str, duration_ms) for the currently selected transition
        in the TransitionsPanel. Falls back to ('dissolve', 500) if not found."""
        # Walk up the widget hierarchy to find the VideoEditorWindow which holds
        # self._transitions_panel. We stop after 20 levels to avoid infinite loops.
        w = self.parent()
        for _ in range(20):
            if w is None:
                break
            panel = getattr(w, "_transitions_panel", None)
            if panel is not None:
                # Find the most-recently-hovered card (cards track _hovered flag)
                ms = int(getattr(panel, "_default_ms", 500))
                # Look for a selected / last-hovered card
                for card in getattr(panel, "_cards", []):
                    if getattr(card, "_hovered", False):
                        return (str(card._ttype), ms)
                # No card hovered — use the first card's type
                cards = getattr(panel, "_cards", [])
                if cards:
                    return (str(cards[0]._ttype), ms)
                return ("dissolve", ms)
            w = w.parent()
        return ("dissolve", 500)

    def _show_transition_menu(self, clip, global_pos) -> None:
        """Right-click menu on a clip's right edge to set/remove transition."""
        menu = QMenu(self)
        cur_type = str(getattr(clip, "transition_out_type", ""))
        cur_ms = int(getattr(clip, "transition_out_ms", 500))

        # --- Add Transition submenu ---
        add_sub = menu.addMenu("Add Transition")
        _TR_MENU_ITEMS = [
            ("dissolve",   f"Cross Dissolve ({cur_ms}ms)"),
            ("fade_black", f"Fade to Black ({cur_ms}ms)"),
            ("fade_white", f"Fade to White ({cur_ms}ms)"),
            ("slide_left", f"Slide Left ({cur_ms}ms)"),
            ("wipe_left",  f"Wipe Left ({cur_ms}ms)"),
            ("zoom_in",    f"Zoom In ({cur_ms}ms)"),
            ("zoom_out",   f"Zoom Out ({cur_ms}ms)"),
        ]
        act_dissolve = act_fade_black = act_fade_white = None
        _tr_acts = {}
        for ttype_k, label_k in _TR_MENU_ITEMS:
            act_k = add_sub.addAction(label_k)
            act_k.setCheckable(True)
            act_k.setChecked(cur_type == ttype_k)
            _tr_acts[ttype_k] = act_k
        act_dissolve = _tr_acts["dissolve"]
        act_fade_black = _tr_acts["fade_black"]
        act_fade_white = _tr_acts["fade_white"]
        add_sub.addSeparator()
        act_custom = add_sub.addAction("Custom duration...")

        act_remove = menu.addAction("Remove Transition")
        act_remove.setEnabled(bool(cur_type))

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        # Check if chosen is one of the transition type actions
        for ttype_k, act_k in _tr_acts.items():
            if chosen is act_k:
                clip.transition_out_type = ttype_k
                clip.transition_out_ms = cur_ms
                self.update()
                return
        if chosen is act_custom:
            from PySide6.QtWidgets import QInputDialog
            val, ok = QInputDialog.getInt(
                self, "Transition Duration", "Duration (ms):",
                cur_ms, 50, 10000, 50,
            )
            if ok:
                clip.transition_out_ms = val
                # Keep type if already set, default to dissolve if not
                if not clip.transition_out_type:
                    clip.transition_out_type = "dissolve"
        elif chosen is act_remove:
            clip.transition_out_type = ""
        else:
            return
        self.update()

    def _fade_under(self, pos: QPoint) -> FadeSegment | None:
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        ms = self._x_to_ms(pos.x())
        for fade in self.track.fades:
            if fade.contains(ms):
                return fade
        return None

    def _show_fade_menu(self, fade: FadeSegment, global_pos) -> None:
        menu = QMenu(self)
        act_in = menu.addAction(tr("veditor.fade_menu.in"))
        act_in.setCheckable(True)
        act_in.setChecked(fade.kind == "in")
        act_out = menu.addAction(tr("veditor.fade_menu.out"))
        act_out.setCheckable(True)
        act_out.setChecked(fade.kind == "out")
        act_both = menu.addAction(tr("veditor.fade_menu.both"))
        act_both.setCheckable(True)
        act_both.setChecked(fade.kind == "both")
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.fade_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_in:
            fade.kind = "in"
        elif chosen is act_out:
            fade.kind = "out"
        elif chosen is act_both:
            fade.kind = "both"
        elif chosen is act_del:
            try:
                self.track.fades.remove(fade)
            except ValueError:
                pass
        else:
            return
        self.update()
        self.fades_changed.emit(self.track.id)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Double-click on a typography / zoom actor opens its editor;
        # on a fade segment, deletes it.
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        zactor, _z = self._zoom_at(pos)
        if zactor is not None:
            self.zoom_double_clicked.emit(self.track.id, zactor.id)
            return
        typo_actor, _zone = self._typography_at(pos)
        if typo_actor is not None:
            self.typography_double_clicked.emit(self.track.id, typo_actor.id)
            return
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return
        ms = self._x_to_ms(pos.x())
        for fade in list(self.track.fades):
            if fade.contains(ms):
                self.track.fades.remove(fade)
                self.update()
                self.fades_changed.emit(self.track.id)
                return

    # ---------- typography actor painting + hit-test ----------

    def _typography_actor_rect(self, actor, strip_rect: QRect) -> QRect:
        """Rect of a typography actor chip in widget coords. Lives as
        a thin strip at the top of the track's timeline rect."""
        x1 = self._ms_to_x(int(actor.start_ms))
        x2 = self._ms_to_x(int(actor.end_ms))
        w = max(2, x2 - x1)
        return QRect(x1, strip_rect.top() + 2, w, self.TYPO_CHIP_H)

    def _zoom_actor_rect(self, zactor: ZoomActor, strip_rect: QRect) -> QRect:
        """Rect of a zoom actor chip in widget coords. Sits at the
        BOTTOM of the timeline strip so it doesn't fight with typography
        at the top."""
        x1 = self._ms_to_x(int(zactor.start_ms))
        x2 = self._ms_to_x(int(zactor.end_ms))
        w = max(2, x2 - x1)
        top = strip_rect.bottom() - self.ZOOM_CHIP_H - 2
        return QRect(x1, top, w, self.ZOOM_CHIP_H)

    def _paint_zoom_actor(
        self, painter: QPainter, zactor: ZoomActor, strip_rect: QRect
    ) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush, QPolygonF
        from PySide6.QtCore import QPointF

        r = self._zoom_actor_rect(zactor, strip_rect)
        if r.width() < 2:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Body — gradient that visually conveys the fade-in / hold /
        # fade-out shape: edges fade from a darker to a fuller blue,
        # so the trapezoid intent reads even before the user touches
        # the inner handles.
        in_x = self._ms_to_x(zactor.start_ms + zactor.zoom_in_ms)
        out_x = self._ms_to_x(zactor.end_ms - zactor.zoom_out_ms)
        # Clamp handles inside the actor rect so paint stays correct
        # even at min span / drag transitions.
        in_x = max(r.left() + 1, min(r.right() - 1, in_x))
        out_x = max(in_x, min(r.right() - 1, out_x))

        # Background fill — light blue band.
        painter.setBrush(QBrush(QColor(74, 155, 238, 80)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

        # Trapezoid: dim outside the in/out handles to visualise the
        # ramp ↔ hold zones (held centre is brightest).
        held_rect = QRect(int(in_x), r.top() + 1,
                          max(1, int(out_x) - int(in_x)), r.height() - 2)
        painter.setBrush(QBrush(QColor(74, 155, 238, 200)))
        painter.drawRect(held_rect)
        # Diagonal triangles for the in / out ramps so the user sees
        # the linear-time mapping.
        if in_x > r.left() + 1:
            ramp = QPolygonF([
                QPointF(r.left() + 1, r.bottom() - 1),
                QPointF(in_x, r.top() + 1),
                QPointF(in_x, r.bottom() - 1),
            ])
            painter.setBrush(QBrush(QColor(74, 155, 238, 160)))
            painter.drawPolygon(ramp)
        if out_x < r.right() - 1:
            ramp = QPolygonF([
                QPointF(out_x, r.top() + 1),
                QPointF(r.right() - 1, r.bottom() - 1),
                QPointF(out_x, r.bottom() - 1),
            ])
            painter.setBrush(QBrush(QColor(255, 122, 74, 160)))
            painter.drawPolygon(ramp)

        # Outer border. Dashed when target rect not picked yet.
        border_color = QColor("#ff7a4a")
        pen = QPen(border_color, 2)
        if not zactor.is_configured():
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

        # Inner fade handles — tall white pins (drawn last so they
        # render on top of the gradient + ramp polys).
        for hx in (in_x, out_x):
            painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            handle_w = 4
            handle_h = r.height() - 4
            painter.drawRoundedRect(
                int(hx) - handle_w // 2, r.top() + 2,
                handle_w, handle_h, 1, 1,
            )

        # Marker + label.
        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(
            r.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "🔍",
        )
        if not zactor.is_configured():
            painter.drawText(
                r.adjusted(6, 0, -6, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                tr("veditor.zoom_actor.unconfigured"),
            )

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    def _paint_typography_actor(
        self, painter: QPainter, actor, strip_rect: QRect
    ) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush

        r = self._typography_actor_rect(actor, strip_rect)
        if r.width() < 2:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Orange → pink gradient (matches the TypographyCard swatch).
        grad = QLinearGradient(r.left(), 0, r.right(), 0)
        grad.setColorAt(0.0, QColor(216, 90, 48, 210))
        grad.setColorAt(1.0, QColor(184, 63, 173, 210))
        painter.setBrush(QBrush(grad))

        border = QColor("#ff7a4a") if actor.id == self._typo_drag_actor_id else QColor("#D85A30")
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

        # "T" badge + preview (leave room for the 4px edge handles so
        # text doesn't collide with them).
        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(9)
        painter.setFont(f)
        painter.drawText(r.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, "T")
        preview = actor.display_text()
        if len(preview) > 18:
            preview = preview[:18] + "…"
        f.setBold(False)
        painter.setFont(f)
        painter.drawText(
            r.adjusted(20, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter,
            preview,
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Edge trim handles — base white for contrast against the
        # orange/pink chip; accent to #D85A30 on hover / drag.
        dragging = self._typo_drag_actor_id == actor.id
        hover = self._hover_typo_actor_id == actor.id
        self._paint_edge_handles(
            painter,
            rect_top=r.top(),
            rect_h=r.height(),
            x_left=r.left() + 1,
            x_right=r.right() - 1,
            left_hot=(hover and self._hover_typo_side == "left")
                or (dragging and self._typo_drag_mode == "resize_l"),
            right_hot=(hover and self._hover_typo_side == "right")
                or (dragging and self._typo_drag_mode == "resize_r"),
            dragging=dragging,
            base_color=QColor(255, 255, 255, 220),
            accent_color=QColor("#ff7a4a"),
        )

    def _zoom_at(self, pos: QPoint) -> "tuple[ZoomActor | None, str]":
        """Hit-test the zoom-actor strip. Returns ``(actor, zone)``:

            "left"      outer left edge — resize total length
            "fade_in"   inner handle at start + zoom_in_ms — fade-in time
            "body"      anywhere else inside — drag to move
            "fade_out"  inner handle at end - zoom_out_ms — fade-out time
            "right"     outer right edge — resize total length

        ``(None, "")`` when the point isn't on any zoom actor."""
        rect = self._timeline_rect()
        handle_grab = 6
        for zactor in getattr(self.track, "zoom_actors", []):
            r = self._zoom_actor_rect(zactor, rect)
            if not r.contains(pos):
                continue
            x = pos.x()
            # Outer resize edges — change start_ms / end_ms.
            if x - r.left() <= self.ZOOM_EDGE_GRAB_PX:
                return zactor, "left"
            if r.right() - x <= self.ZOOM_EDGE_GRAB_PX:
                return zactor, "right"
            # Inner fade-time handles.
            in_x = self._ms_to_x(zactor.start_ms + zactor.zoom_in_ms)
            out_x = self._ms_to_x(zactor.end_ms - zactor.zoom_out_ms)
            if abs(x - in_x) <= handle_grab:
                return zactor, "fade_in"
            if abs(x - out_x) <= handle_grab:
                return zactor, "fade_out"
            return zactor, "body"
        return None, ""

    def _typography_at(self, pos: QPoint) -> "tuple[object, str]":
        """Return ``(actor, zone)`` at ``pos``. ``zone`` is
        ``"left"`` / ``"right"`` (resize grips) or ``"body"``. When
        nothing matches, ``(None, "")``."""
        strip = self._timeline_rect()
        for actor in reversed(getattr(self.track, "typography_actors", [])):
            r = self._typography_actor_rect(actor, strip)
            if not r.contains(pos):
                continue
            if pos.x() - r.left() <= self.TYPO_EDGE_GRAB_PX:
                return actor, "left"
            if r.right() - pos.x() <= self.TYPO_EDGE_GRAB_PX:
                return actor, "right"
            return actor, "body"
        return None, ""

    # ---------- fade segment hit-testing / drag-drop ----------

    def _fade_edge_at(self, x: int, y: int) -> tuple[FadeSegment | None, str]:
        """Return (fade, 'left' / 'right') if the cursor sits on either edge
        of a placed FadeSegment inside the timeline area."""
        if y < self.LABEL_H or y > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        for fade in self.track.fades:
            fx1 = self._ms_to_x(fade.start_ms)
            fx2 = self._ms_to_x(fade.end_ms)
            if abs(x - fx1) <= self.FADE_EDGE_GRAB_PX:
                return fade, "left"
            if abs(x - fx2) <= self.FADE_EDGE_GRAB_PX:
                return fade, "right"
        return None, ""

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasFormat(TRANSITION_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        if md.hasFormat(SPEED_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasFormat(ZOOM_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasFormat(TITLE_PRESET_MIME_TYPE):
            event.acceptProposedAction()
            return
        # Accept any media file (video OR audio); the window will route
        # mismatches to the right track type. Qt does not automatically
        # propagate drags from a dropAccepting child to its parent —
        # so we swallow the event here and emit our own signal.
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        # Transition card: track nearest clip right boundary and highlight it
        if md.hasFormat(TRANSITION_MIME_TYPE):
            event.acceptProposedAction()
            pos = event.position().toPoint()
            self._update_transition_drop_target(pos)
            return
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        if self._drop_target_clip_id is not None:
            self._drop_target_clip_id = None
            self.update()
        super().dragLeaveEvent(event)

    # 30px snap radius for clip right-edge detection during transition drag
    _TRANSITION_DROP_SNAP_PX = 30

    def _update_transition_drop_target(self, pos: QPoint) -> None:
        """Find the clip whose right edge is closest to ``pos`` within the
        snap radius, store its id in ``_drop_target_clip_id``, and repaint."""
        best_id: int | None = None
        best_dist = self._TRANSITION_DROP_SNAP_PX + 1
        for clip in (getattr(self.track, "clips", None) or []):
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                continue
            dist = abs(pos.x() - cr.right())
            if dist < best_dist and cr.top() <= pos.y() <= cr.bottom():
                best_dist = dist
                best_id = int(clip.id)
        if best_id != self._drop_target_clip_id:
            self._drop_target_clip_id = best_id
            self.update()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        # Transition card drop: set clip.transition_out_type / _ms on nearest
        # clip right boundary.
        if md.hasFormat(TRANSITION_MIME_TYPE):
            import json as _json
            try:
                payload = _json.loads(bytes(md.data(TRANSITION_MIME_TYPE)).decode("utf-8"))
                ttype = str(payload.get("type", "dissolve"))
                tms = int(payload.get("ms", 500))
            except Exception:
                ttype = "dissolve"
                tms = 500
            pos = event.position().toPoint()
            self._update_transition_drop_target(pos)
            target_id = self._drop_target_clip_id
            self._drop_target_clip_id = None
            self.update()
            if target_id is not None:
                clip = self._find_clip_by_id(target_id)
                if clip is not None:
                    clip.transition_out_type = ttype
                    clip.transition_out_ms = max(50, tms)
                    self.update()
                    self.speed_changed.emit(self.track.id)  # triggers repaint chain
            event.acceptProposedAction()
            return
        if md.hasFormat(FADE_MIME_TYPE):
            try:
                duration_ms = int(bytes(md.data(FADE_MIME_TYPE)).decode("utf-8"))
            except Exception:
                duration_ms = FadeCard.DEFAULT_DURATION_MS
            duration_ms = max(100, duration_ms)
            if self.track.duration_ms <= 0:
                return
            center_ms = self._x_to_ms(event.position().toPoint().x())
            start = max(0, center_ms - duration_ms // 2)
            end = min(self.track.duration_ms, start + duration_ms)
            if end <= start:
                return
            self.track.fades.append(FadeSegment(start, end))
            self.track.fades.sort(key=lambda f: f.start_ms)
            self.update()
            self.fades_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Typography card drop: add a TextClip actor on this track.
        if md.hasFormat(TEXT_CLIP_MIME):
            if self.track.duration_ms <= 0:
                return
            try:
                duration_ms = int(bytes(md.data(TEXT_CLIP_MIME)).decode("utf-8"))
            except Exception:
                duration_ms = 2000
            duration_ms = max(self.TYPO_MIN_DURATION_MS, duration_ms)
            start = self._x_to_ms(event.position().toPoint().x())
            end = min(self.track.duration_ms, start + duration_ms)
            if end - start < self.TYPO_MIN_DURATION_MS:
                start = max(0, end - self.TYPO_MIN_DURATION_MS)
            if end <= start:
                return
            actor = TextClip(start_ms=start, end_ms=end)
            self.track.typography_actors.append(actor)
            self.track.typography_actors.sort(key=lambda c: c.start_ms)
            self.update()
            self.typography_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Speed card drop: add a SpeedSegment at the selected rate.
        if md.hasFormat(SPEED_MIME_TYPE):
            if self.track.duration_ms <= 0:
                return
            try:
                payload = bytes(md.data(SPEED_MIME_TYPE)).decode("utf-8")
                parts = payload.split("|")
                speed = float(parts[0])
                dur_ms = int(parts[1])
                # Extended payload (v2): "|frame_blend_flag|blend_mode"
                frame_blend = bool(int(parts[2])) if len(parts) > 2 else False
                blend_mode = parts[3] if len(parts) > 3 else "linear"
            except Exception:
                speed = SpeedCard.DEFAULT_SPEED
                dur_ms = SpeedCard.DEFAULT_DURATION_MS
                frame_blend = False
                blend_mode = "linear"
            dur_ms = max(100, dur_ms)
            center_ms = self._x_to_ms(event.position().toPoint().x())
            start = max(0, center_ms - dur_ms // 2)
            end = min(self.track.duration_ms, start + dur_ms)
            if end <= start:
                return
            # Replace any overlapping speed ranges — we can't have two
            # different speeds on the same source ms.
            self.track.speed_segments = [
                seg for seg in self.track.speed_segments
                if seg.end_ms <= start or seg.start_ms >= end
            ]
            self.track.speed_segments.append(
                SpeedSegment(start, end, speed,
                             frame_blend=frame_blend, blend_mode=blend_mode)
            )
            self.track.speed_segments.sort(key=lambda s: s.start_ms)
            self.update()
            self.speed_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Zoom card drop: add a ZoomActor at the drop position with default
        # duration. Target rect is unset until the user clicks → modal.
        if md.hasFormat(ZOOM_MIME_TYPE):
            if self.track.duration_ms <= 0:
                return
            try:
                dur_ms = int(bytes(md.data(ZOOM_MIME_TYPE)).decode("utf-8"))
            except Exception:
                dur_ms = ZoomCard.DEFAULT_DURATION_MS
            dur_ms = max(500, dur_ms)
            center_ms = self._x_to_ms(event.position().toPoint().x())
            start = max(0, center_ms - dur_ms // 2)
            end = min(self.track.duration_ms, start + dur_ms)
            if end <= start:
                return
            new_id = max(
                (z.id for z in self.track.zoom_actors), default=0
            ) + 1
            ramp = max(100, (end - start) // 4)
            actor = ZoomActor(
                id=new_id, start_ms=start, end_ms=end,
                zoom_in_ms=ramp, zoom_out_ms=ramp,
            )
            self.track.zoom_actors.append(actor)
            self.track.zoom_actors.sort(key=lambda z: z.start_ms)
            self.update()
            self.zoom_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            # The actor renders with a dashed outline + "no region" label
            # until the user double-clicks it to open the picker — drop
            # itself shouldn't auto-pop the modal.
            event.acceptProposedAction()
            return
        # Title preset card drop: create a TextClip with preset style +
        # animation settings at the drop position on the typography lane.
        if md.hasFormat(TITLE_PRESET_MIME_TYPE):
            if self.track.duration_ms <= 0:
                event.ignore()
                return
            import json as _json
            try:
                preset = _json.loads(bytes(md.data(TITLE_PRESET_MIME_TYPE)).decode("utf-8"))
            except Exception:
                event.ignore()
                return
            duration_ms = max(self.TYPO_MIN_DURATION_MS, int(preset.get("duration_ms", 3000)))
            start = self._x_to_ms(event.position().toPoint().x())
            end = min(self.track.duration_ms, start + duration_ms)
            if end - start < self.TYPO_MIN_DURATION_MS:
                start = max(0, end - self.TYPO_MIN_DURATION_MS)
            if end <= start:
                event.ignore()
                return
            actor = TextClip(start_ms=start, end_ms=end)
            actor.text = str(preset.get("text", ""))
            # Apply style fields from preset
            actor.style.font_size = int(preset.get("font_size", 48))
            actor.style.color = str(preset.get("color", "#ffffff"))
            actor.style.position_x = float(preset.get("x_norm", 0.5))
            actor.style.position_y = float(preset.get("y_norm", 0.5))
            bg = preset.get("bg_color", "")
            if bg:
                actor.style.background_color = str(bg)
            # Apply animation
            actor.animation.in_animation = str(preset.get("preset_id_in", "fade-in"))
            actor.animation.out_animation = str(preset.get("preset_id_out", "fade-out"))
            self.track.typography_actors.append(actor)
            self.track.typography_actors.sort(key=lambda c: c.start_ms)
            self.update()
            self.typography_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Any media file dropped onto this row — let the window route.
        # Video → fill empty track or add new. Audio → add new audio track.
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    self.media_dropped.emit(self.track.id, p)
                    event.acceptProposedAction()
                    return
        event.ignore()


class TextLaneRow(QWidget):
    """Dedicated timeline lane for text clips.

    Sits between the timeline ruler and the video tracks. Renders all
    clips from a ``TextTrack`` as rounded chips with the spec's orange
    → pink gradient, plus an IN / HOLD / OUT timing bar underneath the
    text preview. Handles drag-drop of the TypographyCard, clip moves
    (drag body) and resizes (drag left/right edge), context menu, and
    double-click to open the typography editor."""

    MARGIN = 10                    # matches TimelineRuler.MARGIN
    ROW_HEIGHT = 58
    EDGE_GRIP_PX = 8               # left/right edge zone for resize
    MIN_CLIP_MS = 200              # can't shrink a clip below this

    clip_double_clicked = Signal(int)    # clip_id
    clip_context_menu = Signal(int, object)   # clip_id, QPoint (global)
    clips_changed = Signal()             # geometry / list mutation

    def __init__(self, track: "TextTrack") -> None:
        super().__init__()
        self.track = track
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._duration_ms: int = 0

        # Interaction state
        self._hover_clip_id: int | None = None
        self._hover_edge: str | None = None       # "left" / "right" / None
        self._active_clip_id: int | None = None
        self._drag_mode: str | None = None        # "move" / "resize_l" / "resize_r"
        self._drag_anchor_ms: int = 0             # mouse-down project ms
        self._drag_orig_start_ms: int = 0
        self._drag_orig_end_ms: int = 0

        self.setFixedHeight(self.ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.setToolTip(tr("veditor.typo_lane.hint"))

    # ---- scaling / width ----

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()
        self.update()

    def set_project_duration(self, ms: int) -> None:
        self._duration_ms = max(0, int(ms))
        self._recalc_width()
        self.update()

    def set_min_width(self, w: int) -> None:
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, int(w)))
        self.update()

    def _recalc_width(self) -> None:
        span_ms = max(self._duration_ms, self.track.extent_ms())
        w = int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, w))

    # ---- coordinate helpers ----

    def _ms_to_x(self, ms: int) -> int:
        return int(self.MARGIN + max(0, ms) / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _clip_rect(self, clip: TextClip) -> QRect:
        x0 = self._ms_to_x(clip.start_ms)
        x1 = self._ms_to_x(clip.end_ms)
        return QRect(x0, 6, max(2, x1 - x0), self.ROW_HEIGHT - 12)

    def _hit_clip(self, pos: QPoint) -> tuple[TextClip | None, str]:
        """Return ``(clip, zone)`` for the clip under ``pos``. ``zone``
        is ``"left"`` / ``"right"`` (edge grips) or ``"body"``. When no
        clip matches, ``(None, "")``."""
        # Walk right-to-left so later (stacked-on-top) clips win.
        for clip in reversed(self.track.clips):
            r = self._clip_rect(clip)
            if not r.contains(pos):
                continue
            if pos.x() - r.left() <= self.EDGE_GRIP_PX:
                return clip, "left"
            if r.right() - pos.x() <= self.EDGE_GRIP_PX:
                return clip, "right"
            return clip, "body"
        return None, ""

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background lane strip — 80% brightness stripes (same as empty track)
        bg = self.rect()
        StripedHost._draw_stripes(
            painter, bg, StripedHost.BG_80, StripedHost.STRIPE_80,
        )

        # Each clip
        for clip in self.track.clips:
            self._paint_clip(painter, clip)

        # Pro-only export badge — Free users see this whenever the
        # lane has clips, so they understand text is preview-only.
        from app import tier
        if (
            tier.is_locked("export.typography")
            and len(self.track.clips) > 0
        ):
            self._paint_pro_export_badge(painter)

    def _paint_pro_export_badge(self, painter: QPainter) -> None:
        """Right-aligned chip telling Free users typography is
        excluded from export. Painted on top of clips so it stays
        visible even on a busy lane."""
        text = tr("veditor.typo_lane.pro_export_badge")
        f = QFont(painter.font())
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 8, 3
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        chip_w = text_w + pad_x * 2
        chip_h = text_h + pad_y * 2
        chip_rect = QRect(
            self.width() - chip_w - 8,
            (self.height() - chip_h) // 2,
            chip_w, chip_h,
        )
        # Chip body — semi-opaque dark with amber border so it reads
        # as "warning / locked" rather than "active".
        painter.setBrush(QColor(20, 20, 28, 220))
        painter.setPen(QPen(QColor("#D8A030"), 1))
        painter.drawRoundedRect(chip_rect, 6, 6)
        painter.setPen(QPen(QColor("#FFD080")))
        painter.drawText(
            chip_rect, Qt.AlignmentFlag.AlignCenter, text,
        )

    def _paint_clip(self, painter: QPainter, clip: TextClip) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush

        r = self._clip_rect(clip)
        if r.width() < 2:
            return

        # Background gradient
        grad = QLinearGradient(r.left(), 0, r.right(), 0)
        grad.setColorAt(0.0, QColor(216, 90, 48, 180))    # orange
        grad.setColorAt(1.0, QColor(184, 63, 173, 180))   # pink
        painter.setBrush(QBrush(grad))

        # Border — brighter when this clip is the active (drag) target
        border = QColor("#ff7a4a") if clip.id == self._active_clip_id else QColor("#D85A30")
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 4, 4)

        # T-icon badge (small) + text preview
        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(10)
        painter.setFont(f)
        painter.drawText(
            r.adjusted(6, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "T",
        )

        f.setBold(False)
        f.setPointSize(9)
        painter.setFont(f)
        preview = clip.display_text()
        if len(preview) > 22:
            preview = preview[:22] + "…"
        painter.drawText(
            r.adjusted(20, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            preview,
        )

        # IN / HOLD / OUT timing bar at the bottom of the chip
        bar_margin = 5
        bar_rect = QRect(
            r.left() + bar_margin,
            r.bottom() - 8,
            max(1, r.width() - 2 * bar_margin),
            4,
        )
        total_s = max(0.001, clip.duration_s)
        in_ratio = max(0.0, min(1.0, clip.animation.in_duration / total_s))
        out_ratio = max(0.0, min(1.0, clip.animation.out_duration / total_s))
        if in_ratio + out_ratio > 1.0:
            # Protect against shorter-than-animation clips.
            scale = 1.0 / (in_ratio + out_ratio)
            in_ratio *= scale
            out_ratio *= scale

        in_w = int(bar_rect.width() * in_ratio)
        out_w = int(bar_rect.width() * out_ratio)
        hold_w = max(0, bar_rect.width() - in_w - out_w)

        if in_w > 0:
            painter.fillRect(
                QRect(bar_rect.left(), bar_rect.top(), in_w, bar_rect.height()),
                QColor("#ff7a4a"),
            )
        if hold_w > 0:
            painter.fillRect(
                QRect(bar_rect.left() + in_w, bar_rect.top(), hold_w, bar_rect.height()),
                QColor(255, 255, 255, 70),
            )
        if out_w > 0:
            painter.fillRect(
                QRect(bar_rect.right() - out_w, bar_rect.top(), out_w, bar_rect.height()),
                QColor("#b04722"),
            )

    # ---- mouse interaction ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        clip, zone = self._hit_clip(pos)
        if clip is None:
            return
        self._active_clip_id = clip.id
        self._drag_anchor_ms = self._x_to_ms(pos.x())
        self._drag_orig_start_ms = int(clip.start_ms)
        self._drag_orig_end_ms = int(clip.end_ms)
        if zone == "left":
            self._drag_mode = "resize_l"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "right":
            self._drag_mode = "resize_r"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self._drag_mode = "move"
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_mode and self._active_clip_id is not None:
            clip = self.track.find(self._active_clip_id)
            if clip is None:
                self._drag_mode = None
                return
            delta_ms = self._x_to_ms(pos.x()) - self._drag_anchor_ms
            if self._drag_mode == "move":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                duration = self._drag_orig_end_ms - self._drag_orig_start_ms
                clip.start_ms = new_start
                clip.end_ms = new_start + duration
            elif self._drag_mode == "resize_l":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                new_start = min(new_start, clip.end_ms - self.MIN_CLIP_MS)
                clip.start_ms = new_start
            elif self._drag_mode == "resize_r":
                new_end = max(
                    clip.start_ms + self.MIN_CLIP_MS,
                    self._drag_orig_end_ms + delta_ms,
                )
                clip.end_ms = new_end
            self._recalc_width()
            self.clips_changed.emit()
            self.update()
            return

        # Idle hover: cursor feedback
        _, zone = self._hit_clip(pos)
        if zone in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "body":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_mode is not None:
            # Sort by start_ms to keep the internal list ordered.
            self.track.clips.sort(key=lambda c: c.start_ms)
            self.clips_changed.emit()
        self._drag_mode = None
        self._active_clip_id = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        clip, _zone = self._hit_clip(pos)
        if clip is not None:
            self.clip_double_clicked.emit(clip.id)

    def contextMenuEvent(self, event) -> None:
        pos = event.pos()
        clip, _zone = self._hit_clip(pos)
        if clip is None:
            event.ignore()
            return
        self.clip_context_menu.emit(clip.id, event.globalPos())
        event.accept()

    # ---- drag-drop (T-card) ----

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        if not md.hasFormat(TEXT_CLIP_MIME):
            super().dropEvent(event)
            return
        try:
            duration_ms = int(bytes(md.data(TEXT_CLIP_MIME)).decode("utf-8"))
        except Exception:
            duration_ms = 2000

        drop_ms = self._x_to_ms(event.position().toPoint().x())
        clip = TextClip(
            start_ms=max(0, drop_ms),
            end_ms=max(0, drop_ms) + max(self.MIN_CLIP_MS, duration_ms),
        )
        self.track.add_clip(clip)
        self._recalc_width()
        self.clips_changed.emit()
        self.update()
        event.acceptProposedAction()
        # Hand back the id so the caller can immediately open the editor.
        self.clip_double_clicked.emit(clip.id)


class _TextPreviewItem:
    """Lightweight QGraphicsItem that paints a TextClip preview.

    Implemented via composition with a QGraphicsRectItem so we don't
    need to subclass QGraphicsItem (which is awkward in PySide6 because
    the abstract methods make instantiation finicky).

    ``bg_provider`` is a zero-arg callable returning a QPixmap to paint
    behind the text (the editor uses this to show the video frame at the
    current playhead). Returning ``None`` falls back to a solid black
    backdrop."""

    def __init__(self, clip: TextClip, bg_provider=None, time_provider=None):
        from PySide6.QtWidgets import QGraphicsRectItem
        self.clip = clip
        self._bg_provider = bg_provider
        # ``time_provider`` returns the current playback time (seconds
        # since the clip's start) used to drive the IN/HOLD/OUT
        # animation. Returning ``None`` means "show the static
        # final-state result" (i.e. no animation applied).
        self._time_provider = time_provider

        self._root = QGraphicsRectItem(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._root.setBrush(QBrush(QColor("#000")))
        self._root.setPen(QPen(Qt.PenStyle.NoPen))

        # Custom paint via overriding paint() on the rect item — easiest
        # cross-version Qt path.
        original_paint = self._root.paint

        def _paint(painter, option, widget=None):
            original_paint(painter, option, widget)
            self._draw_background(painter)
            self._draw_text(painter)

        self._root.paint = _paint

    def graphics_item(self):
        return self._root

    def refresh(self):
        self._root.update()

    def _draw_background(self, painter: QPainter) -> None:
        if self._bg_provider is None:
            return
        try:
            pm = self._bg_provider()
        except Exception:
            return
        if pm is None or pm.isNull():
            return
        scene_w, scene_h = 1920.0, 1080.0
        pw, ph = pm.width(), pm.height()
        if pw <= 0 or ph <= 0:
            return
        scale = min(scene_w / pw, scene_h / ph)
        draw_w = pw * scale
        draw_h = ph * scale
        ox = (scene_w - draw_w) / 2.0
        oy = (scene_h - draw_h) / 2.0
        painter.drawPixmap(int(ox), int(oy), int(draw_w), int(draw_h), pm)

    def _draw_text(self, painter: QPainter) -> None:
        from PySide6.QtGui import QFontMetrics, QPainterPath
        from app.typo_animations import (
            compute_clip_transform, compute_clip_glyph_transforms,
            compute_clip_layers, TextTransform,
        )
        clip = self.clip
        text = clip.text or "Enter text…"
        style = clip.style

        scene_w, scene_h = 1920.0, 1080.0
        cx = float(style.position_x) * scene_w
        cy = float(style.position_y) * scene_h

        # Resolve play time; ``None`` = paused (steady HOLD state).
        play_time = None
        if self._time_provider is not None:
            play_time = self._time_provider()

        # Multi-layer dispatch (RGB split / glitch animations) — drawn
        # once per layer with each layer's color + offset.
        if play_time is not None:
            layers = compute_clip_layers(clip, float(play_time))
            if layers is not None:
                self._draw_text_layers(painter, text, style, cx, cy, layers)
                return

        # Per-glyph dispatch: if the active animation is per-glyph,
        # rendering branches into a different path that iterates each
        # character with its own transform around its own pivot.
        glyph_xfs = None
        if play_time is not None:
            glyph_xfs = compute_clip_glyph_transforms(
                clip, float(play_time), len(text or "")
            )
        if glyph_xfs is not None:
            self._draw_text_perglyph(painter, text, style, cx, cy, glyph_xfs)
            return

        # Whole-text fast path.
        if play_time is not None:
            xf = compute_clip_transform(clip, float(play_time)) or TextTransform.identity()
        else:
            xf = TextTransform.identity()

        # Apply opacity globally for the text drawing block; geometric
        # transform pivots on the text's center (cx, cy).
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
        painter.translate(cx + xf.offset_x, cy + xf.offset_y)
        if abs(xf.rotation_deg) > 0.05:
            painter.rotate(xf.rotation_deg)
        if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
            painter.scale(xf.scale_x, xf.scale_y)
        painter.translate(-cx, -cy)

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            from PySide6.QtGui import QFont as _QFont
            font.setLetterSpacing(_QFont.SpacingType.AbsoluteSpacing,
                                  float(style.letter_spacing))
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Multi-line: split on newlines, render line-by-line.
        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))

        # Top-left of the text block
        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # For each line: shadow → outline → fill
        for i, ln in enumerate(lines):
            ln_w = fm.horizontalAdvance(ln)
            # Honor alignment within the bounding block.
            if style.alignment == "left":
                lx = block_x
            elif style.alignment == "right":
                lx = block_x + (widest - ln_w)
            else:
                lx = block_x + (widest - ln_w) / 2.0
            ly = block_y + i * line_h + fm.ascent()

            # Shadow
            if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                painter.setPen(QColor(style.shadow_color))
                painter.drawText(
                    int(lx + style.shadow_offset_x),
                    int(ly + style.shadow_offset_y),
                    ln,
                )

            # Outline
            if style.outline_color and style.outline_width and style.outline_width > 0:
                path = QPainterPath()
                path.addText(lx, ly, font, ln)
                pen = QPen(QColor(style.outline_color))
                pen.setWidth(int(style.outline_width))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # Fill
            painter.setPen(QColor(style.color or "#FFFFFF"))
            painter.drawText(int(lx), int(ly), ln)

        # Close the save() that opened the animation transform block.
        painter.restore()

    def _draw_text_perglyph(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        glyph_xfs: list,
    ) -> None:
        """Render a Folding-style per-glyph animation. Each char gets
        its own transform around its own pivot. Effects (shadow /
        outline / fill) are drawn per-character so rotation pivots
        stay correct."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                float(style.letter_spacing),
            )
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Lay out chars by line (multi-line text — newlines split).
        # Per-glyph animations don't make as much sense for multi-line,
        # but we still place them sensibly.
        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))

        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect (drawn once, behind every glyph)
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # Walk every char in order, mapping it to the i-th transform.
        # Newlines bump the cursor to the next line and don't consume
        # an entry from glyph_xfs (the animation generator received the
        # full character count including \n; we just skip the visible
        # render for \n). Keep the indices aligned by iterating with i.
        char_idx = 0
        for line_no, ln in enumerate(lines):
            ln_w = fm.horizontalAdvance(ln)
            if style.alignment == "left":
                lx = block_x
            elif style.alignment == "right":
                lx = block_x + (widest - ln_w)
            else:
                lx = block_x + (widest - ln_w) / 2.0
            ly = block_y + line_no * line_h + fm.ascent()

            cursor_x = lx
            for ch in ln:
                gx = cursor_x
                gw = fm.horizontalAdvance(ch)
                if char_idx >= len(glyph_xfs):
                    xf = glyph_xfs[-1] if glyph_xfs else None
                else:
                    xf = glyph_xfs[char_idx]
                char_idx += 1

                if xf is None or ch.strip() == "":
                    # Whitespace still advances the cursor but we don't
                    # bother drawing.
                    cursor_x += gw
                    continue

                pivot_px_x = gx + gw * float(xf.pivot_x)
                # pivot_y: 0=top of glyph (above baseline), 1=bottom.
                # baseline is at ly; ascent above, descent below.
                pivot_px_y = (ly - fm.ascent()) + fm.height() * float(xf.pivot_y)

                painter.save()
                painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
                painter.translate(
                    pivot_px_x + xf.offset_x,
                    pivot_px_y + xf.offset_y,
                )
                if abs(xf.rotation_deg) > 0.05:
                    painter.rotate(xf.rotation_deg)
                if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
                    painter.scale(xf.scale_x, xf.scale_y)
                painter.translate(-pivot_px_x, -pivot_px_y)

                # Shadow (per char)
                if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                    painter.setPen(QColor(style.shadow_color))
                    painter.drawText(
                        int(gx + style.shadow_offset_x),
                        int(ly + style.shadow_offset_y),
                        ch,
                    )

                # Outline
                if style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(gx, ly, font, ch)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                # Fill — honor color override if the glyph carries one,
                # unless the user has locked the clip to a single color.
                if getattr(self.clip.animation, "mono_color", False):
                    fill_color = style.color or "#FFFFFF"
                else:
                    fill_color = xf.color_override or style.color or "#FFFFFF"
                painter.setPen(QColor(fill_color))
                painter.drawText(int(gx), int(ly), ch)

                painter.restore()
                cursor_x += gw
            # Skip the implicit \n character index when there are
            # multiple lines — the global character count we pass to
            # the animation generator includes \n delimiters.
            if line_no < len(lines) - 1:
                char_idx += 1

    def _draw_text_layers(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        layers: list,
    ) -> None:
        """Multi-layer rendering — re-draws the entire text once per
        LayerTransform (different colour + offset). Used by glitch /
        RGB-split style animations."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                float(style.letter_spacing),
            )
        painter.setFont(font)
        fm = QFontMetrics(font)

        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))
        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect drawn once (under all layers).
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # Iterate layers back-to-front. Mono-color flag forces every
        # layer to honor style.color (effectively collapsing the RGB
        # split — useful when users want the glitch motion without
        # the chromatic aberration).
        mono = bool(getattr(self.clip.animation, "mono_color", False))
        for layer in layers:
            painter.save()
            painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
            painter.translate(layer.offset_x, layer.offset_y)

            if mono:
                fill_color = style.color or "#FFFFFF"
            else:
                fill_color = layer.color_override or style.color or "#FFFFFF"

            for i, ln in enumerate(lines):
                ln_w = fm.horizontalAdvance(ln)
                if style.alignment == "left":
                    lx = block_x
                elif style.alignment == "right":
                    lx = block_x + (widest - ln_w)
                else:
                    lx = block_x + (widest - ln_w) / 2.0
                ly = block_y + i * line_h + fm.ascent()

                # Outline only on the topmost layer (last iteration)
                # so the chromatic split stays visible underneath.
                is_top = layer is layers[-1]
                if is_top and style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(lx, ly, font, ln)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                painter.setPen(QColor(fill_color))
                painter.drawText(int(lx), int(ly), ln)

            painter.restore()


class _PreviewView(QScrollArea):
    """Wraps a QGraphicsView; re-fits scene to view on resize."""

    def __init__(self):
        from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        self._scene = QGraphicsScene(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._scene.setBackgroundBrush(QBrush(QColor("#000")))
        self._gview = QGraphicsView(self._scene)
        self._gview.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._gview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setStyleSheet("QGraphicsView { background-color: #000; border: none; }")
        self.setWidget(self._gview)

    def add_item(self, item):
        self._scene.addItem(item)

    def fit(self):
        self._gview.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit()


class _FontPickerDelegate:
    """Item delegate factory for the font list. Each row shows the
    family name in the default UI font (so users can read the name
    even when the font itself has no Latin glyphs), plus a sample
    string rendered IN the actual font."""

    SAMPLE_TEXT = "Aa Bb 한글 漢字 1234"
    ROW_HEIGHT = 40

    @classmethod
    def install(cls, list_widget) -> None:
        """Attach a QStyledItemDelegate on the given QListWidget."""
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QStyledItemDelegate, QStyle

        class _Delegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                painter.save()
                family = index.data(Qt.ItemDataRole.DisplayRole) or ""
                kind = index.data(Qt.ItemDataRole.UserRole) or "font"

                # Background
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, QColor(COLOR_ACCENT_BLUE))
                    name_color = QColor(COLOR_TEXT_PRIMARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)
                else:
                    painter.fillRect(option.rect, QColor(COLOR_BG_L4))
                    name_color = QColor(COLOR_TEXT_TERTIARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)

                if kind == "header":
                    # Section header (non-selectable)
                    f = QFont()
                    f.setBold(True)
                    f.setPointSize(8)
                    painter.setFont(f)
                    painter.setPen(QColor(COLOR_TEXT_TERTIARY))
                    painter.drawText(
                        option.rect.adjusted(10, 0, -8, 0),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        family,
                    )
                    painter.restore()
                    return

                # Top line: family name in the default UI font (small).
                name_font = QFont()
                name_font.setPointSize(8)
                painter.setFont(name_font)
                painter.setPen(name_color)
                painter.drawText(
                    option.rect.adjusted(10, 3, -8, 0),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    family,
                )

                # Bottom line: sample text rendered in this font.
                sample_font = QFont(family, 12)
                painter.setFont(sample_font)
                painter.setPen(sample_color)
                painter.drawText(
                    option.rect.adjusted(10, 16, -8, -3),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    _FontPickerDelegate.SAMPLE_TEXT,
                )
                painter.restore()

            def sizeHint(self, option, index):
                kind = index.data(Qt.ItemDataRole.UserRole)
                if kind == "header":
                    return QSize(200, 22)
                return QSize(200, _FontPickerDelegate.ROW_HEIGHT)

        delegate = _Delegate(list_widget)
        list_widget.setItemDelegate(delegate)
        # Keep a reference so the delegate isn't GC'd when our caller
        # returns — Qt only takes a weak handle.
        list_widget._delegate_ref = delegate


class _FontPickerButton(QWidget):
    """Compact font picker: a button that shows the current family
    rendered in its own typeface, plus a ▾ chevron. Clicking opens a
    popup frame (anchored below the button) with a search field and
    the same scrollable list used in the previous implementation.
    Selection commits the change and closes the popup."""

    font_changed = Signal(str)

    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def __init__(self, current_family: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family = current_family
        self._popup: QWidget | None = None
        self._list = None
        self._search = None

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("FontPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_family(self) -> str:
        return self._family

    def set_family(self, family: str) -> None:
        if family != self._family:
            self._family = family
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        f = QFont(self._family, 11)
        self._btn.setFont(f)
        self._btn.setStyleSheet(
            f"QPushButton#FontPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; }}"
            f"QPushButton#FontPickerBtn:hover {{ border-color: #6a6a72; }}"
        )
        # Right-arrow chevron at the right edge.
        self._btn.setText(f"{self._family}     ▾")

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        from PySide6.QtCore import QTimer
        if self._popup is None:
            self._build_popup()
        # Position the popup just below the button, matching its width
        # (with a sensible minimum so the list is usable).
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 320)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()
        QTimer.singleShot(0, self._scroll_to_current)

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import QFrame, QLineEdit, QListWidget, QListWidgetItem
        from PySide6.QtGui import QFontDatabase

        # WindowType.Popup makes the frame auto-dismiss on outside
        # clicks and not steal focus from its parent dialog.
        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("FontPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#FontPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.font_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        _FontPickerDelegate.install(self._list)
        v.addWidget(self._list, 1)

        # Populate
        available = set(QFontDatabase.families())
        used: set[str] = set()
        pinned = [f for f in self.PINNED_FONTS if f in available]
        if pinned:
            hdr = QListWidgetItem(tr("veditor.typo_editor.font_recommended"))
            hdr.setData(Qt.ItemDataRole.UserRole, "header")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(hdr)
            for fam in pinned:
                used.add(fam)
                it = QListWidgetItem(fam)
                self._list.addItem(it)
                if fam == self._family:
                    self._list.setCurrentItem(it)
        all_hdr = QListWidgetItem(tr("veditor.typo_editor.font_all"))
        all_hdr.setData(Qt.ItemDataRole.UserRole, "header")
        all_hdr.setFlags(Qt.ItemFlag.NoItemFlags)
        self._list.addItem(all_hdr)
        for fam in sorted(available):
            if fam in used:
                continue
            it = QListWidgetItem(fam)
            self._list.addItem(it)
            if fam == self._family:
                self._list.setCurrentItem(it)

        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)

    def _on_item_clicked(self, item) -> None:
        if item is None:
            return
        if item.data(Qt.ItemDataRole.UserRole) == "header":
            return
        self._family = item.text()
        self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.font_changed.emit(self._family)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for i in range(self._list.count()):
            it = self._list.item(i)
            kind = it.data(Qt.ItemDataRole.UserRole)
            if kind == "header":
                it.setHidden(bool(needle))
                continue
            it.setHidden(bool(needle) and needle not in it.text().lower())

    def _scroll_to_current(self) -> None:
        if self._list is None:
            return
        cur = self._list.currentItem()
        if cur is not None:
            self._list.scrollToItem(
                cur, self._list.ScrollHint.PositionAtCenter,
            )


class ScopesPanel(QWidget):
    """DaVinci-style scopes panel — dropdown of Histogram / Parade /
    Waveform / Vectorscope. Subscribes to the player's frame_ready
    signal and re-renders the active scope from the latest frame."""

    SCOPE_W = 360
    SCOPE_H = 220

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._latest_rgb = None
        self._kind = "histogram"
        self.setFixedHeight(self.SCOPE_H + 38)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title = QLabel(tr("veditor.scopes.title"))
        title.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; font-weight: 600;"
        )
        head.addWidget(title)
        head.addStretch(1)
        from PySide6.QtWidgets import QComboBox
        self._kind_combo = QComboBox()
        for kid, key in (
            ("histogram",   "veditor.scopes.histogram"),
            ("parade",      "veditor.scopes.parade"),
            ("waveform",    "veditor.scopes.waveform"),
            ("vectorscope", "veditor.scopes.vectorscope"),
        ):
            self._kind_combo.addItem(tr(key), userData=kid)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        head.addWidget(self._kind_combo)
        outer.addLayout(head)

        self._image_label = QLabel()
        self._image_label.setFixedSize(self.SCOPE_W, self.SCOPE_H)
        self._image_label.setStyleSheet(
            f"background-color: #0a0a0e; border: 1px solid {COLOR_BORDER_DEFAULT};"
        )
        outer.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player frame stream → recompute current scope.
        self._player.frame_ready.connect(self._on_frame_ready)

    def _on_kind_changed(self) -> None:
        self._kind = self._kind_combo.currentData() or "histogram"
        # Re-render with the cached frame, if any.
        if self._latest_rgb is not None:
            self._render_now()

    def _on_frame_ready(self, qimg) -> None:
        """Cache the RGB array from the player and refresh the scope.
        We pull pixel bytes via QImage's bits() — fast enough at 1080p
        for the modest scope canvas."""
        try:
            import numpy as np
            # Force RGB888 layout so bits() is plain RGB bytes.
            img = qimg.convertToFormat(qimg.Format.Format_RGB888)
            w, h = img.width(), img.height()
            ptr = img.constBits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 3)
            arr = arr.reshape((h, w, 3))
            self._latest_rgb = arr.copy()      # decouple from Qt buffer
            self._render_now()
        except Exception:
            pass

    def _render_now(self) -> None:
        if self._latest_rgb is None:
            return
        from app.color_scopes import render_scope
        out = render_scope(self._kind, self._latest_rgb,
                           self.SCOPE_W, self.SCOPE_H)
        h, w = out.shape[:2]
        from PySide6.QtGui import QImage as _QI, QPixmap as _QP
        qimg = _QI(out.data, w, h, w * 3, _QI.Format.Format_RGB888).copy()
        self._image_label.setPixmap(_QP.fromImage(qimg))


class _LumaDial(QWidget):
    """Thin horizontal drag control for per-region luma adjustment.
    Maps drag position to -100..100 range."""
    value_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0   # -100..100
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_val = 0
        self.setFixedHeight(16)
        self.setMinimumWidth(80)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip("Drag to adjust luma (double-click to reset)")

    def set_value(self, v, *, emit=True):
        v = max(-100, min(100, int(v)))
        if v == self._value:
            return
        self._value = v
        self.update()
        if emit:
            self.value_changed.emit(v)

    def value(self):
        return self._value

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = e.position().x()
            self._drag_start_val = self._value

    def mouseMoveEvent(self, e):
        if self._dragging:
            dx = e.position().x() - self._drag_start_x
            new_val = int(self._drag_start_val + dx * 1.5)
            self.set_value(new_val)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def mouseDoubleClickEvent(self, e):
        self.set_value(0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background track
        p.fillRect(0, 0, w, h, QColor(20, 20, 28))

        # Filled portion (from center)
        cx = w // 2
        fill_x = int(cx + self._value / 100.0 * (w // 2 - 4))
        if fill_x > cx:
            p.fillRect(cx, 2, fill_x - cx, h - 4, QColor(80, 140, 200, 160))
        elif fill_x < cx:
            p.fillRect(fill_x, 2, cx - fill_x, h - 4, QColor(80, 140, 200, 160))

        # Center line
        p.setPen(QPen(QColor(60, 60, 80), 1))
        p.drawLine(cx, 1, cx, h - 2)

        # Indicator dot
        ind_x = int(cx + self._value / 100.0 * (cx - 4))
        p.setPen(QPen(QColor(0, 0, 0, 80), 1))
        p.setBrush(QColor(200, 200, 220))
        p.drawEllipse(ind_x - 4, h // 2 - 4, 8, 8)
        p.end()


class _HueCurveWidget(QWidget):
    """DaVinci-style Hue-vs-Hue curve editor.

    X axis: input hue 0..360° (background painted as a rainbow strip).
    Y axis: hue rotation -180..+180° (centre line = no change).

    Default control points cover the six primary hues (R/Y/G/C/B/M)
    with delta = 0; users drag a point up/down to rotate that hue.
    Double-click adds a point, right-click on a point removes it.
    Emits ``points_changed(list)`` whenever the curve mutates.
    """

    points_changed = Signal(list)

    DEFAULT_HUES = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    HANDLE_R = 4
    GRAB_PX = 9
    HEIGHT = 108
    MAX_WIDTH = 480

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(self.HEIGHT)
        self.setMaximumHeight(self.HEIGHT)
        self.setMinimumWidth(280)
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setMouseTracking(True)
        # Each point is (input_hue 0..360, delta_hue -180..180).
        self._points: list[list[float]] = [
            [h, 0.0] for h in self.DEFAULT_HUES
        ]
        self._dragging_idx: int | None = None
        self._selected_idx: int | None = None

    # ---- public ----

    def points(self) -> list[tuple[float, float]]:
        return [(p[0], p[1]) for p in self._points]

    def set_points(self, pts: list[tuple[float, float]]) -> None:
        if pts:
            self._points = [[float(h), float(d)] for h, d in pts]
        else:
            self._points = [[h, 0.0] for h in self.DEFAULT_HUES]
        self._points.sort(key=lambda p: p[0])
        self.update()

    def reset(self) -> None:
        self._points = [[h, 0.0] for h in self.DEFAULT_HUES]
        self._dragging_idx = None
        self._selected_idx = None
        self.update()
        self.points_changed.emit(self.points())

    # ---- coords ----

    def _hue_to_x(self, h: float) -> float:
        w = self.width() - 12
        return 6 + (h / 360.0) * w

    def _x_to_hue(self, x: float) -> float:
        w = self.width() - 12
        return max(0.0, min(360.0, (x - 6) / w * 360.0))

    def _delta_to_y(self, d: float) -> float:
        h = self.height() - 12
        # delta=0 → centre; +180 → top; -180 → bottom
        return 6 + h * (1.0 - (d + 180.0) / 360.0)

    def _y_to_delta(self, y: float) -> float:
        h = self.height() - 12
        return max(-180.0, min(180.0,
                               (1.0 - (y - 6) / h) * 360.0 - 180.0))

    def _point_at(self, pos) -> int | None:
        from math import hypot
        for i, (hue, dlt) in enumerate(self._points):
            x = self._hue_to_x(hue)
            y = self._delta_to_y(dlt)
            if hypot(pos.x() - x, pos.y() - y) <= self.GRAB_PX:
                return i
        return None

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._point_at(event.position().toPoint())
            if idx is not None:
                self._dragging_idx = idx
                self._selected_idx = idx
                self.update()
            else:
                # Click on empty space inside the curve area = add point.
                p = event.position().toPoint()
                hue = self._x_to_hue(p.x())
                dlt = self._y_to_delta(p.y())
                self._points.append([hue, dlt])
                self._points.sort(key=lambda q: q[0])
                self._dragging_idx = next(
                    (i for i, q in enumerate(self._points)
                     if abs(q[0] - hue) < 1e-3 and abs(q[1] - dlt) < 1e-3),
                    None,
                )
                self._selected_idx = self._dragging_idx
                self.update()
                self.points_changed.emit(self.points())
        elif event.button() == Qt.MouseButton.RightButton:
            idx = self._point_at(event.position().toPoint())
            # Don't allow deleting all six default points; require ≥2.
            if idx is not None and len(self._points) > 2:
                del self._points[idx]
                self._dragging_idx = None
                self._selected_idx = None
                self.update()
                self.points_changed.emit(self.points())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_idx is None:
            return
        p = event.position().toPoint()
        hue = self._x_to_hue(p.x())
        dlt = self._y_to_delta(p.y())
        self._points[self._dragging_idx][0] = hue
        self._points[self._dragging_idx][1] = dlt
        # Re-sort + track index.
        sel = self._points[self._dragging_idx]
        self._points.sort(key=lambda q: q[0])
        self._dragging_idx = self._points.index(sel)
        self._selected_idx = self._dragging_idx
        self.update()
        self.points_changed.emit(self.points())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_idx = None

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background: hue rainbow gradient covering the X axis.
        grad = QLinearGradient(6, 0, self.width() - 6, 0)
        for stop, rgb in (
            (0.000, (255, 70,  70)),
            (0.166, (235, 210, 60)),
            (0.333, (110, 220, 70)),
            (0.500, (60,  180, 220)),
            (0.666, (130, 100, 235)),
            (0.833, (235, 90,  200)),
            (1.000, (255, 70,  70)),
        ):
            grad.setColorAt(stop, QColor(*rgb, 110))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 4, 4)

        # Centre baseline (delta = 0)
        cy = self._delta_to_y(0.0)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine))
        painter.drawLine(6, int(cy), self.width() - 6, int(cy))

        # Curve — connect points in order, with wrap from last to first.
        if len(self._points) >= 2:
            pen = QPen(QColor(255, 255, 255), 2)
            painter.setPen(pen)
            n = len(self._points)
            for i in range(n):
                a = self._points[i]
                b = self._points[(i + 1) % n]
                ax = self._hue_to_x(a[0])
                ay = self._delta_to_y(a[1])
                bx = self._hue_to_x(b[0])
                by = self._delta_to_y(b[1])
                # Wrap: don't draw a segment that crosses the seam if
                # the next point's hue is smaller (wraps around 360).
                if b[0] < a[0]:
                    continue
                painter.drawLine(int(ax), int(ay), int(bx), int(by))

        # Control points
        for i, (hue, dlt) in enumerate(self._points):
            x = self._hue_to_x(hue)
            y = self._delta_to_y(dlt)
            r = self.HANDLE_R + (1 if i == self._selected_idx else 0)
            painter.setPen(QPen(QColor(0, 0, 0, 200), 1))
            fill = QColor(255, 255, 255) if i == self._selected_idx else QColor(220, 220, 220)
            painter.setBrush(fill)
            painter.drawEllipse(int(x) - r, int(y) - r, r * 2, r * 2)

        # Outer border
        painter.setPen(QPen(QColor(0, 0, 0, 140), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)


class _ColorWheelWidget(QWidget):
    """DaVinci-style chromaticity wheel with a draggable indicator.

    Emits ``value_changed(x, y)`` in ``-100..100`` while dragging.
    Axis convention matches :func:`app.color_grading._wheel_to_rgb_offset`:

        +x → red / orange (warm)        -x → cyan / blue  (cool)
        +y → magenta                    -y → green

    Visual treatment: smooth 12-stop conical hue ring with a subtle
    outer glow, a feathered radial centre fade for the neutral zone,
    two faint guide rings at 50 % and 100 % saturation, a crosshair,
    and a high-contrast white indicator with an inner colour dot.
    Bottom label sits directly under the wheel, with the live ``x, y``
    readout in a small chip just above the label.
    """

    value_changed = Signal(int, int)

    SIZE = 132              # widget side length (px) — DaVinci-leaning size
    LABEL_H = 16
    READOUT_H = 13
    INDICATOR_R = 7

    def __init__(self, label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._x = 0           # -100..100
        self._y = 0
        self._dragging = False
        # Total height = wheel + readout + label + small gaps.
        self.setFixedSize(self.SIZE, self.SIZE + self.READOUT_H + self.LABEL_H + 4)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def value(self) -> tuple[int, int]:
        return self._x, self._y

    def set_value(self, x: int, y: int, *, emit: bool = True) -> None:
        x = max(-100, min(100, int(x)))
        y = max(-100, min(100, int(y)))
        if x == self._x and y == self._y:
            return
        self._x = x
        self._y = y
        self.update()
        if emit:
            self.value_changed.emit(self._x, self._y)

    # ---- geometry helpers ----

    def _wheel_rect(self) -> QRect:
        # Leave room at the bottom for readout + label.
        return QRect(3, 3, self.SIZE - 6, self.SIZE - 6)

    def _wheel_center(self) -> QPoint:
        r = self._wheel_rect()
        return QPoint(r.left() + r.width() // 2,
                      r.top() + r.height() // 2)

    def _wheel_radius(self) -> float:
        r = self._wheel_rect()
        return min(r.width(), r.height()) / 2.0 - 2.0

    def _value_to_pos(self) -> QPoint:
        c = self._wheel_center()
        rad = self._wheel_radius()
        x = c.x() + self._x / 100.0 * rad
        y = c.y() + self._y / 100.0 * rad
        return QPoint(int(x), int(y))

    def _pos_to_value(self, p: QPoint) -> tuple[int, int]:
        c = self._wheel_center()
        rad = self._wheel_radius()
        if rad <= 0:
            return 0, 0
        dx = (p.x() - c.x()) / rad
        dy = (p.y() - c.y()) / rad
        import math
        d = math.hypot(dx, dy)
        if d > 1.0:
            dx /= d
            dy /= d
        x = int(round(max(-1.0, min(1.0, dx)) * 100))
        y = int(round(max(-1.0, min(1.0, dy)) * 100))
        return x, y

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)
        elif event.button() == Qt.MouseButton.RightButton:
            self.set_value(0, 0)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, _event) -> None:
        self.set_value(0, 0)

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QConicalGradient, QRadialGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        wheel = self._wheel_rect()
        cx = wheel.center().x()
        cy = wheel.center().y()
        rad = self._wheel_radius()

        # ---- subtle outer glow (drawn first, behind everything) ----
        glow = QRadialGradient(QPoint(cx, cy), rad + 6)
        glow.setColorAt(0.85, QColor(0, 0, 0, 0))
        glow.setColorAt(1.00, QColor(0, 0, 0, 90))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(rad + 5), int(rad + 5))

        # ---- conical hue ring ----
        # QConicalGradient progresses counter-clockwise from the 3 o'clock
        # position. To match the value convention (+x=warm red,
        # -y=green at the screen top, -x=cyan, +y=magenta at the screen
        # bottom), place red at t=0, green at t=0.25, cyan at 0.5,
        # magenta at 0.75.
        grad = QConicalGradient(QPoint(cx, cy), 0.0)
        stops = [
            (0.000, (245,  70,  70)),    # red       — 3 o'clock, +x
            (0.083, (245, 150,  60)),    # orange
            (0.166, (235, 210,  60)),    # yellow
            (0.250, (110, 220,  70)),    # GREEN     — 12 o'clock, -y
            (0.333, ( 60, 220, 140)),    # green-cyan
            (0.416, ( 50, 210, 200)),    # cyan-green
            (0.500, ( 60, 180, 220)),    # CYAN      — 9 o'clock, -x
            (0.583, ( 80, 140, 235)),    # blue
            (0.666, (130, 100, 235)),    # blue-violet
            (0.750, (235,  90, 200)),    # MAGENTA   — 6 o'clock, +y
            (0.833, (240, 100, 150)),    # pink
            (0.916, (245,  90, 110)),    # warm pink
            (1.000, (245,  70,  70)),
        ]
        for stop, (r, g, b) in stops:
            grad.setColorAt(stop, QColor(r, g, b))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(wheel)

        # ---- feathered radial fade toward neutral grey at centre ----
        # Two-stop fade gives the wheel that "punched" centre look
        # without obliterating chromatic information at the edge.
        radial = QRadialGradient(QPoint(cx, cy), rad)
        radial.setColorAt(0.00, QColor(232, 232, 234, 245))
        radial.setColorAt(0.35, QColor(232, 232, 234, 130))
        radial.setColorAt(0.65, QColor(232, 232, 234, 0))
        painter.setBrush(radial)
        painter.drawEllipse(wheel)

        # ---- guide rings at 50% and 100% saturation ----
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawEllipse(QPoint(cx, cy), int(rad * 0.5), int(rad * 0.5))
        # 100% ring (rim) — slightly darker to read as the boundary.
        painter.setPen(QPen(QColor(0, 0, 0, 130), 1))
        painter.drawEllipse(wheel)

        # ---- crosshair ----
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(cx - 4, cy, cx + 4, cy)
        painter.drawLine(cx, cy - 4, cx, cy + 4)

        # ---- indicator ----
        # White ring + coloured inner dot. The dot's hue matches the
        # current (x, y) direction so the user can see "what colour
        # am I pulling toward". Saturation = distance from centre.
        ind = self._value_to_pos()
        # Outer ring (with subtle drop shadow).
        painter.setPen(QPen(QColor(0, 0, 0, 110), 1))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(ind, self.INDICATOR_R, self.INDICATOR_R)
        # Inner coloured dot — sample the wheel colour at this position.
        inner_color = self._sample_wheel_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(inner_color)
        painter.drawEllipse(ind, self.INDICATOR_R - 3, self.INDICATOR_R - 3)

        # ---- numeric readout ----
        readout_text = f"{self._x:+d}, {self._y:+d}"
        painter.setPen(QPen(QColor("#9CA0AC")))
        f = QFont(painter.font())
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE - 3, self.width(), self.READOUT_H),
            Qt.AlignmentFlag.AlignCenter,
            readout_text,
        )

        # ---- bottom label ----
        painter.setPen(QPen(QColor("#D6D6DC")))
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE + self.READOUT_H, self.width(), self.LABEL_H),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )

    def _sample_wheel_color(self) -> QColor:
        """Approximate the wheel hue at the current (x, y). Used as the
        indicator's inner-dot colour so the user gets visual feedback
        on which way they're pulling. Uses the same 13-stop hue ring
        the gradient paints, with the screen-Y flip baked into the
        atan2 → t conversion (Qt's CCW gradient on a Y-down canvas)."""
        import math
        if self._x == 0 and self._y == 0:
            return QColor(220, 220, 220)
        # Negate the angle: Qt paints the gradient CCW visually, so a
        # point with screen-Y = +y_data lands further around the wheel
        # in the "going CW visually" direction. The negation aligns the
        # sampled colour with the painted gradient.
        ang = math.atan2(self._y, self._x)
        t = (-ang / (2 * math.pi)) % 1.0
        stops = [
            (0.000, (245,  70,  70)),
            (0.083, (245, 150,  60)),
            (0.166, (235, 210,  60)),
            (0.250, (110, 220,  70)),
            (0.333, ( 60, 220, 140)),
            (0.416, ( 50, 210, 200)),
            (0.500, ( 60, 180, 220)),
            (0.583, ( 80, 140, 235)),
            (0.666, (130, 100, 235)),
            (0.750, (235,  90, 200)),
            (0.833, (240, 100, 150)),
            (0.916, (245,  90, 110)),
            (1.000, (245,  70,  70)),
        ]
        for i in range(len(stops) - 1):
            a, ca = stops[i]
            b, cb = stops[i + 1]
            if a <= t <= b:
                u = (t - a) / max(1e-6, b - a)
                r = int(ca[0] + (cb[0] - ca[0]) * u)
                g = int(ca[1] + (cb[1] - ca[1]) * u)
                bl = int(ca[2] + (cb[2] - ca[2]) * u)
                # Saturation = distance from centre.
                d = min(1.0, math.hypot(self._x, self._y) / 100.0)
                rr = int(220 + (r - 220) * d)
                gg = int(220 + (g - 220) * d)
                bb = int(220 + (bl - 220) * d)
                return QColor(rr, gg, bb)
        return QColor(220, 220, 220)


class _AnimationPickerButton(QWidget):
    """Compact animation picker — button shows the current animation's
    name + icon, click opens a popup with category tabs and a 3-column
    tile grid. Scales for the 50+ presets coming in Phase 4."""

    animation_changed = Signal(str)        # animation id

    CATEGORIES = ("basic", "kinetic", "folding", "hold")     # extended in Phase 4

    def __init__(self, current_id: str, direction: str,
                 parent: QWidget | None = None,
                 extras_mode: bool = False) -> None:
        super().__init__(parent)
        self._direction = direction        # "in" / "out" / "hold"
        self._current_id = current_id
        self._popup: QWidget | None = None
        # In extras mode the button never reflects the picked animation
        # — it stays as a "+ Add modifier" trigger and emits the signal
        # so the parent can append to its extras list.
        self._extras_mode = bool(extras_mode)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("AnimPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_id(self) -> str:
        return self._current_id

    def set_current(self, anim_id: str) -> None:
        if anim_id != self._current_id:
            self._current_id = anim_id
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        if self._extras_mode:
            self._btn.setText("  ＋  " + tr("veditor.typo_editor.modifier.add"))
            self._btn.setMinimumHeight(28)
            self._btn.setStyleSheet(
                f"QPushButton#AnimPickerBtn {{ "
                f"background-color: transparent; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
                f"padding: 4px 10px; text-align: left; font-size: 11px; }}"
                f"QPushButton#AnimPickerBtn:hover {{ "
                f"border-color: #6a6a72; color: {COLOR_TEXT_PRIMARY}; }}"
            )
            return
        from app.typo_animations import get_animation
        anim = get_animation(self._current_id)
        name = tr(anim.name_key)
        self._btn.setText(f" {anim.icon}   {name}     ▾")
        self._btn.setStyleSheet(
            f"QPushButton#AnimPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; font-size: 12px; }}"
            f"QPushButton#AnimPickerBtn:hover {{ border-color: #6a6a72; }}"
        )

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 460)
        self._popup.resize(target_w, 360)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_animations import REGISTRY

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("AnimPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#AnimPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.anim_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All-tab + per-category tabs
        self._tile_buttons: list = []  # references to keep them alive
        # "All" tab first — flat grid
        self._add_tab(
            tr("veditor.typo_editor.anim_cat.all"),
            [a for a in REGISTRY.values()
             if a.direction in (self._direction, "any")],
        )
        for cat in self.CATEGORIES:
            anims = [
                a for a in REGISTRY.values()
                if a.category == cat
                and a.direction in (self._direction, "any")
            ]
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.anim_cat.{cat}"), anims)

    def _add_tab(self, label: str, anims: list) -> None:
        from PySide6.QtWidgets import (
            QScrollArea, QGridLayout,
        )
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, anim in enumerate(anims):
            tile = self._make_tile(anim)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        # Spacer at bottom
        grid.setRowStretch(grid.rowCount(), 1)

        self._tabs.addTab(page, label)

    def _make_tile(self, anim) -> QWidget:
        """One animation tile in the grid: bordered box with icon at
        top + name at bottom. Click selects + closes the popup."""
        tile = QPushButton()
        tile.setProperty("anim_id", anim.id)
        tile.setProperty("anim_search", f"{tr(anim.name_key)} {anim.id}")
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(130, 80)
        tile.setMaximumHeight(96)
        is_current = anim.id == self._current_id
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid "
            f"{COLOR_ACCENT_BLUE if is_current else COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; }}"
            f"QPushButton:hover {{ border-color: #6a6a72; "
            f"background-color: #34343c; }}"
        )
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        icon = QLabel(anim.icon)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 28px; background: transparent; "
            f"border: none;"
        )
        layout.addWidget(icon, 1)
        name = QLabel(tr(anim.name_key))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; "
            f"font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(name, 0)

        tile.clicked.connect(lambda _c=False, aid=anim.id: self._select(aid))
        return tile

    def _select(self, anim_id: str) -> None:
        if not self._extras_mode:
            self._current_id = anim_id
            self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.animation_changed.emit(anim_id)

    def _filter(self, text: str) -> None:
        """Hide tiles whose name or id doesn't contain ``text``."""
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("anim_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class _PresetPickerButton(QWidget):
    """Top-of-dialog preset picker. Click → popup with category tabs +
    tile grid. Selecting a preset emits ``preset_applied(preset_id)``,
    which the dialog uses to overwrite animation + style fields and
    rebuild the editor controls."""

    preset_applied = Signal(str)

    CATEGORIES = ("kinetic", "utaite", "korean", "devila")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._tile_buttons: list = []

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton(tr("veditor.typo_editor.preset_btn"))
        self._btn.setObjectName("PresetPickerBtn")
        self._btn.setMinimumHeight(34)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton#PresetPickerBtn {{ "
            f"background-color: #4a4a4a; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid #5a5a5a; border-radius: 4px; "
            f"padding: 6px 14px; font-weight: 700; font-size: 12px; }}"
            f"QPushButton#PresetPickerBtn:hover {{ "
            f"background-color: #5a5a5a; border-color: #6a6a6a; }}"
        )
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 520)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_presets import list_presets

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("PresetPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#PresetPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.preset_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All tab + per-category
        self._add_tab(tr("veditor.typo_editor.preset_cat.all"), list_presets())
        for cat in self.CATEGORIES:
            anims = list_presets(cat)
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.preset_cat.{cat}"), anims)

    def _add_tab(self, label: str, presets: list) -> None:
        from PySide6.QtWidgets import QScrollArea, QGridLayout

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, preset in enumerate(presets):
            tile = self._make_tile(preset)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        grid.setRowStretch(grid.rowCount(), 1)
        self._tabs.addTab(page, label)

    def _make_tile(self, preset) -> QWidget:
        tile = QPushButton()
        # Search payload: name + reference + id
        tile.setProperty("preset_id", preset.id)
        search_blob = f"{tr(preset.name_key)} {preset.reference_artist} {preset.id}"
        tile.setProperty("preset_search", search_blob)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(150, 92)
        tile.setMaximumHeight(110)
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid {COLOR_BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 6px; text-align: left; }}"
            f"QPushButton:hover {{ border-color: #D85A30; "
            f"background-color: #34343c; }}"
        )

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Top: icon + name on one line
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon = QLabel(preset.icon)
        icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        top.addWidget(icon)
        name = QLabel(tr(preset.name_key))
        name.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        name.setWordWrap(True)
        top.addWidget(name, 1)
        layout.addLayout(top)

        # Bottom: reference artist (if any)
        if preset.reference_artist:
            ref = QLabel(f"— {preset.reference_artist}")
            ref.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                f"background: transparent; border: none;"
            )
            layout.addWidget(ref)

        layout.addStretch(1)
        tile.clicked.connect(lambda _c=False, pid=preset.id: self._select(pid))
        return tile

    def _select(self, preset_id: str) -> None:
        if self._popup is not None:
            self._popup.hide()
        self.preset_applied.emit(preset_id)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("preset_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class _ZoomRegionPicker(QWidget):
    """Custom widget for the zoom-target rectangle picker.

    Shows a still frame from the source video and lets the user drag a
    rectangle on it. Emits ``rect_changed(x, y, w, h)`` in source-frame
    pixel coordinates as the user drags.
    """

    rect_changed = Signal(int, int, int, int)

    def __init__(self, frame: QImage, parent=None) -> None:
        super().__init__(parent)
        self._frame = frame
        self._frame_w = frame.width()
        self._frame_h = frame.height()
        # Rectangle in source-frame px; (0,0,0,0) = unset.
        self._rect_src: QRect = QRect()
        self._dragging = False
        self._drag_start_widget: QPoint = QPoint()
        self.setMinimumSize(640, 360)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_initial_rect(self, x: int, y: int, w: int, h: int) -> None:
        if w > 0 and h > 0:
            self._rect_src = QRect(x, y, w, h)
            self.update()

    def current_rect(self) -> QRect:
        return QRect(self._rect_src)

    # ---- coordinate transforms ----

    def _display_rect(self) -> QRect:
        """The widget rect the source frame is painted into, preserving
        aspect. The picker rectangle is drawn relative to this."""
        if self._frame_w <= 0 or self._frame_h <= 0:
            return self.rect()
        wr = self.rect()
        scale = min(wr.width() / self._frame_w, wr.height() / self._frame_h)
        dw = int(self._frame_w * scale)
        dh = int(self._frame_h * scale)
        dx = (wr.width() - dw) // 2
        dy = (wr.height() - dh) // 2
        return QRect(dx, dy, dw, dh)

    def _widget_to_src(self, p: QPoint) -> QPoint:
        d = self._display_rect()
        if d.width() <= 0 or d.height() <= 0:
            return QPoint(0, 0)
        sx = (p.x() - d.left()) * self._frame_w // d.width()
        sy = (p.y() - d.top()) * self._frame_h // d.height()
        sx = max(0, min(self._frame_w - 1, sx))
        sy = max(0, min(self._frame_h - 1, sy))
        return QPoint(sx, sy)

    def _src_to_widget_rect(self, src: QRect) -> QRect:
        d = self._display_rect()
        if d.width() <= 0 or self._frame_w <= 0:
            return QRect()
        x = d.left() + src.x() * d.width() // self._frame_w
        y = d.top() + src.y() * d.height() // self._frame_h
        w = src.width() * d.width() // self._frame_w
        h = src.height() * d.height() // self._frame_h
        return QRect(x, y, w, h)

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._drag_start_widget = event.position().toPoint()
        # Reset the rect — start a fresh drag.
        sp = self._widget_to_src(self._drag_start_widget)
        self._rect_src = QRect(sp.x(), sp.y(), 0, 0)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            return
        end_widget = event.position().toPoint()
        sp_start = self._widget_to_src(self._drag_start_widget)
        sp_end = self._widget_to_src(end_widget)
        x = min(sp_start.x(), sp_end.x())
        y = min(sp_start.y(), sp_end.y())
        w = abs(sp_end.x() - sp_start.x())
        h = abs(sp_end.y() - sp_start.y())
        self._rect_src = QRect(x, y, w, h)
        self.update()
        self.rect_changed.emit(x, y, w, h)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainter as _QP, QPixmap as _QPM
        painter = _QP(self)
        painter.fillRect(self.rect(), QColor("#0a0a0e"))

        d = self._display_rect()
        if not self._frame.isNull() and d.width() > 0:
            painter.drawImage(d, self._frame)

        # Dim everything outside the chosen rect.
        if self._rect_src.width() > 0 and self._rect_src.height() > 0:
            wr = self._src_to_widget_rect(self._rect_src)
            # Dim mask
            painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
            # Punch out the picked rect (re-draw the original clip there)
            painter.setCompositionMode(_QP.CompositionMode.CompositionMode_Source)
            if not self._frame.isNull():
                # Compute the source crop in the original image
                sx = self._rect_src.x() * d.width() // self._frame_w
                sy = self._rect_src.y() * d.height() // self._frame_h
                sw = self._rect_src.width() * d.width() // self._frame_w
                sh = self._rect_src.height() * d.height() // self._frame_h
                src_view = QRect(self._rect_src)
                target_view = wr
                painter.drawImage(target_view, self._frame, src_view)
            painter.setCompositionMode(_QP.CompositionMode.CompositionMode_SourceOver)
            # Highlight border
            pen = QPen(QColor(COLOR_ACCENT_BLUE), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(wr)
            # Centre marker
            cx = wr.left() + wr.width() // 2
            cy = wr.top() + wr.height() // 2
            painter.setPen(QPen(QColor(COLOR_ACCENT_BLUE), 1))
            painter.drawLine(cx - 6, cy, cx + 6, cy)
            painter.drawLine(cx, cy - 6, cx, cy + 6)


class ZoomActorDialog(QDialog):
    """Modal: pick the zoom target rectangle on a still frame from the
    source video, plus zoom-in / zoom-out duration sliders. Mutates the
    actor in-place on Apply."""

    def __init__(self, track: VideoTrack, zactor: ZoomActor,
                 player, parent=None) -> None:
        super().__init__(parent)
        self.track = track
        self.zactor = zactor
        self._player = player
        self.setWindowTitle(tr("veditor.zoom_dialog.title"))
        self.setMinimumSize(820, 620)

        # Snapshot a frame from the source at the actor's start time.
        frame = self._capture_source_frame(zactor.start_ms)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hint = QLabel(tr("veditor.zoom_dialog.hint"))
        hint.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        v.addWidget(hint)

        self._picker = _ZoomRegionPicker(frame)
        self._picker.set_initial_rect(
            zactor.target_x, zactor.target_y, zactor.target_w, zactor.target_h
        )
        v.addWidget(self._picker, 1)

        # Fade times (zoom_in_ms / zoom_out_ms) are edited directly on
        # the timeline via the inner handles on the actor block — same
        # pattern as Fade actors. The dialog only handles the target
        # rectangle, which can't sensibly live on a 1-D timeline.

        # Apply / Cancel
        from PySide6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).clicked.connect(
            self.reject
        )
        v.addWidget(buttons)

    def _capture_source_frame(self, source_ms: int) -> QImage:
        """Read one frame from the track's source video at ``source_ms``.
        Falls back to a blank frame if reading fails."""
        path = self.track.source_path
        if path is None:
            return QImage(640, 360, QImage.Format.Format_RGB888)
        try:
            import cv2
            import numpy as np
            cap = cv2.VideoCapture(str(path))
            try:
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                idx = int(source_ms / 1000.0 * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    raise RuntimeError("frame read failed")
                rgb = np.ascontiguousarray(bgr[:, :, ::-1])
                h, w = rgb.shape[:2]
                return QImage(rgb.data, w, h, rgb.strides[0],
                              QImage.Format.Format_RGB888).copy()
            finally:
                cap.release()
        except Exception:
            return QImage(640, 360, QImage.Format.Format_RGB888)

    def _on_apply(self) -> None:
        rect = self._picker.current_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                tr("veditor.zoom_dialog.title"),
                tr("veditor.zoom_dialog.no_rect"),
            )
            return
        self.zactor.target_x = int(rect.x())
        self.zactor.target_y = int(rect.y())
        self.zactor.target_w = int(rect.width())
        self.zactor.target_h = int(rect.height())
        self.accept()


class TypographyEditorDialog(QDialog):
    """Phase 2 typography editor — 3-pane (text / animation placeholder
    / style) modal with a real-time preview at the top.

    Edits mutate the clip in-place so the underlying preview updates
    live; Cancel restores from a snapshot taken at open time."""

    WEIGHT_PRESETS = [
        ("thin", 200),
        ("regular", 400),
        ("bold", 700),
        ("black", 900),
    ]

    ALIGN_OPTIONS = ("left", "center", "right")

    def __init__(self, clip: TextClip, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip = clip
        self._snapshot = self._snapshot_clip()
        self._suppress_signals = False

        # Capture the parent editor's current preview frame for the
        # video-background option. Copy so subsequent player frames
        # don't mutate it under us.
        self._video_bg_pixmap: QPixmap | None = None
        if parent is not None:
            pm = getattr(parent, "_preview_pixmap", None)
            if pm is not None and not pm.isNull():
                self._video_bg_pixmap = QPixmap(pm)
        self._show_video_bg: bool = self._video_bg_pixmap is not None

        title = clip.text[:30] or "—"
        self.setWindowTitle(tr("veditor.typo_editor.title", name=title))
        self.setModal(True)
        self.resize(1200, 800)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
            f"QLabel {{ color: {COLOR_TEXT_SECONDARY}; }}"
            f"QGroupBox {{ color: {COLOR_TEXT_PRIMARY}; font-weight: 700; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"margin-top: 10px; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; "
            f"subcontrol-position: top left; left: 10px; padding: 0 4px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # ---- Preview ----
        self._preview_view = _PreviewView()
        self._preview_view.setMinimumHeight(280)
        self._preview_item = _TextPreviewItem(
            clip,
            bg_provider=self._current_bg,
            time_provider=self._current_play_time,
        )
        self._preview_view.add_item(self._preview_item.graphics_item())
        root.addWidget(self._preview_view, stretch=2)

        # Playback state for animation preview.
        self._play_time_s: float = 0.0
        self._is_playing: bool = False
        from PySide6.QtCore import QTimer
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)         # ~30 fps; smooth enough
        self._play_timer.timeout.connect(self._on_play_tick)

        # Preview controls row: Play / Reset + Video-background toggle
        from PySide6.QtWidgets import QCheckBox
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("ToolButton")
        self._play_btn.setFixedWidth(40)
        self._play_btn.setToolTip(tr("veditor.typo_editor.preview_play"))
        self._play_btn.clicked.connect(self._toggle_preview_play)
        ctrl_row.addWidget(self._play_btn)

        self._reset_btn = QPushButton("⟲")
        self._reset_btn.setObjectName("ToolButton")
        self._reset_btn.setFixedWidth(40)
        self._reset_btn.setToolTip(tr("veditor.typo_editor.preview_reset"))
        self._reset_btn.clicked.connect(self._reset_preview)
        ctrl_row.addWidget(self._reset_btn)

        self._play_label = QLabel(self._format_play_label())
        self._play_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-family: Consolas, monospace;"
        )
        ctrl_row.addWidget(self._play_label)

        ctrl_row.addStretch(1)

        self._video_bg_check = QCheckBox(tr("veditor.typo_editor.show_video_bg"))
        self._video_bg_check.setChecked(self._show_video_bg)
        self._video_bg_check.setEnabled(self._video_bg_pixmap is not None)
        if self._video_bg_pixmap is None:
            self._video_bg_check.setToolTip(
                tr("veditor.typo_editor.show_video_bg.unavailable")
            )
        self._video_bg_check.toggled.connect(self._on_video_bg_toggle)
        ctrl_row.addWidget(self._video_bg_check)

        root.addLayout(ctrl_row)

        # ---- Preset picker (single full-width purple button) ----
        self._preset_picker = _PresetPickerButton()
        self._preset_picker.preset_applied.connect(self._on_preset_picked)
        root.addWidget(self._preset_picker)

        # ---- 3 panes ----
        panes = QHBoxLayout()
        panes.setSpacing(10)
        panes.addWidget(self._build_text_pane(), stretch=1)
        panes.addWidget(self._build_animation_pane(), stretch=1)
        panes.addWidget(self._build_style_pane(), stretch=2)
        self._panes_layout = panes        # kept for preset-apply rebuild
        root.addLayout(panes, stretch=3)

        # ---- Buttons ----
        from PySide6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox()
        save_btn = bb.addButton(
            tr("veditor.typo_editor.save_template"),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        save_btn.setEnabled(False)  # Phase 4: preset system
        save_btn.setToolTip(tr("veditor.typo_editor.save_template.tooltip"))
        cancel_btn = bb.addButton(
            tr("veditor.typo_editor.cancel"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        apply_btn = bb.addButton(
            tr("veditor.typo_editor.apply"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        apply_btn.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self._on_cancel)
        root.addWidget(bb)

    # ---- snapshot / cancel ----

    def _snapshot_clip(self) -> dict:
        import copy
        return {
            "text": self._clip.text,
            "style": copy.deepcopy(self._clip.style),
            "in_duration": self._clip.animation.in_duration,
            "out_duration": self._clip.animation.out_duration,
            "in_animation": self._clip.animation.in_animation,
            "out_animation": self._clip.animation.out_animation,
            "hold_animation": getattr(self._clip.animation, "hold_animation", "none"),
            "in_extras": list(getattr(self._clip.animation, "in_extras", []) or []),
            "out_extras": list(getattr(self._clip.animation, "out_extras", []) or []),
            "hold_extras": list(getattr(self._clip.animation, "hold_extras", []) or []),
            "in_intensity": self._clip.animation.in_intensity,
            "out_intensity": self._clip.animation.out_intensity,
            "hold_intensity": getattr(self._clip.animation, "hold_intensity", 100.0),
            "mono_color": getattr(self._clip.animation, "mono_color", False),
        }

    def _on_cancel(self) -> None:
        snap = self._snapshot
        self._clip.text = snap["text"]
        self._clip.style = snap["style"]
        self._clip.animation.in_duration = snap["in_duration"]
        self._clip.animation.out_duration = snap["out_duration"]
        self._clip.animation.in_animation = snap["in_animation"]
        self._clip.animation.out_animation = snap["out_animation"]
        self._clip.animation.hold_animation = snap["hold_animation"]
        self._clip.animation.in_extras = list(snap["in_extras"])
        self._clip.animation.out_extras = list(snap["out_extras"])
        self._clip.animation.hold_extras = list(snap["hold_extras"])
        self._clip.animation.in_intensity = snap["in_intensity"]
        self._clip.animation.out_intensity = snap["out_intensity"]
        self._clip.animation.hold_intensity = snap["hold_intensity"]
        self._clip.animation.mono_color = snap["mono_color"]
        self.reject()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_play_timer"):
            self._play_timer.stop()
        super().closeEvent(event)

    def _refresh_preview(self) -> None:
        self._preview_item.refresh()

    def _current_bg(self):
        """Provider used by ``_TextPreviewItem`` — returns the captured
        video frame when the user wants it shown, else ``None`` for a
        plain black backdrop."""
        if self._show_video_bg and self._video_bg_pixmap is not None:
            return self._video_bg_pixmap
        return None

    def _on_video_bg_toggle(self, on: bool) -> None:
        self._show_video_bg = bool(on)
        self._refresh_preview()

    # ---- preview playback ----

    def _current_play_time(self):
        """Animation time provider. Returns seconds-since-clip-start
        when the user is actively playing; ``None`` while paused (so
        the preview shows the steady HOLD state for editing)."""
        if self._is_playing:
            return self._play_time_s
        # When paused, show the steady "fully on screen" state by
        # passing a time that lands inside HOLD.
        return None

    def _toggle_preview_play(self) -> None:
        if self._is_playing:
            self._is_playing = False
            self._play_timer.stop()
            self._play_btn.setText("▶")
        else:
            # Start fresh from 0 if we were paused at end.
            if self._play_time_s >= self._clip.duration_s - 0.001:
                self._play_time_s = 0.0
            self._is_playing = True
            self._play_timer.start()
            self._play_btn.setText("⏸")
        self._refresh_preview()
        self._update_play_label()

    def _reset_preview(self) -> None:
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _on_play_tick(self) -> None:
        # Advance and loop. Looping makes it easy to compare animations
        # without mashing the play button between every change.
        self._play_time_s += self._play_timer.interval() / 1000.0
        if self._play_time_s >= self._clip.duration_s:
            self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _format_play_label(self) -> str:
        return f"{self._play_time_s:5.2f} / {self._clip.duration_s:5.2f} s"

    def _update_play_label(self) -> None:
        if hasattr(self, "_play_label"):
            self._play_label.setText(self._format_play_label())

    # ---- text pane ----

    def _build_text_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox, QPlainTextEdit

        box = QGroupBox(tr("veditor.typo_editor.text_pane"))
        box.setMinimumWidth(220)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(self._clip.text)
        self._text_edit.setPlaceholderText(tr("veditor.typo_editor.placeholder"))
        self._text_edit.setStyleSheet(
            f"QPlainTextEdit {{ padding: 8px; font-size: 14px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._text_edit.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._text_edit, stretch=1)

        return box

    def _on_text_changed(self) -> None:
        if self._suppress_signals:
            return
        self._clip.text = self._text_edit.toPlainText()
        self._refresh_preview()

    # ---- animation pane (placeholder + timing sliders) ----

    def _build_animation_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox

        box = QGroupBox(tr("veditor.typo_editor.animation_pane"))
        box.setMinimumWidth(240)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        # IN animation picker — visual grid in popup.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_in")))
        self._in_picker = _AnimationPickerButton(
            self._clip.animation.in_animation, direction="in",
        )
        self._in_picker.animation_changed.connect(self._on_in_anim_picked)
        lay.addWidget(self._in_picker)
        # IN extras chip row + add button
        self._in_extras_row = self._build_extras_row("in")
        lay.addWidget(self._in_extras_row)

        # IN duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.in"),
            value=int(self._clip.animation.in_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_in_changed,
        ))
        # IN intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.in"),
            value=int(self._clip.animation.in_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_in_intensity_changed,
        ))

        # OUT animation picker
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_out")))
        self._out_picker = _AnimationPickerButton(
            self._clip.animation.out_animation, direction="out",
        )
        self._out_picker.animation_changed.connect(self._on_out_anim_picked)
        lay.addWidget(self._out_picker)
        # OUT extras chip row
        self._out_extras_row = self._build_extras_row("out")
        lay.addWidget(self._out_extras_row)

        # OUT duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.out"),
            value=int(self._clip.animation.out_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_out_changed,
        ))
        # OUT intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.out"),
            value=int(self._clip.animation.out_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_out_intensity_changed,
        ))

        # HOLD animation picker — loops between IN and OUT.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_hold")))
        self._hold_picker = _AnimationPickerButton(
            getattr(self._clip.animation, "hold_animation", "none"),
            direction="hold",
        )
        self._hold_picker.animation_changed.connect(self._on_hold_anim_picked)
        lay.addWidget(self._hold_picker)
        # HOLD extras chip row
        self._hold_extras_row = self._build_extras_row("hold")
        lay.addWidget(self._hold_extras_row)

        # HOLD intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.hold"),
            value=int(getattr(self._clip.animation, "hold_intensity", 100.0)),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_hold_intensity_changed,
        ))

        # Hold derived label (live) — shows the seconds available between IN and OUT.
        self._hold_label = QLabel("")
        self._hold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hold_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        self._update_hold_label()
        lay.addWidget(self._hold_label)

        # Mono-color toggle — disables per-glyph color overrides
        # (e.g. Angle Break's flash) so the whole clip stays one tone.
        from PySide6.QtWidgets import QCheckBox
        self._mono_check = QCheckBox(tr("veditor.typo_editor.mono_color"))
        self._mono_check.setChecked(bool(getattr(self._clip.animation, "mono_color", False)))
        self._mono_check.setToolTip(tr("veditor.typo_editor.mono_color.tooltip"))
        self._mono_check.toggled.connect(self._on_mono_color_toggle)
        lay.addWidget(self._mono_check)

        lay.addStretch(1)
        return box

    # ---- extras (composed animations) ----

    def _extras_attr(self, direction: str) -> str:
        return f"{direction}_extras"

    def _build_extras_row(self, direction: str) -> QWidget:
        """Wraps the chips + an `[+ Add modifier]` button for one slot.
        The wrapper widget keeps a hidden ``_AnimationPickerButton`` in
        ``extras_mode`` so we get the picker popup for free."""
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Hidden adder picker: we trigger its popup by clicking the
        # visible add-button. Adding it to the layout keeps Qt's parent
        # ownership tidy; visibility is the picker button's responsibility.
        adder = _AnimationPickerButton(
            current_id="none", direction=direction, extras_mode=True,
        )
        adder.animation_changed.connect(
            lambda aid, d=direction: self._on_extra_added(d, aid)
        )
        setattr(self, f"_{direction}_adder", adder)

        chips_host = QWidget()
        chips_lay = QHBoxLayout(chips_host)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(4)
        setattr(self, f"_{direction}_chips_lay", chips_lay)

        lay.addWidget(chips_host, 0)
        lay.addWidget(adder, 1)
        self._render_extras_chips(direction)
        return wrap

    def _render_extras_chips(self, direction: str) -> None:
        """Rebuild the chip widgets for ``direction`` from the current
        clip state."""
        chips_lay: QHBoxLayout | None = getattr(self, f"_{direction}_chips_lay", None)
        if chips_lay is None:
            return
        # Clear existing
        while chips_lay.count():
            item = chips_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        extras = list(getattr(self._clip.animation, self._extras_attr(direction), []) or [])
        from app.typo_animations import get_animation
        for idx, aid in enumerate(extras):
            anim = get_animation(aid)
            chip = QPushButton(f" {anim.icon} {tr(anim.name_key)}  ✕")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(tr("veditor.typo_editor.modifier.remove_tooltip"))
            chip.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; "
                f"color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
                f"border-radius: 10px; padding: 2px 8px; font-size: 10px; }}"
                f"QPushButton:hover {{ background-color: #4a3a3a; "
                f"border-color: #7a4a4a; }}"
            )
            chip.clicked.connect(
                lambda _c=False, d=direction, i=idx: self._on_extra_removed(d, i)
            )
            chips_lay.addWidget(chip)

    def _on_extra_added(self, direction: str, anim_id: str) -> None:
        if not anim_id or anim_id == "none":
            return
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        cur.append(anim_id)
        setattr(self._clip.animation, attr, cur)
        self._render_extras_chips(direction)
        self._refresh_preview()

    def _on_extra_removed(self, direction: str, index: int) -> None:
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        if 0 <= index < len(cur):
            del cur[index]
            setattr(self._clip.animation, attr, cur)
            self._render_extras_chips(direction)
            self._refresh_preview()

    # ---- primary picker handlers ----

    def _on_in_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.in_animation = anim_id
        self._refresh_preview()

    def _on_out_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.out_animation = anim_id
        self._refresh_preview()

    def _on_hold_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.hold_animation = anim_id
        self._refresh_preview()

    def _on_preset_picked(self, preset_id: str) -> None:
        """Apply a preset bundle to the clip and rebuild the editor's
        controls so users immediately see the new animation + style
        choices. Animation pane (pickers + sliders) and style pane
        (font, size, weight, effects, etc.) need a full rebuild — the
        cheapest way is to discard them and re-add."""
        from app.typo_presets import get_preset, apply_preset
        preset = get_preset(preset_id)
        if preset is None:
            return
        apply_preset(self._clip, preset)

        # Rebuild the IN/OUT pickers' visible label by re-syncing them
        # to the clip's new animation ids.
        self._in_picker.set_current(self._clip.animation.in_animation)
        self._out_picker.set_current(self._clip.animation.out_animation)
        if hasattr(self, "_hold_picker"):
            self._hold_picker.set_current(
                getattr(self._clip.animation, "hold_animation", "none"),
            )

        # The size / weight / color / sliders / effects don't have a
        # cheap "set value" path that handles every control, so the
        # safest move is to rebuild the whole 3-pane row. Delegate to a
        # helper that swaps the panes in place.
        self._rebuild_panes()

        # Reset the preview clock so the user sees the IN sequence of
        # the new preset right away.
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _rebuild_panes(self) -> None:
        """Replace the 3-pane row with freshly-built widgets so every
        control reflects current clip state. Called after preset apply."""
        panes_layout = self._panes_layout
        if panes_layout is None:
            return
        # Remove old widgets
        while panes_layout.count():
            item = panes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        panes_layout.addWidget(self._build_text_pane(), stretch=1)
        panes_layout.addWidget(self._build_animation_pane(), stretch=1)
        panes_layout.addWidget(self._build_style_pane(), stretch=2)

    def _slider_row(self, *, label: str, value: int, minimum: int,
                    maximum: int, suffix: str, step: int, on_change) -> QWidget:
        """Inline label + QSlider + value-readout helper."""
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        readout = QLabel(f"{value}{suffix}")
        readout.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600;")
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(readout)
        v.addLayout(head)

        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(minimum, maximum)
        sld.setSingleStep(step)
        sld.setPageStep(step * 4)
        sld.setValue(int(value))

        def _emit(val: int) -> None:
            readout.setText(f"{val}{suffix}")
            on_change(val)

        sld.valueChanged.connect(_emit)
        v.addWidget(sld)
        return wrap

    def _on_in_changed(self, ms: int) -> None:
        self._clip.animation.in_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_out_changed(self, ms: int) -> None:
        self._clip.animation.out_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_in_intensity_changed(self, percent: int) -> None:
        self._clip.animation.in_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_out_intensity_changed(self, percent: int) -> None:
        self._clip.animation.out_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_hold_intensity_changed(self, percent: int) -> None:
        self._clip.animation.hold_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_mono_color_toggle(self, on: bool) -> None:
        self._clip.animation.mono_color = bool(on)
        self._refresh_preview()

    def _update_hold_label(self) -> None:
        if not hasattr(self, "_hold_label"):
            return
        hold = self._clip.hold_duration_s
        self._hold_label.setText(
            tr("veditor.typo_editor.timing.hold", seconds=f"{hold:.2f}")
        )

    # ---- style pane ----

    # Recommended fonts pinned to the top of the picker. These are the
    # families the typography spec recommends for Korean / Japanese MV
    # styles + a few staple Latin display faces. Filtered against the
    # actual installed set at runtime.
    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def _build_style_pane(self) -> QWidget:
        from PySide6.QtWidgets import (
            QGroupBox, QPushButton, QButtonGroup, QSpinBox,
        )

        box = QGroupBox(tr("veditor.typo_editor.style_pane"))
        box.setMinimumWidth(300)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        s = self._clip.style

        # Font family — compact button + click-to-open popup picker.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.font")))
        self._font_picker = _FontPickerButton(s.font_family)
        self._font_picker.font_changed.connect(self._on_font_family_changed)
        lay.addWidget(self._font_picker)

        # Size
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.size")))
        size_row = QHBoxLayout()
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(16, 200)
        self._size_slider.setValue(int(s.font_size))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(16, 200)
        self._size_spin.setValue(int(s.font_size))
        self._size_spin.setFixedWidth(64)
        self._size_slider.valueChanged.connect(self._size_spin.setValue)
        self._size_spin.valueChanged.connect(self._size_slider.setValue)
        self._size_spin.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_slider, stretch=1)
        size_row.addWidget(self._size_spin)
        lay.addLayout(size_row)

        # Weight buttons
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.weight")))
        weight_row = QHBoxLayout()
        self._weight_group = QButtonGroup(self)
        self._weight_group.setExclusive(True)
        for key, weight in self.WEIGHT_PRESETS:
            btn = QPushButton(tr(f"veditor.typo_editor.weight.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("weight", weight)
            if abs(s.font_weight - weight) < 50:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, w=weight: self._on_weight_changed(w))
            self._weight_group.addButton(btn)
            weight_row.addWidget(btn)
        lay.addLayout(weight_row)

        # Color + Alignment row
        ca_row = QHBoxLayout()
        self._color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._color_btn.setObjectName("ToolButton")
        self._update_color_btn_swatch()
        self._color_btn.clicked.connect(self._on_color_picked)
        ca_row.addWidget(self._color_btn, stretch=1)

        # Alignment
        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)
        for key in self.ALIGN_OPTIONS:
            btn = QPushButton(tr(f"veditor.typo_editor.align.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("align_key", key)
            if s.alignment == key:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, k=key: self._on_align_changed(k))
            self._align_group.addButton(btn)
            ca_row.addWidget(btn)
        lay.addLayout(ca_row)

        # Position X / Y
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_x"),
            value=int(s.position_x * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_x_changed,
        ))
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_y"),
            value=int(s.position_y * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_y_changed,
        ))

        # Letter spacing
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.letter_spacing"),
            value=int(s.letter_spacing),
            minimum=-5, maximum=30, suffix=" px", step=1,
            on_change=self._on_letter_spacing_changed,
        ))

        # Effects (outline / shadow / background) — collapsed-style block
        lay.addWidget(self._build_effects_block())

        lay.addStretch(1)
        return box

    def _build_effects_block(self) -> QWidget:
        from PySide6.QtWidgets import QCheckBox, QGroupBox, QPushButton

        s = self._clip.style
        box = QGroupBox(tr("veditor.typo_editor.effects.section"))
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 14, 8, 8)
        v.setSpacing(6)

        # ---- Outline ----
        ol_row = QHBoxLayout()
        self._outline_check = QCheckBox(tr("veditor.typo_editor.effects.outline"))
        self._outline_check.setChecked(bool(s.outline_color and s.outline_width > 0))
        self._outline_check.toggled.connect(self._on_outline_toggle)
        ol_row.addWidget(self._outline_check)
        self._outline_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._outline_color_btn.setObjectName("ToolButton")
        self._update_outline_swatch()
        self._outline_color_btn.clicked.connect(self._on_outline_color)
        ol_row.addWidget(self._outline_color_btn)
        v.addLayout(ol_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.outline_width"),
            value=int(s.outline_width or 0),
            minimum=0, maximum=12, suffix=" px", step=1,
            on_change=self._on_outline_width,
        ))

        # ---- Shadow ----
        sh_row = QHBoxLayout()
        self._shadow_check = QCheckBox(tr("veditor.typo_editor.effects.shadow"))
        self._shadow_check.setChecked(bool(s.shadow_color))
        self._shadow_check.toggled.connect(self._on_shadow_toggle)
        sh_row.addWidget(self._shadow_check)
        self._shadow_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._shadow_color_btn.setObjectName("ToolButton")
        self._update_shadow_swatch()
        self._shadow_color_btn.clicked.connect(self._on_shadow_color)
        sh_row.addWidget(self._shadow_color_btn)
        v.addLayout(sh_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_x"),
            value=int(s.shadow_offset_x or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_x,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_y"),
            value=int(s.shadow_offset_y or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_y,
        ))

        # ---- Background ----
        bg_row = QHBoxLayout()
        self._bg_check = QCheckBox(tr("veditor.typo_editor.effects.background"))
        self._bg_check.setChecked(bool(s.background_color))
        self._bg_check.toggled.connect(self._on_bg_toggle)
        bg_row.addWidget(self._bg_check)
        self._bg_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._bg_color_btn.setObjectName("ToolButton")
        self._update_bg_swatch()
        self._bg_color_btn.clicked.connect(self._on_bg_color)
        bg_row.addWidget(self._bg_color_btn)
        v.addLayout(bg_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_padding"),
            value=int(s.background_padding or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_padding,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_radius"),
            value=int(s.background_radius or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_radius,
        ))

        return box

    @staticmethod
    def _labelled(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                          f"font-weight: 700; letter-spacing: 0.5px;")
        return lbl

    # ---- style change handlers ----

    def _on_font_family_changed(self, family: str) -> None:
        self._clip.style.font_family = family
        self._refresh_preview()

    def _on_size_changed(self, value: int) -> None:
        self._clip.style.font_size = int(value)
        self._refresh_preview()

    def _on_weight_changed(self, weight: int) -> None:
        self._clip.style.font_weight = int(weight)
        self._refresh_preview()

    def _on_color_picked(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.color or "#FFFFFF")
        chosen = QColorDialog.getColor(cur, self,
                                       tr("veditor.typo_editor.color_dialog"))
        if chosen.isValid():
            self._clip.style.color = chosen.name()
            self._update_color_btn_swatch()
            self._refresh_preview()

    def _on_align_changed(self, key: str) -> None:
        self._clip.style.alignment = key
        self._refresh_preview()

    def _on_pos_x_changed(self, percent: int) -> None:
        self._clip.style.position_x = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_pos_y_changed(self, percent: int) -> None:
        self._clip.style.position_y = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_letter_spacing_changed(self, value: int) -> None:
        self._clip.style.letter_spacing = int(value)
        self._refresh_preview()

    # ---- effects ----

    def _on_outline_toggle(self, on: bool) -> None:
        if on and not self._clip.style.outline_color:
            self._clip.style.outline_color = "#000000"
        if on and self._clip.style.outline_width <= 0:
            self._clip.style.outline_width = 2
        if not on:
            self._clip.style.outline_width = 0
        self._update_outline_swatch()
        self._refresh_preview()

    def _on_outline_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.outline_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.outline_color = c.name()
            if not self._outline_check.isChecked():
                self._outline_check.setChecked(True)
            self._update_outline_swatch()
            self._refresh_preview()

    def _on_outline_width(self, w: int) -> None:
        self._clip.style.outline_width = int(w)
        if w > 0 and not self._outline_check.isChecked():
            self._outline_check.setChecked(True)
        self._refresh_preview()

    def _on_shadow_toggle(self, on: bool) -> None:
        if on and not self._clip.style.shadow_color:
            self._clip.style.shadow_color = "#000000"
        if on and not (self._clip.style.shadow_offset_x or self._clip.style.shadow_offset_y):
            self._clip.style.shadow_offset_x = 3
            self._clip.style.shadow_offset_y = 3
        if not on:
            self._clip.style.shadow_color = None
        self._update_shadow_swatch()
        self._refresh_preview()

    def _on_shadow_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.shadow_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.shadow_color = c.name()
            if not self._shadow_check.isChecked():
                self._shadow_check.setChecked(True)
            self._update_shadow_swatch()
            self._refresh_preview()

    def _on_shadow_x(self, v: int) -> None:
        self._clip.style.shadow_offset_x = int(v)
        self._refresh_preview()

    def _on_shadow_y(self, v: int) -> None:
        self._clip.style.shadow_offset_y = int(v)
        self._refresh_preview()

    def _on_bg_toggle(self, on: bool) -> None:
        if on and not self._clip.style.background_color:
            self._clip.style.background_color = "#000000"
        if not on:
            self._clip.style.background_color = None
        self._update_bg_swatch()
        self._refresh_preview()

    def _on_bg_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.background_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.background_color = c.name()
            if not self._bg_check.isChecked():
                self._bg_check.setChecked(True)
            self._update_bg_swatch()
            self._refresh_preview()

    def _on_bg_padding(self, v: int) -> None:
        self._clip.style.background_padding = int(v)
        self._refresh_preview()

    def _on_bg_radius(self, v: int) -> None:
        self._clip.style.background_radius = int(v)
        self._refresh_preview()

    # ---- swatch updates ----

    def _swatch_style(self, hex_color: str | None) -> str:
        c = hex_color or "transparent"
        return (
            f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 8px; text-align: left; }}"
            # We'll prepend a colored square via icon-ish trick below
        )

    def _set_swatch_button(self, btn, hex_color: str | None, label: str) -> None:
        c = hex_color or "transparent"
        if hex_color:
            btn.setText(f"  {label}  ({hex_color})")
            # Use a stylesheet block with a left-side colored gutter
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; "
                f"border-left: 12px solid {hex_color}; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )
        else:
            btn.setText(f"  {label}")
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )

    def _update_color_btn_swatch(self) -> None:
        self._set_swatch_button(
            self._color_btn, self._clip.style.color,
            tr("veditor.typo_editor.btn.text_color"),
        )

    def _update_outline_swatch(self) -> None:
        col = self._clip.style.outline_color if self._clip.style.outline_width else None
        self._set_swatch_button(
            self._outline_color_btn, col,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_shadow_swatch(self) -> None:
        self._set_swatch_button(
            self._shadow_color_btn, self._clip.style.shadow_color,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_bg_swatch(self) -> None:
        self._set_swatch_button(
            self._bg_color_btn, self._clip.style.background_color,
            tr("veditor.typo_editor.btn.color"),
        )


# Module-level: which clip type currently owns the marching-ants selection.
# "video" | "audio" | ""  — updated by click handlers so only ONE type shows ants.
_ANTS_OWNER: str = ""


def _draw_marching_ants(painter: "QPainter", rect: "QRect", offset: int) -> None:
    """Draw Photoshop-style marching-ants selection border on *rect*.

    Two complementary dashed layers (dark + white) alternate so the ants
    are visible on any background.  *offset* (0–11) drives the animation
    and should be incremented by the caller's timer.
    """
    r = rect.adjusted(1, 1, -2, -2)
    if r.width() <= 0 or r.height() <= 0:
        return
    # Layer 1: dark backing so white is visible on dark clip bodies
    dark_pen = QPen(QColor(0, 0, 0, 160))
    dark_pen.setWidth(2)
    dark_pen.setDashPattern([6.0, 6.0])
    dark_pen.setDashOffset(float(offset))
    painter.setPen(dark_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(r)
    # Layer 2: white ants (offset by 6 so they fill the gaps of layer 1)
    white_pen = QPen(QColor(255, 255, 255, 220))
    white_pen.setWidth(2)
    white_pen.setDashPattern([6.0, 6.0])
    white_pen.setDashOffset(float(offset + 6))
    painter.setPen(white_pen)
    painter.drawRect(r)


class StripedHost(QWidget):
    """Scrollable timeline host. Paints a continuous 45° diagonal-stripe
    pattern as its background — track rows render on top with 80%/50%
    brightness variants of the same pattern."""

    # Original stripe colors (100% brightness reference)
    BG     = QColor("#373744")
    STRIPE = QColor("#454554")
    STRIPE_WIDTH = 10
    STRIPE_STEP  = 20

    # 80% brightness variant — used by empty video track rows
    BG_80     = QColor("#2c2c38")   # #373744 × 0.80
    STRIPE_80 = QColor("#373743")   # #454554 × 0.80

    # 80% brightness, audio tint — same luminance but sightly higher
    # blue-teal saturation to visually hint "audio" without being loud.
    BG_80_AUDIO     = QColor("#262e38")   # subtle teal-blue tint
    STRIPE_80_AUDIO = QColor("#2f3d47")   # more saturated teal stripe

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        self._draw_stripes(painter, self.rect(), self.BG, self.STRIPE)

    @staticmethod
    def _draw_stripes(
        painter: QPainter,
        rect: "QRect",
        bg: QColor,
        stripe: QColor,
        step: int = 20,
        width: int = 10,
    ) -> None:
        painter.fillRect(rect, bg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(stripe)
        pen.setWidth(width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        h = rect.height()
        x0, y0 = rect.left(), rect.top()
        x_start = x0 - h
        x_end   = x0 + rect.width() + h
        x = x_start - (x_start % step)
        while x <= x_end:
            painter.drawLine(x, y0, x + h, y0 + h)
            x += step


class ClipWaveformView(QWidget):
    """Interactive waveform renderer for a single AudioClip.

    Renders the effective trim range stretched across the widget width,
    with cuts as dark overlays, fade segments as orange gradients,
    markers as cyan dots, selection as a translucent blue band, and a
    vertical playhead when driven by the sound editor's player.

    Inputs:
    - click (anywhere)   → scrub the playhead (``scrub_requested``)
    - shift + drag       → build a selection range (``selection_changed``)
    - double-click       → clear the current selection
    - right-click on a marker → ``marker_right_clicked``
    """

    scrub_requested = Signal(int)                   # source_ms
    selection_changed = Signal(int, int)            # start_ms, end_ms (source)
    selection_cleared = Signal()
    marker_right_clicked = Signal(int, QPoint)      # marker_idx, global_pos

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"background-color: {COLOR_BG_L2}; border-radius: 6px;"
        )
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Playback position in clip-local source ms (i.e. ms from the
        # start of the source file, not the project timeline). -1 when
        # nothing is playing.
        self._playhead_source_ms: int = -1
        # Selection stored in source-ms (same domain as clip.trim_*).
        # -1 means "no selection".
        self._selection_start_ms: int = -1
        self._selection_end_ms: int = -1
        # In-progress drag state.
        self._dragging_selection: bool = False
        self._drag_start_source_ms: int = 0

    # ---- public API ----

    def refresh(self) -> None:
        self.update()

    def set_playhead_source_ms(self, source_ms: int) -> None:
        self._playhead_source_ms = int(source_ms)
        self.update()

    def clear_playhead(self) -> None:
        self._playhead_source_ms = -1
        self.update()

    def selection(self) -> tuple[int, int] | None:
        if self._selection_start_ms >= 0 and self._selection_end_ms > self._selection_start_ms:
            return (self._selection_start_ms, self._selection_end_ms)
        return None

    def set_selection(self, start_ms: int, end_ms: int) -> None:
        if end_ms > start_ms:
            self._selection_start_ms = int(start_ms)
            self._selection_end_ms = int(end_ms)
            self.selection_changed.emit(self._selection_start_ms, self._selection_end_ms)
        else:
            self._selection_start_ms = -1
            self._selection_end_ms = -1
            self.selection_cleared.emit()
        self.update()

    def clear_selection(self) -> None:
        self.set_selection(0, 0)

    # ---- coordinate helpers ----

    def _content_rect(self) -> QRect:
        return self.rect().adjusted(8, 8, -8, -8)

    def _x_to_source_ms(self, x: int) -> int:
        rect = self._content_rect()
        if rect.width() <= 0:
            return self.clip.trim_start_ms
        eff = max(1, self.clip.effective_length_ms)
        local_ms = (x - rect.left()) / rect.width() * eff
        return self.clip.trim_start_ms + max(0, min(eff, int(round(local_ms))))

    def _source_ms_to_x(self, source_ms: int) -> int:
        rect = self._content_rect()
        eff = max(1, self.clip.effective_length_ms)
        local_ms = source_ms - self.clip.trim_start_ms
        return rect.left() + int(round(local_ms / eff * rect.width()))

    # ---- mouse ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click on a marker → notify the window.
            idx = self._marker_index_at_x(event.position().toPoint().x())
            if idx is not None:
                self.marker_right_clicked.emit(idx, event.globalPosition().toPoint())
                event.accept()
                return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        src_ms = self._x_to_source_ms(event.position().toPoint().x())
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            # Start building a selection without seeking.
            self._dragging_selection = True
            self._drag_start_source_ms = src_ms
            self._selection_start_ms = src_ms
            self._selection_end_ms = src_ms
            self.update()
            event.accept()
            return
        # Plain click = seek + also start a potential drag-selection if
        # the user proceeds to drag. We seed the drag anchor but only
        # commit a selection when the cursor actually moves.
        self._dragging_selection = True
        self._drag_start_source_ms = src_ms
        self._selection_start_ms = -1
        self._selection_end_ms = -1
        self.scrub_requested.emit(src_ms)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging_selection:
            return
        src_ms = self._x_to_source_ms(event.position().toPoint().x())
        if abs(src_ms - self._drag_start_source_ms) < 20:
            return  # too-small drag — keep as a click
        start = min(self._drag_start_source_ms, src_ms)
        end = max(self._drag_start_source_ms, src_ms)
        self._selection_start_ms = start
        self._selection_end_ms = end
        self.selection_changed.emit(start, end)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_selection = False
        # If we only clicked (no drag), leave selection cleared.
        if (
            self._selection_start_ms >= 0
            and self._selection_end_ms == self._selection_start_ms
        ):
            self._selection_start_ms = -1
            self._selection_end_ms = -1
            self.selection_cleared.emit()
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_selection()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # ---- markers ----

    def _marker_index_at_x(self, x: int) -> int | None:
        markers = getattr(self.clip, "_se_markers", None) or []
        for i, m_ms in enumerate(markers):
            mx = self._source_ms_to_x(int(m_ms))
            if abs(mx - x) <= 5:
                return i
        return None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(self.rect(), QColor(COLOR_BG_L2))
        painter.setPen(QPen(QColor("#6bb1c9"), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        clip = self.clip
        eff_len = max(1, clip.effective_length_ms)
        mid_y = rect.top() + rect.height() // 2

        # --- waveform ---
        wf = clip.waveform
        if wf is not None and wf.size > 0:
            import numpy as _np
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
            n = wf.shape[1] if is_stereo else len(wf)
            # Merge stereo to mono for the large single-canvas view
            mono = (wf[0] + wf[1]) * 0.5 if is_stereo else wf
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = (rect.height() - 10) // 2
            px_per_sec = rect.width() / (eff_len / 1000.0)
            xs = _np.arange(rect.left() + 2, rect.right() - 1, dtype=_np.float64)
            src_s = trim_start_s + (xs - rect.left()) / max(px_per_sec, 0.001)
            buckets = (src_s * WAVEFORM_BUCKETS_PER_SEC).astype(_np.int32)
            valid = (buckets >= 0) & (buckets < n)
            bc = _np.clip(buckets, 0, n - 1)
            m_raw = _np.where(valid, mono[bc], 0.0)
            peak_max = max(float(m_raw.max()), 0.005)
            m_h = (m_raw / peak_max) ** 0.6 * half_h * 0.88
            pts_top = [QPointF(float(xs[i]), float(mid_y - m_h[i])) for i in range(len(xs))]
            pts_bot = [QPointF(float(xs[i]), float(mid_y + m_h[i])) for i in range(len(xs) - 1, -1, -1)]
            poly_pts = [QPointF(float(xs[0]), float(mid_y))] + pts_top + [QPointF(float(xs[-1]), float(mid_y))] + pts_bot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(160, 220, 255, 180))
            painter.drawPolygon(QPolygonF(poly_pts))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter,
                tr("veditor.sound_editor.waveform_loading"),
            )

        # --- cuts (clip-local ms → rect.x) ---
        for cut in clip.cuts:
            x1 = rect.left() + int(cut.start_ms / eff_len * rect.width())
            x2 = rect.left() + int(cut.end_ms / eff_len * rect.width())
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(),
                QColor(30, 30, 30, 200),
            )

        # --- fade segments (source-ms → clip-local) ---
        from PySide6.QtGui import QLinearGradient
        for fade in clip.fades:
            local_start = fade.start_ms - clip.trim_start_ms
            local_end = fade.end_ms - clip.trim_start_ms
            if local_end <= 0 or local_start >= eff_len:
                continue
            fx1 = rect.left() + int(max(0, local_start) / eff_len * rect.width())
            fx2 = rect.left() + int(min(eff_len, local_end) / eff_len * rect.width())
            kind = getattr(fade, "kind", "both")
            painter.save()
            painter.setClipRect(rect)
            if kind == "in":
                g = QLinearGradient(fx1, 0, fx2, 0)
                g.setColorAt(0.0, QColor(0, 0, 0, 180))
                g.setColorAt(1.0, QColor(216, 90, 48, 0))
                painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), g)
            elif kind == "out":
                g = QLinearGradient(fx1, 0, fx2, 0)
                g.setColorAt(0.0, QColor(216, 90, 48, 0))
                g.setColorAt(1.0, QColor(0, 0, 0, 180))
                painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), g)
            else:
                mid = (fx1 + fx2) // 2
                g1 = QLinearGradient(fx1, 0, mid, 0)
                g1.setColorAt(0.0, QColor(216, 90, 48, 0))
                g1.setColorAt(1.0, QColor(0, 0, 0, 180))
                painter.fillRect(fx1, rect.top(), mid - fx1, rect.height(), g1)
                g2 = QLinearGradient(mid, 0, fx2, 0)
                g2.setColorAt(0.0, QColor(0, 0, 0, 180))
                g2.setColorAt(1.0, QColor(216, 90, 48, 0))
                painter.fillRect(mid, rect.top(), fx2 - mid, rect.height(), g2)
            painter.restore()
            painter.setPen(QPen(QColor(COLOR_ACCENT_ORANGE), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(fx1, rect.top(), max(1, fx2 - fx1), rect.height())

        # --- selection band (source-ms range) ---
        if (
            self._selection_start_ms >= 0
            and self._selection_end_ms > self._selection_start_ms
        ):
            sx1 = self._source_ms_to_x(self._selection_start_ms)
            sx2 = self._source_ms_to_x(self._selection_end_ms)
            sel_rect = QRect(sx1, rect.top(), max(1, sx2 - sx1), rect.height())
            painter.fillRect(sel_rect, QColor(55, 138, 221, 80))
            pen = QPen(QColor(COLOR_ACCENT_BLUE))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_rect)

        # --- markers (clip._se_markers, source-ms) ---
        markers = getattr(clip, "_se_markers", None) or []
        if markers:
            painter.setPen(Qt.PenStyle.NoPen)
            marker_color = QColor("#ff7a4a")
            for m_ms in markers:
                if m_ms < clip.trim_start_ms or m_ms > clip.effective_trim_end_ms:
                    continue
                mx = self._source_ms_to_x(int(m_ms))
                # Vertical guide line
                painter.setPen(QPen(QColor(93, 202, 165, 140), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(mx, rect.top() + 6, mx, rect.bottom() - 2)
                # Triangle flag at the top
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(marker_color)
                from PySide6.QtCore import QPoint as _QP2
                from PySide6.QtGui import QPolygon as _QPoly2
                painter.drawPolygon(
                    _QPoly2([
                        _QP2(mx - 4, rect.top()),
                        _QP2(mx + 4, rect.top()),
                        _QP2(mx, rect.top() + 7),
                    ])
                )

        # --- playhead ---
        if self._playhead_source_ms >= 0:
            local_ms = self._playhead_source_ms - clip.trim_start_ms
            if 0 <= local_ms <= eff_len:
                px = rect.left() + int(local_ms / eff_len * rect.width())
                pen = QPen(QColor(COLOR_ACCENT_ORANGE))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(px, rect.top(), px, rect.bottom())
                painter.setBrush(QColor(COLOR_ACCENT_ORANGE))
                painter.setPen(QColor("#ff7a4a"))
                from PySide6.QtCore import QPoint as _QP
                from PySide6.QtGui import QPolygon
                painter.drawPolygon(
                    QPolygon([
                        _QP(px, rect.top()),
                        _QP(px + 5, rect.top() + 6),
                        _QP(px, rect.top() + 12),
                        _QP(px - 5, rect.top() + 6),
                    ])
                )


class SpectrumExtractor(QThread):
    """Background FFT-based spectrum analyser.

    Extracts 8192 PCM samples from the middle of the audio file at 44100 Hz,
    applies a real FFT, and maps the result to 64 log-spaced magnitude bins
    spanning 20 Hz – 20 kHz (normalised 0-1).  Emits ``ready(bins)`` where
    *bins* is a ``numpy.ndarray`` of shape ``(64,)`` and dtype ``float32``,
    or ``ready(None)`` on failure / no audio stream.
    """

    ready = Signal(object)  # np.ndarray float32 shape (64,) or None

    def __init__(self, path: "Path") -> None:
        super().__init__()
        self._path = Path(path)

    def run(self) -> None:  # noqa: C901
        import sys
        try:
            import subprocess

            import numpy as np
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg = get_ffmpeg_exe()
            target_sr = 44100
            n_samples = 8192

            # ---- probe duration so we can seek to the middle ----
            # Use -v info so stream info (including "Audio:") appears in stderr.
            probe_cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "info",
                "-i", str(self._path),
            ]
            probe = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(0x08000000 if sys.platform == "win32" else 0),
            )
            stderr_txt = probe.stderr or ""
            if "Audio:" not in stderr_txt:
                self.ready.emit(None)
                return

            import re
            dur_m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_txt)
            duration_s = 0.0
            if dur_m:
                h, mn, s = int(dur_m.group(1)), int(dur_m.group(2)), float(dur_m.group(3))
                duration_s = h * 3600 + mn * 60 + s

            # Seek to the middle (but not closer than 0.5 s before end).
            seek_s = max(0.0, min(duration_s / 2.0, duration_s - n_samples / target_sr - 0.1))

            # ---- extract raw PCM ----
            cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "error",
                "-ss", f"{seek_s:.3f}",
                "-i", str(self._path),
                "-map", "0:a:0",
                "-ac", "1",                # mono
                "-ar", str(target_sr),
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "-t", f"{n_samples / target_sr:.6f}",
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=(0x08000000 if sys.platform == "win32" else 0),
            )
            raw, _ = proc.communicate()
            if not raw:
                self.ready.emit(None)
                return

            pcm = np.frombuffer(raw, dtype=np.float32)
            if pcm.size == 0:
                self.ready.emit(None)
                return

            # Zero-pad or truncate to exactly n_samples for a clean FFT.
            if pcm.size < n_samples:
                pcm = np.pad(pcm, (0, n_samples - pcm.size))
            else:
                pcm = pcm[:n_samples]

            # Apply Hann window to reduce spectral leakage.
            window = np.hanning(n_samples).astype(np.float32)
            pcm = pcm * window

            # Real FFT — only positive frequencies.
            fft_out = np.fft.rfft(pcm)
            magnitude = np.abs(fft_out).astype(np.float32)

            # Frequency axis for each FFT bin.
            freqs = np.fft.rfftfreq(n_samples, d=1.0 / target_sr).astype(np.float32)

            # Map into 64 log-spaced bins from 20 Hz to 20 kHz.
            n_bins = 64
            f_min, f_max = 20.0, 20000.0
            bin_edges = np.logspace(np.log10(f_min), np.log10(f_max), n_bins + 1)

            out_bins = np.zeros(n_bins, dtype=np.float32)
            for i in range(n_bins):
                mask = (freqs >= bin_edges[i]) & (freqs < bin_edges[i + 1])
                if mask.any():
                    out_bins[i] = magnitude[mask].mean()

            # Normalise to 0-1 (avoid div-by-zero on silence).
            peak = out_bins.max()
            if peak > 0:
                out_bins /= peak

            self.ready.emit(out_bins)

        except Exception:
            self.ready.emit(None)


class SpectrumView(QWidget):
    """Displays 64 log-spaced magnitude bars (20 Hz – 20 kHz).

    While analysis is pending, shows a gray placeholder with Korean status
    text.  Bar colours follow the DaVinci Resolve convention:
      0 – 60 %  →  green
      60 – 80 % →  yellow
      80 – 100 % → red
    Frequency labels (20 Hz / 1 kHz / 20 kHz) are shown on the bottom axis.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(90)
        self._bins = None  # type: None | object  # np.ndarray or None sentinel

    def set_bins(self, bins) -> None:
        """Slot connected to SpectrumExtractor.ready."""
        self._bins = bins  # may be None (failed) or ndarray
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bg = QColor("#1a1a22")
        painter.fillRect(self.rect(), bg)

        w, h = self.width(), self.height()
        label_h = 14  # pixels reserved at bottom for freq labels
        bar_area_h = h - label_h

        try:
            import numpy as np
            bins_available = (
                self._bins is not None
                and isinstance(self._bins, np.ndarray)
                and self._bins.size > 0
            )
        except ImportError:
            bins_available = False

        if not bins_available:
            # ---- placeholder ----
            painter.setPen(QColor("#555566"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            text = "분석 중..." if self._bins is None else "오디오 없음"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            return

        n = len(self._bins)
        if n == 0:
            painter.end()
            return

        bar_w = max(1, w / n)
        gap = max(0, bar_w - max(1, bar_w * 0.8))

        for i, val in enumerate(self._bins):
            val = float(val)
            bar_h = int(val * bar_area_h)
            if bar_h < 1:
                continue
            x = int(i * bar_w)
            y = bar_area_h - bar_h

            if val <= 0.6:
                color = QColor("#2ecc71")   # green
            elif val <= 0.8:
                color = QColor("#f1c40f")   # yellow
            else:
                color = QColor("#e74c3c")   # red

            painter.fillRect(int(x), y, max(1, int(bar_w - gap)), bar_h, color)

        # ---- frequency axis labels ----
        painter.setPen(QColor("#888899"))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)

        import math as _math
        f_min, f_max = 20.0, 20000.0
        label_info = [
            (20.0,    "20Hz"),
            (1000.0,  "1kHz"),
            (20000.0, "20kHz"),
        ]
        log_range = _math.log10(f_max) - _math.log10(f_min)
        for freq, lbl in label_info:
            ratio = (_math.log10(freq) - _math.log10(f_min)) / log_range
            lx = int(ratio * w)
            painter.drawText(lx - 16, bar_area_h, 32, label_h,
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                             lbl)

        painter.end()


class SoundEditorWindow(QWidget):
    """Knob-based per-clip audio editor (Phase 1/2 of SOUND_EDITOR_SPEC).

    Layout:
        TitleBar
        FileInfo        — filename + duration + cuts/fades counts
        Waveform        — full trimmed peaks + playhead + cut/fade markup
        TabBar          — Basic (live), EQ / Dynamics / Effects / Advanced (placeholders)
        TabContent
            Basic       — 6 knobs (Volume, Pan, Fade In, Fade Out, Speed, Pitch)
                         + action row (Mute, Reverse, Reset All)
                         + preset row
        Transport       — ▶/⏸ + time + 🔊 volume + Apply / Close

    The six Basic-tab knob values flow into the clip (fade_in_ms, fade_out_ms)
    and the track volume slider on the main timeline. Speed / Pitch / Pan are
    stashed on the clip for later wiring into the FFmpeg export filter.
    """

    # Preset definitions (Basic tab). Values match the spec.
    BASIC_PRESETS: dict[str, dict[str, float]] = {
        "Voice Recording": dict(volume=3, pan=0, fade_in=0.1, fade_out=0.3, speed=1.0, pitch=0),
        "Background Music": dict(volume=-6, pan=0, fade_in=1.5, fade_out=2.0, speed=1.0, pitch=0),
        "Game Audio":      dict(volume=0, pan=0, fade_in=0, fade_out=0.2, speed=1.0, pitch=0),
        "Podcast":         dict(volume=2, pan=0, fade_in=0.5, fade_out=0.5, speed=1.0, pitch=0),
    }

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.clip = clip
        name = clip.display_name or "(unnamed)"
        self.setWindowTitle(tr("veditor.sound_editor.title", name=name))
        self.resize(900, 680)
        self.setStyleSheet(self._qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar(name))
        root.addWidget(self._build_file_info())

        # Waveform section (reuses the existing ClipWaveformView).
        wf_wrap = QWidget()
        wf_wrap.setObjectName("SEWaveformSection")
        wf_layout = QVBoxLayout(wf_wrap)
        wf_layout.setContentsMargins(20, 16, 20, 16)
        self._waveform_view = ClipWaveformView(clip, wf_wrap)
        self._waveform_view.setMinimumHeight(100)
        wf_layout.addWidget(self._waveform_view)
        root.addWidget(wf_wrap)

        # ---- Spectrum analyser ----
        self._spectrum_view = SpectrumView()
        root.addWidget(self._spectrum_view)
        self._spectrum_extractor = None  # type: SpectrumExtractor | None
        if clip.source_path is not None:
            self._start_spectrum_extractor(clip.source_path)

        root.addWidget(self._build_tab_bar())
        root.addWidget(self._build_tab_content(), stretch=1)
        root.addWidget(self._build_transport())

        # ---- Local playback engine ----
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self._player_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._player_output)
        if clip.source_path is not None:
            self._player.setSource(QUrl.fromLocalFile(str(clip.source_path)))
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.positionChanged.connect(self._on_player_position)
        self._player_output.setVolume(0.8)
        self._transport_volume_slider.setValue(80)

        # Wire waveform-view signals once all referenced slots exist.
        self._waveform_view.scrub_requested.connect(self._on_waveform_scrub)
        self._waveform_view.selection_changed.connect(self._on_waveform_selection)
        self._waveform_view.selection_cleared.connect(self._on_waveform_selection_cleared)
        self._waveform_view.marker_right_clicked.connect(self._on_marker_right_clicked)

    # -------- Spectrum helpers --------

    def _start_spectrum_extractor(self, path: "Path") -> None:
        """Launch a fresh SpectrumExtractor thread for *path*."""
        if self._spectrum_extractor is not None:
            self._spectrum_extractor.quit()
            self._spectrum_extractor.wait(500)
        ext = SpectrumExtractor(path)
        ext.ready.connect(self._spectrum_view.set_bins)
        ext.finished.connect(ext.deleteLater)
        self._spectrum_extractor = ext
        ext.start()

    def refresh_spectrum(self) -> None:
        """Restart the spectrum analysis (call after changing source_path)."""
        if self.clip.source_path is not None:
            self._start_spectrum_extractor(self.clip.source_path)
        else:
            self._spectrum_view.set_bins(None)

    # -------- QSS --------

    def _qss(self) -> str:
        return f"""
            QWidget {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}
            QWidget#SETitleBar {{
                background-color: {COLOR_BG_L4};
                border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QWidget#SEFileInfo {{
                background-color: #1e1e22;
                border-bottom: 1px solid {COLOR_BG_L4};
            }}
            QWidget#SEWaveformSection {{
                background-color: #0f0f14;
                border-bottom: 1px solid {COLOR_BG_L4};
            }}
            QWidget#SETabBar {{
                background-color: {COLOR_BG_L4};
                border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QPushButton#SETab {{
                background: transparent;
                color: {COLOR_TEXT_TERTIARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 18px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton#SETab:hover {{ color: {COLOR_TEXT_SECONDARY}; }}
            QPushButton#SETab:checked {{
                color: {COLOR_ACCENT_BLUE};
                border-bottom: 2px solid {COLOR_ACCENT_BLUE};
            }}
            /* AI Master tab uses the orange accent so users can see
               at a glance which tab drives the post-processing chain. */
            QPushButton#SETabAI {{
                background: transparent;
                color: #D85A30;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 18px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton#SETabAI:hover {{ color: #ff7a4a; }}
            QPushButton#SETabAI:checked {{
                color: #ff7a4a;
                border-bottom: 2px solid #D85A30;
            }}
            QWidget#SEContent {{ background-color: {COLOR_BG_L3}; }}
            QWidget#SETransport {{
                background-color: {COLOR_BG_L4};
                border-top: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QPushButton#SEActionBtn {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#SEActionBtn:hover {{
                background-color: #44444a;
                border-color: #6a6a72;
            }}
            QPushButton#SEActionBtn:checked {{
                background-color: {COLOR_ACCENT_BLUE};
                border-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton#SEPresetBtn {{
                background-color: transparent;
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QPushButton#SEPresetBtn:hover {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_ACCENT_BLUE};
            }}
            /* AI Master preset tiles: bigger, 3x2 grid, orange accent. */
            QPushButton#SEAIPresetBtn {{
                background-color: rgba(216, 90, 48, 0.08);
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid rgba(216, 90, 48, 0.35);
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#SEAIPresetBtn:hover {{
                background-color: rgba(216, 90, 48, 0.18);
                color: #ff7a4a;
                border-color: #D85A30;
            }}
            QPushButton#SEAIPresetBtn[selected="true"] {{
                background-color: rgba(216, 90, 48, 0.25);
                color: #fff;
                border-color: #D85A30;
            }}
            QPushButton#SEPlayBtn {{
                background-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#SEPlayBtn:hover {{ background-color: {COLOR_ACCENT_BLUE_HOVER}; }}
            QPushButton#SEClose {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#SEApply {{
                background-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
        """

    # -------- section builders --------

    def _build_title_bar(self, name: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETitleBar")
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)
        icon = QLabel("🎵")
        icon.setStyleSheet("font-size: 16px;")
        title = QLabel(tr("veditor.sound_editor.header"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; font-size: 13px;")
        sub = QLabel(f"— {name}")
        sub.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        return bar

    def _build_file_info(self) -> QWidget:
        info = QWidget()
        info.setObjectName("SEFileInfo")
        lay = QVBoxLayout(info)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(6)
        name = QLabel(self.clip.display_name or "(unnamed)")
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(name)

        meta_bits: list[str] = []
        if self.clip.duration_ms > 0:
            meta_bits.append(f"⏱ {self.clip.duration_ms / 1000.0:.2f} s")
        meta_bits.append(f"✂ {len(self.clip.cuts)} cuts")
        meta_bits.append(f"⫷ {len(self.clip.fades)} fades")
        if self.clip.source_path is not None:
            meta_bits.append(f"📁 {self.clip.source_path.name}")
        meta = QLabel("   ".join(meta_bits))
        meta.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; font-family: Consolas, monospace;"
        )
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(meta)
        return info

    def _build_tab_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETabBar")
        bar.setFixedHeight(42)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        from PySide6.QtWidgets import QButtonGroup

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        tabs = [
            ("basic", tr("veditor.sound_editor.tab.basic")),
            ("eq", tr("veditor.sound_editor.tab.eq")),
            ("dynamics", tr("veditor.sound_editor.tab.dynamics")),
            ("effects", tr("veditor.sound_editor.tab.effects")),
            ("advanced", tr("veditor.sound_editor.tab.advanced")),
            ("ai_master", tr("veditor.sound_editor.tab.ai_master")),
        ]
        self._tab_buttons: dict[str, QPushButton] = {}
        for tab_id, tab_label in tabs:
            # "AI Master" gets an orange accent + "NEW" badge appended
            # via HTML — QPushButton supports rich text through a
            # QTextDocument paint path. Simplest trick: append NEW as
            # a unicode suffix styled via QSS descendant selectors.
            if tab_id == "ai_master":
                btn = QPushButton(f"{tab_label}  NEW")
                btn.setObjectName("SETabAI")
            else:
                btn = QPushButton(tab_label)
                btn.setObjectName("SETab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if tab_id == "basic":
                btn.setChecked(True)
            btn.clicked.connect(lambda _c, t=tab_id: self._switch_tab(t))
            self._tab_group.addButton(btn)
            self._tab_buttons[tab_id] = btn
            lay.addWidget(btn)
        lay.addStretch(1)
        return bar

    def _build_tab_content(self) -> QWidget:
        from PySide6.QtWidgets import QStackedWidget

        self._tab_stack = QStackedWidget()
        self._tab_stack.setObjectName("SEContent")
        # Wrap every tab in a QScrollArea so when the sound editor is
        # resized short the tab content scrolls instead of clipping
        # knob rows / clamping section headers off-screen.
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_basic_tab()))      # 0
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_eq_tab()))          # 1
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_dynamics_tab()))    # 2
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_effects_tab()))     # 3
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_advanced_tab()))    # 4
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_ai_master_tab()))   # 5
        return self._tab_stack

    def _wrap_tab_in_scroll(self, tab_widget: QWidget) -> QWidget:
        """Wrap a sound-editor tab in a QScrollArea. Vertical scroll
        appears only when the tab's natural height exceeds the
        viewport (the editor lives in a fixed-size dialog so this
        kicks in the moment the user shrinks it)."""
        scroll = QScrollArea()
        scroll.setWidget(tab_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        return scroll

    def _build_basic_tab(self) -> QWidget:
        from app.knob_widget import (
            KnobWidget,
            fmt_db, fmt_pan, fmt_seconds, fmt_semitones, fmt_speed,
        )

        c = self.clip
        # Map current clip state into knob starting values.
        init_vol_db = self._track_volume_to_db(self._get_track_volume())
        init_pan = 0.0  # Pan isn't stored yet — starts at center.
        init_fade_in = c.fade_in_ms / 1000.0
        init_fade_out = c.fade_out_ms / 1000.0
        init_speed = getattr(c, "_se_speed", 1.0)
        init_pitch = getattr(c, "_se_pitch", 0.0)

        panel = QWidget()
        panel.setObjectName("SEBasicTab")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # --- knob grid ---
        knob_row = QHBoxLayout()
        knob_row.setSpacing(12)

        self._knob_volume = KnobWidget(
            label="Volume", value=init_vol_db, minimum=-60, maximum=12,
            default=0, unit="dB", color="blue", formatter=fmt_db,
        )
        self._knob_pan = KnobWidget(
            label="Pan", value=init_pan, minimum=-100, maximum=100,
            default=0, color="green", bipolar=True, formatter=fmt_pan,
        )
        self._knob_fade_in = KnobWidget(
            label="Fade In", value=init_fade_in, minimum=0, maximum=10,
            default=0, unit=" s", color="blue", formatter=fmt_seconds,
        )
        self._knob_fade_out = KnobWidget(
            label="Fade Out", value=init_fade_out, minimum=0, maximum=10,
            default=0, unit=" s", color="blue", formatter=fmt_seconds,
        )
        self._knob_speed = KnobWidget(
            label="Speed", value=init_speed, minimum=0.5, maximum=2.0,
            default=1.0, color="orange", formatter=fmt_speed,
        )
        self._knob_pitch = KnobWidget(
            label="Pitch", value=init_pitch, minimum=-12, maximum=12,
            default=0, unit=" st", color="orange", formatter=fmt_semitones,
        )

        # Wire knobs to live state
        self._knob_volume.valueChanged.connect(self._on_volume_knob)
        self._knob_pan.valueChanged.connect(self._on_pan_knob)
        self._knob_fade_in.valueChanged.connect(self._on_fade_in_knob)
        self._knob_fade_out.valueChanged.connect(self._on_fade_out_knob)
        self._knob_speed.valueChanged.connect(self._on_speed_knob)
        self._knob_pitch.valueChanged.connect(self._on_pitch_knob)

        for k in (
            self._knob_volume, self._knob_pan,
            self._knob_fade_in, self._knob_fade_out,
            self._knob_speed, self._knob_pitch,
        ):
            knob_row.addWidget(k)
        knob_row.addStretch(1)
        root.addLayout(knob_row)

        # --- action buttons ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._btn_mute = QPushButton(tr("veditor.sound_editor.basic.mute"))
        self._btn_mute.setObjectName("SEActionBtn")
        self._btn_mute.setCheckable(True)
        self._btn_mute.toggled.connect(self._on_mute_toggled)
        self._btn_reverse = QPushButton(tr("veditor.sound_editor.basic.reverse"))
        self._btn_reverse.setObjectName("SEActionBtn")
        self._btn_reverse.setCheckable(True)
        self._btn_reverse.toggled.connect(
            lambda on: setattr(self.clip, "_se_reverse", on)
        )
        self._btn_reset = QPushButton(tr("veditor.sound_editor.basic.reset_all"))
        self._btn_reset.setObjectName("SEActionBtn")
        self._btn_reset.clicked.connect(self._reset_basic_to_defaults)

        actions.addWidget(self._btn_mute)
        actions.addWidget(self._btn_reverse)
        actions.addSpacing(20)
        actions.addWidget(self._btn_reset)
        actions.addStretch(1)
        root.addLayout(actions)

        # --- presets ---
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        presets_label = QLabel(tr("veditor.sound_editor.basic.presets"))
        presets_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        presets_row.addWidget(presets_label)
        for preset_name in self.BASIC_PRESETS.keys():
            b = QPushButton(preset_name)
            b.setObjectName("SEPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, n=preset_name: self._apply_preset(n))
            presets_row.addWidget(b)
        presets_row.addStretch(1)
        root.addLayout(presets_row)

        root.addStretch(1)
        return panel

    # ========= EQ tab =========

    EQ_PRESETS: dict[str, dict] = {
        "Flat":        {"low_g": 0, "mid_g": 0, "high_g": 0},
        "Vocal Boost": {"low_g": -2, "mid_g": 4, "high_g": 2},
        "Bass Boost":  {"low_g": 6, "mid_g": 0, "high_g": 0},
        "Podcast":     {"low_g": -3, "mid_g": 2, "high_g": 3},
        "Treble Cut":  {"low_g": 0, "mid_g": 0, "high_g": -4},
    }

    def _build_eq_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_hz
        eq = self.clip.effects["eq"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # Enable toggle at top
        self._eq_enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
        self._eq_enabled_btn.setObjectName("SEActionBtn")
        self._eq_enabled_btn.setCheckable(True)
        self._eq_enabled_btn.setChecked(bool(eq.get("enabled")))
        self._eq_enabled_btn.toggled.connect(lambda on: self._set_fx("eq", "enabled", on))
        row_top = QHBoxLayout()
        row_top.addWidget(self._eq_enabled_btn)
        row_top.addStretch(1)
        root.addLayout(row_top)

        # Curve visualization
        self._eq_curve = _EqCurveView(self.clip)
        self._eq_curve.setFixedHeight(88)
        root.addWidget(self._eq_curve)

        # 3 band rows (each with Freq / Gain / Q)
        def _band_ui(band: str, freq_range: tuple[float, float]) -> QHBoxLayout:
            band_state = eq[band]
            row = QHBoxLayout()
            row.setSpacing(10)
            lbl = QLabel(band.upper())
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; "
                f"font-weight: 700; letter-spacing: 2px; min-width: 50px;"
            )
            row.addWidget(lbl)

            k_freq = KnobWidget(
                label="Freq", value=band_state["freq"],
                minimum=freq_range[0], maximum=freq_range[1],
                default=band_state["freq"],
                color="blue", logarithmic=True, formatter=fmt_hz,
            )
            k_gain = KnobWidget(
                label="Gain", value=band_state["gain"],
                minimum=-12, maximum=12, default=0,
                color="green", bipolar=True, formatter=fmt_db,
            )
            k_q = KnobWidget(
                label="Q", value=band_state["q"],
                minimum=0.1, maximum=10, default=band_state["q"],
                color="orange",
                formatter=lambda v: f"{v:.2f}",
            )
            k_freq.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "freq"), v))
            k_gain.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "gain"), v))
            k_q.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "q"), v))
            row.addWidget(k_freq)
            row.addWidget(k_gain)
            row.addWidget(k_q)
            row.addStretch(1)
            return row

        root.addLayout(_band_ui("low", (20, 250)))
        root.addLayout(_band_ui("mid", (200, 5000)))
        root.addLayout(_band_ui("high", (2000, 20000)))

        # Presets
        root.addLayout(self._preset_row(
            self.EQ_PRESETS.keys(),
            lambda name: self._apply_eq_preset(name),
        ))
        root.addStretch(1)
        return panel

    def _apply_eq_preset(self, name: str) -> None:
        p = self.EQ_PRESETS.get(name) or {}
        eq = self.clip.effects["eq"]
        eq["low"]["gain"]  = p.get("low_g", 0)
        eq["mid"]["gain"]  = p.get("mid_g", 0)
        eq["high"]["gain"] = p.get("high_g", 0)
        eq["enabled"] = True
        self._eq_enabled_btn.setChecked(True)
        self._eq_curve.refresh()
        self._rebuild_tab_ui()

    # ========= Dynamics tab =========

    DYN_PRESETS: dict[str, dict] = {
        "Voice Gentle": {"thr": -20, "ratio": 3, "atk": 5, "rel": 120, "makeup": 2, "knee": 4},
        "Voice Strong": {"thr": -24, "ratio": 6, "atk": 2, "rel": 80,  "makeup": 4, "knee": 2},
        "Podcast":      {"thr": -18, "ratio": 4, "atk": 5, "rel": 150, "makeup": 3, "knee": 3},
    }

    def _build_dynamics_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db
        comp = self.clip.effects["comp"]
        gate = self.clip.effects["gate"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- Compressor ---
        comp_header = self._fx_header(
            tr("veditor.sound_editor.dyn.compressor"),
            "comp",
        )
        self._comp_enabled_btn = comp_header[1]
        root.addWidget(comp_header[0])

        comp_row = QHBoxLayout()
        comp_row.setSpacing(10)

        k_thr = KnobWidget(
            label="Threshold", value=comp["threshold"], minimum=-60, maximum=0,
            default=-20, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_ratio = KnobWidget(
            label="Ratio", value=comp["ratio"], minimum=1, maximum=20,
            default=4, color="orange", formatter=lambda v: f"{v:.1f}:1",
        )
        k_atk = KnobWidget(
            label="Attack", value=comp["attack_ms"], minimum=0.1, maximum=100,
            default=5, color="green", logarithmic=True, formatter=lambda v: f"{v:.1f} ms",
        )
        k_rel = KnobWidget(
            label="Release", value=comp["release_ms"], minimum=10, maximum=1000,
            default=150, color="green", logarithmic=True, formatter=lambda v: f"{v:.0f} ms",
        )
        k_makeup = KnobWidget(
            label="Makeup", value=comp["makeup_db"], minimum=0, maximum=24,
            default=0, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_knee = KnobWidget(
            label="Knee", value=comp["knee_db"], minimum=0, maximum=10,
            default=2, color="orange", formatter=lambda v: f"{v:.1f} dB",
        )
        k_thr.valueChanged.connect(lambda v: self._set_fx("comp", "threshold", v))
        k_ratio.valueChanged.connect(lambda v: self._set_fx("comp", "ratio", v))
        k_atk.valueChanged.connect(lambda v: self._set_fx("comp", "attack_ms", v))
        k_rel.valueChanged.connect(lambda v: self._set_fx("comp", "release_ms", v))
        k_makeup.valueChanged.connect(lambda v: self._set_fx("comp", "makeup_db", v))
        k_knee.valueChanged.connect(lambda v: self._set_fx("comp", "knee_db", v))
        for k in (k_thr, k_ratio, k_atk, k_rel, k_makeup, k_knee):
            comp_row.addWidget(k)
        comp_row.addStretch(1)
        root.addLayout(comp_row)

        # Presets
        root.addLayout(self._preset_row(
            self.DYN_PRESETS.keys(),
            lambda name: self._apply_dyn_preset(name),
        ))

        # --- Gate ---
        gate_header = self._fx_header(
            tr("veditor.sound_editor.dyn.gate"),
            "gate",
        )
        self._gate_enabled_btn = gate_header[1]
        root.addWidget(gate_header[0])

        gate_row = QHBoxLayout()
        gate_row.setSpacing(10)
        k_gthr = KnobWidget(
            label="Threshold", value=gate["threshold"], minimum=-80, maximum=0,
            default=-50, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_gred = KnobWidget(
            label="Reduction", value=gate["reduction"], minimum=0, maximum=100,
            default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_gthr.valueChanged.connect(lambda v: self._set_fx("gate", "threshold", v))
        k_gred.valueChanged.connect(lambda v: self._set_fx("gate", "reduction", v))
        gate_row.addWidget(k_gthr)
        gate_row.addWidget(k_gred)
        gate_row.addStretch(1)
        root.addLayout(gate_row)

        root.addStretch(1)
        return panel

    def _apply_dyn_preset(self, name: str) -> None:
        p = self.DYN_PRESETS.get(name) or {}
        c = self.clip.effects["comp"]
        c["threshold"] = p.get("thr", c["threshold"])
        c["ratio"]     = p.get("ratio", c["ratio"])
        c["attack_ms"] = p.get("atk", c["attack_ms"])
        c["release_ms"] = p.get("rel", c["release_ms"])
        c["makeup_db"] = p.get("makeup", c["makeup_db"])
        c["knee_db"]   = p.get("knee", c["knee_db"])
        c["enabled"] = True
        self._comp_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Effects tab =========

    FX_PRESETS: dict[str, dict] = {
        "Small Room":   {"type": "Room",   "size": 20, "decay": 0.8, "damp": 60, "mix": 20},
        "Concert Hall": {"type": "Hall",   "size": 80, "decay": 3.0, "damp": 30, "mix": 35},
        "Plate":        {"type": "Plate",  "size": 50, "decay": 2.0, "damp": 40, "mix": 30},
        "Spring":       {"type": "Spring", "size": 30, "decay": 1.5, "damp": 50, "mix": 25},
        "Slap Delay":   {"type": "Room",   "size": 15, "decay": 0.5, "damp": 50, "mix": 15,
                         "_delay": {"time_ms": 150, "feedback": 0, "mix": 40}},
    }

    def _build_effects_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget

        rev = self.clip.effects["reverb"]
        delay = self.clip.effects["delay"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- Reverb ---
        rev_header_row = QHBoxLayout()
        rev_header = self._fx_header(
            tr("veditor.sound_editor.fx.reverb"), "reverb"
        )
        self._rev_enabled_btn = rev_header[1]
        rev_header_row.addWidget(rev_header[0])

        # Type dropdown
        from PySide6.QtWidgets import QComboBox
        self._rev_type = QComboBox()
        self._rev_type.addItems(["Room", "Hall", "Plate", "Spring"])
        self._rev_type.setCurrentText(rev["type"])
        self._rev_type.currentTextChanged.connect(
            lambda t: self._set_fx("reverb", "type", t)
        )
        rev_header_row.addWidget(self._rev_type)
        rev_header_row.addStretch(1)
        root.addLayout(rev_header_row)

        rev_row = QHBoxLayout()
        rev_row.setSpacing(10)
        k_size = KnobWidget(
            label="Size", value=rev["size"], minimum=0, maximum=100,
            default=30, color="blue", formatter=lambda v: f"{v:.0f} %",
        )
        k_decay = KnobWidget(
            label="Decay", value=rev["decay_s"], minimum=0.1, maximum=10,
            default=1.5, color="blue", formatter=lambda v: f"{v:.1f} s",
        )
        k_damp = KnobWidget(
            label="Damping", value=rev["damping"], minimum=0, maximum=100,
            default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_mix = KnobWidget(
            label="Mix", value=rev["mix"], minimum=0, maximum=100,
            default=20, color="green", formatter=lambda v: f"{v:.0f} %",
        )
        k_size.valueChanged.connect(lambda v: self._set_fx("reverb", "size", v))
        k_decay.valueChanged.connect(lambda v: self._set_fx("reverb", "decay_s", v))
        k_damp.valueChanged.connect(lambda v: self._set_fx("reverb", "damping", v))
        k_mix.valueChanged.connect(lambda v: self._set_fx("reverb", "mix", v))
        for k in (k_size, k_decay, k_damp, k_mix):
            rev_row.addWidget(k)
        rev_row.addStretch(1)
        root.addLayout(rev_row)

        root.addLayout(self._preset_row(
            self.FX_PRESETS.keys(),
            lambda name: self._apply_fx_preset(name),
        ))

        # --- Delay ---
        delay_header = self._fx_header(
            tr("veditor.sound_editor.fx.delay"), "delay"
        )
        self._delay_enabled_btn = delay_header[1]
        root.addWidget(delay_header[0])

        delay_row = QHBoxLayout()
        delay_row.setSpacing(10)
        k_time = KnobWidget(
            label="Time", value=delay["time_ms"], minimum=0, maximum=2000,
            default=250, color="blue", formatter=lambda v: f"{v:.0f} ms",
        )
        k_fb = KnobWidget(
            label="Feedback", value=delay["feedback"], minimum=0, maximum=95,
            default=30, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_dmix = KnobWidget(
            label="Mix", value=delay["mix"], minimum=0, maximum=100,
            default=20, color="green", formatter=lambda v: f"{v:.0f} %",
        )
        k_time.valueChanged.connect(lambda v: self._set_fx("delay", "time_ms", v))
        k_fb.valueChanged.connect(lambda v: self._set_fx("delay", "feedback", v))
        k_dmix.valueChanged.connect(lambda v: self._set_fx("delay", "mix", v))
        for k in (k_time, k_fb, k_dmix):
            delay_row.addWidget(k)
        delay_row.addStretch(1)
        root.addLayout(delay_row)

        root.addStretch(1)
        return panel

    def _apply_fx_preset(self, name: str) -> None:
        p = self.FX_PRESETS.get(name) or {}
        rev = self.clip.effects["reverb"]
        rev["type"] = p.get("type", rev["type"])
        rev["size"] = p.get("size", rev["size"])
        rev["decay_s"] = p.get("decay", rev["decay_s"])
        rev["damping"] = p.get("damp", rev["damping"])
        rev["mix"] = p.get("mix", rev["mix"])
        rev["enabled"] = True
        self._rev_enabled_btn.setChecked(True)
        # Slap Delay also drives the delay section.
        if "_delay" in p:
            d = self.clip.effects["delay"]
            d.update(p["_delay"])
            d["enabled"] = True
            self._delay_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Advanced tab =========

    def _build_advanced_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_hz, fmt_speed
        deess = self.clip.effects["deesser"]
        ts = self.clip.effects["time_stretch"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- De-esser ---
        deess_header = self._fx_header(
            tr("veditor.sound_editor.adv.deesser"), "deesser"
        )
        self._deess_enabled_btn = deess_header[1]
        root.addWidget(deess_header[0])

        deess_row = QHBoxLayout()
        deess_row.setSpacing(10)
        k_dfreq = KnobWidget(
            label="Frequency", value=deess["freq"], minimum=2000, maximum=12000,
            default=6000, color="blue", logarithmic=True, formatter=fmt_hz,
        )
        k_dthr = KnobWidget(
            label="Threshold", value=deess["threshold"], minimum=-60, maximum=0,
            default=-30, unit=" dB", color="green", formatter=fmt_db,
        )
        k_dred = KnobWidget(
            label="Reduction", value=deess["reduction"], minimum=0, maximum=100,
            default=40, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_dfreq.valueChanged.connect(lambda v: self._set_fx("deesser", "freq", v))
        k_dthr.valueChanged.connect(lambda v: self._set_fx("deesser", "threshold", v))
        k_dred.valueChanged.connect(lambda v: self._set_fx("deesser", "reduction", v))
        for k in (k_dfreq, k_dthr, k_dred):
            deess_row.addWidget(k)
        deess_row.addStretch(1)
        root.addLayout(deess_row)

        # --- Time Stretch ---
        ts_header = self._fx_header(
            tr("veditor.sound_editor.adv.time_stretch"), "time_stretch"
        )
        self._ts_enabled_btn = ts_header[1]
        root.addWidget(ts_header[0])

        ts_row = QHBoxLayout()
        ts_row.setSpacing(10)
        k_ratio = KnobWidget(
            label="Ratio", value=ts["ratio"], minimum=0.5, maximum=2.0,
            default=1.0, color="orange", formatter=fmt_speed,
        )
        k_ratio.valueChanged.connect(lambda v: self._set_fx("time_stretch", "ratio", v))
        ts_row.addWidget(k_ratio)

        # Algorithm dropdown
        from PySide6.QtWidgets import QComboBox
        self._ts_algo = QComboBox()
        self._ts_algo.addItems(["atempo", "rubberband"])
        self._ts_algo.setCurrentText(ts.get("algorithm", "atempo"))
        self._ts_algo.currentTextChanged.connect(
            lambda t: self._set_fx("time_stretch", "algorithm", t)
        )
        algo_label = QLabel(tr("veditor.sound_editor.adv.algorithm"))
        algo_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        ts_row.addWidget(algo_label)
        ts_row.addWidget(self._ts_algo)
        ts_row.addStretch(1)
        root.addLayout(ts_row)

        # --- Markers list ---
        markers_label = QLabel(tr("veditor.sound_editor.adv.markers"))
        markers_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1px; padding-top: 8px;"
        )
        root.addWidget(markers_label)

        from PySide6.QtWidgets import QListWidget
        self._markers_list = QListWidget()
        self._markers_list.setMaximumHeight(110)
        self._refresh_markers_list()
        # Jump to marker on double-click
        self._markers_list.itemDoubleClicked.connect(self._on_marker_list_dblclick)
        root.addWidget(self._markers_list)

        root.addStretch(1)
        return panel

    def _refresh_markers_list(self) -> None:
        if not hasattr(self, "_markers_list"):
            return
        self._markers_list.clear()
        for i, m_ms in enumerate(self._markers()):
            from PySide6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(f"#{i + 1}   {_format_ms(int(m_ms))}")
            it.setData(Qt.ItemDataRole.UserRole, int(m_ms))
            self._markers_list.addItem(it)

    def _on_marker_list_dblclick(self, item) -> None:
        ms = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        try:
            self._player.setPosition(ms)
        except Exception:
            pass

    # ========= AI Master tab =========

    # Per-model tuning for AI-generated music. Values are percentages /
    # dB matching the AI Master knob ranges. ``width`` is bipolar with
    # 100 as the neutral center.
    AI_PRESETS: dict[str, dict] = {
        "Suno v3":    {"air": 5, "clarity": 60, "warmth": 40, "width": 130, "punch": 50, "excite": 70},
        "Suno v4":    {"air": 3, "clarity": 50, "warmth": 30, "width": 120, "punch": 40, "excite": 50},
        "Udio":       {"air": 4, "clarity": 45, "warmth": 35, "width": 110, "punch": 55, "excite": 60},
        "ACE-Step":   {"air": 6, "clarity": 55, "warmth": 50, "width": 140, "punch": 45, "excite": 75},
        "Generic AI": {"air": 4, "clarity": 50, "warmth": 40, "width": 120, "punch": 50, "excite": 60},
        "Custom":     {"air": 0, "clarity": 0,  "warmth": 0,  "width": 100, "punch": 0,  "excite": 0},
    }

    def _build_ai_master_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_percentage
        ai = self.clip.effects["ai_master"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- One-Click Fix (preset buttons) ---
        preset_header = QLabel(tr("veditor.sound_editor.ai.one_click"))
        preset_header.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        root.addWidget(preset_header)

        # 6 preset buttons in a 3x2 grid — gives the AI-model labels
        # room to breathe without eating the knob row's vertical space.
        from PySide6.QtWidgets import QGridLayout
        preset_grid = QGridLayout()
        preset_grid.setSpacing(6)
        names = list(self.AI_PRESETS.keys())
        for idx, name in enumerate(names):
            b = QPushButton(name)
            b.setObjectName("SEAIPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            # Highlight the currently-applied preset.
            if ai.get("preset") == name:
                b.setProperty("selected", True)
            b.clicked.connect(lambda _c, n=name: self._apply_ai_preset(n))
            preset_grid.addWidget(b, idx // 3, idx % 3)
        root.addLayout(preset_grid)

        # --- Detailed controls (6 macro knobs) ---
        ctrl_header = self._fx_header(
            tr("veditor.sound_editor.ai.detailed"),
            "ai_master",
        )
        self._ai_enabled_btn = ctrl_header[1]
        root.addWidget(ctrl_header[0])

        knob_row = QHBoxLayout()
        knob_row.setSpacing(10)

        k_air = KnobWidget(
            label="Air", value=float(ai["air"]),
            minimum=0, maximum=8, default=0, unit=" dB",
            color="green", formatter=fmt_db,
        )
        k_clarity = KnobWidget(
            label="Clarity", value=float(ai["clarity"]),
            minimum=0, maximum=100, default=0,
            color="blue", formatter=fmt_percentage,
        )
        k_warmth = KnobWidget(
            label="Warmth", value=float(ai["warmth"]),
            minimum=0, maximum=100, default=0,
            color="orange", formatter=fmt_percentage,
        )
        k_width = KnobWidget(
            label="Width", value=float(ai["width"]),
            minimum=0, maximum=200, default=100,
            color="green", bipolar=True, formatter=fmt_percentage,
        )
        k_punch = KnobWidget(
            label="Punch", value=float(ai["punch"]),
            minimum=0, maximum=100, default=0,
            color="blue", formatter=fmt_percentage,
        )
        k_excite = KnobWidget(
            label="Excite", value=float(ai["excite"]),
            minimum=0, maximum=100, default=0,
            color="orange", formatter=fmt_percentage,
        )

        # Any knob touch implies "user wants custom tuning" — mark the
        # preset state as Custom so the grid highlight doesn't lie.
        def _on_knob(field: str, value: float) -> None:
            self._set_fx("ai_master", field, float(value))
            if self.clip.effects["ai_master"].get("preset") != "Custom":
                self._set_fx("ai_master", "preset", "Custom")

        k_air.valueChanged.connect(lambda v: _on_knob("air", v))
        k_clarity.valueChanged.connect(lambda v: _on_knob("clarity", v))
        k_warmth.valueChanged.connect(lambda v: _on_knob("warmth", v))
        k_width.valueChanged.connect(lambda v: _on_knob("width", v))
        k_punch.valueChanged.connect(lambda v: _on_knob("punch", v))
        k_excite.valueChanged.connect(lambda v: _on_knob("excite", v))

        for k in (k_air, k_clarity, k_warmth, k_width, k_punch, k_excite):
            knob_row.addWidget(k)
        knob_row.addStretch(1)
        root.addLayout(knob_row)

        # --- Per-knob description strip (mirrors the HTML mock) ---
        desc_row = QHBoxLayout()
        desc_row.setSpacing(10)
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            lbl = QLabel(tr(f"veditor.sound_editor.ai.desc.{key}"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setWordWrap(True)
            lbl.setFixedWidth(88)
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;"
            )
            desc_row.addWidget(lbl)
        desc_row.addStretch(1)
        root.addLayout(desc_row)

        # --- Hint / note ---
        note = QLabel(tr("veditor.sound_editor.ai.hint"))
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"padding-top: 6px;"
        )
        root.addWidget(note)

        root.addStretch(1)
        return panel

    def _apply_ai_preset(self, name: str) -> None:
        p = self.AI_PRESETS.get(name) or {}
        ai = self.clip.effects["ai_master"]
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            if key in p:
                ai[key] = float(p[key])
        ai["preset"] = name
        # Auto-enable unless the user explicitly picked Custom at zero.
        if name != "Custom":
            ai["enabled"] = True
        self._refresh_timeline_row()
        self._rebuild_tab_ui()

    # ========= shared helpers =========

    def _fx_header(self, title: str, fx_key: str) -> tuple[QWidget, QPushButton]:
        """Returns (header_row_widget, enable_toggle_button)."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 4, 0, 2)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
        enabled_btn.setObjectName("SEActionBtn")
        enabled_btn.setCheckable(True)
        enabled_btn.setChecked(bool(self.clip.effects[fx_key].get("enabled")))
        enabled_btn.toggled.connect(lambda on, k=fx_key: self._set_fx(k, "enabled", on))
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(enabled_btn)
        return container, enabled_btn

    def _preset_row(self, names, callback) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(6)
        lbl = QLabel(tr("veditor.sound_editor.basic.presets"))
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        r.addWidget(lbl)
        for name in names:
            b = QPushButton(name)
            b.setObjectName("SEPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, n=name: callback(n))
            r.addWidget(b)
        r.addStretch(1)
        return r

    def _set_fx(self, fx_key: str, sub_key, value) -> None:
        """Write a nested effect-state value. ``sub_key`` may be a
        string (top-level) or a tuple (band, field) for the 3-band EQ."""
        fx = self.clip.effects[fx_key]
        if isinstance(sub_key, tuple):
            a, b = sub_key
            fx[a][b] = value
        else:
            fx[sub_key] = value
        # Refresh dependent views.
        if fx_key == "eq" and hasattr(self, "_eq_curve"):
            self._eq_curve.refresh()
        self._refresh_timeline_row()

    def _rebuild_tab_ui(self) -> None:
        """Preset application changes many knob values at once — the
        simplest way to keep every widget in sync is to rebuild the
        affected tab. Called after preset application."""
        current = self._tab_stack.currentIndex()
        # Rebuild just the stack panels (preserves title/waveform).
        # Wrap each one in a scroll area, same as the initial build,
        # so user-shrunk windows still get scroll bars after a preset
        # rebuild instead of clipping.
        new_panels = [
            self._wrap_tab_in_scroll(self._build_basic_tab()),
            self._wrap_tab_in_scroll(self._build_eq_tab()),
            self._wrap_tab_in_scroll(self._build_dynamics_tab()),
            self._wrap_tab_in_scroll(self._build_effects_tab()),
            self._wrap_tab_in_scroll(self._build_advanced_tab()),
            self._wrap_tab_in_scroll(self._build_ai_master_tab()),
        ]
        # Swap in place.
        for i in range(self._tab_stack.count()):
            old = self._tab_stack.widget(0)
            self._tab_stack.removeWidget(old)
            old.deleteLater()
        for p in new_panels:
            self._tab_stack.addWidget(p)
        self._tab_stack.setCurrentIndex(current)


    def _build_transport(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETransport")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)

        def _mk_icon_btn(symbol: str, tooltip: str, handler) -> QPushButton:
            b = QPushButton(symbol)
            b.setObjectName("SEActionBtn")
            b.setFixedSize(32, 32)
            b.setToolTip(tooltip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(handler)
            return b

        self._prev_marker_btn = _mk_icon_btn(
            "⏮", tr("veditor.sound_editor.tooltip.prev_marker"),
            self._go_to_prev_marker,
        )
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("SEPlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.clicked.connect(self._toggle_play)
        self._next_marker_btn = _mk_icon_btn(
            "⏭", tr("veditor.sound_editor.tooltip.next_marker"),
            self._go_to_next_marker,
        )
        self._add_marker_btn = _mk_icon_btn(
            "📌", tr("veditor.sound_editor.tooltip.add_marker"),
            self._add_marker_at_playhead,
        )
        self._loop_btn = _mk_icon_btn(
            "🔁", tr("veditor.sound_editor.tooltip.loop"),
            lambda: None,  # replaced below
        )
        self._loop_btn.setCheckable(True)
        # We want toggled state, so replace the clicked handler with
        # a noop and rely on the checked state directly.
        self._loop_btn.clicked.disconnect()

        self._position_label = QLabel("0:00 / 0:00")
        self._position_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-family: Consolas, monospace; font-size: 12px;"
        )

        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 12px;")
        self._transport_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._transport_volume_slider.setRange(0, 100)
        self._transport_volume_slider.setFixedWidth(100)
        self._transport_volume_slider.valueChanged.connect(
            lambda v: self._player_output.setVolume(max(0.0, min(1.0, v / 100.0)))
        )

        # Audio export quality dropdown — sits left of the export
        # button. Default = "standard" (44.1 kHz / 192 kbps / 16-bit),
        # which matches the Free tier ceiling.
        from app.audio_tracks import DEFAULT_AUDIO_QUALITY_ID
        self._audio_export_quality_id = DEFAULT_AUDIO_QUALITY_ID
        self._audio_quality_btn = QToolButton()
        self._audio_quality_btn.setObjectName("AudioQualityDropdown")
        self._audio_quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._audio_quality_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup,
        )
        self._audio_quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
        self._audio_quality_btn.setMinimumHeight(28)
        self._audio_quality_btn.setStyleSheet(
            f"QToolButton#AudioQualityDropdown {{ "
            f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 3px 26px 3px 10px; font-size: 11px; }}"
            f"QToolButton#AudioQualityDropdown:hover {{ "
            f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
            f"QToolButton#AudioQualityDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 8px; }}"
        )
        self._refresh_audio_quality_btn_label()
        self._build_audio_quality_menu()

        self._export_btn = QPushButton(tr("veditor.sound_editor.export"))
        self._export_btn.setObjectName("SEClose")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setToolTip(tr("veditor.sound_editor.export.tooltip"))
        self._export_btn.clicked.connect(self._on_export_clicked)

        self._apply_btn = QPushButton(tr("veditor.sound_editor.apply"))
        self._apply_btn.setObjectName("SEApply")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.clicked.connect(self._apply_and_close)

        self._close_btn = QPushButton(tr("veditor.sound_editor.close"))
        self._close_btn.setObjectName("SEClose")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)

        lay.addWidget(self._prev_marker_btn)
        lay.addWidget(self._play_btn)
        lay.addWidget(self._next_marker_btn)
        lay.addSpacing(6)
        lay.addWidget(self._add_marker_btn)
        lay.addWidget(self._loop_btn)
        lay.addSpacing(10)
        lay.addWidget(self._position_label)
        lay.addStretch(1)
        lay.addWidget(vol_icon)
        lay.addWidget(self._transport_volume_slider)
        lay.addSpacing(14)
        lay.addWidget(self._audio_quality_btn)
        lay.addWidget(self._export_btn)
        lay.addWidget(self._close_btn)
        lay.addWidget(self._apply_btn)

        # --- keyboard shortcuts (scoped to this window) ---
        from PySide6.QtGui import QKeySequence, QShortcut
        for key, handler in (
            ("Space", self._toggle_play),
            ("M",     self._add_marker_at_playhead),
            ("L",     lambda: self._loop_btn.setChecked(not self._loop_btn.isChecked())),
            (",",     self._go_to_prev_marker),
            (".",     self._go_to_next_marker),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(handler)

        return bar

    # -------- state plumbing --------

    def _get_track_volume(self) -> float:
        """Find the parent AudioTrack's master volume, fall back to 1.0."""
        parent = self.parent()
        if parent is not None:
            tracks = getattr(parent, "_audio_tracks", None) or []
            for t in tracks:
                if self.clip in t.clips:
                    return float(t.volume)
        return 1.0

    def _set_track_volume(self, vol_linear: float) -> None:
        parent = self.parent()
        if parent is None:
            return
        tracks = getattr(parent, "_audio_tracks", None) or []
        for t in tracks:
            if self.clip in t.clips:
                t.volume = float(vol_linear)
                # Update the row's slider + mixer.
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    with _block_signals(row._volume_slider):
                        row._volume_slider.setValue(int(round(t.volume * 100)))
                parent._audio_mixer.update_track(t)
                break

    @staticmethod
    def _track_volume_to_db(vol_linear: float) -> float:
        """Convert linear gain (0..1.5) to dB for UI display."""
        if vol_linear <= 0.0:
            return -60.0
        return max(-60.0, 20.0 * math.log10(vol_linear))

    @staticmethod
    def _db_to_track_volume(db: float) -> float:
        if db <= -60.0:
            return 0.0
        return 10.0 ** (db / 20.0)

    def _switch_tab(self, tab_id: str) -> None:
        idx = {
            "basic": 0, "eq": 1, "dynamics": 2, "effects": 3,
            "advanced": 4, "ai_master": 5,
        }.get(tab_id, 0)
        self._tab_stack.setCurrentIndex(idx)
        # Sync checked state (QButtonGroup should handle, but be defensive).
        for tid, btn in self._tab_buttons.items():
            btn.setChecked(tid == tab_id)

    # -------- knob handlers --------

    def _on_volume_knob(self, db: float) -> None:
        # Main timeline + export use the track's linear volume.
        linear = self._db_to_track_volume(db)
        self._set_track_volume(linear)
        # Local preview: drive the editor's own player output so the
        # user hears the change immediately. The local master (the
        # transport 🔊 slider) multiplies on top, so we cap at 1.0
        # here — the slider can still attenuate further.
        try:
            self._player_output.setVolume(max(0.0, min(1.0, linear)))
        except Exception:
            pass

    def _on_pan_knob(self, pan: float) -> None:
        # Pan is captured on the clip for FFmpeg export. Qt's
        # QMediaPlayer / QAudioOutput doesn't expose a built-in
        # pan, so local preview stays centered — fine for v1.
        self.clip._se_pan = pan

    def _on_fade_in_knob(self, sec: float) -> None:
        self.clip.fade_in_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_fade_out_knob(self, sec: float) -> None:
        self.clip.fade_out_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_speed_knob(self, rate: float) -> None:
        self.clip._se_speed = rate
        # QMediaPlayer supports playbackRate natively — let the
        # local preview respond immediately to the Speed knob.
        try:
            self._player.setPlaybackRate(float(rate))
        except Exception:
            pass

    def _on_pitch_knob(self, semitones: float) -> None:
        # Real-time pitch shifting isn't available in QMediaPlayer; the
        # value is stashed for FFmpeg export (`asetrate` + `atempo` chain).
        # No audible local preview change for now.
        self.clip._se_pitch = semitones

    def _on_mute_toggled(self, muted: bool) -> None:
        # Implement mute as a volume-knob override: record the current
        # volume, swap to silence, and restore on un-mute.
        if muted:
            self._muted_restore_db = self._knob_volume.value()
            self._knob_volume.setValue(-60.0)
        else:
            restore = getattr(self, "_muted_restore_db", 0.0)
            self._knob_volume.setValue(restore)

    def _reset_basic_to_defaults(self) -> None:
        self._knob_volume.setValue(0.0)
        self._knob_pan.setValue(0.0)
        self._knob_fade_in.setValue(0.0)
        self._knob_fade_out.setValue(0.0)
        self._knob_speed.setValue(1.0)
        self._knob_pitch.setValue(0.0)
        self._btn_mute.setChecked(False)
        self._btn_reverse.setChecked(False)

    def _apply_preset(self, name: str) -> None:
        preset = self.BASIC_PRESETS.get(name)
        if preset is None:
            return
        self._knob_volume.setValue(preset["volume"])
        self._knob_pan.setValue(preset["pan"])
        self._knob_fade_in.setValue(preset["fade_in"])
        self._knob_fade_out.setValue(preset["fade_out"])
        self._knob_speed.setValue(preset["speed"])
        self._knob_pitch.setValue(preset["pitch"])

    # -------- transport --------

    def _toggle_play(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_player_position(self, pos_ms: int) -> None:
        dur = self._player.duration() or self.clip.duration_ms
        self._position_label.setText(
            f"{_format_ms(int(pos_ms))} / {_format_ms(int(dur))}"
        )
        self._waveform_view.set_playhead_source_ms(int(pos_ms))
        # Loop handling: if loop is on AND a selection exists, wrap the
        # playhead back to the selection start whenever it crosses the
        # selection end. Uses the waveform view's selection as the
        # single source of truth.
        if self._loop_btn.isChecked():
            sel = self._waveform_view.selection()
            if sel is not None and pos_ms >= sel[1]:
                try:
                    self._player.setPosition(int(sel[0]))
                except Exception:
                    pass

    def _on_playback_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
        else:
            self._play_btn.setText("▶")
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._waveform_view.clear_playhead()

    # -------- markers + selection + loop --------

    def _markers(self) -> list[int]:
        if not hasattr(self.clip, "_se_markers") or self.clip._se_markers is None:
            self.clip._se_markers = []
        return self.clip._se_markers

    def _add_marker_at_playhead(self) -> None:
        pos = self._player.position()
        if pos <= 0:
            return
        # Dedup within 50 ms so repeated 'M' presses don't stack.
        markers = self._markers()
        for m in markers:
            if abs(m - pos) < 50:
                return
        markers.append(int(pos))
        markers.sort()
        self._waveform_view.refresh()
        self._refresh_markers_list()

    def _go_to_prev_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        # Previous marker = the latest one strictly before pos (minus a
        # small epsilon so hitting ⏮ twice in a row actually jumps back).
        target = None
        for m in markers:
            if m < pos - 200:
                target = m
        if target is None:
            target = markers[0]
        self._player.setPosition(int(target))

    def _go_to_next_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        for m in markers:
            if m > pos + 50:
                self._player.setPosition(int(m))
                return

    def _on_waveform_scrub(self, source_ms: int) -> None:
        # QMediaPlayer position is source-ms (absolute within the file).
        try:
            self._player.setPosition(int(source_ms))
        except Exception:
            pass

    def _on_waveform_selection(self, start_ms: int, end_ms: int) -> None:
        # Park the selection on the clip so the loop logic + future
        # clip-range effects (e.g. "apply EQ to selection") can read it.
        self.clip.selection_start_ms = max(0, int(start_ms) - self.clip.trim_start_ms)
        self.clip.selection_end_ms = max(0, int(end_ms) - self.clip.trim_start_ms)

    def _on_waveform_selection_cleared(self) -> None:
        self.clip.selection_start_ms = -1
        self.clip.selection_end_ms = -1

    def _on_marker_right_clicked(self, idx: int, global_pos: QPoint) -> None:
        markers = self._markers()
        if idx < 0 or idx >= len(markers):
            return
        menu = QMenu(self)
        act_delete = menu.addAction(tr("veditor.sound_editor.marker.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_delete:
            del markers[idx]
            self._waveform_view.refresh()
            self._refresh_markers_list()

    def _apply_and_close(self) -> None:
        # All knob mutations already flow live; "Apply" is effectively
        # the same as "Close" today. Left as a separate button so the
        # upcoming effects tabs (which stage changes) have somewhere to
        # hook into.
        self._refresh_timeline_row()
        self.close()

    # ---- audio quality dropdown ----

    def _refresh_audio_quality_btn_label(self) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(self._audio_export_quality_id)
        label = tr(q.name_key)
        if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
            label = f"{label} ★"
        self._audio_quality_btn.setText(
            f"{tr('veditor.export.quality.label')}: {label}  ▾"
        )

    def _build_audio_quality_menu(self) -> None:
        from app.audio_tracks import AUDIO_QUALITY_PRESETS
        from app import tier
        menu = QMenu(self._audio_quality_btn)
        menu.setObjectName("AudioQualityMenu")
        menu.setStyleSheet(
            f"QMenu#AudioQualityMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#AudioQualityMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#AudioQualityMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#AudioQualityMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#AudioQualityMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for q in AUDIO_QUALITY_PRESETS:
            badge = ""
            if tier.requires_pro(q.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(q.feature_id) else "★ PRO  "
            label = f"{badge}{tr(q.name_key)}  ·  {tr(q.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(q.id == self._audio_export_quality_id)
            act.triggered.connect(
                lambda _checked=False, qid=q.id: self._on_audio_quality_picked(qid)
            )
        self._audio_quality_btn.setMenu(menu)

    def _on_audio_quality_picked(self, quality_id: str) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(quality_id)
        if tier.is_locked(q.feature_id):
            self._show_audio_upsell(tr(q.name_key))
            self._build_audio_quality_menu()
            return
        self._audio_export_quality_id = quality_id
        self._refresh_audio_quality_btn_label()
        self._build_audio_quality_menu()

    def _show_audio_upsell(self, feature_label: str) -> None:
        """Modal upsell shown when a Free user picks a Pro-only audio
        format. Mirrors the video editor's upsell — same i18n keys."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            tr("upsell.title"),
            tr("upsell.body", feature=feature_label),
        )

    def _on_export_clicked(self) -> None:
        """Render the current clip (trim + cuts + fades + effects) to a
        standalone audio file. Free tier covers MP3 + WAV; Pro formats
        appear in the dialog with a "(PRO)" suffix and trigger an
        upsell when picked by a Free user."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from app.audio_tracks import CLIP_EXPORT_FORMATS, ClipExporter
        from app import tier

        if self.clip.source_path is None:
            return

        # Free formats first (they're the only ones a Free user can
        # actually pick), Pro formats after — keeps the default useful
        # without hiding the upsell entirely.
        order = ["mp3", "wav", "flac", "alac", "aac", "ogg"]

        def _filter_for(key: str) -> str:
            base = CLIP_EXPORT_FORMATS[key]["filter"]
            fid = CLIP_EXPORT_FORMATS[key]["feature_id"]
            if tier.is_locked(fid):
                return base.replace("(*", "(PRO) (*")
            return base

        filters = [_filter_for(k) for k in order]
        all_filters = ";;".join(filters)

        src = Path(self.clip.source_path)
        # Default filename uses the first Free format (mp3) so save
        # dialogs land somewhere usable for everyone.
        default_name = str(src.with_name(f"{src.stem}_edited.mp3"))

        out_path, chosen_filter = QFileDialog.getSaveFileName(
            self,
            tr("veditor.sound_editor.export.dialog_title"),
            default_name,
            all_filters,
            filters[0],
        )
        if not out_path:
            return

        format_key = next(
            (k for k in order if _filter_for(k) == chosen_filter),
            "mp3",
        )

        # Pro-gating: if a Free user picked a locked format, show
        # upsell and abort instead of running the encode.
        feature_id = CLIP_EXPORT_FORMATS[format_key]["feature_id"]
        if tier.is_locked(feature_id):
            label = CLIP_EXPORT_FORMATS[format_key]["label"]
            self._show_audio_upsell(label)
            return

        # Make sure the extension on disk matches the chosen format —
        # users sometimes type a wrong extension in the save dialog.
        out_path_obj = Path(out_path)
        expected_ext = CLIP_EXPORT_FORMATS[format_key]["ext"]
        if out_path_obj.suffix.lower() != expected_ext.lower():
            out_path_obj = out_path_obj.with_suffix(expected_ext)

        # Disable the button so the user can't spam it. Re-enabled in
        # the completion/failure slots.
        self._export_btn.setEnabled(False)
        self._export_btn.setText(tr("veditor.sound_editor.export.running"))

        self._clip_exporter = ClipExporter(
            self.clip, str(out_path_obj), format_key, parent=self,
            quality_id=getattr(self, "_audio_export_quality_id", "standard"),
        )

        def _on_done(path: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.information(
                self,
                tr("veditor.sound_editor.export.success_title"),
                tr("veditor.sound_editor.export.success_body", path=path),
            )

        def _on_failed(reason: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.warning(
                self,
                tr("veditor.sound_editor.export.failed_title"),
                tr("veditor.sound_editor.export.failed_body", reason=reason),
            )

        self._clip_exporter.done.connect(_on_done)
        self._clip_exporter.failed.connect(_on_failed)
        self._clip_exporter.start()

    def _refresh_timeline_row(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        for t in getattr(parent, "_audio_tracks", None) or []:
            if self.clip in t.clips:
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    row.update()
                parent._audio_mixer.update_track(t)
                break

    def refresh_waveform(self) -> None:
        self._waveform_view.refresh()

    def closeEvent(self, event) -> None:
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass
        super().closeEvent(event)


class _EqCurveView(QWidget):
    """Simple magnitude-response preview for the 3-band EQ. Computes
    the summed response of three biquads (low-shelf / peak / high-
    shelf) on a log frequency grid and paints it as a filled curve.
    Not meant as a 1:1 match for ffmpeg's ``equalizer`` — it's a
    visual indicator of shape, same as every DAW does."""

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self.setStyleSheet(
            f"background-color: #000; border: 1px solid {COLOR_BG_L4}; border-radius: 6px;"
        )

    def refresh(self) -> None:
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)
        if rect.width() < 10 or rect.height() < 10:
            return
        eq = self.clip.effects.get("eq") or {}

        # Grid lines at 0 dB center + ±6 dB
        mid_y = rect.center().y()
        painter.setPen(QPen(QColor(40, 40, 48), 1))
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        painter.setPen(QPen(QColor(30, 30, 38), 1, Qt.PenStyle.DashLine))
        painter.drawLine(rect.left(), mid_y - rect.height() // 4, rect.right(), mid_y - rect.height() // 4)
        painter.drawLine(rect.left(), mid_y + rect.height() // 4, rect.right(), mid_y + rect.height() // 4)

        # Log-frequency axis (20 Hz – 20 kHz)
        import math
        f_min, f_max = 20.0, 20000.0
        log_min, log_max = math.log10(f_min), math.log10(f_max)
        w = rect.width()
        h = rect.height()

        # Compute the summed response (dB) across the range.
        def band_response(freq: float, f0: float, gain_db: float, q: float, kind: str) -> float:
            """Approximate biquad magnitude at ``freq`` in dB."""
            if abs(gain_db) < 0.05:
                return 0.0
            # Use a Gaussian bell around f0 for peak; slope for shelves.
            # This is a rough visual approximation, not textbook biquad.
            if kind == "peak":
                sigma = f0 / max(q, 0.1) * 0.6
                dist = freq - f0
                weight = math.exp(-(dist * dist) / (2 * sigma * sigma + 1e-9))
                return gain_db * weight
            if kind == "lowshelf":
                # Full gain below f0, rolls off above
                if freq <= f0:
                    return gain_db
                roll = math.exp(-(math.log(freq / f0)) ** 2 / 0.5)
                return gain_db * roll
            if kind == "highshelf":
                if freq >= f0:
                    return gain_db
                roll = math.exp(-(math.log(f0 / freq)) ** 2 / 0.5)
                return gain_db * roll
            return 0.0

        low = eq.get("low") or {"freq": 80, "gain": 0, "q": 0.7}
        mid = eq.get("mid") or {"freq": 1000, "gain": 0, "q": 1.0}
        high = eq.get("high") or {"freq": 10000, "gain": 0, "q": 0.7}

        # Sample the response
        samples = 120
        points: list[tuple[int, float]] = []
        for i in range(samples + 1):
            t = i / samples
            freq = 10 ** (log_min + t * (log_max - log_min))
            resp_db = (
                band_response(freq, low["freq"], low["gain"], low["q"], "lowshelf")
                + band_response(freq, mid["freq"], mid["gain"], mid["q"], "peak")
                + band_response(freq, high["freq"], high["gain"], high["q"], "highshelf")
            )
            x = rect.left() + int(t * w)
            # ±12 dB spans ±h/2 ish; clamp.
            y = mid_y - int((resp_db / 12.0) * (h / 2 - 4))
            y = max(rect.top(), min(rect.bottom(), y))
            points.append((x, y))

        # Fill under the curve
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(points[0][0], mid_y)
        for x, y in points:
            path.lineTo(x, y)
        path.lineTo(points[-1][0], mid_y)
        path.closeSubpath()
        painter.fillPath(path, QColor(255, 122, 74, 60))

        # Curve line
        painter.setPen(QPen(QColor("#ff7a4a"), 2))
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
            painter.drawLine(x1, y1, x2, y2)


class PreviewPopoutWindow(QWidget):
    """Top-level mirror of the preview area. Displays the latest frame
    coming from ``ProjectPlayer.frame_ready`` scaled to fit. Closing
    this window simply destroys it — the in-editor preview was never
    disturbed, so editing keeps working the whole time.
    """

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L1}; }}"
        )
        self.resize(960, 540)
        self.setMinimumSize(320, 180)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._last_image: QImage | None = None
        self._last_pixmap: QPixmap | None = None

    def update_frame(self, image: QImage) -> None:
        self._last_image = image
        self._rescale()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._last_image is None:
            return
        target = self._label.size()
        if target.width() < 2 or target.height() < 2:
            return
        pm = QPixmap.fromImage(self._last_image).scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._last_pixmap = pm
        self._label.setPixmap(pm)

    def keyPressEvent(self, event) -> None:
        # F11 toggles fullscreen on the popout monitor; Esc leaves it.
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class ColorPopoutWindow(QWidget):
    """Floating window that hosts the color-grading panel + scopes
    while the user has the section "popped out" of the editor.

    The widget tree is *moved* (reparented) into this window — there's
    only one canonical color panel in the app, so sliders/wheels keep
    their values across pop-out / pop-in transitions and the rest of
    the editor's signals don't need to be re-wired.

    Closing the window emits ``closed``; the editor re-installs the
    panel into its own layout in response.
    """

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.color_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(960, 480)
        self.setMinimumSize(720, 400)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        """Reparent ``host`` into this window so the user can edit
        from the floating surface."""
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class TimelinePopoutWindow(QWidget):
    """Floating window that hosts the timeline (tracks + ruler + audio
    rows) when the user pops it out of the editor. Same reparent-the-
    widget-tree pattern as ``ColorPopoutWindow`` — a single canonical
    timeline lives on the editor and just changes parent across pop-
    out / pop-in transitions, so all the existing track signals stay
    wired."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.timeline_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(1280, 360)
        self.setMinimumSize(640, 240)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class SubtitlePopoutWindow(QWidget):
    """Floating window that hosts the subtitle dock when the user pops
    it out of the editor's right column. Same reparent pattern as the
    timeline / colour popouts — only one canonical subtitle panel
    exists in the app, so its list and slider state survive pop-out /
    pop-in cycles."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.subtitle_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(560, 480)
        self.setMinimumSize(320, 280)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class EffectsLibraryPopoutWindow(QWidget):
    """Floating window that hosts the Effects Library when the user
    pops it out. Same reparent pattern as the other popouts — the
    cards keep their drag handlers since they're real QWidgets, the
    popout just owns the layout while the dock shows a placeholder."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.effects_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(320, 360)
        self.setMinimumSize(220, 280)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class MediaPoolPopoutWindow(QWidget):
    """Floating window that hosts the media pool when the user pops
    it out. Same reparent pattern as the other popouts — registered
    items keep their selection / order across pop-out cycles."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.media_pool_popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L3}; }}"
        )
        self.resize(560, 600)
        self.setMinimumSize(320, 320)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class AudioTrackRow(QWidget):
    """Multi-clip timeline row for an ``AudioTrack``.

    One row = one AudioTrack. Multiple AudioClips belonging to that
    track are drawn side-by-side on the bar area; each can be dragged,
    selected, faded, and split independently.

    The row header shows the track's master volume slider. Per-clip
    interactions (drag / selection / fade / context menu / double-click
    for sound editor) target the clip the user actually clicks on.
    """

    clicked = Signal(int)                 # track_id
    volume_changed = Signal(int, float)   # track_id, master volume
    row_context_menu = Signal(int, QPoint)   # track_id, global_pos (clicked on empty area)
    clip_context_menu = Signal(int, int, QPoint)  # track_id, clip_id, global_pos
    load_source_requested = Signal(int)   # track_id — empty-row click
    media_dropped = Signal(int, object)   # track_id, Path — any media for routing
    track_changed = Signal(int)           # track_id — clips were mutated
    clip_selection_changed = Signal(int, int, int, int)  # track_id, clip_id, start, end
    open_editor_requested = Signal(int, int)  # track_id, clip_id

    MARGIN = 10
    CLIP_LEFT = 10    # same as MARGIN — left meters removed (now in mixer panel)
    LABEL_H = 22
    BAR_H = 48
    SPECTRUM_H = 54   # spectrum strip below the waveform bar
    PADDING = 8

    BAR_COLOR = QColor("#3e6a7e")          # teal-ish for audio
    BAR_BORDER = QColor("#6bb1c9")
    BAR_COLOR_EMPTY = QColor("#2a2a32")
    BAR_COLOR_ACTIVE = QColor("#4a86a0")

    FADE_EDGE_GRAB_PX = 6

    def __init__(self, track: AudioTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._active_clip_id: int | None = None
        self._march_offset: int = 0   # marching-ants animation offset
        self._position_ms: int = 0
        self._px_per_sec: float = DEFAULT_PX_PER_SEC

        # Active interaction state. ``_interaction_clip`` points to the
        # AudioClip the user is currently manipulating (drag / select /
        # fade-resize); cleared on mouse release.
        self._interaction_clip: AudioClip | None = None
        self._dragging_offset: bool = False
        self._drag_start_x: int = 0
        self._drag_start_offset_ms: int = 0
        self._resizing_fade: FadeSegment | None = None
        self._resizing_clip: AudioClip | None = None
        self._resize_side: str = ""
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._waveform_errors: dict[int, str] = {}  # clip_id → reason
        # Realtime L/R level meters (0.0–1.0, peak-hold decay)
        self._level_l: float = 0.0
        self._level_r: float = 0.0
        # Volume envelope drag state
        self._env_drag_clip: AudioClip | None = None
        self._env_drag_idx: int = -1       # index into clip.volume_points (-1 = new)
        self._env_drag_active: bool = False
        # Hover tracking for audio-fade edge handles.
        self._hover_audio_fade_key: tuple | None = None    # (id(clip), id(fade))
        self._hover_audio_fade_side: str = ""

        self.setFixedHeight(self.LABEL_H + self.BAR_H + self.SPECTRUM_H + self.PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAcceptDrops(True)

        _audio_name = track.display_name or tr("veditor.audio.track_empty")
        self._name_label = QLabel(f"♫  {_audio_name}", self)
        self._name_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-weight: 600; font-size: 11px; background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._volume_slider.setMinimum(0)
        self._volume_slider.setMaximum(150)
        self._volume_slider.setValue(int(round(track.volume * 100)))
        self._volume_slider.setFixedWidth(110)
        self._volume_slider.setToolTip(tr("veditor.audio.volume"))
        self._volume_slider.valueChanged.connect(self._on_volume_slider_changed)

        self._reposition_header()

    # ---- geometry / state helpers ----

    def deselect_clip(self) -> None:
        """Clear the active clip selection (called when video clip is selected)."""
        if self._active_clip_id is not None:
            self._active_clip_id = None
            self._march_offset = 0
            self.update()

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = max(0, int(ms))
        self.update()

    def refresh_from_track(self) -> None:
        _n = self.track.display_name or tr("veditor.audio.track_empty")
        self._name_label.setText(f"♫  {_n}")
        with _block_signals(self._volume_slider):
            self._volume_slider.setValue(int(round(self.track.volume * 100)))
        self.update()

    def set_waveform_error(self, clip_id: int, reason: str) -> None:
        self._waveform_errors[clip_id] = reason or "decode failed"
        self.update()

    def clear_waveform_error(self, clip_id: int) -> None:
        self._waveform_errors.pop(clip_id, None)

    def _preferred_width(self) -> int:
        span = self.track.extent_ms()
        return int(span / 1000.0 * self._px_per_sec) + 2 * self.MARGIN + 40

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_header()

    def _reposition_header(self) -> None:
        self._name_label.setGeometry(
            self.CLIP_LEFT, 3,
            max(50, self.width() - self.CLIP_LEFT - self._volume_slider.width() - self.MARGIN * 2),
            self.LABEL_H - 4,
        )
        self._volume_slider.setGeometry(
            self.width() - self._volume_slider.width() - self.MARGIN,
            (self.LABEL_H - self._volume_slider.sizeHint().height()) // 2,
            self._volume_slider.width(),
            self._volume_slider.sizeHint().height(),
        )

    def _project_ms_to_x(self, ms: int) -> int:
        return int(self.CLIP_LEFT + ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.CLIP_LEFT) / self._px_per_sec * 1000))

    # ---- per-clip hit testing ----

    def _clip_bar_rect(self, clip: AudioClip) -> QRect:
        bar_y = self.LABEL_H
        x1 = self._project_ms_to_x(clip.offset_ms)
        x2 = self._project_ms_to_x(clip.offset_ms + clip.effective_length_ms)
        return QRect(x1, bar_y + 4, max(2, x2 - x1), self.BAR_H - 8)

    def _clip_at_pos(self, pos: QPoint) -> AudioClip | None:
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        for clip in self.track.clips:
            if clip.source_path is None:
                continue
            r = self._clip_bar_rect(clip)
            if r.left() <= pos.x() <= r.right():
                return clip
        return None

    def _x_to_clip_local_ms(self, clip: AudioClip, x: int) -> int:
        project_ms = self._x_to_project_ms(x)
        local = project_ms - clip.offset_ms
        return max(0, min(clip.effective_length_ms, local))

    def _clip_local_ms_to_x(self, clip: AudioClip, local_ms: int) -> int:
        return self._project_ms_to_x(clip.offset_ms + local_ms)

    def _fade_edge_at(self, clip: AudioClip, x: int, y: int):
        bar_y = self.LABEL_H
        if y < bar_y or y > bar_y + self.BAR_H:
            return None, ""
        for fade in clip.fades:
            local_start = fade.start_ms - clip.trim_start_ms
            local_end = fade.end_ms - clip.trim_start_ms
            fx1 = self._clip_local_ms_to_x(clip, local_start)
            fx2 = self._clip_local_ms_to_x(clip, local_end)
            if abs(x - fx1) <= self.FADE_EDGE_GRAB_PX:
                return fade, "left"
            if abs(x - fx2) <= self.FADE_EDGE_GRAB_PX:
                return fade, "right"
        return None, ""

    def _fade_under(self, clip: AudioClip, pos: QPoint):
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        local_ms = self._x_to_clip_local_ms(clip, pos.x())
        source_ms = clip.trim_start_ms + local_ms
        for fade in clip.fades:
            if fade.start_ms <= source_ms < fade.end_ms:
                return fade
        return None

    # ---- mouse ----

    def _on_volume_slider_changed(self, value: int) -> None:
        vol = max(0.0, min(1.5, value / 100.0))
        self.track.volume = vol
        self.volume_changed.emit(self.track.id, vol)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        y = pos.y()
        mods = event.modifiers()

        # Right-click dispatches to fade menu / clip menu / row menu.
        if event.button() == Qt.MouseButton.RightButton:
            clip = self._clip_at_pos(pos)
            if clip is not None:
                # Check if right-clicking on an envelope point first
                bar_rect = self._clip_bar_rect(clip)
                env_idx = self._envelope_hit_test(clip, bar_rect, pos)
                if env_idx >= 0:
                    from PySide6.QtWidgets import QMenu
                    m = QMenu(self)
                    act_del = m.addAction("포인트 삭제")
                    act_clr = m.addAction("엔벨로프 초기화")
                    chosen = m.exec(event.globalPosition().toPoint())
                    pts = getattr(clip, "volume_points", None) or []
                    if chosen is act_del and 0 <= env_idx < len(pts):
                        pts.pop(env_idx)
                        self.update()
                    elif chosen is act_clr:
                        clip.volume_points = []
                        self.update()
                    return
                fade = self._fade_under(clip, pos)
                if fade is not None:
                    self._show_fade_menu(clip, fade, event.globalPosition().toPoint())
                    return
                self.clip_context_menu.emit(
                    self.track.id, clip.id, event.globalPosition().toPoint()
                )
                return
            self.row_context_menu.emit(self.track.id, event.globalPosition().toPoint())
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        if y < self.LABEL_H:
            return

        # Empty row → request to load an audio file.
        if not self.track.is_loaded:
            self.load_source_requested.emit(self.track.id)
            return

        clip = self._clip_at_pos(pos)
        if clip is None:
            return
        self._active_clip_id = clip.id
        self._interaction_clip = clip
        # Notify the window so it can take ants ownership away from video.
        self.clip_selection_changed.emit(
            self.track.id, clip.id,
            getattr(clip, "selection_start_ms", -1),
            getattr(clip, "selection_end_ms", -1),
        )
        self.update()

        # 0. Volume envelope: Ctrl+click adds a point; dragging existing
        #    points moves them; right-click on a point deletes it.
        if mods & Qt.KeyboardModifier.ControlModifier:
            bar_rect = self._clip_bar_rect(clip)
            if bar_rect.contains(pos):
                t = self._clip_local_norm(clip, x, bar_rect)
                v = self._envelope_vol(bar_rect, y)
                pts = getattr(clip, "volume_points", None)
                if pts is None:
                    clip.volume_points = []
                    pts = clip.volume_points
                pts.append((round(t, 4), round(v, 3)))
                pts.sort(key=lambda p: p[0])
                self.update()
                return
        bar_rect = self._clip_bar_rect(clip)
        if bar_rect.contains(pos):
            idx = self._envelope_hit_test(clip, bar_rect, pos)
            if idx >= 0:
                self._env_drag_clip = clip
                self._env_drag_idx = idx
                self._env_drag_active = True
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return

        # 1. Fade edge resize takes priority.
        fade, side = self._fade_edge_at(clip, x, y)
        if fade is not None:
            self._resizing_fade = fade
            self._resizing_clip = clip
            self._resize_side = side
            self._resize_orig_start = fade.start_ms
            self._resize_orig_end = fade.end_ms
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Option C: legacy Shift+drag clip-local range select removed.
        # Industry NLEs use click-to-select on clips; Shift toggles add
        # to the multi-clip selection set instead.

        # 2. Else drag the clip on the project timeline.
        self._dragging_offset = True
        self._drag_start_x = x
        self._drag_start_offset_ms = clip.offset_ms
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        clip = self._interaction_clip

        # Volume envelope drag
        if self._env_drag_active and self._env_drag_clip is not None:
            ec = self._env_drag_clip
            bar_rect = self._clip_bar_rect(ec)
            t = round(self._clip_local_norm(ec, x, bar_rect), 4)
            v = round(self._envelope_vol(bar_rect, pos.y()), 3)
            pts = getattr(ec, "volume_points", None) or []
            if 0 <= self._env_drag_idx < len(pts):
                pts[self._env_drag_idx] = (t, v)
                pts.sort(key=lambda p: p[0])
                self._env_drag_idx = next(
                    (i for i, p in enumerate(pts) if p == (t, v)), self._env_drag_idx
                )
            self.update()
            return

        if self._resizing_fade is not None and clip is not None:
            delta_ms = int((x - self._drag_start_x) / max(self._px_per_sec, 0.001) * 1000)
            fade = self._resizing_fade
            # Fade start/end are in source-ms (absolute within the source
            # file), so their valid range is [clip.trim_start_ms, clip.effective_trim_end_ms].
            if self._resize_side == "left":
                new_start = max(
                    clip.trim_start_ms,
                    min(fade.end_ms - 100, self._resize_orig_start + delta_ms),
                )
                fade.start_ms = new_start
            else:
                new_end = min(
                    clip.effective_trim_end_ms,
                    max(fade.start_ms + 100, self._resize_orig_end + delta_ms),
                )
                fade.end_ms = new_end
            self.update()
            self.track_changed.emit(self.track.id)
            return

        if self._dragging_offset and clip is not None:
            dx = x - self._drag_start_x
            d_ms = int(dx / max(self._px_per_sec, 0.001) * 1000)
            new_offset = max(0, self._drag_start_offset_ms + d_ms)
            if new_offset != clip.offset_ms:
                clip.offset_ms = new_offset
                self.track_changed.emit(self.track.id)
                self.update()
            return

        # Idle hover: cursor hinting + edge-handle hover highlight.
        prev_key = self._hover_audio_fade_key
        prev_side = self._hover_audio_fade_side
        hover_clip = self._clip_at_pos(pos)
        if hover_clip is not None:
            fade, side = self._fade_edge_at(hover_clip, x, pos.y())
            if fade is not None:
                self._hover_audio_fade_key = (id(hover_clip), id(fade))
                self._hover_audio_fade_side = side
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                if (prev_key != self._hover_audio_fade_key
                        or prev_side != self._hover_audio_fade_side):
                    self.update()
                return
        self._hover_audio_fade_key = None
        self._hover_audio_fade_side = ""
        if prev_key is not None:
            self.update()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, _event) -> None:
        if self._hover_audio_fade_key is not None:
            self._hover_audio_fade_key = None
            self._hover_audio_fade_side = ""
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_offset = False
        self._resizing_fade = None
        self._resizing_clip = None
        self._resize_side = ""
        self._interaction_clip = None
        if self._env_drag_active:
            self._env_drag_active = False
            self._env_drag_clip = None
            self._env_drag_idx = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        clip = self._clip_at_pos(pos)
        if clip is None:
            return
        # Double-click on a fade → delete that fade.
        fade = self._fade_under(clip, pos)
        if fade is not None:
            try:
                clip.fades.remove(fade)
            except ValueError:
                return
            self.update()
            self.track_changed.emit(self.track.id)
            return
        # Else open the sound editor for this clip.
        self.open_editor_requested.emit(self.track.id, clip.id)

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_audio_path(p) or is_video_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        pos = event.position().toPoint()

        if md.hasFormat(FADE_MIME_TYPE):
            clip = self._clip_at_pos(pos)
            if clip is None or clip.source_path is None or clip.effective_length_ms <= 0:
                event.ignore()
                return
            try:
                dur_ms = int(bytes(md.data(FADE_MIME_TYPE)).decode("utf-8"))
            except Exception:
                dur_ms = FadeCard.DEFAULT_DURATION_MS
            dur_ms = max(100, dur_ms)
            center_local = self._x_to_clip_local_ms(clip, pos.x())
            # FadeSegments are stored in source-ms (absolute within
            # source file) so they survive trim / split correctly.
            source_center = clip.trim_start_ms + center_local
            start = max(clip.trim_start_ms, source_center - dur_ms // 2)
            end = min(clip.effective_trim_end_ms, start + dur_ms)
            if end <= start:
                event.ignore()
                return
            clip.fades.append(FadeSegment(start, end))
            clip.fades.sort(key=lambda f: f.start_ms)
            self.update()
            self.track_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return

        if not md.hasUrls():
            event.ignore()
            return
        for u in md.urls():
            p = Path(u.toLocalFile())
            if is_audio_path(p) or is_video_path(p):
                self.media_dropped.emit(self.track.id, p)
                event.acceptProposedAction()
                return
        event.ignore()

    # ---- fade menu (per-fade, on right-click) ----

    def _show_fade_menu(self, clip: AudioClip, fade, global_pos) -> None:
        menu = QMenu(self)
        act_in = menu.addAction(tr("veditor.fade_menu.in"))
        act_in.setCheckable(True)
        act_in.setChecked(getattr(fade, "kind", "both") == "in")
        act_out = menu.addAction(tr("veditor.fade_menu.out"))
        act_out.setCheckable(True)
        act_out.setChecked(getattr(fade, "kind", "both") == "out")
        act_both = menu.addAction(tr("veditor.fade_menu.both"))
        act_both.setCheckable(True)
        act_both.setChecked(getattr(fade, "kind", "both") == "both")
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.fade_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_in:
            fade.kind = "in"
        elif chosen is act_out:
            fade.kind = "out"
        elif chosen is act_both:
            fade.kind = "both"
        elif chosen is act_del:
            try:
                clip.fades.remove(fade)
            except ValueError:
                pass
        else:
            return
        self.update()
        self.track_changed.emit(self.track.id)

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Header bg
        if self._is_active:
            painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L5))
        else:
            painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L3))
        # Bar + spectrum area: 80% audio-tinted stripe — fills full widget
        # width so it extends to the scroll end identical to the video track.
        bar_y = self.LABEL_H
        full_bar = QRect(0, bar_y, self.width(), self.BAR_H + self.SPECTRUM_H)
        StripedHost._draw_stripes(
            painter, full_bar,
            StripedHost.BG_80_AUDIO, StripedHost.STRIPE_80_AUDIO,
        )
        # Large watermark ♫ — right side of the bar area
        painter.save()
        _wm_font = painter.font()
        _wm_font.setPixelSize(min(40, max(20, self.BAR_H - 8)))
        painter.setFont(_wm_font)
        painter.setPen(QColor(100, 180, 200, 40))
        painter.drawText(
            QRect(0, bar_y, self.width(), self.BAR_H),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "♫  ",
        )
        painter.restore()

        track = self.track
        if not track.is_loaded:
            painter.setPen(QPen(QColor(COLOR_BORDER_DEFAULT), 1, Qt.PenStyle.DashLine))
            rect = QRect(self.MARGIN, bar_y + 4, self.width() - 2 * self.MARGIN, self.BAR_H - 8)
            painter.drawRect(rect)
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.audio.drop_hint")
            )
            return

        # Each clip renders independently.
        for clip in track.clips:
            if clip.source_path is None:
                continue
            self._paint_clip(painter, clip)

        # Spectrum strip below the waveform bar.
        spec_y = self.LABEL_H + self.BAR_H
        self._paint_spectrum_strip(painter, spec_y)

        # Playhead spans the full row including spectrum.
        px = self._project_ms_to_x(self._position_ms)
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(px, bar_y, px, bar_y + self.BAR_H + self.SPECTRUM_H)

    def _paint_clip(self, painter: QPainter, clip: AudioClip) -> None:
        bar_rect = self._clip_bar_rect(clip)
        is_active_clip = (clip.id == self._active_clip_id)
        color = self.BAR_COLOR_ACTIVE if is_active_clip else self.BAR_COLOR
        painter.fillRect(bar_rect, color)
        painter.setPen(QPen(self.BAR_BORDER, 1))
        painter.drawRect(bar_rect)
        # Marching ants on selected (active) audio clip (only when audio owns selection)
        if is_active_clip and _ANTS_OWNER == "audio":
            painter.save()
            _draw_marching_ants(painter, bar_rect, self._march_offset)
            painter.restore()

        # Waveform — filled-polygon approach (DaVinci-style).
        # Stereo (shape 2×N): L fills top half, R fills bottom half.
        # Mono (shape N,): symmetric fill centred on mid_y.
        mid_y = bar_rect.top() + bar_rect.height() // 2
        wf = clip.waveform
        err = self._waveform_errors.get(clip.id)
        if wf is not None and wf.size > 0:
            import numpy as _np
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
            n = wf.shape[1] if is_stereo else len(wf)
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = max(2, (bar_rect.height() - 4) // 2)
            # Visible pixel range (clamp to widget width for speed)
            x_start = max(bar_rect.left() + 1, 0)
            x_end = min(bar_rect.right() - 1, self.width())
            if x_end > x_start and n > 0:
                # Vectorised bucket lookup for every visible x-pixel
                xs = _np.arange(x_start, x_end, dtype=_np.float64)
                src_s = trim_start_s + (xs - bar_rect.left()) / max(self._px_per_sec, 0.001)
                buckets = (src_s * WAVEFORM_BUCKETS_PER_SEC).astype(_np.int32)
                valid = (buckets >= 0) & (buckets < n)
                bc = _np.clip(buckets, 0, n - 1)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

                if is_stereo:
                    l_raw = _np.where(valid, wf[0, bc], 0.0)
                    r_raw = _np.where(valid, wf[1, bc], 0.0)
                    # Normalise to the loudest sample so even quiet clips fill the bar
                    peak_max = max(float(l_raw.max()), float(r_raw.max()), 0.005)
                    l_h = (l_raw / peak_max) ** 0.6 * half_h * 0.88
                    r_h = (r_raw / peak_max) ** 0.6 * half_h * 0.88

                    # L polygon: baseline at mid_y, tip above
                    pts_l = ([QPointF(float(x_start), float(mid_y))] +
                             [QPointF(float(xs[i]), float(mid_y - l_h[i])) for i in range(len(xs))] +
                             [QPointF(float(x_end - 1), float(mid_y))])
                    painter.setBrush(QColor(160, 220, 255, 200))
                    painter.drawPolygon(QPolygonF(pts_l))

                    # R polygon: baseline at mid_y, tip below
                    pts_r = ([QPointF(float(x_start), float(mid_y))] +
                             [QPointF(float(xs[i]), float(mid_y + r_h[i])) for i in range(len(xs))] +
                             [QPointF(float(x_end - 1), float(mid_y))])
                    painter.setBrush(QColor(100, 185, 255, 160))
                    painter.drawPolygon(QPolygonF(pts_r))

                    # Centre divider
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawLine(x_start, mid_y, x_end, mid_y)

                else:
                    m_raw = _np.where(valid, wf[bc], 0.0)
                    peak_max = max(float(m_raw.max()), 0.005)
                    m_h = (m_raw / peak_max) ** 0.6 * half_h * 0.88
                    pts_top = [QPointF(float(xs[i]), float(mid_y - m_h[i])) for i in range(len(xs))]
                    pts_bot = [QPointF(float(xs[i]), float(mid_y + m_h[i])) for i in range(len(xs) - 1, -1, -1)]
                    pts_m = [QPointF(float(x_start), float(mid_y))] + pts_top + [QPointF(float(x_end - 1), float(mid_y))] + pts_bot
                    painter.setBrush(QColor(200, 235, 255, 200))
                    painter.drawPolygon(QPolygonF(pts_m))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        elif err:
            painter.setPen(QPen(QColor(200, 80, 80, 200), 1, Qt.PenStyle.DashLine))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)
            painter.setPen(QColor(230, 140, 140, 230))
            f = painter.font(); f.setPixelSize(10); f.setBold(True); painter.setFont(f)
            painter.drawText(
                bar_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignCenter,
                "⚠ decode failed",
            )
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)

        # Filename on the bar
        painter.setPen(QColor(255, 255, 255, 230))
        f = painter.font(); f.setPixelSize(10); f.setBold(False); painter.setFont(f)
        painter.drawText(
            bar_rect.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            clip.display_name,
        )

        # Cuts — clip-local ms domain, dark overlay.
        for cut in clip.cuts:
            cx1 = self._clip_local_ms_to_x(clip, cut.start_ms)
            cx2 = self._clip_local_ms_to_x(clip, cut.end_ms)
            cut_rect = QRect(cx1, bar_rect.top(), max(1, cx2 - cx1), bar_rect.height())
            painter.fillRect(cut_rect, QColor(30, 30, 30, 210))
            if cut_rect.width() > 24:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(cut_rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.cut_label"))

        # FadeSegment actors — in source-ms domain.
        for fade in clip.fades:
            self._paint_fade_segment(painter, clip, fade, bar_rect)

        # Volume envelope — yellow-orange rubberband line on the bar.
        self._paint_volume_envelope(painter, clip, bar_rect)

        # Hint text when no envelope points are set yet.
        if not (getattr(clip, "volume_points", None)):
            painter.save()
            f = painter.font()
            f.setPixelSize(9)
            painter.setFont(f)
            painter.setPen(QColor(255, 220, 80, 120))
            painter.drawText(
                bar_rect.adjusted(4, 0, -4, -2),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                "Ctrl+클릭 → 볼륨 포인트 추가",
            )
            painter.restore()

    # ---- Level meters ----

    def set_level(self, l: float, r: float) -> None:
        """Update peak levels (0.0–1.0) and repaint the header strip."""
        # Soft decay so the meter falls gradually
        self._level_l = max(l, self._level_l * 0.85)
        self._level_r = max(r, self._level_r * 0.85)
        self.update()

    def _paint_level_meters(self, painter: QPainter) -> None:
        """Draw L/R level meter bars in the LEFT fixed zone — always visible."""
        bar_w = 13
        pad = 2
        gap = 2
        top = pad
        h = self.LABEL_H + self.BAR_H - pad * 2
        if h <= 0:
            return
        x_l = pad
        x_r = pad + bar_w + gap
        for level, x, label in ((self._level_l, x_l, "L"), (self._level_r, x_r, "R")):
            painter.fillRect(x, top, bar_w, h, QColor("#060610"))
            fill_h = int(level * h)
            if fill_h > 0:
                if level < 0.70:
                    color = QColor(45, 210, 45)
                elif level < 0.90:
                    color = QColor(240, 200, 20)
                else:
                    color = QColor(240, 40, 40)
                painter.fillRect(x, top + h - fill_h, bar_w, fill_h, color)
            painter.setPen(QPen(QColor(140, 140, 180, 100), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, top, bar_w - 1, h - 1)
            f = painter.font(); f.setPixelSize(8); f.setBold(True); painter.setFont(f)
            painter.setPen(QColor(160, 160, 200, 200))
            painter.drawText(x + 2, top + 1, bar_w - 2, 9, 0, label)

    def _paint_spectrum_strip(self, painter: QPainter, y: int) -> None:
        """Draw 64-bar FFT spectrum below the waveform clip area."""
        try:
            self.__paint_spectrum_strip_impl(painter, y)
        except Exception:
            pass

    def __paint_spectrum_strip_impl(self, painter: QPainter, y: int) -> None:
        import numpy as _np
        h = self.SPECTRUM_H - 4
        total_w = self.width() - 2 * self.MARGIN
        if total_w <= 0 or h <= 0:
            return

        # Background already drawn by bar+spectrum stripe in paintEvent header

        # Collect first clip with spectrum data and its bar extent
        clip_x1 = self.MARGIN
        clip_x2 = self.MARGIN
        bins = None
        for clip in self.track.clips:
            sb = getattr(clip, "spectrum_bins", None)
            if sb is not None and sb.size > 0:
                bins = sb
                br = self._clip_bar_rect(clip)
                clip_x1 = br.left()
                clip_x2 = br.right()
                break

        # Draw clip-extent background and placeholder text
        clip_w = max(0, clip_x2 - clip_x1)
        if clip_w > 0:
            painter.fillRect(clip_x1, y, clip_w, self.SPECTRUM_H, QColor("#1c2830"))
        painter.setPen(QPen(QColor(50, 50, 70), 1))
        painter.drawRect(self.MARGIN, y, total_w - 1, self.SPECTRUM_H - 1)

        if bins is None:
            if clip_w > 20:
                f = painter.font(); f.setPixelSize(9); painter.setFont(f)
                painter.setPen(QColor(100, 100, 130))
                painter.drawText(
                    QRect(clip_x1, y, clip_w, self.SPECTRUM_H),
                    Qt.AlignmentFlag.AlignCenter, "스펙트럼 분석 중..."
                )
            return

        if clip_w <= 0:
            return

        n = len(bins)
        bar_w = max(1, clip_w // n)
        gap = 1
        for i in range(n):
            mag = float(bins[i])
            bar_h = max(0, int(mag * h))
            bx = clip_x1 + i * (bar_w + gap)
            if bx + bar_w > clip_x2:
                break
            by = y + self.SPECTRUM_H - 2 - bar_h
            if mag < 0.60:
                color = QColor(40, 180, 40)
            elif mag < 0.85:
                color = QColor(220, 190, 20)
            else:
                color = QColor(220, 50, 50)
            painter.fillRect(bx, by, bar_w, bar_h, color)

        # Frequency axis labels within clip extent
        f = painter.font(); f.setPixelSize(8); painter.setFont(f)
        painter.setPen(QColor(100, 110, 140))
        for label, frac in (("20Hz", 0.0), ("200", 0.3), ("2k", 0.6), ("20k", 1.0)):
            lx = clip_x1 + int(frac * (clip_w - bar_w))
            if lx < clip_x2:
                painter.drawText(lx, y + self.SPECTRUM_H - 2, label)

    # ---- Volume envelope ----

    _ENV_COLOR = QColor(255, 220, 80, 220)     # yellow-orange line
    _ENV_POINT_R = 4                            # handle radius px
    _ENV_LINE_W = 2
    _ENVELOPE_GRAB_PX = 8                      # hit-test radius for existing points

    def _envelope_y(self, bar_rect: QRect, vol: float) -> int:
        """Map volume [0,2] to a y pixel inside ``bar_rect``.
        vol=0 → bottom, vol=1 → centre, vol=2 → top."""
        h = bar_rect.height() - 2
        clamped = max(0.0, min(2.0, float(vol)))
        return bar_rect.bottom() - 1 - int(clamped / 2.0 * h)

    def _envelope_vol(self, bar_rect: QRect, y: int) -> float:
        """Inverse of _envelope_y: pixel → volume [0,2]."""
        h = bar_rect.height() - 2
        if h <= 0:
            return 1.0
        frac = (bar_rect.bottom() - 1 - y) / h
        return max(0.0, min(2.0, frac * 2.0))

    def _clip_local_norm(self, clip: AudioClip, x_px: int, bar_rect: QRect) -> float:
        """x pixel → normalised [0,1] position within the clip."""
        bw = max(1, bar_rect.width() - 2)
        t = (x_px - bar_rect.left() - 1) / bw
        return max(0.0, min(1.0, t))

    def _eval_envelope(self, clip: AudioClip, t_norm: float) -> float:
        """Interpolate the volume envelope at ``t_norm`` [0,1]."""
        pts = getattr(clip, "volume_points", None) or []
        if not pts:
            return 1.0
        if t_norm <= pts[0][0]:
            return pts[0][1]
        if t_norm >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            t0, v0 = pts[i]
            t1, v1 = pts[i + 1]
            if t0 <= t_norm <= t1:
                if t1 == t0:
                    return v0
                alpha = (t_norm - t0) / (t1 - t0)
                return v0 + alpha * (v1 - v0)
        return 1.0

    def _paint_volume_envelope(self, painter: QPainter, clip: AudioClip, bar_rect: QRect) -> None:
        pts = getattr(clip, "volume_points", None) or []
        bw = bar_rect.width() - 2
        if bw <= 0:
            return
        painter.save()
        painter.setClipRect(bar_rect)
        line_pen = QPen(self._ENV_COLOR, self._ENV_LINE_W)
        painter.setPen(line_pen)
        # Build screen-space polyline from all points (add sentinel
        # endpoints at t=0 and t=1 so the line always spans the clip).
        def _px(t: float) -> int:
            return bar_rect.left() + 1 + int(t * bw)
        anchor_pts = []
        if not pts or pts[0][0] > 0:
            anchor_pts.append((0.0, (pts[0][1] if pts else 1.0)))
        anchor_pts.extend(pts)
        if not pts or pts[-1][0] < 1:
            anchor_pts.append((1.0, (pts[-1][1] if pts else 1.0)))
        for i in range(len(anchor_pts) - 1):
            t0, v0 = anchor_pts[i]
            t1, v1 = anchor_pts[i + 1]
            x0, y0 = _px(t0), self._envelope_y(bar_rect, v0)
            x1, y1 = _px(t1), self._envelope_y(bar_rect, v1)
            painter.drawLine(x0, y0, x1, y1)
        # Draw handles for editable points.
        painter.setBrush(self._ENV_COLOR)
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        r = self._ENV_POINT_R
        for t, v in pts:
            cx, cy = _px(t), self._envelope_y(bar_rect, v)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        painter.restore()

    def _envelope_hit_test(self, clip: AudioClip, bar_rect: QRect, pos: QPoint) -> int:
        """Return index of the envelope point under ``pos``, or -1."""
        pts = getattr(clip, "volume_points", None) or []
        bw = bar_rect.width() - 2
        if bw <= 0:
            return -1
        for i, (t, v) in enumerate(pts):
            cx = bar_rect.left() + 1 + int(t * bw)
            cy = self._envelope_y(bar_rect, v)
            if abs(pos.x() - cx) <= self._ENVELOPE_GRAB_PX and abs(pos.y() - cy) <= self._ENVELOPE_GRAB_PX:
                return i
        return -1

    def _paint_fade_segment(self, painter: QPainter, clip: AudioClip, fade, bar_rect: QRect) -> None:
        local_start = fade.start_ms - clip.trim_start_ms
        local_end = fade.end_ms - clip.trim_start_ms
        fx1 = self._clip_local_ms_to_x(clip, local_start)
        fx2 = self._clip_local_ms_to_x(clip, local_end)
        if fx2 <= fx1:
            return
        kind = getattr(fade, "kind", "both")
        painter.save()
        painter.setClipRect(bar_rect)
        if kind == "in":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 220))
            g.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        elif kind == "out":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(216, 90, 48, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        else:
            mid = (fx1 + fx2) // 2
            g_out = QLinearGradient(fx1, 0, mid, 0)
            g_out.setColorAt(0.0, QColor(216, 90, 48, 0))
            g_out.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), mid - fx1, bar_rect.height(), g_out)
            g_in = QLinearGradient(mid, 0, fx2, 0)
            g_in.setColorAt(0.0, QColor(0, 0, 0, 220))
            g_in.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(mid, bar_rect.top(), fx2 - mid, bar_rect.height(), g_in)
        painter.restore()
        pen = QPen(QColor(COLOR_ACCENT_ORANGE)); pen.setWidth(2)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, bar_rect.top(), max(1, fx2 - fx1), bar_rect.height())

        # Edge trim handles (always visible — DAW-style). Hover / drag
        # detection mirrors TrackRow's scheme.
        hover_key = (id(clip), id(fade))
        is_hover = self._hover_audio_fade_key == hover_key
        is_drag = (
            self._resizing_fade is fade
            and self._resizing_clip is clip
        )
        left_hot = (is_hover and self._hover_audio_fade_side == "left") \
            or (is_drag and self._resize_side == "left")
        right_hot = (is_hover and self._hover_audio_fade_side == "right") \
            or (is_drag and self._resize_side == "right")

        def _one(x: int, hot: bool) -> None:
            if is_drag and hot:
                w = 8; color = QColor("#ff7a4a")
            elif hot:
                w = 6; color = QColor("#ff7a4a")
            else:
                w = 4; color = QColor(255, 150, 80, 210)
            painter.fillRect(x - w // 2, bar_rect.top(), w, bar_rect.height(), color)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            n = max(2, w - 2)
            painter.drawLine(
                x - n // 2, bar_rect.top() + 2,
                x + n // 2, bar_rect.top() + 2,
            )
            painter.drawLine(
                x - n // 2, bar_rect.top() + bar_rect.height() - 3,
                x + n // 2, bar_rect.top() + bar_rect.height() - 3,
            )

        _one(fx1, left_hot)
        _one(fx2, right_hot)


class _block_signals:
    """Context manager — blocks Qt signals on the given object."""
    def __init__(self, obj):
        self._obj = obj
    def __enter__(self):
        self._prev = self._obj.blockSignals(True)
        return self._obj
    def __exit__(self, *exc):
        self._obj.blockSignals(self._prev)


# ---------------------------------------------------------------------------
# Audio Scopes: Goniometer + LUFS
# ---------------------------------------------------------------------------

class GoniometerWidget(QWidget):
    """Lissajous / stereo phase goniometer display.

    Call ``update_from_stereo(l_peaks, r_peaks)`` with numpy arrays of
    recent L/R amplitude values (float32, 0–1) to refresh the display.
    """

    _DOT_RADIUS = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self._l_vals = []   # list of float
        self._r_vals = []   # list of float
        self._max_trail = 64

    # ------------------------------------------------------------------
    def update_from_stereo(self, l_peaks, r_peaks) -> None:
        """Accept numpy arrays and store (L, R) pairs for painting."""
        import numpy as _np
        l = _np.asarray(l_peaks, dtype=_np.float32).ravel()
        r = _np.asarray(r_peaks, dtype=_np.float32).ravel()
        n = min(len(l), len(r))
        if n == 0:
            return
        self._l_vals = (self._l_vals + list(l[:n]))[-self._max_trail:]
        self._r_vals = (self._r_vals + list(r[:n]))[-self._max_trail:]
        self.update()

    def clear(self) -> None:
        self._l_vals = []
        self._r_vals = []
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
        from PySide6.QtCore import Qt

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.45

        # --- background circle ---
        p.setBrush(QBrush(QColor("#0a0a14")))
        p.setPen(QPen(QColor("#2a2a3a"), 1))
        p.drawEllipse(int(cx - radius), int(cy - radius),
                      int(radius * 2), int(radius * 2))

        # --- crosshair ---
        p.setPen(QPen(QColor("#333348"), 1))
        p.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
        p.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))

        # --- dots with trail ---
        n = len(self._l_vals)
        for i, (lv, rv) in enumerate(zip(self._l_vals, self._r_vals)):
            # goniometer math: M/S conversion
            x_norm = (rv - lv) * 0.5   # side  → horizontal
            y_norm = (lv + rv) * 0.5   # mid   → vertical (up = loud)

            px = cx + x_norm * radius
            py = cy - y_norm * radius   # y-axis inverted in screen coords

            # colour: green if correlated (x near 0), red if anti-correlated
            corr = 1.0 - min(abs(x_norm) * 2.0, 1.0)
            r_ch = int((1.0 - corr) * 220)
            g_ch = int(corr * 220)
            alpha = int(60 + 195 * (i / max(n - 1, 1)))   # fade trail

            color = QColor(r_ch, g_ch, 40, alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            dr = self._DOT_RADIUS
            p.drawEllipse(int(px - dr), int(py - dr), dr * 2, dr * 2)

        # --- labels ---
        label_font = QFont()
        label_font.setPointSize(8)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QPen(QColor("#7878a0")))

        margin = 6
        p.drawText(int(cx - radius + margin), int(cy - radius + margin + 10), "L")
        p.drawText(int(cx + radius - margin - 10), int(cy - radius + margin + 10), "R")
        p.drawText(int(cx - 4), int(cy - radius + margin + 10), "M")
        p.drawText(int(cx - 4), int(cy + radius - margin), "S")

        p.end()


class LUFSWidget(QWidget):
    """Displays Integrated / Short-term / Momentary LUFS + True Peak."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setMinimumHeight(180)
        self._integrated = None   # float LUFS or None
        self._short_term = None
        self._momentary = None
        self._true_peak = None    # dBFS

    # ------------------------------------------------------------------
    @staticmethod
    def _rms_to_lufs(arr) -> float | None:
        """Convert a 1-D float32 array of peak amplitudes to a rough LUFS value."""
        import numpy as _np
        if arr is None or len(arr) == 0:
            return None
        # Use mean-square of peak values as a proxy for power
        ms = float(_np.mean(arr.astype(_np.float32) ** 2))
        if ms <= 0.0:
            return None
        db = 10.0 * _np.log10(ms)   # dB relative to full scale (squared peaks)
        return db - 0.7             # rough K-weighting offset

    def update_from_peaks(self, l_peaks, r_peaks, full_l, full_r) -> None:
        """Compute LUFS metrics and refresh the widget.

        Parameters
        ----------
        l_peaks, r_peaks : array-like
            Recent ~400 ms window (≈16 buckets) for momentary measurement.
        full_l, full_r : array-like or None
            Full waveform arrays for integrated measurement.
        """
        import numpy as _np

        def _to_f32(a):
            if a is None:
                return None
            arr = _np.asarray(a, dtype=_np.float32).ravel()
            return arr if len(arr) > 0 else None

        lp = _to_f32(l_peaks)
        rp = _to_f32(r_peaks)
        fl = _to_f32(full_l)
        fr = _to_f32(full_r)

        # Momentary (400 ms window)
        if lp is not None and rp is not None:
            combined_m = _np.concatenate([lp, rp])
            self._momentary = self._rms_to_lufs(combined_m)
        else:
            self._momentary = None

        # Short-term: use last 3 s ≈ 120 buckets from full waveform
        if fl is not None and fr is not None:
            n120 = min(120, len(fl), len(fr))
            combined_s = _np.concatenate([fl[-n120:], fr[-n120:]])
            self._short_term = self._rms_to_lufs(combined_s)
        else:
            self._short_term = None

        # Integrated: full waveform
        if fl is not None and fr is not None:
            combined_i = _np.concatenate([fl, fr])
            self._integrated = self._rms_to_lufs(combined_i)
        else:
            self._integrated = None

        # True peak: max of full waveform
        if fl is not None and fr is not None:
            peak_val = float(_np.maximum(fl, fr[:len(fl)]).max()) if len(fl) <= len(fr) else float(_np.maximum(fl[:len(fr)], fr).max())
            self._true_peak = 20.0 * _np.log10(peak_val) if peak_val > 0 else None
        else:
            self._true_peak = None

        self.update()

    # ------------------------------------------------------------------
    @staticmethod
    def _lufs_color(val: float | None) -> "QColor":
        from PySide6.QtGui import QColor
        if val is None:
            return QColor("#555570")
        if val < -14.0:
            return QColor("#44cc66")   # green — safe
        if val < -9.0:
            return QColor("#ddaa22")   # yellow — loud
        return QColor("#ee4444")       # red — too loud

    @staticmethod
    def _fmt(val: float | None, suffix: str = " LUFS") -> str:
        if val is None:
            return "---"
        return f"{val:.1f}{suffix}"

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
        from PySide6.QtCore import Qt, QRect

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor("#0a0a14"))

        rows = [
            ("Integrated",  self._integrated, True),
            ("Short-term",  self._short_term, False),
            ("Momentary",   self._momentary,  False),
            ("True Peak",   self._true_peak,  False),
        ]

        bar_h = 24
        label_h = 14
        row_h = bar_h + label_h + 6
        top_pad = 8

        for idx, (name, val, big) in enumerate(rows):
            y = top_pad + idx * row_h
            color = self._lufs_color(val)

            # Label
            lf = QFont()
            lf.setPointSize(8)
            p.setFont(lf)
            p.setPen(QPen(QColor("#7878a0")))
            p.drawText(QRect(8, y, w - 16, label_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       name)

            # Value text
            vf = QFont()
            vf.setPointSize(10 if big else 9)
            vf.setBold(big)
            p.setFont(vf)
            p.setPen(QPen(color))
            suffix = " dBFS" if name == "True Peak" else " LUFS"
            p.drawText(QRect(8, y + label_h, w - 16, bar_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._fmt(val, suffix))

        # Momentary loudness bar at the bottom
        bar_area_top = top_pad + len(rows) * row_h + 4
        bar_area_h = max(h - bar_area_top - 8, 8)
        bar_area_w = w - 16

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#1a1a28")))
        p.drawRect(8, bar_area_top, bar_area_w, bar_area_h)

        if self._momentary is not None:
            # Map -60..0 LUFS to 0..1
            frac = max(0.0, min(1.0, (self._momentary + 60.0) / 60.0))
            fill_w = int(bar_area_w * frac)
            p.setBrush(QBrush(self._lufs_color(self._momentary)))
            p.drawRect(8, bar_area_top, fill_w, bar_area_h)

        p.end()


class AudioScopesPanel(QWidget):
    """Panel combining GoniometerWidget and LUFSWidget.

    Add to the timeline section and call ``update_at_position()``
    from ``_on_position_changed`` whenever audio scopes should refresh.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioScopesPanel")
        self.setStyleSheet(
            "QWidget#AudioScopesPanel { background: #111118; border-top: 1px solid #2a2a3a; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setObjectName("ScopesTitleBar")
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "QWidget#ScopesTitleBar { background: #181824; border-bottom: 1px solid #2a2a3a; }"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        title_lbl = QLabel("Audio Scopes")
        title_lbl.setStyleSheet("color: #9898b8; font-size: 11px; font-weight: bold;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #7878a0; border: none; font-size: 10px; }"
            "QPushButton:hover { color: #ee4444; }"
        )
        close_btn.clicked.connect(self.hide)
        tb_layout.addWidget(close_btn)

        outer.addWidget(title_bar)

        # --- Scopes row ---
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(12)

        self._goniometer = GoniometerWidget()
        self._lufs = LUFSWidget()

        body_layout.addWidget(self._goniometer)
        body_layout.addWidget(self._lufs)
        body_layout.addStretch(1)

        outer.addWidget(body)

    # ------------------------------------------------------------------
    def update_at_position(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform data around pos_ms and refresh both scope widgets."""
        import numpy as _np
        from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC

        # Collect combined L/R peak arrays across all tracks
        momentary_l: list = []
        momentary_r: list = []
        full_l_chunks: list = []
        full_r_chunks: list = []

        _buckets_400ms = int(0.4 * WAVEFORM_BUCKETS_PER_SEC)   # ≈ 16

        for track in audio_tracks:
            vol = getattr(track, "volume", 1.0)
            for clip in getattr(track, "clips", []):
                if getattr(clip, "source_path", None) is None:
                    continue
                wf = getattr(clip, "waveform", None)
                if wf is None or (hasattr(wf, "size") and wf.size == 0):
                    continue

                wf = _np.asarray(wf, dtype=_np.float32)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)

                if is_stereo:
                    wf_l, wf_r = wf[0], wf[1]
                else:
                    wf_l = wf_r = wf.ravel()

                n = len(wf_l)

                # Full waveform for integrated LUFS
                full_l_chunks.append(wf_l * vol)
                full_r_chunks.append(wf_r * vol)

                # Window around playhead for momentary
                local_ms = pos_ms - getattr(clip, "offset_ms", 0)
                if local_ms < 0:
                    continue
                src_ms = getattr(clip, "trim_start_ms", 0) + local_ms
                center_bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                b_start = max(0, center_bucket - _buckets_400ms)
                b_end = min(n, center_bucket + 1)
                if b_start < b_end:
                    momentary_l.append(wf_l[b_start:b_end] * vol)
                    momentary_r.append(wf_r[b_start:b_end] * vol)

        if not full_l_chunks:
            # No data — show blank / placeholder
            self._goniometer.clear()
            self._lufs.update_from_peaks(
                _np.zeros(1, _np.float32), _np.zeros(1, _np.float32),
                None, None,
            )
            return

        full_l = _np.concatenate(full_l_chunks)
        full_r = _np.concatenate(full_r_chunks)

        if momentary_l:
            mom_l = _np.concatenate(momentary_l)
            mom_r = _np.concatenate(momentary_r)
        else:
            mom_l = mom_r = _np.zeros(1, _np.float32)

        self._goniometer.update_from_stereo(mom_l, mom_r)
        self._lufs.update_from_peaks(mom_l, mom_r, full_l, full_r)


# ---------------------------------------------------------------------------
#  Audio Mixer Panel
# ---------------------------------------------------------------------------


class _VUMeterWidget(QWidget):
    """Tiny L/R bar-graph VU meter used inside a ChannelStrip."""

    _GREEN = QColor("#3ccc5a")
    _YELLOW = QColor("#e8c84a")
    _RED = QColor("#ee4444")
    _BG = QColor("#0a0a12")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._l: float = 0.0
        self._r: float = 0.0
        self.setFixedSize(18, 80)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def set_levels(self, l: float, r: float) -> None:
        self._l = max(0.0, min(1.0, l))
        self._r = max(0.0, min(1.0, r))
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        bar_w = (w - 3) // 2  # 2 bars + 1px gap
        for i, level in enumerate((self._l, self._r)):
            x = i * (bar_w + 1) + 1
            p.fillRect(x, 0, bar_w, h, self._BG)
            fill_h = int(level * h)
            if fill_h > 0:
                if level < 0.70:
                    color = self._GREEN
                elif level < 0.90:
                    color = self._YELLOW
                else:
                    color = self._RED
                p.fillRect(x, h - fill_h, bar_w, fill_h, color)
        p.end()


class _ChannelStrip(QWidget):
    """Single 70-px wide mixer channel: pan · VU · fader · mute."""

    fader_changed = Signal(float)   # new volume 0.0–1.5
    pan_changed = Signal(float)     # new pan -1.0..+1.0

    _STRIP_BG = "#131320"
    _BORDER = "#2a2a3a"
    _TITLE_COLOR = "#9898b8"
    _TRACK_COLORS = [
        "#3e6a7e", "#6a3e7e", "#7e6a3e", "#3e7e4a", "#7e3e3e",
        "#3e5a7e", "#7e3e6a", "#5a7e3e",
    ]

    def __init__(self, label: str, track_index: int = -1, is_master: bool = False, parent=None):
        super().__init__(parent)
        self._is_master = is_master
        self._track_index = track_index
        self._muted = False

        self.setFixedWidth(70)
        self.setStyleSheet(
            f"QWidget {{ background: {self._STRIP_BG}; }}"
            f"QWidget#ChannelStripFrame {{ border-right: 1px solid {self._BORDER}; }}"
        )
        self.setObjectName("ChannelStripFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Title
        title_lbl = QLabel(label[:8])
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            f"color: {self._TITLE_COLOR}; font-size: 10px; font-weight: bold;"
            " background: transparent;"
        )
        title_lbl.setFixedHeight(16)
        layout.addWidget(title_lbl)

        # Pan knob (skip for master)
        if not is_master:
            self._pan_dial = QDial()
            self._pan_dial.setRange(-100, 100)
            self._pan_dial.setValue(0)
            self._pan_dial.setFixedSize(40, 40)
            self._pan_dial.setNotchesVisible(True)
            self._pan_dial.setToolTip("Pan: 0  (applies on export)")
            self._pan_dial.valueChanged.connect(self._on_pan_changed)
            pan_row = QWidget()
            pan_row.setStyleSheet("background: transparent;")
            pan_inner = QHBoxLayout(pan_row)
            pan_inner.setContentsMargins(0, 0, 0, 0)
            pan_inner.addStretch(1)
            pan_inner.addWidget(self._pan_dial)
            pan_inner.addStretch(1)
            layout.addWidget(pan_row)
        else:
            self._pan_dial = None
            layout.addSpacing(44)

        # VU meter
        vu_row = QWidget()
        vu_row.setStyleSheet("background: transparent;")
        vu_inner = QHBoxLayout(vu_row)
        vu_inner.setContentsMargins(0, 0, 0, 0)
        vu_inner.addStretch(1)
        self._vu = _VUMeterWidget()
        vu_inner.addWidget(self._vu)
        vu_inner.addStretch(1)
        layout.addWidget(vu_row)

        # Fader (vertical)
        self._fader = QSlider(Qt.Orientation.Vertical)
        self._fader.setRange(0, 150)
        self._fader.setValue(100)
        self._fader.setFixedHeight(100)
        self._fader.setToolTip("Volume: 1.00")
        self._fader.valueChanged.connect(self._on_fader_changed)
        fader_row = QWidget()
        fader_row.setStyleSheet("background: transparent;")
        fader_inner = QHBoxLayout(fader_row)
        fader_inner.setContentsMargins(0, 0, 0, 0)
        fader_inner.addStretch(1)
        fader_inner.addWidget(self._fader)
        fader_inner.addStretch(1)
        layout.addWidget(fader_row)

        # Volume label
        self._vol_label = QLabel("1.00")
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vol_label.setStyleSheet(
            "color: #c0c0d8; font-size: 10px; font-family: monospace; background: transparent;"
        )
        layout.addWidget(self._vol_label)

        # Mute button
        self._mute_btn = QPushButton("M")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedHeight(20)
        self._mute_btn.setStyleSheet(
            "QPushButton { background: #1e1e2e; color: #7878a0; border: 1px solid #2a2a3a;"
            " border-radius: 3px; font-size: 10px; font-weight: bold; }"
            "QPushButton:checked { background: #e84444; color: white; border-color: #e84444; }"
            "QPushButton:hover { color: #e0e0f0; }"
        )
        self._mute_btn.toggled.connect(self._on_mute_toggled)
        layout.addWidget(self._mute_btn)

        # Color indicator at bottom
        color = self._TRACK_COLORS[track_index % len(self._TRACK_COLORS)] if not is_master else "#6060a0"
        num_lbl = QLabel("MASTER" if is_master else f"A{track_index + 1}")
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setFixedHeight(14)
        num_lbl.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(num_lbl)

        layout.addStretch(1)

    # ---- public API ----

    def set_volume(self, volume: float) -> None:
        """Set fader without firing fader_changed (for external sync)."""
        with _block_signals(self._fader):
            self._fader.setValue(int(round(volume * 100)))
        self._vol_label.setText(f"{volume:.2f}")

    def set_pan(self, pan: float) -> None:
        """Set pan dial without firing pan_changed (for external sync)."""
        if self._pan_dial is not None:
            with _block_signals(self._pan_dial):
                self._pan_dial.setValue(int(round(pan * 100)))

    def set_levels(self, l: float, r: float) -> None:
        self._vu.set_levels(l, r)

    def pan_value(self) -> int:
        return self._pan_dial.value() if self._pan_dial else 0

    # ---- private ----

    def _on_fader_changed(self, value: int) -> None:
        vol = value / 100.0
        if self._muted:
            self._vol_label.setText(f"{vol:.2f} [M]")
        else:
            self._vol_label.setText(f"{vol:.2f}")
            self.fader_changed.emit(vol)

    def _on_pan_changed(self, value: int) -> None:
        pan = value / 100.0
        if self._pan_dial is not None:
            self._pan_dial.setToolTip(f"Pan: {value:+d}  (applies on export)")
        self.pan_changed.emit(pan)

    def _on_mute_toggled(self, muted: bool) -> None:
        self._muted = muted
        if muted:
            self.fader_changed.emit(0.0)
        else:
            self.fader_changed.emit(self._fader.value() / 100.0)


class AudioMixerPanel(QWidget):
    """Compact DaVinci-Fairlight-style channel strip mixer.

    One ChannelStrip per AudioTrack + one Master strip.
    A collapsible right-side scopes column (GoniometerWidget + LUFSWidget)
    lives inside this panel so no separate AudioScopesPanel is needed below
    the timeline.

    Call ``rebuild(audio_tracks)`` to refresh the strips list.
    Call ``update_levels(pos_ms, audio_tracks)`` each playhead tick.
    Call ``update_scopes(pos_ms, audio_tracks)`` to refresh scope widgets.
    Call ``set_scopes_visible(bool)`` to show/hide the scopes column.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioMixerPanel")
        self.setStyleSheet(
            "QWidget#AudioMixerPanel { background: #0e0e1a; border-top: 1px solid #2a2a3a; }"
        )
        self.setFixedHeight(310)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setObjectName("MixerTitleBar")
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "QWidget#MixerTitleBar { background: #181824; border-bottom: 1px solid #2a2a3a; }"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        title_lbl = QLabel("Audio Mixer")
        title_lbl.setStyleSheet("color: #9898b8; font-size: 11px; font-weight: bold;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch(1)

        # Popout button — same "⛶" icon as other panels (unified dock)
        self._popout_win: "QWidget | None" = None
        popout_btn = QPushButton("⛶")
        popout_btn.setObjectName("PreviewPopoutIcon")
        popout_btn.setFixedSize(28, 24)
        popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        popout_btn.setToolTip("독립 창으로 열기")
        popout_btn.clicked.connect(self._toggle_popout)
        tb_layout.addWidget(popout_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #7878a0; border: none; font-size: 10px; }"
            "QPushButton:hover { color: #ee4444; }"
        )
        close_btn.clicked.connect(self.hide)
        tb_layout.addWidget(close_btn)
        outer.addWidget(title_bar)

        # --- Horizontal splitter: strips (left) | scopes (right) ---
        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setHandleWidth(3)
        self._body_splitter.setStyleSheet(
            "QSplitter::handle { background: #2a2a3a; }"
        )

        # --- Strips scroll area (left side) ---
        strips_scroll = QScrollArea()
        strips_scroll.setWidgetResizable(True)
        strips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        strips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        strips_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        strips_scroll.setStyleSheet(
            "QScrollArea { background: #0e0e1a; border: none; }"
        )

        self._strips_host = QWidget()
        self._strips_host.setStyleSheet("background: #0e0e1a;")
        self._strips_layout = QHBoxLayout(self._strips_host)
        self._strips_layout.setContentsMargins(4, 4, 4, 4)
        self._strips_layout.setSpacing(1)
        self._strips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Master strip placeholder (always last)
        self._master_strip = _ChannelStrip("MASTER", is_master=True)
        # Master doesn't need to call external callbacks — just keep as local state
        self._strips_layout.addStretch(1)
        self._strips_layout.addWidget(self._master_strip)

        strips_scroll.setWidget(self._strips_host)
        self._body_splitter.addWidget(strips_scroll)

        # --- Scopes column (right side, ~220 px wide) ---
        self._scopes_col = QWidget()
        self._scopes_col.setObjectName("MixerScopesCol")
        self._scopes_col.setStyleSheet(
            "QWidget#MixerScopesCol { background: #111118; border-left: 1px solid #2a2a3a; }"
        )
        self._scopes_col.setFixedWidth(220)
        scopes_vlay = QVBoxLayout(self._scopes_col)
        scopes_vlay.setContentsMargins(6, 6, 6, 6)
        scopes_vlay.setSpacing(4)

        self._mixer_goniometer = GoniometerWidget()
        self._mixer_goniometer.setFixedSize(140, 140)
        # Center goniometer horizontally
        gonio_row = QHBoxLayout()
        gonio_row.setContentsMargins(0, 0, 0, 0)
        gonio_row.addStretch(1)
        gonio_row.addWidget(self._mixer_goniometer)
        gonio_row.addStretch(1)
        scopes_vlay.addLayout(gonio_row)

        self._mixer_lufs = LUFSWidget()
        scopes_vlay.addWidget(self._mixer_lufs, stretch=1)

        self._body_splitter.addWidget(self._scopes_col)

        # Splitter proportions: strips stretch, scopes fixed
        self._body_splitter.setStretchFactor(0, 1)
        self._body_splitter.setStretchFactor(1, 0)

        outer.addWidget(self._body_splitter, stretch=1)

        # Internal state: track_id → ChannelStrip
        self._track_strips: dict[int, _ChannelStrip] = {}
        # Callback set by the editor: (track_id, volume) → None
        self._volume_callback = None
        # Callback set by the editor: (track_id, pan) → None
        self._pan_callback = None

        # VU meter decay: 30fps timer smoothly lowers meters when no new
        # level data arrives (e.g. playback stopped or clip is silent).
        from PySide6.QtCore import QTimer as _QTimer
        self._vu_decay_timer = _QTimer(self)
        self._vu_decay_timer.setInterval(33)
        self._vu_decay_timer.timeout.connect(self._decay_vu_meters)
        self._vu_decay_timer.start()

    def _decay_vu_meters(self) -> None:
        """Gently decay all VU meters by 15% per frame (~30 fps fall-off)."""
        decay = 0.85
        for strip in self._track_strips.values():
            vu = strip._vu
            new_l = vu._l * decay
            new_r = vu._r * decay
            if new_l > 0.001 or new_r > 0.001:
                vu.set_levels(new_l, new_r)
        m_vu = self._master_strip._vu
        m_l = m_vu._l * decay
        m_r = m_vu._r * decay
        if m_l > 0.001 or m_r > 0.001:
            m_vu.set_levels(m_l, m_r)

    def set_volume_callback(self, cb) -> None:
        """Register callback(track_id, volume) called when a fader moves."""
        self._volume_callback = cb

    def set_pan_callback(self, cb) -> None:
        """Register callback(track_id, pan) called when a pan dial moves."""
        self._pan_callback = cb

    # ------------------------------------------------------------------
    # Scopes column visibility

    def set_scopes_visible(self, visible: bool) -> None:
        """Show or hide the right-side scopes column (goniometer + LUFS)."""
        self._scopes_col.setVisible(visible)

    def scopes_visible(self) -> bool:
        """Return True if the scopes column is currently shown."""
        return self._scopes_col.isVisible()

    # ------------------------------------------------------------------
    # Scopes update (called each playhead tick)

    def update_scopes(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform data around pos_ms and refresh goniometer + LUFS."""
        if not self._scopes_col.isVisible():
            return
        try:
            import numpy as _np
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
        except Exception:
            return

        momentary_l: list = []
        momentary_r: list = []
        full_l_chunks: list = []
        full_r_chunks: list = []
        _buckets_400ms = int(0.4 * WAVEFORM_BUCKETS_PER_SEC)

        for track in audio_tracks:
            vol = getattr(track, "volume", 1.0)
            for clip in getattr(track, "clips", []):
                if getattr(clip, "source_path", None) is None:
                    continue
                wf = getattr(clip, "waveform", None)
                if wf is None or (hasattr(wf, "size") and wf.size == 0):
                    continue
                wf = _np.asarray(wf, dtype=_np.float32)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
                if is_stereo:
                    wf_l, wf_r = wf[0], wf[1]
                else:
                    wf_l = wf_r = wf.ravel()
                n = len(wf_l)
                full_l_chunks.append(wf_l * vol)
                full_r_chunks.append(wf_r * vol)
                local_ms = pos_ms - getattr(clip, "offset_ms", 0)
                if local_ms < 0:
                    continue
                src_ms = getattr(clip, "trim_start_ms", 0) + local_ms
                center_bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                b_start = max(0, center_bucket - _buckets_400ms)
                b_end = min(n, center_bucket + 1)
                if b_start < b_end:
                    momentary_l.append(wf_l[b_start:b_end] * vol)
                    momentary_r.append(wf_r[b_start:b_end] * vol)

        if not full_l_chunks:
            self._mixer_goniometer.clear()
            self._mixer_lufs.update_from_peaks(
                _np.zeros(1, _np.float32), _np.zeros(1, _np.float32),
                None, None,
            )
            return

        full_l = _np.concatenate(full_l_chunks)
        full_r = _np.concatenate(full_r_chunks)
        if momentary_l:
            mom_l = _np.concatenate(momentary_l)
            mom_r = _np.concatenate(momentary_r)
        else:
            mom_l = mom_r = _np.zeros(1, _np.float32)

        self._mixer_goniometer.update_from_stereo(mom_l, mom_r)
        self._mixer_lufs.update_from_peaks(mom_l, mom_r, full_l, full_r)

    def _toggle_popout(self) -> None:
        """Open/close the mixer as a floating window (reparent pattern)."""
        if self._popout_win is not None:
            self._popout_win.close()
            return
        from PySide6.QtCore import QSize
        win = QWidget(None, Qt.WindowType.Window)
        win.setWindowTitle("Audio Mixer")
        win.resize(QSize(max(600, self.width()), 340))
        win.setStyleSheet("QWidget { background: #0e0e1a; }")
        lay = QVBoxLayout(win)
        lay.setContentsMargins(0, 0, 0, 0)
        # Reparent the body splitter (strips + scopes) into the floating window
        self._body_splitter.setParent(win)
        lay.addWidget(self._body_splitter)
        self._popout_win = win

        def _on_close():
            # Bring splitter back to the panel
            self._body_splitter.setParent(self)
            self.layout().addWidget(self._body_splitter)
            self._popout_win = None
            win.deleteLater()

        win.closeEvent = lambda ev, _cb=_on_close: (_cb(), ev.accept())
        win.show()
        win.raise_()

    def rebuild(self, audio_tracks: list) -> None:
        """Recreate channel strips to match current audio track list."""
        # Remove old track strips (not master)
        for strip in list(self._track_strips.values()):
            self._strips_layout.removeWidget(strip)
            strip.deleteLater()
        self._track_strips.clear()

        for i, track in enumerate(audio_tracks):
            name = (track.display_name or f"Audio {i+1}")[:8]
            strip = _ChannelStrip(name, track_index=i)
            strip.set_volume(track.volume)
            strip.set_pan(getattr(track, "pan", 0.0))
            tid = track.id

            def _make_vol_cb(track_id):
                def _cb(vol):
                    if self._volume_callback:
                        self._volume_callback(track_id, vol)
                return _cb

            def _make_pan_cb(track_id):
                def _cb(pan):
                    if self._pan_callback:
                        self._pan_callback(track_id, pan)
                return _cb

            strip.fader_changed.connect(_make_vol_cb(tid))
            strip.pan_changed.connect(_make_pan_cb(tid))
            self._track_strips[tid] = strip
            # Insert before the stretch+master at the end
            insert_pos = self._strips_layout.count() - 2  # before stretch + master
            self._strips_layout.insertWidget(insert_pos, strip)

    def sync_track_volume(self, track_id: int, volume: float) -> None:
        """Called when a track's volume changes externally (track row slider)."""
        strip = self._track_strips.get(track_id)
        if strip is not None:
            strip.set_volume(volume)

    def update_levels(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform peaks and update VU meters."""
        try:
            import numpy as _np
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
        except Exception:
            return

        master_l = master_r = 0.0

        for track in audio_tracks:
            strip = self._track_strips.get(track.id)
            l_peak = r_peak = 0.0
            for clip in track.clips:
                if clip.source_path is None:
                    continue
                local_ms = pos_ms - clip.offset_ms
                if local_ms < 0 or local_ms > clip.effective_length_ms:
                    continue
                src_ms = clip.trim_start_ms + local_ms
                wf = clip.waveform
                if wf is None or wf.size == 0:
                    continue
                bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
                n = wf.shape[1] if is_stereo else len(wf)
                if 0 <= bucket < n:
                    if is_stereo:
                        l_peak = max(l_peak, float(wf[0, bucket]) * track.volume)
                        r_peak = max(r_peak, float(wf[1, bucket]) * track.volume)
                    else:
                        v = float(wf[bucket]) * track.volume
                        l_peak = max(l_peak, v)
                        r_peak = max(r_peak, v)
            if strip is not None:
                strip.set_levels(l_peak, r_peak)
            master_l = max(master_l, l_peak)
            master_r = max(master_r, r_peak)

        self._master_strip.set_levels(master_l, master_r)


# ---------------------------------------------------------------------------
#  Title animation preset cards (drag-source for typography lane)
# ---------------------------------------------------------------------------


class TitlePresetCard(QFrame):
    """Draggable 130×80 px card for a single title animation preset.

    Dragging onto a TrackRow (or TextLaneRow) and dropping creates a
    TextClip with the preset's text, style, and animation settings baked in.
    MIME type: ``TITLE_PRESET_MIME_TYPE``.
    """

    def __init__(self, preset: dict) -> None:
        super().__init__()
        self._preset = preset
        self._hovered = False

        self.setFixedSize(130, 80)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setToolTip(f"{preset['name']}\n{preset['desc']}\nDrag onto timeline to add")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(2)

        # Icon row
        icon_lbl = QLabel(preset["icon"])
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = icon_lbl.font()
        icon_font.setPixelSize(28)
        icon_lbl.setFont(icon_font)
        icon_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(icon_lbl)

        # Name label (bold)
        name_lbl = QLabel(preset["name"])
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = name_lbl.font()
        name_font.setPixelSize(11)
        name_font.setBold(True)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet("color: #e0e0e8; background: transparent;")
        layout.addWidget(name_lbl)

        # Desc label (small, gray)
        desc_lbl = QLabel(preset["desc"])
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_font = desc_lbl.font()
        desc_font.setPixelSize(9)
        desc_lbl.setFont(desc_font)
        desc_lbl.setStyleSheet("color: #888896; background: transparent;")
        layout.addWidget(desc_lbl)

        self._update_style()

    def _update_style(self) -> None:
        border_color = "#d85a30" if self._hovered else "#3a3a42"
        self.setStyleSheet(
            f"""
            TitlePresetCard {{
                background-color: #1e1e26;
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
            """
        )

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        import json
        payload = json.dumps(self._preset)
        mime = QMimeData()
        mime.setData(TITLE_PRESET_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class TitlePresetsPanel(QWidget):
    """Left-dock panel showing a 2-column grid of TitlePresetCards."""

    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, preset in enumerate(TITLE_PRESETS):
            card = TitlePresetCard(preset)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)
        root.addLayout(grid)


# ---------------------------------------------------------------------------
#  DaVinci-style Transition cards
# ---------------------------------------------------------------------------


class TransitionCard(QFrame):
    """Draggable 90×70 px card for a single clip-boundary transition type.

    Dragging the card onto a TrackRow and releasing near a clip's right
    edge sets ``clip.transition_out_type`` and ``clip.transition_out_ms``
    via the ``TRANSITION_MIME_TYPE`` MIME type.

    ``ttype`` is one of: ``"dissolve"``, ``"fade_black"``, ``"fade_white"``,
    ``"dip_white"``.
    """

    _NAMES = {
        "dissolve":   "Cross Dissolve",
        "fade_black": "Fade to Black",
        "fade_white": "Fade to White",
        "dip_white":  "Dip to White",
        "slide_left": "Slide Left",
        "wipe_left":  "Wipe Left",
        "zoom_in":    "Zoom In",
        "zoom_out":   "Zoom Out",
    }

    def __init__(self, ttype: str, default_ms: int = 500) -> None:
        super().__init__()
        self._ttype = ttype
        self._default_ms = default_ms
        self._hovered = False

        self.setFixedSize(90, 70)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setToolTip(
            f"{self._NAMES.get(ttype, ttype)}\n"
            "Drag onto a clip's right edge to apply"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Mini preview swatch
        self._swatch = _TransitionSwatch(ttype)
        self._swatch.setFixedSize(78, 36)
        layout.addWidget(self._swatch, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Label
        lbl = QLabel(self._NAMES.get(ttype, ttype))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        font = lbl.font()
        font.setPixelSize(9)
        lbl.setFont(font)
        lbl.setStyleSheet("color: #c0c0c8; background: transparent;")
        layout.addWidget(lbl)

        self._update_style()

    def _update_style(self) -> None:
        border_color = "#d85a30" if self._hovered else "#3a3a42"
        self.setStyleSheet(
            f"""
            TransitionCard {{
                background-color: #1e1e26;
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
            """
        )

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        import json
        payload = json.dumps({"type": self._ttype, "ms": self._default_ms})
        mime = QMimeData()
        mime.setData(TRANSITION_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _TransitionSwatch(QWidget):
    """Mini visual preview drawn for each transition type."""

    def __init__(self, ttype: str) -> None:
        super().__init__()
        self._ttype = ttype

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QBrush, QLinearGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor("#141418"))

        ttype = self._ttype
        if ttype == "dissolve":
            # Left clip (blue-grey), right clip (blue-grey) with overlap gradient
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            p.fillRect(w // 2, 0, w - w // 2, h, QColor("#2a3a4a"))
            # Overlap dissolve gradient centre
            g = QLinearGradient(w // 4, 0, 3 * w // 4, 0)
            g.setColorAt(0.0, QColor(42, 58, 74, 0))
            g.setColorAt(0.5, QColor(180, 180, 220, 160))
            g.setColorAt(1.0, QColor(42, 58, 74, 0))
            p.fillRect(w // 4, 0, w // 2, h, QBrush(g))
            # Centre line
            pen = QPen(QColor(180, 180, 220, 200), 1)
            p.setPen(pen)
            p.drawLine(w // 2, 0, w // 2, h)

        elif ttype == "fade_black":
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            g = QLinearGradient(w // 4, 0, w, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 255))
            p.fillRect(0, 0, w, h, QBrush(g))

        elif ttype in ("fade_white", "dip_white"):
            p.fillRect(0, 0, w // 2, h, QColor("#2a3a4a"))
            g = QLinearGradient(w // 4, 0, w, 0)
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(1.0, QColor(255, 255, 255, 255))
            p.fillRect(0, 0, w, h, QBrush(g))

        # Border
        pen = QPen(QColor("#3a3a4a"), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)


class TransitionsPanel(QWidget):
    """Left-dock panel showing a grid of TransitionCards + a duration slider.

    The duration slider sets the default duration that gets baked into the
    MIME payload when a card is dragged. The current value is shown in the
    label "기본 길이: 500ms".
    """

    _CARD_TYPES = [
        ("dissolve",   "Cross Dissolve"),
        ("fade_black", "Fade to Black"),
        ("fade_white", "Fade to White"),
        ("dip_white",  "Dip to White"),
        ("slide_left", "Slide Left"),
        ("wipe_left",  "Wipe Left"),
        ("zoom_in",    "Zoom In"),
        ("zoom_out",   "Zoom Out"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._default_ms = 500

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(8)

        # Card grid — 2 columns
        grid = QGridLayout()
        grid.setSpacing(6)
        self._cards: list[TransitionCard] = []
        for idx, (ttype, _label) in enumerate(self._CARD_TYPES):
            card = TransitionCard(ttype, self._default_ms)
            self._cards.append(card)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)
        root.addLayout(grid)

        # Duration slider
        dur_row = QHBoxLayout()
        dur_row.setContentsMargins(0, 0, 0, 0)
        dur_row.setSpacing(6)
        self._dur_label = QLabel(f"기본 길이: {self._default_ms}ms")
        self._dur_label.setStyleSheet("color: #9a9aa8; font-size: 10px;")
        dur_row.addWidget(self._dur_label)
        root.addLayout(dur_row)

        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setRange(100, 3000)
        self._dur_slider.setSingleStep(50)
        self._dur_slider.setPageStep(100)
        self._dur_slider.setValue(self._default_ms)
        self._dur_slider.setToolTip("Transition default duration (ms)")
        self._dur_slider.valueChanged.connect(self._on_duration_changed)
        root.addWidget(self._dur_slider)

    def _on_duration_changed(self, value: int) -> None:
        # Round to nearest 50 ms for readability
        snapped = round(value / 50) * 50
        self._default_ms = snapped
        self._dur_label.setText(f"기본 길이: {snapped}ms")
        for card in self._cards:
            card._default_ms = snapped


# ---------------------------------------------------------------------------
# AI subtitle generation — Whisper backend
# ---------------------------------------------------------------------------

class WhisperTranscriber(QThread):
    """Background thread that extracts audio from a video file and runs
    Whisper (faster-whisper or openai-whisper) to produce subtitle
    segments.  Emits ready(list[dict]) on success or failed(str) on
    error, with progress(int) 0-100 during processing."""

    ready    = Signal(object)  # list of {"text", "start", "end"} dicts
    failed   = Signal(str)
    progress = Signal(int)

    def __init__(
        self,
        video_path: Path,
        language: str,
        model_size: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path       = video_path
        self._language   = language
        self._model_size = model_size

    def run(self) -> None:  # noqa: C901 – intentional monolith for clarity
        try:
            import sys
            import subprocess
            import tempfile
            import os
            from imageio_ffmpeg import get_ffmpeg_exe

            # ── 1. Extract audio to temp WAV (16 kHz mono) ──────────────
            ffmpeg = get_ffmpeg_exe()
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()

            self.progress.emit(10)
            # First probe to check if audio stream exists
            probe_result = subprocess.run(
                [ffmpeg, "-nostdin", "-v", "info", "-i", str(self._path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                creationflags=(0x08000000 if sys.platform == "win32" else 0),
            )
            if "Audio:" not in probe_result.stderr:
                os.unlink(tmp_path)
                self.failed.emit(
                    f"'{self._path.name}' 파일에 오디오 스트림이 없습니다.\n"
                    "오디오가 있는 영상 파일을 사용해 주세요."
                )
                return
            cmd = [
                ffmpeg, "-nostdin", "-v", "error",
                "-i", str(self._path),
                "-vn",  # ignore video
                "-ac", "1", "-ar", "16000", "-f", "wav", "-y", tmp_path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                creationflags=(0x08000000 if sys.platform == "win32" else 0),
            )
            if result.returncode != 0:
                os.unlink(tmp_path)
                err_txt = result.stderr.decode("utf-8", errors="replace")[-300:]
                self.failed.emit(
                    f"오디오 추출 실패 (rc={result.returncode})\n{err_txt}"
                )
                return
            self.progress.emit(30)

            # ── 2. Transcribe in isolated subprocess (ctranslate2 can segfault) ──
            lang_arg = self._language or ""
            script = (
                "import sys, json\n"
                "try:\n"
                "    from faster_whisper import WhisperModel\n"
                f"    m = WhisperModel({repr(self._model_size)}, device='cpu', compute_type='float32')\n"
                f"    segs, info = m.transcribe({repr(tmp_path)}, language={repr(lang_arg) if lang_arg else 'None'}, beam_size=5, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))\n"
                "    out = [{'text': s.text.strip(), 'start': s.start, 'end': s.end} for s in segs if s.text.strip()]\n"
                "    sys.stderr.write(f'detected_language={info.language} duration={info.duration:.1f}s segments={len(out)}\\n')\n"
                "except ImportError:\n"
                "    import whisper\n"
                f"    m = whisper.load_model({repr(self._model_size)})\n"
                f"    r = m.transcribe({repr(tmp_path)}, language={repr(lang_arg) if lang_arg else 'None'})\n"
                "    out = [{'text': s['text'].strip(), 'start': s['start'], 'end': s['end']} for s in r['segments'] if s['text'].strip()]\n"
                "print(json.dumps(out))\n"
            )
            self.progress.emit(50)
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(0x08000000 if sys.platform == "win32" else 0),
                timeout=600,  # 10 min max
            )
            os.unlink(tmp_path)
            if proc.returncode != 0:
                err = (proc.stderr or "unknown error")[-400:]
                self.failed.emit(f"Whisper process failed (rc={proc.returncode}):\n{err}")
                return
            if not proc.stdout.strip():
                diag = proc.stderr.strip()[-200:] if proc.stderr else "no output"
                self.failed.emit(f"Whisper returned no output.\n{diag}")
                return
            import json as _json
            segments = _json.loads(proc.stdout.strip())
            self.progress.emit(100)
            self.ready.emit(segments)

        except Exception as exc:
            self.failed.emit(str(exc))


class WhisperDialog(QDialog):
    """Modal settings + progress dialog for AI subtitle generation.

    The caller checks ``dialog.segments`` after ``exec()`` returns
    ``QDialog.DialogCode.Accepted``."""

    # Language codes — empty string means auto-detect
    _LANGUAGES = [
        ("자동감지", ""),
        ("한국어",   "ko"),
        ("영어",     "en"),
        ("일본어",   "ja"),
        ("중국어",   "zh"),
        ("스페인어", "es"),
        ("프랑스어", "fr"),
        ("독일어",   "de"),
    ]

    _MODELS = [
        ("tiny   — 빠름 / 낮은 정확도",  "tiny"),
        ("base   — 균형",                 "base"),
        ("small  — 권장",                 "small"),
        ("medium — 정확",                 "medium"),
        ("large  — 최고 정확도",          "large-v3"),
    ]

    def __init__(self, video_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._video_path = video_path
        self._worker: WhisperTranscriber | None = None
        self.segments: list[dict] = []

        self.setWindowTitle("🎤 AI 자막 생성")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Model ────────────────────────────────────────────────────────
        root.addWidget(QLabel("모델 크기"))
        self._model_combo = QComboBox()
        for label, _ in self._MODELS:
            self._model_combo.addItem(label)
        self._model_combo.setCurrentIndex(2)  # default: small
        root.addWidget(self._model_combo)

        # ── Language ─────────────────────────────────────────────────────
        root.addWidget(QLabel("언어"))
        self._lang_combo = QComboBox()
        for label, _ in self._LANGUAGES:
            self._lang_combo.addItem(label)
        root.addWidget(self._lang_combo)

        # ── Status label ─────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        # ── Progress bar (hidden until transcription starts) ──────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        root.addWidget(self._progress)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("자막 생성")
        self._run_btn.setObjectName("PrimaryToolButton")
        self._run_btn.clicked.connect(self._start)
        self._cancel_btn = QPushButton("취소")
        self._cancel_btn.setObjectName("ToolButton")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._cancel_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _start(self) -> None:
        model_size = self._MODELS[self._model_combo.currentIndex()][1]
        language   = self._LANGUAGES[self._lang_combo.currentIndex()][1]

        self._run_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.setText("오디오 추출 중…")

        self._worker = WhisperTranscriber(self._video_path, language, model_size, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, value: int) -> None:
        self._progress.setValue(value)
        if value < 30:
            self._status_label.setText("오디오 추출 중…")
        elif value < 50:
            self._status_label.setText("모델 로딩 중…")
        elif value < 100:
            self._status_label.setText("전사 중…")
        else:
            self._status_label.setText("완료!")

    def _on_ready(self, segments: list) -> None:
        self.segments = segments
        self.accept()

    def _on_failed(self, reason: str) -> None:
        self._progress.hide()
        self._status_label.setText("오류 발생 — 아래 내용을 복사해서 공유해 주세요")
        self._run_btn.setEnabled(True)
        # Log to tigercapture.log
        import sys
        print(f"[whisper] FAILED: {reason}", file=sys.stderr, flush=True)
        # Show copyable error in a QTextEdit popup
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton as _QPB
        err_dlg = QDialog(self)
        err_dlg.setWindowTitle("AI 자막 오류")
        err_dlg.resize(600, 300)
        vlay = QVBoxLayout(err_dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(reason)
        txt.setStyleSheet("font-family: monospace; font-size: 11px;")
        vlay.addWidget(txt)
        close_btn = _QPB("닫기")
        close_btn.clicked.connect(err_dlg.accept)
        vlay.addWidget(close_btn)
        err_dlg.exec()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().closeEvent(event)


class VideoEditorWindow(QWidget):
    """Professional video editor with multi-track timeline, per-region speed
    (0.25x ~ 16x), cut regions, thumbnails, and right-click context menus.

    Playback model (v1): one active track plays in the preview at a time.
    Switch between tracks by clicking a track row.
    """

    def __init__(self, source_path: Path | None = None) -> None:
        super().__init__()
        self._tracks: list[VideoTrack] = []
        self._track_rows: dict[int, TrackRow] = {}
        self._audio_tracks: list[AudioTrack] = []
        self._audio_rows: dict[int, AudioTrackRow] = {}
        self._waveform_extractors: dict[int, WaveformExtractor] = {}
        self._preview_popout: "PreviewPopoutWindow | None" = None
        self._next_track_id: int = 1
        self._active_track_id: int | None = None
        self._current_segment_speed: float = 1.0
        self._extractors: dict[int, ThumbnailExtractor] = {}
        # Per-clip thumbnail extractors keyed by (track_id, clip_id).
        # Used for multi-source clips appended to an existing track.
        self._clip_extractors: dict[tuple, ThumbnailExtractor] = {}
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._strokes: list[Stroke] = []
        self._bubbles: list[SpeechBubble] = []
        self._bubble_items: list[SpeechBubbleItem] = []
        self._stickers: list = []             # list[Sticker]
        self._sticker_items: list = []        # list[StickerItem]
        # Label used to render the currently-active typography actor on
        # top of the preview. Phase 1 renders statically (no animations
        # yet). Actors themselves live on each VideoTrack.
        self._text_preview_label: QLabel | None = None

        # 10-step undo / redo. Initial snapshot is pushed once
        # ``_build_ui`` finishes wiring the subtitle panel — see
        # ``_seed_history`` below.
        from app.history import HistoryStack
        self._history = HistoryStack(max_undo_steps=10)
        self._history_suspended: bool = False

        # Option C: industry-standard clip selection state. Each
        # entry is ``(track_id, clip_id)``. Editor manages the list
        # so multi-track multi-select Just Works under Shift+click.
        self._selected_clips: list[tuple[int, int]] = []
        # Option C: project-level IN / OUT markers (export range).
        # ``-1`` means unset. The TimelineRuler renders them and the
        # I / O shortcuts set them; track-local ``selection_*_ms``
        # stays as a *secondary* concept driven by Shift+drag.
        self._global_in_ms: int = -1
        self._global_out_ms: int = -1
        # Project timeline markers — colored triangles on the ruler.
        # Each: {"ms": int, "color": str, "label": str}
        # Cycles through orange→green→blue→yellow on successive adds.
        self._timeline_markers: list[dict] = []
        self._MARKER_COLORS = ["#f0a030", "#40c060", "#4090e0", "#e0d040"]

        # DaVinci-style per-node colour grading. ``_node_grade_target``
        # holds the NodeItem the Color panel is currently editing.
        # ``_active_color_grade()`` reads through this; falls back to
        # ``track.color_grade`` when nothing is bound.
        self._node_grade_target = None

        # 3D LUT state. ``_lut_data`` is a numpy (S,S,S,3) float32
        # array when a .cube file is loaded, or None when no LUT is active.
        self._lut_data = None
        self._lut_strength: float = 1.0
        self._lut_path: str = ""

        # Proxy workflow state
        self._proxy_mode: bool = False
        self._proxy_dir: "Path | None" = None   # None = same directory as source
        # Active proxy generator threads keyed by original path string.
        self._proxy_threads: dict[str, ProxyGeneratorThread] = {}

        # Marching-ants animation — drives both blade-cut markers and
        # clip selection gizmo (Photoshop-style animated dashed border).
        from PySide6.QtCore import QTimer
        self._blade_dash_offset: int = 0
        self._blade_dash_timer = QTimer(self)
        self._blade_dash_timer.setInterval(80)   # ~12fps animation
        self._blade_dash_timer.timeout.connect(self._tick_blade_dash)
        self._blade_dash_timer.start()            # always running

        # Auto-save: fires every 5 minutes, saves to a sibling ~autosave.tgp.
        # ``_project_path`` tracks the last manually-saved / opened path so
        # the autosave sits next to it; falls back to ~/autosave.tgp.
        self._project_path: "Path | None" = None
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(5 * 60 * 1000)  # 5 minutes
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._autosave_timer.start()

        self.setObjectName("EditorRoot")
        self.setWindowTitle(tr("veditor.title"))
        self.resize(1180, 780)
        self.setStyleSheet(VIDEO_EDITOR_EXTRA_QSS)
        # Accept dropped files anywhere on the editor — drop on a track
        # row targets that row; drop on empty area creates a new track.
        self.setAcceptDrops(True)

        self._player = ProjectPlayer(self)
        self._player.frame_ready.connect(self._on_frame_ready)
        self._player.gpu_frame_ready.connect(self._on_gpu_frame_ready)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.duration_changed.connect(self._on_duration_changed)
        self._player.state_changed.connect(self._on_playback_state_changed)
        self._player.error_occurred.connect(self._on_player_error)

        # Audio mixer — listens to the project player and keeps each
        # audio track's QMediaPlayer in sync.
        self._audio_mixer = AudioMixer(self)
        self._player.state_changed.connect(self._audio_mixer.on_state_changed)
        self._player.position_changed.connect(self._audio_mixer.on_position_changed)

        self._build_ui()

        if source_path is not None:
            self._add_track_with_source(Path(source_path))
        # Empty placeholder track removed: opening the editor without a
        # source now starts with zero video tracks. Users add the first
        # track by dragging from the media pool (creates a real loaded
        # track) or pressing the "Add Track" button.

        # Seed history with the post-load state so the user's first
        # Ctrl+Z reverts the very first edit (cut, drag, etc.) back to
        # the freshly-loaded project. ``_register_change`` is a no-op
        # while ``_history.depth() == 0``, so we push directly.
        from app.history import capture_editor_snapshot
        self._history.push(capture_editor_snapshot(self), label="initial")

    # ------------------------- UI --------------------------

    @staticmethod
    def _make_section_header(title: str, accent: str) -> QLabel:
        label = QLabel(title.upper())
        label.setProperty("sectionHeader", "true")
        label.setProperty("accent", accent)  # preview / timeline / subtitles
        return label

    def _build_fade_card(self) -> QWidget:
        self.fade_card = FadeCard()
        return self.fade_card

    def _build_ui(self) -> None:
        # Outer horizontal split: main work area (preview / controls /
        # tracks / color) on the left, dock column on the right. The
        # right dock holds the subtitle panel for now and is the
        # designated home for future side-panel tools (text, stickers,
        # etc.) so they don't pile up below the timeline.
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(0)

        self._main_dock_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_dock_splitter.setChildrenCollapsible(False)
        self._main_dock_splitter.setHandleWidth(6)
        outer.addWidget(self._main_dock_splitter, stretch=1)

        # Left = media pool dock. DaVinci-style: imported clips live
        # here, drag them onto a track to add to the timeline.
        self._left_dock_host = QWidget()
        self._left_dock_host.setObjectName("LeftDockColumn")
        self._left_dock_host.setMinimumWidth(192)
        left_dock_layout = QVBoxLayout(self._left_dock_host)
        left_dock_layout.setContentsMargins(0, 0, 8, 0)
        left_dock_layout.setSpacing(8)
        self._left_dock_layout = left_dock_layout
        self._main_dock_splitter.addWidget(self._left_dock_host)

        # Center = main work area. ``root`` (QVBoxLayout) is preserved
        # as the local name everything below appends to, so the rest
        # of the build flow keeps reading naturally.
        main_col = QWidget()
        root = QVBoxLayout(main_col)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self._main_dock_splitter.addWidget(main_col)

        # Right = subtitle dock + future contextual inspector tabs.
        # Sized to roughly a 4:3 portrait sidebar at default. The user
        # can drag the splitters to resize either side column.
        self._right_dock_host = QWidget()
        self._right_dock_host.setObjectName("RightDockColumn")
        self._right_dock_host.setMinimumWidth(224)
        right_dock_layout = QVBoxLayout(self._right_dock_host)
        right_dock_layout.setContentsMargins(8, 0, 0, 0)
        right_dock_layout.setSpacing(8)
        self._right_dock_layout = right_dock_layout
        self._main_dock_splitter.addWidget(self._right_dock_host)

        # Stretch factors: centre column is the canvas, so it absorbs
        # most extra width; both side docks get a fixed-ish share.
        self._main_dock_splitter.setStretchFactor(0, 1)
        self._main_dock_splitter.setStretchFactor(1, 5)
        self._main_dock_splitter.setStretchFactor(2, 1)
        # Default sizes; user-dragged sizes are persisted via Qt's
        # splitter state if we wire it later.
        self._main_dock_splitter.setSizes([224, 900, 256])

        # --- Top toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.add_track_btn = QPushButton(tr("veditor.btn.add_track"))
        self.add_track_btn.setObjectName("ToolButton")
        self.add_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_track_btn.clicked.connect(self._add_empty_track)

        self.del_track_btn = QPushButton(tr("veditor.btn.del_track"))
        self.del_track_btn.setObjectName("ToolButton")
        self.del_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_track_btn.clicked.connect(self._delete_active_track)

        self.add_audio_btn = QPushButton(tr("veditor.btn.add_audio"))
        self.add_audio_btn.setObjectName("ToolButton")
        self.add_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_audio_btn.setToolTip(tr("veditor.audio.add_hint"))
        self.add_audio_btn.clicked.connect(self._add_empty_audio_track)

        self.reset_btn = QPushButton(tr("veditor.btn.reset"))
        self.reset_btn.setObjectName("ToolButton")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.clicked.connect(self._on_reset_active_track)

        # Blade button — splits the active track's clip at the playhead.
        # Same behaviour as the B/C/Ctrl+K/Ctrl+\\ shortcuts; surfaces
        # the action for users who don't know them.
        self.blade_btn = QPushButton(tr("veditor.btn.blade"))
        self.blade_btn.setObjectName("ToolButton")
        self.blade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.blade_btn.setToolTip(tr("veditor.btn.blade.tooltip"))
        self.blade_btn.clicked.connect(self._blade_at_playhead)

        self.export_btn = QPushButton(tr("veditor.btn.export"))
        self.export_btn.setObjectName("PrimaryToolButton")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._on_export)

        # Export quality + format dropdowns sit left of the Export
        # button. Default: high quality / mp4 — matches the pre-tier
        # hardcoded values so existing exports stay byte-equivalent.
        from app.video_exporter import (
            DEFAULT_FORMAT_ID,
            DEFAULT_QUALITY_ID,
            EXPORT_FORMATS,
            QUALITY_PRESETS,
            get_export_format,
            get_quality_preset,
        )
        self._export_quality_id = DEFAULT_QUALITY_ID
        self._export_format_id = DEFAULT_FORMAT_ID
        # Export resolution and FPS presets. None means "original".
        self._export_resolution: "tuple[int,int] | None" = None   # (w, h) or None
        self._export_fps: "float | None" = None                    # fps or None

        _TOOLBTN_QSS = (
            f"QToolButton#{{name}} {{ "
            f"background-color: {COLOR_BG_L5}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 26px 4px 10px; font-size: 11px; min-height: 24px; }}"
            f"QToolButton#{{name}}:hover {{ "
            f"background-color: {COLOR_BG_L6}; border-color: #4a4a52; }}"
            f"QToolButton#{{name}}:pressed {{ "
            f"background-color: {COLOR_BG_L4}; }}"
            f"QToolButton#{{name}}::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 7px; }}"
        )

        self.resolution_btn = QToolButton()
        self.resolution_btn.setObjectName("ResolutionDropdown")
        self.resolution_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resolution_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.resolution_btn.setToolTip("내보내기 해상도")
        self.resolution_btn.setMinimumHeight(30)
        self.resolution_btn.setStyleSheet(
            _TOOLBTN_QSS.replace("{name}", "ResolutionDropdown")
        )
        self._refresh_resolution_btn_label()
        self._build_resolution_menu()

        self.fps_btn = QToolButton()
        self.fps_btn.setObjectName("FpsDropdown")
        self.fps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fps_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.fps_btn.setToolTip("내보내기 FPS")
        self.fps_btn.setMinimumHeight(30)
        self.fps_btn.setStyleSheet(
            _TOOLBTN_QSS.replace("{name}", "FpsDropdown")
        )
        self._refresh_fps_btn_label()
        self._build_fps_menu()

        self.quality_btn = QToolButton()
        self.quality_btn.setObjectName("QualityDropdown")
        self.quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quality_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
        self.quality_btn.setMinimumHeight(30)
        # Inline style so the QToolButton matches the dark dialog theme
        # (the global ``QPushButton#ToolButton`` rule does not target
        # QToolButton) and the dropdown arrow gets enough breathing room.
        self.quality_btn.setStyleSheet(
            f"QToolButton#QualityDropdown {{ "
            f"background-color: {COLOR_BG_L5}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 26px 4px 10px; font-size: 11px; min-height: 24px; }}"
            f"QToolButton#QualityDropdown:hover {{ "
            f"background-color: {COLOR_BG_L6}; border-color: #4a4a52; }}"
            f"QToolButton#QualityDropdown:pressed {{ "
            f"background-color: {COLOR_BG_L4}; }}"
            f"QToolButton#QualityDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 7px; }}"
        )
        self._refresh_quality_btn_label()
        self._build_quality_menu()

        # Format dropdown — sibling of quality_btn, identical styling.
        self.format_btn = QToolButton()
        self.format_btn.setObjectName("FormatDropdown")
        self.format_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.format_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.format_btn.setToolTip(tr("veditor.export.format.tooltip"))
        self.format_btn.setMinimumHeight(30)
        self.format_btn.setStyleSheet(
            f"QToolButton#FormatDropdown {{ "
            f"background-color: {COLOR_BG_L5}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 26px 4px 10px; font-size: 11px; min-height: 24px; }}"
            f"QToolButton#FormatDropdown:hover {{ "
            f"background-color: {COLOR_BG_L6}; border-color: #4a4a52; }}"
            f"QToolButton#FormatDropdown:pressed {{ "
            f"background-color: {COLOR_BG_L4}; }}"
            f"QToolButton#FormatDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 7px; }}"
        )
        self._refresh_format_btn_label()
        self._build_format_menu()

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setObjectName("ToolButton")
        self.zoom_out_btn.setFixedWidth(32)
        self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_out_btn.clicked.connect(lambda: self._change_zoom(0.6667))

        self.zoom_label = QLabel(self._format_zoom())
        self.zoom_label.setObjectName("ZoomLabel")
        self.zoom_label.setFixedWidth(70)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("ToolButton")
        self.zoom_in_btn.setFixedWidth(32)
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.clicked.connect(lambda: self._change_zoom(1.5))

        self.zoom_fit_btn = QPushButton(tr("veditor.btn.zoom_fit"))
        self.zoom_fit_btn.setObjectName("ToolButton")
        self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)

        # Pop-out icon is shown inside the PREVIEW section header (right
        # end) rather than here, so that it reads as "this control
        # belongs to the preview". Created eagerly so _build_preview_header
        # can reference it, attached there.
        self.popout_btn = QPushButton("⛶")
        self.popout_btn.setObjectName("PreviewPopoutIcon")
        self.popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
        self.popout_btn.setFixedSize(28, 24)
        self.popout_btn.clicked.connect(self._toggle_preview_popout)

        # Project Save / Load buttons
        self.new_project_btn = QPushButton("+ 새 프로젝트")
        self.new_project_btn.setObjectName("ToolButton")
        self.new_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_project_btn.setToolTip("새 프로젝트 만들기 (Ctrl+N)")
        self.new_project_btn.clicked.connect(self._on_new_project)
        self.new_project_btn.setStyleSheet(
            f"QPushButton{{background:{COLOR_BG_L5}; color:{COLOR_TEXT_PRIMARY};"
            f"border:1px solid {COLOR_BORDER_DEFAULT}; border-radius:4px;"
            "padding:5px 9px; font-size:11px; font-weight:600;}"
            f"QPushButton:hover{{background:{COLOR_BG_L6}; border-color:#4a4a52;}}"
            f"QPushButton:pressed{{background:{COLOR_BG_L4};}}"
        )

        self.save_project_btn = QPushButton("💾 저장")
        self.save_project_btn.setObjectName("ToolButton")
        self.save_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_project_btn.setToolTip("프로젝트 저장 (Ctrl+S)")
        self.save_project_btn.clicked.connect(self._on_save_project)

        self.open_project_btn = QPushButton("📂 열기")
        self.open_project_btn.setObjectName("ToolButton")
        self.open_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_project_btn.setToolTip("프로젝트 열기 (Ctrl+O)")
        self.open_project_btn.clicked.connect(self._on_open_project)

        toolbar.addWidget(self.new_project_btn)
        toolbar.addWidget(self.open_project_btn)
        toolbar.addWidget(self.save_project_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.reset_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addWidget(self.zoom_fit_btn)
        toolbar.addSpacing(10)

        # Audio Scopes toggle button
        self.audio_scopes_btn = QPushButton("Scopes")
        self.audio_scopes_btn.setObjectName("ToolButton")
        self.audio_scopes_btn.setCheckable(True)
        self.audio_scopes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_scopes_btn.setToolTip("Toggle Audio Scopes panel (Goniometer + LUFS)")
        self.audio_scopes_btn.toggled.connect(self._on_audio_scopes_toggled)
        toolbar.addWidget(self.audio_scopes_btn)
        toolbar.addSpacing(10)

        # Proxy toggle button — checkable; enables proxy playback for
        # high-resolution sources so editing stays smooth.
        self.proxy_btn = QPushButton("Proxy")
        self.proxy_btn.setObjectName("ToolButton")
        self.proxy_btn.setCheckable(True)
        self.proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.proxy_btn.setToolTip(
            "프록시 모드 켜기/끄기 — 고해상도 편집 성능 향상\n"
            "(프록시가 없으면 자동 생성 안내가 표시됩니다)"
        )
        self.proxy_btn.toggled.connect(self._toggle_proxy_mode)
        toolbar.addWidget(self.proxy_btn)
        toolbar.addSpacing(4)

        toolbar.addWidget(self.resolution_btn)
        toolbar.addWidget(self.fps_btn)
        toolbar.addWidget(self.format_btn)
        toolbar.addWidget(self.quality_btn)
        toolbar.addWidget(self.export_btn)

        # Batch export button — opens the batch-export queue dialog for
        # all timeline marker segments.
        self.batch_export_btn = QPushButton("일괄 내보내기")
        self.batch_export_btn.setObjectName("ToolButton")
        self.batch_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_export_btn.setToolTip(
            "타임라인 마커 구간을 일괄 내보내기합니다"
        )
        self.batch_export_btn.clicked.connect(self._on_batch_export)
        toolbar.addWidget(self.batch_export_btn)

        root.addLayout(toolbar)

        # --- Preview section ---
        # Custom header: section label on the left, pop-out icon on the
        # right. The container itself carries the accent bar + bg so the
        # row renders as one cohesive strip.
        preview_header = QWidget()
        preview_header.setObjectName("PreviewSectionHeader")
        pheader_layout = QHBoxLayout(preview_header)
        pheader_layout.setContentsMargins(0, 0, 8, 0)
        pheader_layout.setSpacing(0)
        self._preview_section_label = QLabel(tr("veditor.section.preview").upper())
        self._preview_section_label.setObjectName("PreviewSectionTitle")
        pheader_layout.addWidget(self._preview_section_label, stretch=1)
        pheader_layout.addWidget(self.popout_btn)
        root.addWidget(preview_header)
        preview_host = QWidget()
        preview_host.setObjectName("PreviewHost")
        preview_host.setFixedHeight(280)
        preview_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        host_layout = QVBoxLayout(preview_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.setText(tr("veditor.no_file"))
        self._preview_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_label.setToolTip(tr("paint.hint"))
        self._preview_label.installEventFilter(self)
        self._preview_pixmap: QPixmap | None = None
        host_layout.addWidget(self._preview_label)

        # GPU preview surface — sits on top of the QLabel as a sibling
        # child of the host. Receives raw RGB + ColorGrade and applies
        # grading in a fragment shader. The QLabel underneath remains
        # the source of truth for video-rect geometry and PaintDialog /
        # popout (which keep using ``_preview_pixmap``).
        from app.opengl_preview import OpenGLPreviewWidget
        self._preview_gl = OpenGLPreviewWidget(preview_host)
        self._preview_gl.installEventFilter(self)
        self._preview_gl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_gl.hide()  # shown once the first frame lands
        # Track latest frame size for video-rect math when no QLabel
        # pixmap is available (during the brief moment between drop and
        # first frame).
        self._preview_gl_frame_size: tuple[int, int] = (0, 0)

        # Drawing canvas — transparent overlay above the preview, below subtitles.
        # Stays in "off" tool mode so mouse events pass through to preview_label.
        self._drawing_canvas = DrawingCanvas(
            get_time_ms=lambda: self._player.position(),
            get_strokes=lambda: self._strokes,
            parent=preview_host,
        )

        # Subtitle overlay (child of preview host, positioned at bottom)
        self._subtitle_overlay = QLabel(preview_host)
        self._subtitle_overlay.setStyleSheet(
            "QLabel { color: white; "
            "background-color: rgba(0, 0, 0, 180); "
            "padding: 6px 14px; "
            "border-radius: 4px; "
            "font-size: 18px; "
            "font-weight: 600; }"
        )
        self._subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_overlay.setWordWrap(True)
        self._subtitle_overlay.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._subtitle_overlay.hide()
        self._preview_host = preview_host

        root.addWidget(preview_host, stretch=0)

        # --- Paint hint ---
        self._paint_hint_label = QLabel(tr("paint.hint"))
        self._paint_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._paint_hint_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; padding: 4px;"
        )
        root.addWidget(self._paint_hint_label)

        # --- Play bar ---
        play_bar = QWidget()
        play_bar.setObjectName("PlayBar")
        transport = QHBoxLayout(play_bar)
        transport.setContentsMargins(14, 10, 14, 10)
        transport.setSpacing(10)
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setFixedSize(38, 38)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_play)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("TimeLabel")

        self.current_speed_label = QLabel(
            tr("veditor.current_speed", speed="1.0")
        )
        self.current_speed_label.setObjectName("SpeedLabel")

        # Mark In / Mark Out / Clear selection — prosumer-editor style
        # range selection tied to the playhead. Tracks can still be
        # shift+dragged directly, but the buttons + I/O shortcuts are
        # the primary path now.
        self.mark_in_btn = QPushButton(tr("veditor.btn.mark_in"))
        self.mark_in_btn.setObjectName("ToolButton")
        self.mark_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_in_btn.setToolTip(tr("veditor.mark_in.tooltip"))
        self.mark_in_btn.clicked.connect(self._mark_in_at_playhead)

        self.mark_out_btn = QPushButton(tr("veditor.btn.mark_out"))
        self.mark_out_btn.setObjectName("ToolButton")
        self.mark_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_out_btn.setToolTip(tr("veditor.mark_out.tooltip"))
        self.mark_out_btn.clicked.connect(self._mark_out_at_playhead)

        self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_sel_short"))
        self.clear_sel_btn.setObjectName("ToolButton")
        self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_sel_btn.setToolTip(tr("veditor.clear_sel.tooltip"))
        self.clear_sel_btn.clicked.connect(self._clear_active_selection)

        self.add_marker_btn = QPushButton("♦ M")
        self.add_marker_btn.setObjectName("ToolButton")
        self.add_marker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_marker_btn.setToolTip("플레이헤드 위치에 타임라인 마커 추가 (M)")
        self.add_marker_btn.clicked.connect(self._add_marker_at_playhead)

        transport.addWidget(self.play_btn)
        transport.addWidget(self.time_label)
        transport.addSpacing(12)
        transport.addWidget(self.mark_in_btn)
        transport.addWidget(self.mark_out_btn)
        transport.addWidget(self.clear_sel_btn)
        transport.addSpacing(8)
        transport.addWidget(self.add_marker_btn)
        transport.addStretch(1)
        # Phase 7: mini Sony PVW-2800-style jog/shuttle. Inner ring
        # scrubs frame-by-frame; outer ring sets play rate. Sits in
        # the play bar between the speed label and the right edge so
        # it's discoverable without dominating the layout.
        from app.jog_shuttle import JogShuttleWidget
        self._jog_shuttle = JogShuttleWidget(size=64)
        self._jog_shuttle.setToolTip(tr("veditor.jog_shuttle.tooltip"))
        self._jog_shuttle.jog_delta.connect(self._on_jog_delta)
        self._jog_shuttle.shuttle_speed_changed.connect(
            self._on_shuttle_speed_changed,
        )
        transport.addWidget(self._jog_shuttle)
        transport.addWidget(self.current_speed_label)
        root.addWidget(play_bar)

        # --- Keyboard shortcuts for selection ---
        from PySide6.QtGui import QKeySequence, QShortcut
        self._sc_mark_in = QShortcut(QKeySequence("I"), self)
        self._sc_mark_in.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_mark_in.activated.connect(self._mark_in_at_playhead)
        self._sc_mark_out = QShortcut(QKeySequence("O"), self)
        self._sc_mark_out.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_mark_out.activated.connect(self._mark_out_at_playhead)
        self._sc_clear_sel = QShortcut(QKeySequence("X"), self)
        self._sc_clear_sel.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_clear_sel.activated.connect(self._clear_active_selection)
        # M: add a timeline marker at the current playhead position.
        self._sc_add_marker = QShortcut(QKeySequence("M"), self)
        self._sc_add_marker.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_add_marker.activated.connect(self._add_marker_at_playhead)
        # Undo / redo — 10 levels (see app/history.py).
        self._sc_undo = QShortcut(QKeySequence.StandardKey.Undo, self)
        self._sc_undo.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_undo.activated.connect(self._on_undo)
        self._sc_redo = QShortcut(QKeySequence.StandardKey.Redo, self)
        self._sc_redo.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_redo.activated.connect(self._on_redo)
        # Ctrl+Y is the historical Windows redo binding; bind it
        # alongside the StandardKey.Redo (Ctrl+Shift+Z) for parity.
        self._sc_redo_y = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._sc_redo_y.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_redo_y.activated.connect(self._on_redo)
        # Project Save / Load shortcuts
        self._sc_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self._sc_new.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_new.activated.connect(self._on_new_project)
        self._sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self._sc_save.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_save.activated.connect(self._on_save_project)
        self._sc_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self._sc_open.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_open.activated.connect(self._on_open_project)
        # Option C — industry-standard editing shortcuts.
        # B / C: Blade at playhead (DaVinci / Premiere convention).
        self._sc_blade_b = QShortcut(QKeySequence("B"), self)
        self._sc_blade_b.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_blade_b.activated.connect(self._blade_at_playhead)
        self._sc_blade_c = QShortcut(QKeySequence("C"), self)
        self._sc_blade_c.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_blade_c.activated.connect(self._blade_at_playhead)
        # Ctrl+K (Premiere "Add Edit") + Ctrl+\ (DaVinci "Split").
        self._sc_blade_ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self._sc_blade_ctrl_k.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_blade_ctrl_k.activated.connect(self._blade_at_playhead)
        self._sc_blade_ctrl_bs = QShortcut(QKeySequence("Ctrl+\\"), self)
        self._sc_blade_ctrl_bs.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_blade_ctrl_bs.activated.connect(self._blade_at_playhead)
        # Delete = ripple-delete the selected clip(s). Backspace too
        # so trackpad-only users on Mac-style keyboards can reach it.
        self._sc_clip_delete = QShortcut(QKeySequence("Delete"), self)
        self._sc_clip_delete.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_clip_delete.activated.connect(self._ripple_delete_selected)
        self._sc_clip_backspace = QShortcut(QKeySequence("Backspace"), self)
        self._sc_clip_backspace.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_clip_backspace.activated.connect(self._ripple_delete_selected)

        # --- Timeline section ---
        root.addWidget(
            self._make_section_header(tr("veditor.section.timeline"), "timeline")
        )

        # --- Track-management bar (sits right above the track view) ---
        track_bar = QHBoxLayout()
        track_bar.setContentsMargins(0, 0, 0, 0)
        track_bar.setSpacing(6)
        track_bar.addWidget(self.add_track_btn)
        track_bar.addWidget(self.add_audio_btn)
        track_bar.addWidget(self.del_track_btn)
        track_bar.addSpacing(20)
        # Edit-tools group — sits next to the track-management buttons
        # because Blade operates on the tracks below it. Industry NLEs
        # (DaVinci/Premiere/FCP) all place editing tools directly above
        # the timeline for the same spatial-association reason.
        track_bar.addWidget(self.blade_btn)
        track_bar.addSpacing(20)
        # Track effects — Fade / Typography / Zoom / Speed are
        # time-anchored timeline actors (they live on the track at a
        # specific ms range), so their drag sources sit directly
        # above the tracks. Distinct from the Color page node graph,
        # which handles pixel-level transformations across the whole
        # clip. Effects Library left-dock section was removed once
        # this layout landed — too much UI for four cards.
        self.fade_card = self._build_fade_card()
        self.typo_card = TypographyCard()
        self.zoom_card = ZoomCard()
        self.speed_card = SpeedCard()
        for card in (self.fade_card, self.typo_card, self.zoom_card, self.speed_card):
            card.setMinimumWidth(0)
            track_bar.addWidget(card)
        track_bar.addStretch(1)
        # Scopes toggle — right side of timeline toolbar
        self.audio_scopes_tl_btn = QPushButton("🎛 Scopes")
        self.audio_scopes_tl_btn.setObjectName("ToolButton")
        self.audio_scopes_tl_btn.setCheckable(True)
        self.audio_scopes_tl_btn.setChecked(False)
        self.audio_scopes_tl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_scopes_tl_btn.setToolTip("고니오미터 + LUFS 패널 토글")
        self.audio_scopes_tl_btn.toggled.connect(
            lambda checked: self._on_audio_scopes_toggled(checked)
        )
        track_bar.addWidget(self.audio_scopes_tl_btn)
        # Mixer toggle — right side of timeline toolbar
        self.audio_mixer_tl_btn = QPushButton("🎚 Mixer")
        self.audio_mixer_tl_btn.setObjectName("ToolButton")
        self.audio_mixer_tl_btn.setCheckable(True)
        self.audio_mixer_tl_btn.setChecked(False)
        self.audio_mixer_tl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_mixer_tl_btn.setToolTip("오디오 믹서 패널 토글")
        self.audio_mixer_tl_btn.toggled.connect(
            lambda checked: self._on_audio_mixer_toggled(checked)
        )
        track_bar.addWidget(self.audio_mixer_tl_btn)
        root.addLayout(track_bar)

        # --- Tracks container (scrollable vertically). Continuous 45deg
        # stripe background so every gap / empty area reads as "timeline". ---
        self._tracks_host = StripedHost()
        self._tracks_layout = QVBoxLayout(self._tracks_host)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(0)  # rows handle their own dividers
        self._tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Shared project-time ruler at the top of the scroll viewport so it
        # scrolls horizontally with the tracks.
        self._timeline_ruler = TimelineRuler()
        self._timeline_ruler.scrub_requested.connect(self._player.set_position)
        self._timeline_ruler.marker_delete_requested.connect(self._delete_timeline_marker)
        self._tracks_layout.addWidget(self._timeline_ruler)

        self._tracks_layout.addStretch(1)

        self._tracks_scroll = QScrollArea()
        self._tracks_scroll.setWidgetResizable(True)
        self._tracks_scroll.setWidget(self._tracks_host)
        self._tracks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._tracks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setMinimumHeight(230)
        # Keep the scroll viewport transparent so StripedHost's pattern fills
        # the entire visible area (especially below the last track).
        self._tracks_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        # Mouse wheel over the timeline zooms its horizontal length.
        self._tracks_scroll.viewport().installEventFilter(self)

        # Wrap the timeline in a section host so we can detach the
        # whole thing (header + scroll) into a floating popout window
        # — same pattern as the colour grading section. The header sits
        # above the scroll with a ⛶ icon on the right.
        self._timeline_section_host = QWidget()
        ts_layout = QVBoxLayout(self._timeline_section_host)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(0)
        timeline_header = QWidget()
        timeline_header.setObjectName("TimelineSectionHeader")
        th_layout = QHBoxLayout(timeline_header)
        th_layout.setContentsMargins(0, 0, 8, 0)
        th_layout.setSpacing(0)
        th_layout.addWidget(
            self._make_section_header(
                tr("veditor.section.timeline"), "timeline",
            ),
            stretch=1,
        )
        self.timeline_popout_btn = QPushButton("⛶")
        self.timeline_popout_btn.setObjectName("PreviewPopoutIcon")
        self.timeline_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeline_popout_btn.setToolTip(
            tr("veditor.timeline_popout.tooltip"),
        )
        self.timeline_popout_btn.setFixedSize(28, 24)
        self.timeline_popout_btn.clicked.connect(self._toggle_timeline_popout)
        th_layout.addWidget(self.timeline_popout_btn)
        ts_layout.addWidget(timeline_header)
        ts_layout.addWidget(self._tracks_scroll, stretch=1)

        # --- Audio Mixer panel (includes built-in scopes column on the right) ---
        self._audio_mixer_panel = AudioMixerPanel()
        self._audio_mixer_panel.setVisible(False)
        self._audio_mixer_panel.set_volume_callback(self._on_mixer_fader_changed)
        self._audio_mixer_panel.set_pan_callback(self._on_mixer_pan_changed)
        self._active_audio_track_id: int | None = None
        ts_layout.addWidget(self._audio_mixer_panel)

        root.addWidget(self._timeline_section_host, stretch=1)
        # Track where in the main column the timeline lives so the
        # popout can leave a placeholder and put it back later.
        self._timeline_root_layout = root
        self._timeline_root_index = root.count() - 1
        self._timeline_popout: "TimelinePopoutWindow | None" = None
        self._timeline_placeholder: QLabel | None = None

        # --- Selection / clear-selection row (controls bar) ---
        # Speed-rate buttons used to live here too, but the SpeedCard
        # (drag-drop) and right-click context menu cover the same
        # workflow with less clutter, so the buttons were removed.
        # ``_speed_buttons`` stays as an empty list so the existing
        # selection-state update loop is a no-op rather than a bug.
        controls_bar = QWidget()
        controls_bar.setObjectName("ControlsBar")
        sel_row = QHBoxLayout(controls_bar)
        sel_row.setContentsMargins(12, 10, 12, 10)
        sel_row.setSpacing(6)
        self.selection_label = QLabel(tr("veditor.no_selection"))
        self.selection_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;"
        )
        sel_row.addWidget(self.selection_label)
        sel_row.addStretch(1)

        self._speed_buttons: list[QPushButton] = []

        self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_selection"))
        self.clear_sel_btn.setObjectName("ToolButton")
        self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_sel_btn.setEnabled(False)
        self.clear_sel_btn.clicked.connect(self._clear_selection_active_track)
        sel_row.addWidget(self.clear_sel_btn)

        sel_row.addSpacing(16)

        # ---- Page switcher: Edit | Color ----
        _ps_qss = (
            "QPushButton { background: #28283a; color: #9898b8; "
            "border: 1px solid #2a2a42; border-radius: 4px; "
            "padding: 4px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #32324a; color: #c8c8e8; }"
            "QPushButton:checked { background: #5050a0; color: #ffffff; "
            "border-color: #7070c0; }"
        )
        self._page_edit_btn = QPushButton("✂ 편집")
        self._page_edit_btn.setCheckable(True)
        self._page_edit_btn.setChecked(True)
        self._page_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._page_edit_btn.setStyleSheet(_ps_qss)
        self._page_edit_btn.clicked.connect(lambda: self._switch_page("edit"))
        sel_row.addWidget(self._page_edit_btn)

        self._page_color_btn = QPushButton("🎨 색보정")
        self._page_color_btn.setCheckable(True)
        self._page_color_btn.setChecked(False)
        self._page_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._page_color_btn.setStyleSheet(_ps_qss)
        self._page_color_btn.clicked.connect(lambda: self._switch_page("color"))
        sel_row.addWidget(self._page_color_btn)

        self._color_page_window: "ColorPageWindow | None" = None

        root.addWidget(controls_bar)

        # --- Color grading section (panel + scopes, popout-capable) ---
        # Custom header with a ⛶ pop-out button on the right, so the
        # user can detach the whole color surface into a floating
        # window (DaVinci-style docking, single-window app version).
        self._color_header_widget = QWidget()
        self._color_header_widget.setObjectName("ColorSectionHeader")
        chh = QHBoxLayout(self._color_header_widget)
        chh.setContentsMargins(0, 0, 8, 0)
        chh.setSpacing(0)
        chh.addWidget(
            self._make_section_header(tr("veditor.section.color"), "color"),
            stretch=1,
        )
        self.color_popout_btn = QPushButton("⛶")
        self.color_popout_btn.setObjectName("PreviewPopoutIcon")
        self.color_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_popout_btn.setToolTip(tr("veditor.color_popout.tooltip"))
        self.color_popout_btn.setFixedSize(28, 24)
        self.color_popout_btn.clicked.connect(self._toggle_color_popout)
        chh.addWidget(self.color_popout_btn)
        # (Color section moved above timeline — see addWidget calls near _timeline_section_host)
        # Mask toolbar — DaVinci-style. The four primary mask
        # actions are surfaced as big always-visible buttons (when
        # the dock is open) so users don't have to right-click a
        # small node thumbnail. All actions act on the currently
        # selected NodeItem (``self._node_grade_target``) and
        # delegate to ``_on_node_mask_request`` so the same code
        # path handles toolbar + context-menu invocations.
        from PySide6.QtWidgets import QToolButton as _QToolButton
        self._mask_toolbar_widget = QWidget()
        mt_layout = QHBoxLayout(self._mask_toolbar_widget)
        mt_layout.setContentsMargins(8, 4, 8, 4)
        mt_layout.setSpacing(6)
        self._mask_btn_window = QPushButton(tr("nodemask.toolbar.window"))
        self._mask_btn_window.setObjectName("ToolButton")
        self._mask_btn_window.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_btn_window.clicked.connect(
            lambda: self._mask_toolbar_action("power_window"),
        )
        self._mask_btn_qualifier = QPushButton(tr("nodemask.toolbar.qualifier"))
        self._mask_btn_qualifier.setObjectName("ToolButton")
        self._mask_btn_qualifier.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_btn_qualifier.clicked.connect(
            lambda: self._mask_toolbar_action("hsl"),
        )
        # 👤 Person — single-click selfie / background segmentation.
        # Removed the niche lips/eyes/face presets that aren't
        # standard in DaVinci/Premiere/AE — keeping the toolbar
        # focused on the 80% workflow. Power Window + Rotoscope
        # cover everything else.
        self._mask_btn_person = QPushButton(tr("nodemask.toolbar.person"))
        self._mask_btn_person.setObjectName("ToolButton")
        self._mask_btn_person.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_btn_person.clicked.connect(
            lambda: self._mask_toolbar_action("magic:person"),
        )

        # 🔪 Rotoscope — GrabCut / SAM / manual polygon entry
        # points. All routes through ``_mask_toolbar_action`` and
        # ends in a node mask attachment.
        self._mask_btn_roto = _QToolButton()
        self._mask_btn_roto.setText(tr("nodemask.toolbar.rotoscope") + " ▾")
        self._mask_btn_roto.setObjectName("ToolButton")
        self._mask_btn_roto.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_btn_roto.setPopupMode(
            _QToolButton.ToolButtonPopupMode.InstantPopup,
        )
        self._mask_btn_roto.setStyleSheet(
            "QToolButton { padding: 4px 12px; font-weight: 600; "
            "background-color: #2e2e2e; color: #ffffff; "
            "border: 1px solid #3a3a3a; border-radius: 4px; }"
            "QToolButton:hover { background-color: #383838; }"
            "QToolButton::menu-indicator { image: none; }"
        )
        roto_menu = QMenu(self)
        roto_menu.addAction(
            tr("nodemask.menu.roto_grabcut"),
            lambda: self._mask_toolbar_action("roto:grabcut"),
        )
        roto_menu.addAction(
            tr("nodemask.menu.roto_sam"),
            lambda: self._mask_toolbar_action("roto:sam"),
        )
        roto_menu.addAction(
            tr("nodemask.menu.roto_manual"),
            lambda: self._mask_toolbar_action("power_window"),
        )
        self._mask_btn_roto.setMenu(roto_menu)

        self._mask_btn_clear = QPushButton(tr("nodemask.toolbar.clear"))
        self._mask_btn_clear.setObjectName("ToolButton")
        self._mask_btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mask_btn_clear.clicked.connect(
            lambda: self._mask_toolbar_action("clear"),
        )
        for b in (
            self._mask_btn_window, self._mask_btn_qualifier,
            self._mask_btn_person, self._mask_btn_roto, self._mask_btn_clear,
        ):
            b.setToolTip(tr("nodemask.toolbar.tip"))
            mt_layout.addWidget(b)
        mt_layout.addStretch(1)
        self._mask_toolbar_widget.hide()  # follows _color_header_widget visibility
        # (mask toolbar added above timeline — see earlier addWidget near _timeline_section_host)

        # The host widget is the single canonical container for the
        # color panel + scopes. We move (reparent) it between the
        # editor's root layout and the popout window — same widget
        # tree, no state duplication.
        # The colour grading panel embeds the scopes panel internally
        # (as a sibling column to the wheels) so the histogram and the
        # wheels naturally align on the same row. The host widget is
        # the canonical container we reparent between the editor and
        # the popout window — same widget tree, no state duplication.
        self._color_row_host = QWidget()
        color_row = QHBoxLayout(self._color_row_host)
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(0)
        # Wrap the colour panel in a QScrollArea so a short editor
        # window can scroll instead of crushing the fixed-size knobs /
        # wheels into each other. The popout window reparents the
        # whole ``_color_row_host`` (scroll area included) so the
        # scroll bar follows the panel into the floating window — and
        # disappears there because the popout is tall enough to fit
        # everything natively.
        _color_scroll = QScrollArea()
        _color_scroll.setWidget(self._build_color_grading_panel())
        _color_scroll.setWidgetResizable(True)
        _color_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        _color_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        _color_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        # Floor on the visible scroll area itself — guarantees the user
        # always sees at least a wheel row of content even when the
        # main column is squeezed to its minimum.
        _color_scroll.setMinimumHeight(420)
        _color_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        color_row.addWidget(_color_scroll, 1)
        # The row host should never collapse below the scroll area
        # either — same defensive pattern.
        self._color_row_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum,
        )
        # (color_row_host added above timeline — see earlier addWidget near _timeline_section_host)
        # Remember where to put the host back after a popout closes.
        self._color_root_layout = root
        self._color_root_index = 2  # index in root: after preview, before timeline
        self._color_popout: "ColorPopoutWindow | None" = None
        # Placeholder shown in-place while the host is in the popout.
        self._color_placeholder: QLabel | None = None
        # Unreal-style click-to-reveal: the color dock is hidden by
        # default and only appears when a Color-grading node is
        # selected in the workbench NodeGraph. Saves vertical space
        # for the timeline during plain capture / trim sessions while
        # keeping the wheels at full horizontal size when actually
        # grading. ``_update_color_dock_visibility()`` flips both the
        # header strip and the row host based on
        # ``self._node_grade_target``.
        self._color_header_widget.hide()
        self._color_row_host.hide()

        # Move color section ABOVE the timeline using a QSplitter so the user
        # can drag the divider to give the color wheels more vertical space.
        # The splitter replaces the plain stretch-based layout that was causing
        # the wheels to be vertically clipped when window height was limited.
        _color_container = QWidget()
        _cc_layout = QVBoxLayout(_color_container)
        _cc_layout.setContentsMargins(0, 0, 0, 0)
        _cc_layout.setSpacing(0)
        _cc_layout.addWidget(self._color_header_widget)
        _cc_layout.addWidget(self._mask_toolbar_widget)
        _cc_layout.addWidget(self._color_row_host, 1)
        self._color_container = _color_container
        self._color_container.hide()  # hidden until a Color node is selected

        color_timeline_splitter = QSplitter(Qt.Orientation.Vertical)
        color_timeline_splitter.setChildrenCollapsible(False)
        color_timeline_splitter.setHandleWidth(4)
        color_timeline_splitter.addWidget(_color_container)
        color_timeline_splitter.addWidget(self._timeline_section_host)
        # Default split: color panel gets 480px, timeline gets 240px.
        # Qt will honour these proportionally on first show.
        color_timeline_splitter.setSizes([480, 240])
        color_timeline_splitter.setStretchFactor(0, 1)
        color_timeline_splitter.setStretchFactor(1, 1)
        self._color_timeline_splitter = color_timeline_splitter

        # Remove the bare _timeline_section_host from root and replace with
        # the splitter at the same position.
        _tl_idx = self._timeline_root_layout.indexOf(self._timeline_section_host)
        self._timeline_root_layout.removeWidget(self._timeline_section_host)
        self._timeline_root_layout.insertWidget(_tl_idx, color_timeline_splitter, 1)

        # Point popout plumbing at the color_container's layout so
        # reparenting in _toggle_color_popout / _on_color_popout_closed works.
        self._color_root_layout = _cc_layout
        self._color_root_index = 2  # after header + mask toolbar

        # --- Media Pool section — DaVinci-style. OS file drops go
        # here and pool items can be dragged onto a track row to
        # create a clip without going through the right-click menu.
        # Lives in the LEFT dock column so the preview / timeline
        # stays the visual centre of the editor. Sits ABOVE the
        # Effects Library so a clip → effects card workflow scans
        # top → bottom.
        self._media_pool_section_host = QWidget()
        mph = QVBoxLayout(self._media_pool_section_host)
        mph.setContentsMargins(0, 0, 0, 0)
        mph.setSpacing(6)
        mph.addWidget(
            self._make_section_header(tr("veditor.section.media_pool"), "media_pool")
        )
        self._media_pool = MediaPool()
        self._media_pool.popout_requested.connect(self._toggle_media_pool_popout)
        mph.addWidget(self._media_pool)
        self._left_dock_layout.addWidget(
            self._media_pool_section_host, stretch=1,
        )

        # --- Effects Library section — TigerCapture's drag-source
        # effect cards (Fade / Typography / Zoom / Speed). Cards were
        # built earlier in ``_build_ui``; here we just place them in a
        # Effects Library left-dock section removed: the four cards
        # (Fade / Typography / Zoom / Speed) now live in the track
        # bar directly above the timeline. Stubs below keep external
        # references valid (popout helpers, retranslate, etc).
        self._effects_library_section_host = None
        self._effects_popout_btn = None

        # --- Title Presets section — drag-to-timeline typography presets.
        self._title_presets_section_host = QWidget()
        tpsh = QVBoxLayout(self._title_presets_section_host)
        tpsh.setContentsMargins(0, 0, 0, 0)
        tpsh.setSpacing(6)
        tpsh.addWidget(
            self._make_section_header("타이틀 프리셋", "timeline")
        )
        self._title_presets_panel = TitlePresetsPanel()
        tpsh.addWidget(self._title_presets_panel)
        self._left_dock_layout.addWidget(self._title_presets_section_host)

        # --- Transitions section — DaVinci-style clip-boundary transitions.
        # Each card can be dragged to a clip's right edge to set
        # clip.transition_out_type / clip.transition_out_ms.
        self._transitions_section_host = QWidget()
        tsh = QVBoxLayout(self._transitions_section_host)
        tsh.setContentsMargins(0, 0, 0, 0)
        tsh.setSpacing(6)
        tsh.addWidget(
            self._make_section_header("트랜지션", "timeline")
        )
        self._transitions_panel = TransitionsPanel()
        tsh.addWidget(self._transitions_panel)
        self._left_dock_layout.addWidget(self._transitions_section_host)

        # Pad the rest of the left column so sections hug the top.
        self._left_dock_layout.addStretch(1)
        self._media_pool_root_layout = self._left_dock_layout
        self._media_pool_root_index = self._left_dock_layout.indexOf(
            self._media_pool_section_host,
        )
        self._media_pool_popout: "MediaPoolPopoutWindow | None" = None
        # Effects Library popout state — kept as None since the section
        # itself is gone. _toggle_effects_library_popout is now a
        # no-op for any code paths still calling it.
        self._effects_library_root_layout = None
        self._effects_library_root_index = -1
        self._effects_library_popout = None
        self._effects_library_placeholder = None
        self._media_pool_placeholder: QLabel | None = None

        # --- Inspector section — DaVinci-style contextual properties
        # for the currently selected track / clip. Read-only Phase B1;
        # editable knobs (transform, opacity, per-clip speed) come in
        # Phase B2 once VideoTrack supports multi-clip splits.
        self._workbench_section_host = QWidget()
        ish = QVBoxLayout(self._workbench_section_host)
        ish.setContentsMargins(0, 0, 0, 0)
        ish.setSpacing(6)
        ish.addWidget(
            self._make_section_header(tr("veditor.section.workbench"), "workbench")
        )
        self._workbench_panel = WorkbenchPanel()
        self._workbench_panel.fade_in_changed.connect(
            self._on_workbench_fade_in_changed,
        )
        self._workbench_panel.fade_out_changed.connect(
            self._on_workbench_fade_out_changed,
        )
        self._workbench_panel.volume_changed.connect(
            self._on_workbench_volume_changed,
        )
        # History savepoints — fire on slider release so a drag of
        # the fade-in slider produces one undo entry, not 50.
        self._workbench_panel.fade_in_committed.connect(
            lambda _v: self._register_change("workbench fade-in"),
        )
        self._workbench_panel.fade_out_committed.connect(
            lambda _v: self._register_change("workbench fade-out"),
        )
        self._workbench_panel.volume_committed.connect(
            lambda _v: self._register_change("workbench volume"),
        )
        # NodeGraph row click → focus the matching panel. Today only
        # the Color node is wired; future LUT/Blur nodes will land
        # here as separate kinds and route to their own panels.
        self._workbench_panel.node_focused.connect(self._on_workbench_node_focused)
        # DaVinci routing — when the user picks a node in the graph,
        # bind the Color panel sliders to that node's grade.
        ngw = self._workbench_panel.expose_node_graph_widget()
        if ngw is not None:
            ngw.selected_node_changed.connect(self._on_node_graph_selection)
            # Rebuild the active track's chain whenever the graph
            # topology changes (node added/deleted/connected). Slider
            # edits don't fire graph_mutated — they mutate the
            # ColorGrade in place, so the cached chain references
            # stay valid.
            ngw.scene.graph_mutated.connect(self._rebuild_active_chain)
            # Phase E — node mask add / edit / clear requests from
            # the right-click submenu. The editor handler attaches
            # the mask, opens any needed dialog, and refreshes the
            # preview.
            ngw.mask_request.connect(self._on_node_mask_request)
        ish.addWidget(self._workbench_panel)
        self._right_dock_layout.addWidget(self._workbench_section_host)

        # --- PIP section — Picture-in-Picture controls for the active track.
        # Shown / hidden dynamically by ``_refresh_pip_panel`` depending on
        # whether the active track is a non-bottom track (track index > 0).
        self._pip_section_host = QWidget()
        pip_sh = QVBoxLayout(self._pip_section_host)
        pip_sh.setContentsMargins(0, 0, 0, 0)
        pip_sh.setSpacing(4)
        pip_sh.addWidget(
            self._make_section_header(tr("PIP"), "pip"),
        )
        pip_body = QWidget()
        pip_body.setObjectName("PIPPanel")
        pip_body_layout = QVBoxLayout(pip_body)
        pip_body_layout.setContentsMargins(8, 4, 8, 4)
        pip_body_layout.setSpacing(6)

        # Enable PIP toggle
        self._pip_enable_btn = QPushButton(tr("Enable PIP"))
        self._pip_enable_btn.setCheckable(True)
        self._pip_enable_btn.setObjectName("ToolButton")
        self._pip_enable_btn.toggled.connect(self._on_pip_enable_toggled)
        pip_body_layout.addWidget(self._pip_enable_btn)

        def _make_pip_row(label_text: str, lo: int, hi: int, step: int):
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setFixedWidth(52)
            lbl.setObjectName("SmallLabel")
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(lo, hi)
            sl.setSingleStep(step)
            sl.setPageStep(step * 5)
            val_lbl = QLabel(f"{lo}")
            val_lbl.setFixedWidth(30)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setObjectName("SmallLabel")
            row_l.addWidget(lbl)
            row_l.addWidget(sl, stretch=1)
            row_l.addWidget(val_lbl)
            return row_w, sl, val_lbl

        _pip_x_row, self._pip_x_slider, self._pip_x_val = _make_pip_row("X pos", -100, 200, 1)
        _pip_y_row, self._pip_y_slider, self._pip_y_val = _make_pip_row("Y pos", -100, 200, 1)
        _pip_s_row, self._pip_scale_slider, self._pip_scale_val = _make_pip_row("Scale", 0, 200, 5)
        _pip_o_row, self._pip_opacity_slider, self._pip_opacity_val = _make_pip_row("Opacity", 0, 100, 5)

        # Default slider positions (50 / 50 / 30 / 100)
        self._pip_x_slider.setValue(50)
        self._pip_y_slider.setValue(50)
        self._pip_scale_slider.setValue(30)
        self._pip_opacity_slider.setValue(100)
        self._pip_x_val.setText("50")
        self._pip_y_val.setText("50")
        self._pip_scale_val.setText("30")
        self._pip_opacity_val.setText("100")

        for _row, _sl, _vl, _attr in [
            (_pip_x_row,    self._pip_x_slider,      self._pip_x_val,      "pip_x"),
            (_pip_y_row,    self._pip_y_slider,      self._pip_y_val,      "pip_y"),
            (_pip_s_row,    self._pip_scale_slider,  self._pip_scale_val,  "pip_scale"),
            (_pip_o_row,    self._pip_opacity_slider, self._pip_opacity_val, "pip_opacity"),
        ]:
            pip_body_layout.addWidget(_row)
            # Capture _sl / _vl / _attr by value via default arg.
            def _on_slider(v: int, sl=_sl, vl=_vl, attr=_attr):
                vl.setText(str(v))
                self._on_pip_slider_changed(attr, v)
            _sl.valueChanged.connect(_on_slider)

        # Keyframe controls
        _kf_btn_row = QWidget()
        _kf_btn_layout = QHBoxLayout(_kf_btn_row)
        _kf_btn_layout.setContentsMargins(0, 0, 0, 0)
        _kf_btn_layout.setSpacing(4)
        self._pip_add_kf_btn = QPushButton("🔑 키프레임 추가")
        self._pip_add_kf_btn.setObjectName("ToolButton")
        self._pip_add_kf_btn.clicked.connect(self._pip_add_keyframe)
        self._pip_del_kf_btn = QPushButton("삭제")
        self._pip_del_kf_btn.setObjectName("ToolButton")
        self._pip_del_kf_btn.clicked.connect(self._pip_delete_keyframe)
        _kf_btn_layout.addWidget(self._pip_add_kf_btn, stretch=1)
        _kf_btn_layout.addWidget(self._pip_del_kf_btn)
        pip_body_layout.addWidget(_kf_btn_row)

        from PySide6.QtWidgets import QListWidget as _QListWidget
        self._pip_kf_list = _QListWidget()
        self._pip_kf_list.setObjectName("SmallList")
        self._pip_kf_list.setMaximumHeight(80)
        self._pip_kf_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pip_body_layout.addWidget(self._pip_kf_list)

        pip_sh.addWidget(pip_body)
        self._pip_section_host.setVisible(False)   # hidden until a non-bottom track is selected
        self._right_dock_layout.addWidget(self._pip_section_host)

        # --- Subtitles section — lives in the right dock column, but
        # can also pop out into its own floating window. The whole
        # section (header + panel) is wrapped in a host widget that
        # gets reparented across pop-out / dock the same way as the
        # colour grading and timeline sections.
        self._subtitle_section_host = QWidget()
        ssh = QVBoxLayout(self._subtitle_section_host)
        ssh.setContentsMargins(0, 0, 0, 0)
        ssh.setSpacing(6)
        # Subtitle section header row: section label + AI 자막 button
        _sub_hdr_row = QWidget()
        _sub_hdr_row.setObjectName("SubtitleHeaderRow")
        _sub_hdr_h = QHBoxLayout(_sub_hdr_row)
        _sub_hdr_h.setContentsMargins(0, 0, 8, 0)
        _sub_hdr_h.setSpacing(0)
        _sub_hdr_h.addWidget(
            self._make_section_header(tr("veditor.section.subtitles"), "subtitles"),
            stretch=1,
        )
        _ai_sub_btn = QPushButton("🎤 AI 자막")
        _ai_sub_btn.setObjectName("ToolButton")
        _ai_sub_btn.setToolTip("Whisper로 자동 자막 생성")
        _ai_sub_btn.clicked.connect(self._generate_ai_subtitles)
        _sub_hdr_h.addWidget(_ai_sub_btn)
        ssh.addWidget(_sub_hdr_row)
        self._subtitle_panel = SubtitlePanel(
            position_provider=lambda: self._player.position()
        )
        self._subtitle_panel.subtitles_changed.connect(self._on_subtitles_changed)
        self._subtitle_panel.popout_requested.connect(
            self._toggle_subtitle_popout,
        )
        # Phase 5 Step A: bind the subtitle layer to the timeline
        # ruler so its marker strip refreshes whenever the user adds /
        # edits / deletes a subtitle.
        self._timeline_ruler.set_subtitle_layer(self._subtitle_panel.layer)

        # Phase 5 Step B: drop a SubtitleLaneRow into the tracks scroll
        # right after the ruler. Sits at the top of the tracks area so
        # it's always visible (DaVinci's titles-on-top convention).
        self._subtitle_lane = SubtitleLaneRow(self._subtitle_panel.layer)
        self._subtitle_lane.set_px_per_sec(self._px_per_sec)
        self._subtitle_lane.request_edit.connect(self._on_subtitle_lane_edit)
        # Insert directly after the ruler (index 1) — the existing
        # stretch / track rows shift down by one.
        ruler_idx = self._tracks_layout.indexOf(self._timeline_ruler)
        self._tracks_layout.insertWidget(ruler_idx + 1, self._subtitle_lane)
        ssh.addWidget(self._subtitle_panel)
        self._right_dock_layout.addWidget(self._subtitle_section_host)
        self._subtitle_root_layout = self._right_dock_layout
        self._subtitle_root_index = self._right_dock_layout.count() - 1
        self._subtitle_popout: "SubtitlePopoutWindow | None" = None
        self._subtitle_placeholder: QLabel | None = None
        # Pad the bottom of the dock so the panel hugs the top.
        self._right_dock_layout.addStretch(1)

    # ------------------- track management --------------------

    def _add_empty_track(self) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = VideoTrack(id=tid)
        self._tracks.append(track)
        self._insert_track_widget(track)
        if self._active_track_id is None:
            self._set_active_track(tid)

    def _add_track_with_source(self, path: Path) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = VideoTrack(id=tid, source_path=path)
        # HDR Phase 1: probe colour metadata so ProjectPlayer's
        # decoder factory can pick ffmpeg+tonemap for HDR sources. The
        # probe is the same one Media Pool runs at import; doing it
        # again here is cheap (~150 ms) and keeps tracks added by
        # other paths (capture finish, drag-from-OS) HDR-aware.
        try:
            from app.hdr_probe import probe_hdr
            track.hdr_info = probe_hdr(path)
        except Exception:
            track.hdr_info = None
        self._tracks.append(track)
        self._insert_track_widget(track)
        self._start_thumbnail_extraction(track)
        self._set_active_track(tid)
        # ``_refresh_player_tracks`` opens the cap and sets duration_ms,
        # then rebuilds clips so the new track has the single covering
        # clip Phase 1.5d wants.
        self._refresh_player_tracks()
        _ensure_video_clips(track)
        # Phase 1.5d Step A regression fix: stored ``clips`` is set
        # AFTER the row was first inserted (which painted with an
        # empty clip list and a 0 duration). Without an explicit
        # repaint here the row stays as the "empty slot" render until
        # thumbnail extraction happens to kick an ``update()`` —
        # which can be seconds away on long sources, leaving the
        # user staring at a blank track. ``update()`` only — calling
        # ``_recalc_width`` here triggered a second layout reflow
        # cycle that left the row collapsed in some scenarios.
        row = self._track_rows.get(tid)
        if row is not None:
            row.update()

        # Proxy: if the source is high-resolution, ask the user once
        # whether to generate a proxy for smoother editing.
        try:
            if _is_high_resolution(path):
                w, h = _probe_video_dimensions(path)
                res_label = f"{w}x{h}" if w and h else "4K"
                choice = QMessageBox.question(
                    self,
                    "프록시 생성",
                    f"고해상도 영상이 감지됐습니다 ({res_label}).\n"
                    f"프록시를 생성하면 편집 성능이 향상됩니다.\n\n"
                    f"프록시는 백그라운드에서 생성되며 완료 후 Proxy 버튼으로 전환할 수 있습니다.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if choice == QMessageBox.StandardButton.Yes:
                    self._start_proxy_generation(path)
        except Exception:
            pass

        # DIAG: surface row geometry so the trackview-not-visible
        # regression report can be reproduced from logs.
        import sys as _sys
        try:
            print(
                f"[DIAG add_track] tid={tid} "
                f"row_visible={row.isVisible() if row else None} "
                f"row_geo={row.geometry() if row else None} "
                f"row_size={row.size() if row else None} "
                f"clips={len(track.clips)} "
                f"duration_ms={track.duration_ms} "
                f"layout_count={self._tracks_layout.count()} "
                f"layout_indexes=[{','.join(str(self._tracks_layout.indexOf(self._tracks_layout.itemAt(i).widget())) for i in range(self._tracks_layout.count()) if self._tracks_layout.itemAt(i).widget())}]",
                file=_sys.stderr, flush=True,
            )
        except Exception as e:
            print(f"[DIAG add_track] err={e!r}", file=_sys.stderr, flush=True)

    def _insert_track_widget(self, track: VideoTrack) -> None:
        row = TrackRow(track)
        row.set_px_per_sec(self._px_per_sec)
        row.clicked.connect(self._set_active_track)
        row.position_requested.connect(self._on_track_position_requested)
        row.selection_changed.connect(self._on_track_selection_changed)
        row.context_menu.connect(self._on_track_context_menu)
        row.clip_context_menu.connect(self._on_video_clip_context_menu)
        row.offset_changed.connect(self._on_track_offset_changed)
        row.drag_committed.connect(
            lambda _tid: self._register_change("clip drag")
        )
        # Option C — clip-level selection signals.
        row.clip_clicked.connect(self._on_clip_clicked)
        row.empty_area_clicked.connect(self._on_track_empty_area_clicked)
        row.fades_changed.connect(self._on_track_fades_changed)
        row.speed_changed.connect(self._on_track_speed_changed)
        row.media_dropped.connect(self._on_media_dropped_on_video_row)
        row.typography_double_clicked.connect(self._open_typography_editor)
        row.typography_context_menu.connect(self._show_typography_menu)
        row.typography_changed.connect(self._on_typography_changed)
        row.typography_actor_selected.connect(self._on_typography_actor_selected)
        row.zoom_double_clicked.connect(self._open_zoom_editor)
        row.zoom_context_menu.connect(self._show_zoom_menu)
        row.zoom_changed.connect(self._on_track_zoom_changed)
        row.clip_drag_delta.connect(self._on_clip_drag_delta)
        # Seed the row with current snap targets so it immediately picks
        # up playhead + marker positions without waiting for the next move.
        row.set_extra_snap_targets(
            [self._player.position()] + [int(m["ms"]) for m in self._timeline_markers]
        )
        self._track_rows[track.id] = row
        # Insert video track BEFORE any audio track rows so video always
        # sits above audio in the timeline (DaVinci / Premiere convention).
        insert_idx = self._tracks_layout.count() - 1  # default: before stretch
        for i in range(self._tracks_layout.count()):
            item = self._tracks_layout.itemAt(i)
            if item and item.widget() and item.widget() in self._audio_rows.values():
                insert_idx = i
                break
        self._tracks_layout.insertWidget(insert_idx, row)
        # Belt-and-suspenders: re-assert the fixed height + visible
        # state AND force a layout activation. Qt's ``insertWidget``
        # queues the geometry update for the next event loop spin —
        # if any code reads ``row.size()`` before that spin lands it
        # sees the default 640×480, which can also leave the row
        # invisible until a downstream paint kicks layout. Calling
        # ``invalidate`` + ``activate`` resolves the geometry
        # synchronously so subsequent reads + paints are correct.
        row.setFixedHeight(
            row.LABEL_H + row.TIMELINE_H + TRACK_V_PADDING,
        )
        row.show()
        self._tracks_layout.invalidate()
        self._tracks_layout.activate()
        self._tracks_host.adjustSize()
        self._update_tracks_host_width()

    # ============== audio tracks (multi-clip model) ==============

    def _next_clip_id(self) -> int:
        cid = getattr(self, "_next_audio_clip_id", 1)
        self._next_audio_clip_id = cid + 1
        return cid

    def _find_audio_track(self, track_id: int) -> AudioTrack | None:
        return next((a for a in self._audio_tracks if a.id == track_id), None)

    def _find_audio_clip(self, track_id: int, clip_id: int) -> tuple[AudioTrack | None, AudioClip | None]:
        track = self._find_audio_track(track_id)
        if track is None:
            return None, None
        return track, next((c for c in track.clips if c.id == clip_id), None)

    def _add_empty_audio_track(self) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = AudioTrack(id=tid)
        self._audio_tracks.append(track)
        self._insert_audio_track_widget(track)

    def _add_audio_track_with_source(self, path: Path) -> None:
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        tid = self._next_track_id
        self._next_track_id += 1
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            trim_end_ms=duration,
        )
        track = AudioTrack(id=tid, clips=[clip])
        self._audio_tracks.append(track)
        self._insert_audio_track_widget(track)
        self._audio_mixer.add_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _populate_audio_track(self, track_id: int, path: Path) -> None:
        """Fill an empty AudioTrack (no clips) with a newly-loaded file."""
        track = self._find_audio_track(track_id)
        if track is None or track.is_loaded:
            return
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            trim_end_ms=duration,
        )
        track.clips.append(clip)
        row = self._audio_rows.get(track_id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _start_waveform_extraction(self, clip: AudioClip) -> None:
        if clip.source_path is None:
            return
        import sys
        from pathlib import Path as _Path
        msg = f"[waveform] start  clip_id={clip.id} path={clip.source_path.name}\n"
        print(msg, end='', file=sys.stderr, flush=True)
        try:
            with open(_Path(__file__).parent.parent / "logs" / "waveform_debug.log", "a", encoding="utf-8") as _f:
                import datetime as _dt
                _f.write(f"{_dt.datetime.now().isoformat()} {msg}")
        except Exception:
            pass
        # Use a small sequential job counter as the extractor key —
        # avoids id() overflow and clip.id collisions across sessions.
        if not hasattr(self, "_waveform_job_seq"):
            self._waveform_job_seq: int = 1
        if not hasattr(self, "_waveform_clip_map"):
            self._waveform_clip_map: dict[int, "AudioClip"] = {}
        # Cancel any existing job for the same clip object.
        old_jid = next((jid for jid, c in self._waveform_clip_map.items() if c is clip), None)
        if old_jid is not None:
            prev = self._waveform_extractors.pop(old_jid, None)
            self._waveform_clip_map.pop(old_jid, None)
            if prev is not None:
                try:
                    prev.ready.disconnect()
                    prev.failed.disconnect()
                except Exception:
                    pass
        jid = self._waveform_job_seq
        self._waveform_job_seq += 1
        self._waveform_clip_map[jid] = clip
        ex = WaveformExtractor(jid, clip.source_path)
        ex.ready.connect(self._on_waveform_ready)
        ex.failed.connect(self._on_waveform_failed)
        ex.finished.connect(ex.deleteLater)
        self._waveform_extractors[jid] = ex
        ex.start()
        # Start spectrum extraction after waveform (500ms delay to avoid contention).
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(600, lambda _c=clip: self._start_spectrum_extraction(_c))

    def _start_spectrum_extraction(self, clip: AudioClip) -> None:
        if clip.source_path is None:
            return
        if not hasattr(self, "_spectrum_map"):
            self._spectrum_map: dict = {}   # sp_ex -> clip (keeps sp_ex alive)
        sp_ex = SpectrumExtractor(clip.source_path)
        # Store sp_ex as key to prevent GC while thread is running.
        self._spectrum_map[sp_ex] = clip
        sp_ex.ready.connect(self._on_spectrum_ready)
        sp_ex.finished.connect(sp_ex.deleteLater)
        sp_ex.finished.connect(
            lambda _ex=sp_ex: self._spectrum_map.pop(_ex, None)
        )
        sp_ex.start()

    def _on_spectrum_ready(self, bins) -> None:
        """Called on the main thread via Qt auto-queued cross-thread connection."""
        sp_map = getattr(self, "_spectrum_map", {})
        sender = self.sender()
        # sender is the SpectrumExtractor; look it up directly in map.
        target = sp_map.get(sender) if sender else None
        if target is None or bins is None:
            return
        target.spectrum_bins = bins
        for track in self._audio_tracks:
            if any(c is target for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.update()
                break

    def _on_waveform_ready(self, oid: int, peaks) -> None:
        import sys
        from pathlib import Path as _Path
        _mx = float(peaks.max()) if hasattr(peaks, 'max') else 0
        _sh = getattr(peaks, 'shape', '?')
        msg = f"[waveform] ready  oid={oid} shape={_sh} max={_mx:.4f}\n"
        print(msg, end='', file=sys.stderr, flush=True)
        try:
            with open(_Path(__file__).parent.parent / "logs" / "waveform_debug.log", "a", encoding="utf-8") as _f:
                import datetime as _dt
                _f.write(f"{_dt.datetime.now().isoformat()} {msg}")
        except Exception:
            pass
        clip_map = getattr(self, "_waveform_clip_map", {})
        target = clip_map.pop(oid, None)
        self._waveform_extractors.pop(oid, None)
        if target is None:
            return
        target.waveform = peaks
        # Find the row for the track containing this clip and repaint.
        for track in self._audio_tracks:
            if any(c is target for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.clear_waveform_error(target.id)
                    row.update()
                break
        for editor in getattr(self, "_sound_editors", []):
            if getattr(editor, "clip", None) is target:
                editor.refresh_waveform()

    def _on_waveform_failed(self, oid: int, reason: str) -> None:
        import sys
        from pathlib import Path as _Path
        msg = f"[waveform] FAILED oid={oid} reason={reason[:120]}\n"
        print(msg, end='', file=sys.stderr, flush=True)
        try:
            with open(_Path(__file__).parent.parent / "logs" / "waveform_debug.log", "a", encoding="utf-8") as _f:
                import datetime as _dt
                _f.write(f"{_dt.datetime.now().isoformat()} {msg}")
        except Exception:
            pass
        clip_map = getattr(self, "_waveform_clip_map", {})
        target = clip_map.pop(oid, None)
        self._waveform_extractors.pop(oid, None)
        if target is None:
            return
        for track in self._audio_tracks:
            if any(c is target for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.set_waveform_error(target.id, reason)
                break

    def _populate_video_track(self, track_id: int, path: Path) -> None:
        track = self._find_track(track_id)
        if track is None or track.source_path is not None:
            return
        track.source_path = path
        try:
            from app.hdr_probe import probe_hdr
            track.hdr_info = probe_hdr(path)
        except Exception:
            track.hdr_info = None
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._start_thumbnail_extraction(track)
        self._refresh_player_tracks()
        _ensure_video_clips(track)
        # Repaint AFTER ``_ensure_video_clips`` populates the stored
        # clips list — without this the "empty slot" paint sticks.
        # ``update()`` only; an extra ``_recalc_width`` here destabilised
        # the layout reflow on some Qt builds.
        if row is not None:
            row.update()
        if track_id == self._active_track_id:
            self._refresh_workbench()

    def _insert_audio_track_widget(self, track: AudioTrack) -> None:
        row = AudioTrackRow(track)
        row.set_px_per_sec(self._px_per_sec)
        row.clicked.connect(self._set_active_track)
        row.volume_changed.connect(self._on_audio_volume_changed)
        row.row_context_menu.connect(self._on_audio_row_context_menu)
        row.clip_context_menu.connect(self._on_audio_clip_context_menu)
        row.load_source_requested.connect(self._on_audio_load_source_requested)
        row.media_dropped.connect(self._on_media_dropped_on_audio_row)
        row.track_changed.connect(self._on_audio_track_changed)
        row.clip_selection_changed.connect(self._on_audio_clip_selection_changed)
        row.open_editor_requested.connect(self._open_sound_editor)
        self._audio_rows[track.id] = row
        self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
        self._update_tracks_host_width()
        # Rebuild mixer panel if it's visible
        if hasattr(self, "_audio_mixer_panel") and self._audio_mixer_panel.isVisible():
            self._audio_mixer_panel.rebuild(self._audio_tracks)

    def _on_audio_track_changed(self, tid: int) -> None:
        """Fires whenever a clip is dragged / resized / fades mutated.
        Re-sync the mixer and refresh project duration."""
        track = self._find_audio_track(tid)
        if track is not None:
            self._audio_mixer.update_track(track)
        self._refresh_player_tracks()

    def _on_audio_clip_selection_changed(
        self, tid: int, cid: int, _start: int, _end: int
    ) -> None:
        # Take ownership of the ants — clears video ants globally.
        # Use globals() directly so we mutate THIS module's namespace,
        # not a potentially-stale re-import reference.
        import sys as _sys
        _sys.modules[__name__]._ANTS_OWNER = "audio"
        if self._selected_clips:
            self._selected_clips.clear()
            for row in self._track_rows.values():
                row.set_selected_clip_ids(set())
        # Trigger a repaint on all video track rows so the ants disappear there.
        for row in self._track_rows.values():
            row.update()
        # Row persists the selection on the clip itself; we just push
        # the clip's metadata into the right-dock inspector so the
        # user has a contextual readout.
        if not hasattr(self, "_workbench_panel"):
            return
        track = self._find_audio_track(tid)
        if track is None:
            self._workbench_panel.clear()
            return
        clip = next((c for c in track.clips if c.id == cid), None)
        if clip is None:
            self._workbench_panel.clear()
            return
        self._workbench_panel.set_audio_clip(track, clip)

    def _split_audio_clip(self, track: AudioTrack, clip: AudioClip) -> None:
        """Split ``clip`` into two clips on the SAME track at the clip's
        current selection [sel_start, sel_end] (clip-local ms). Leaves
        the track intact with two clips that can be moved independently."""
        sel_start = clip.selection_start_ms
        sel_end = clip.selection_end_ms
        if sel_start < 0 or sel_end <= sel_start:
            return

        a_trim_start = clip.trim_start_ms
        a_trim_end = clip.trim_start_ms + sel_start
        b_trim_start = clip.trim_start_ms + sel_end
        b_trim_end = clip.effective_trim_end_ms

        a_keeps = a_trim_end > a_trim_start
        b_keeps = b_trim_end > b_trim_start
        if not a_keeps and not b_keeps:
            # Entire clip cut out — drop it from the track.
            try:
                track.clips.remove(clip)
            except ValueError:
                pass
            self._waveform_extractors.pop(clip.id, None)
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()
            self._audio_rows[track.id].update()
            return

        new_clip_b: AudioClip | None = None
        if b_keeps:
            new_clip_b = AudioClip(
                id=self._next_clip_id(),
                source_path=clip.source_path,
                duration_ms=clip.duration_ms,
                # Leave Piece B at the project-timeline position where
                # its source content used to play — there's now a real
                # gap where the cut was. User can drag either piece to
                # close the gap or move them freely.
                offset_ms=clip.offset_ms + sel_end,
                trim_start_ms=b_trim_start,
                trim_end_ms=b_trim_end,
                fade_in_ms=0,
                fade_out_ms=clip.fade_out_ms,
            )
            new_clip_b.waveform = clip.waveform  # shared source
            new_clip_b.fades = [
                FadeSegment(f.start_ms, f.end_ms, getattr(f, "kind", "both"))
                for f in clip.fades
                if f.start_ms >= b_trim_start
            ]
            new_clip_b.cuts = [
                CutSegment(
                    max(0, c.start_ms - sel_end),
                    max(0, c.end_ms - sel_end),
                )
                for c in clip.cuts
                if c.start_ms >= sel_end
            ]

        if a_keeps:
            clip.trim_end_ms = a_trim_end
            clip.fade_out_ms = 0  # tail fade belongs to piece B now
            clip.fades = [
                f for f in clip.fades if f.end_ms <= a_trim_end
            ]
            clip.cuts = [
                c for c in clip.cuts if c.end_ms <= sel_start
            ]
            clip.selection_start_ms = -1
            clip.selection_end_ms = -1
        else:
            # Piece A collapsed — remove it from the track.
            try:
                track.clips.remove(clip)
            except ValueError:
                pass

        if new_clip_b is not None:
            track.clips.append(new_clip_b)
            # Keep clips sorted by offset so the render order is stable.
            track.clips.sort(key=lambda c: c.offset_ms)

        row = self._audio_rows.get(track.id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._refresh_player_tracks()

    # ============== selection via Mark In / Mark Out (keyboard I/O) ==============

    def _mark_in_at_playhead(self) -> None:
        """Option C: I sets the GLOBAL project IN marker (export
        range start), not a per-track selection. The legacy
        Shift+drag still drives per-track selections for users who
        rely on the "select a sub-region of one clip" workflow."""
        self._set_global_in(self._player.position())

    def _mark_out_at_playhead(self) -> None:
        self._set_global_out(self._player.position())

    def _set_selection_end_at_playhead(self, in_point: bool) -> None:
        project_ms = self._player.position()
        candidates = self._candidate_tracks_at(project_ms)
        if not candidates:
            return
        changed = False
        for entry in candidates:
            kind = entry[0]
            if kind == "audio":
                _, track, clip = entry
                local = max(0, project_ms - clip.offset_ms)
                local = min(local, max(0, clip.effective_length_ms))
                if in_point:
                    clip.selection_start_ms = local
                    if clip.selection_end_ms < local:
                        clip.selection_end_ms = local
                else:
                    clip.selection_end_ms = local
                    if (
                        clip.selection_start_ms < 0
                        or clip.selection_start_ms > local
                    ):
                        clip.selection_start_ms = local
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.update()
            else:
                _, track = entry
                local = max(0, project_ms - getattr(track, "offset_ms", 0))
                local = min(local, max(0, track.duration_ms))
                if in_point:
                    track.selection_start_ms = local
                    if track.selection_end_ms < local:
                        track.selection_end_ms = local
                else:
                    track.selection_end_ms = local
                    if (
                        track.selection_start_ms < 0
                        or track.selection_start_ms > local
                    ):
                        track.selection_start_ms = local
                row = self._track_rows.get(track.id)
                if row is not None:
                    row.update()
            changed = True
        if changed:
            self._refresh_selection_row()

    def _clear_active_selection(self) -> None:
        # Option C: X clears BOTH the per-track Shift+drag selection
        # and the global IN/OUT markers, so a single press resets
        # every selection state to "none".
        self._clear_global_markers()
        for t in self._tracks:
            t.selection_start_ms = -1
            t.selection_end_ms = -1
        for track in self._audio_tracks:
            for clip in track.clips:
                clip.selection_start_ms = -1
                clip.selection_end_ms = -1
        for row in self._track_rows.values():
            row.update()
        for row in self._audio_rows.values():
            row.update()
        self._refresh_selection_row()

    def _candidate_tracks_at(self, project_ms: int) -> list:
        """Return list of entries whose window contains ``project_ms``.
        Each entry is either ("video", VideoTrack) or ("audio", track, clip)."""
        out: list = []
        active = self._active_track()
        if active is not None and active.source_path is not None:
            offset = getattr(active, "offset_ms", 0)
            if offset <= project_ms <= offset + active.duration_ms:
                out.append(("video", active))
        for t in self._tracks:
            if t is active or t.source_path is None:
                continue
            offset = getattr(t, "offset_ms", 0)
            if offset <= project_ms <= offset + t.duration_ms:
                out.append(("video", t))
        for track in self._audio_tracks:
            for clip in track.clips:
                if clip.source_path is None:
                    continue
                end = clip.offset_ms + clip.effective_length_ms
                if clip.offset_ms <= project_ms <= end:
                    out.append(("audio", track, clip))
        return out

    def _open_sound_editor(self, tid: int, cid: int) -> None:
        track, clip = self._find_audio_clip(tid, cid)
        if clip is None or clip.source_path is None:
            return
        editor = SoundEditorWindow(clip, self)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if not hasattr(self, "_sound_editors"):
            self._sound_editors: list[SoundEditorWindow] = []
        self._sound_editors.append(editor)
        editor.destroyed.connect(
            lambda _obj, e=editor: (
                self._sound_editors.remove(e) if e in self._sound_editors else None
            )
        )
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _append_clip_to_track(self, track: "VideoTrack", path: Path) -> None:
        """Industry-standard multi-source append: add a new clip at the tail
        of an existing video track without creating a new track row.

        - Probes ``path`` duration with cv2 (fast, no new QThread needed).
        - Creates a ``VideoClip`` with its own ``source_path`` and places it
          immediately after the current rightmost clip.
        - Starts per-clip thumbnail extraction so thumbnails are kept separate
          from the existing track-level thumbnails.
        - Calls ``_refresh_player_tracks`` so the player opens a decoder for
          the new source and recomputes project duration.
        """
        from app.timeline_model import VideoClip as _VC, NodeGraph as _NG
        duration_ms = probe_video_duration_ms(path)
        if duration_ms <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        tail_ms = max(
            (int(c.timeline_out_ms) for c in track.clips), default=0
        )
        clip_id_val = getattr(self, "_next_video_clip_id", 2_000_000)
        self._next_video_clip_id = clip_id_val + 1
        new_clip = _VC(
            id=clip_id_val,
            source_path=path,
            source_duration_ms=duration_ms,
            timeline_in_ms=tail_ms,
            source_in_ms=0,
            source_out_ms=duration_ms,
            node_graph=_NG.default(),
        )
        track.clips.append(new_clip)
        # Update track-level display_name to reflect multiple sources.
        # (VideoTrack.display_name property already handles this.)
        self._start_thumbnail_extraction_for_clip(new_clip, track.id)
        self._refresh_player_tracks()
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._register_change("append clip")

    def _on_media_dropped_on_video_row(self, track_id: int, path: Path) -> None:
        # Auto-register the dropped file in the media pool too — even
        # the OS-direct-drop shortcut keeps the project's pool in
        # sync (DaVinci behaviour: every external file lives in the
        # pool, no exceptions).
        if hasattr(self, "_media_pool"):
            self._media_pool.add_path(path)
        if is_audio_path(path):
            self._add_audio_track_with_source(path)
            return
        if is_video_path(path):
            track = self._find_track(track_id)
            if track is not None and track.source_path is None and not track.clips:
                # Truly empty track (no source and no clips) → populate it.
                self._populate_video_track(track_id, path)
            elif track is not None and track.clips:
                # Industry-standard: append a new clip at the end of the track.
                self._append_clip_to_track(track, path)
            else:
                # No matching track or the drop landed outside any row.
                self._add_track_with_source(path)

    def _on_media_dropped_on_audio_row(self, track_id: int, path: Path) -> None:
        """Media dropped on an audio row. Audio file → append as a new
        clip on the same track if loaded, else populate it. Video →
        spawn a new video track."""
        # Same auto-register pattern as the video row handler.
        if hasattr(self, "_media_pool"):
            self._media_pool.add_path(path)
        if is_video_path(path):
            self._add_track_with_source(path)
            return
        if not is_audio_path(path):
            return
        track = self._find_audio_track(track_id)
        if track is None:
            self._add_audio_track_with_source(path)
            return
        if not track.is_loaded:
            self._populate_audio_track(track_id, path)
            return
        # Loaded track already — append as a new clip at the tail.
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        tail = track.extent_ms()
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            offset_ms=tail,
            trim_end_ms=duration,
        )
        track.clips.append(clip)
        row = self._audio_rows.get(track_id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _on_audio_volume_changed(self, tid: int, _vol: float) -> None:
        track = self._find_audio_track(tid)
        if track is not None:
            self._audio_mixer.update_track(track)
            # Sync mixer panel fader if open
            if hasattr(self, "_audio_mixer_panel"):
                self._audio_mixer_panel.sync_track_volume(tid, track.volume)

    def _on_audio_load_source_requested(self, tid: int) -> None:
        from PySide6.QtWidgets import QFileDialog
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            tr("veditor.audio.open_dialog_title"),
            "",
            tr("veditor.audio.open_filter"),
        )
        if not path_str:
            return
        self._populate_audio_track(tid, Path(path_str))

    def _on_audio_row_context_menu(self, tid: int, global_pos: QPoint) -> None:
        """Right-click on empty row area — offer row-level actions only."""
        track = self._find_audio_track(tid)
        if track is None:
            return
        menu = QMenu(self)
        act_remove = menu.addAction(tr("veditor.audio.ctx.remove"))
        chosen = menu.exec(global_pos)
        if chosen is act_remove:
            self._delete_audio_track(tid)

    def _on_audio_clip_context_menu(
        self, tid: int, cid: int, global_pos: QPoint
    ) -> None:
        """Right-click on a specific clip — per-clip actions."""
        track, clip = self._find_audio_clip(tid, cid)
        if clip is None:
            return
        menu = QMenu(self)
        act_cut_sel = QAction(tr("veditor.menu.cut_selection"), self)
        act_clear_cuts = QAction(tr("veditor.menu.clear_cuts"), self)
        act_trim = QAction(tr("veditor.audio.ctx.trim"), self)
        act_delete_clip = QAction(tr("veditor.audio.ctx.delete_clip"), self)

        def _cut_selection():
            if (
                clip.selection_start_ms < 0
                or clip.selection_end_ms <= clip.selection_start_ms
            ):
                return
            self._split_audio_clip(track, clip)

        def _clear_cuts():
            clip.cuts.clear()
            self._audio_rows[tid].update()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        def _prompt_trim():
            start, ok = QInputDialog.getInt(
                self,
                tr("veditor.audio.ctx.trim"),
                tr("veditor.audio.trim_start_prompt"),
                clip.trim_start_ms, 0, max(1, clip.duration_ms), 100,
            )
            if not ok:
                return
            end, ok2 = QInputDialog.getInt(
                self,
                tr("veditor.audio.ctx.trim"),
                tr("veditor.audio.trim_end_prompt"),
                clip.effective_trim_end_ms, start + 1,
                max(start + 1, clip.duration_ms), 100,
            )
            if not ok2:
                return
            clip.trim_start_ms = int(start)
            clip.trim_end_ms = int(end)
            self._audio_rows[tid].update()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        def _delete_clip():
            try:
                track.clips.remove(clip)
            except ValueError:
                return
            self._waveform_extractors.pop(clip.id, None)
            row = self._audio_rows.get(tid)
            if row is not None:
                row.refresh_from_track()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        act_cut_sel.triggered.connect(_cut_selection)
        act_clear_cuts.triggered.connect(_clear_cuts)
        act_trim.triggered.connect(_prompt_trim)
        act_delete_clip.triggered.connect(_delete_clip)

        has_sel = (
            clip.selection_start_ms >= 0
            and clip.selection_end_ms > clip.selection_start_ms
        )
        act_cut_sel.setEnabled(has_sel)
        act_clear_cuts.setEnabled(bool(clip.cuts))
        menu.addAction(act_cut_sel)
        menu.addAction(act_clear_cuts)
        menu.addSeparator()
        menu.addAction(act_trim)
        menu.addSeparator()
        menu.addAction(act_delete_clip)
        menu.exec(global_pos)

    def _delete_audio_track(self, track_id: int) -> None:
        row = self._audio_rows.pop(track_id, None)
        if row is not None:
            self._tracks_layout.removeWidget(row)
            row.deleteLater()
        track = self._find_audio_track(track_id)
        if track is not None:
            for clip in track.clips:
                self._waveform_extractors.pop(clip.id, None)
        self._audio_tracks = [a for a in self._audio_tracks if a.id != track_id]
        self._audio_mixer.remove_track(track_id)
        self._refresh_player_tracks()
        # Rebuild mixer panel if it's visible
        if hasattr(self, "_audio_mixer_panel") and self._audio_mixer_panel.isVisible():
            self._audio_mixer_panel.rebuild(self._audio_tracks)

    def _extract_audio_from_video(self, track: VideoTrack) -> None:
        """Create a new AudioTrack whose single clip points at the video
        file itself. FFmpeg / QMediaPlayer both treat a video file as a
        valid audio source — they decode the audio stream and ignore
        the video stream — so this is effectively "ripping the BGM" as
        an editable clip on the audio lane."""
        if track.source_path is None:
            return
        duration = probe_audio_duration_ms(track.source_path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.menu.extract_audio_none"),
            )
            return
        tid = self._next_track_id
        self._next_track_id += 1
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=track.source_path,
            duration_ms=duration,
            # Align to the video's position on the project timeline so
            # the extracted audio stays in sync if the user never moves
            # either track afterwards.
            offset_ms=getattr(track, "offset_ms", 0),
            trim_end_ms=duration,
        )
        new_track = AudioTrack(id=tid, clips=[clip])
        self._audio_tracks.append(new_track)
        self._insert_audio_track_widget(new_track)
        self._audio_mixer.add_track(new_track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    # ============== drag & drop (window-level) ==============

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        if not md.hasUrls():
            event.ignore()
            return
        for u in md.urls():
            p = Path(u.toLocalFile())
            if is_video_path(p) or is_audio_path(p):
                # Pool registration first — a drop on the empty
                # editor area still goes through the same DaVinci-
                # style path: pool → timeline.
                if hasattr(self, "_media_pool"):
                    self._media_pool.add_path(p)
            if is_video_path(p):
                self._add_track_with_source(p)
                event.acceptProposedAction()
                return
            if is_audio_path(p):
                self._add_audio_track_with_source(p)
                event.acceptProposedAction()
                return
        event.ignore()

    def _update_tracks_host_width(self) -> None:
        # Start with baseline (ruler) and each track's own preferred width.
        max_w = max(MIN_TRACK_WIDTH, self._timeline_ruler.desired_width())
        # Consider each row's natural duration-driven width.
        for row in self._track_rows.values():
            row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
            max_w = max(max_w, row_pref)
        for row in self._audio_rows.values():
            row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
            max_w = max(max_w, row_pref)
        # Also honor the viewport width so the divider / stripes can extend
        # the full visible area even when clips are short.
        vp_w = self._tracks_scroll.viewport().width() if hasattr(self, "_tracks_scroll") else 0
        max_w = max(max_w, vp_w)
        # Stretch every row + the ruler to the same width so the bottom
        # separator runs edge-to-edge regardless of clip length.
        self._timeline_ruler.setFixedWidth(max_w)
        for row in self._track_rows.values():
            row.setFixedWidth(max_w)
        for row in self._audio_rows.values():
            row.setFixedWidth(max_w)
        # Subtitle lane must match so its background fills the full timeline.
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.setFixedWidth(max_w)
        self._tracks_host.setMinimumWidth(max_w)

    def _change_zoom(self, factor: float) -> None:
        new_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, self._px_per_sec * factor))
        if abs(new_px - self._px_per_sec) < 0.001:
            return
        self._px_per_sec = new_px
        for row in self._track_rows.values():
            row.set_px_per_sec(new_px)
        for row in self._audio_rows.values():
            row.set_px_per_sec(new_px)
        self._timeline_ruler.set_px_per_sec(new_px)
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.set_px_per_sec(new_px)
        self.zoom_label.setText(self._format_zoom())
        self._update_tracks_host_width()

    def _zoom_fit(self) -> None:
        if not self._tracks:
            return
        max_span = max(
            (t.offset_ms + t.duration_ms for t in self._tracks), default=0
        )
        if max_span <= 0:
            return
        viewport_w = self._tracks_scroll.viewport().width()
        if viewport_w <= 50:
            return
        target_px = (viewport_w - 40) / (max_span / 1000.0)
        target_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, target_px))
        self._px_per_sec = target_px
        for row in self._track_rows.values():
            row.set_px_per_sec(target_px)
        self._timeline_ruler.set_px_per_sec(target_px)
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.set_px_per_sec(target_px)
        self.zoom_label.setText(self._format_zoom())
        self._update_tracks_host_width()

    def _format_zoom(self) -> str:
        return f"{self._px_per_sec:.0f} px/s"

    def _delete_active_track(self) -> None:
        # Allow deleting the only video track when audio tracks exist —
        # the project is still non-empty. If nothing remains at all,
        # the editor just shows the empty-timeline hint.
        if self._active_track_id is None:
            return
        if len(self._tracks) <= 1 and not self._audio_tracks:
            return
        self._delete_track(self._active_track_id)

    def _move_track(self, track_id: int, direction: int) -> None:
        """Move a track up (-1) or down (+1) in the layer order."""
        try:
            idx = next(i for i, t in enumerate(self._tracks) if t.id == track_id)
        except StopIteration:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._tracks):
            return
        # Swap in data model
        self._tracks[idx], self._tracks[new_idx] = self._tracks[new_idx], self._tracks[idx]
        # Swap rows in layout: find current positions and reinsert
        row_a = self._track_rows.get(self._tracks[idx].id)
        row_b = self._track_rows.get(self._tracks[new_idx].id)
        if row_a is None or row_b is None:
            return
        lay = self._tracks_layout
        idx_a = lay.indexOf(row_a)
        idx_b = lay.indexOf(row_b)
        if idx_a < 0 or idx_b < 0:
            return
        # Remove both and reinsert in swapped order
        lay.removeWidget(row_a)
        lay.removeWidget(row_b)
        # Insert at the lower index first, then the higher
        lo, hi = min(idx_a, idx_b), max(idx_a, idx_b)
        if idx_a < idx_b:  # row_a was on top, row_b below → swap them
            lay.insertWidget(lo, row_b)
            lay.insertWidget(hi, row_a)
        else:
            lay.insertWidget(lo, row_a)
            lay.insertWidget(hi, row_b)
        self._update_tracks_host_width()
        self._refresh_player_tracks()
        self._refresh_pip_panel()
        self._register_change("move track")

    def _delete_track(self, track_id: int) -> None:
        row = self._track_rows.pop(track_id, None)
        if row is not None:
            self._tracks_layout.removeWidget(row)
            row.deleteLater()
        self._tracks = [t for t in self._tracks if t.id != track_id]
        ex = self._extractors.pop(track_id, None)
        if ex is not None:
            ex.stop()
        if self._active_track_id == track_id:
            self._active_track_id = None
            if self._tracks:
                self._set_active_track(self._tracks[-1].id)
        self._refresh_player_tracks()

    def _set_active_track(self, track_id: int) -> None:
        """Active track is the UI focus target for edits (speed/cut apply to
        this track). Playback cascades through ALL tracks — last-added is
        the top layer. Switching active track does NOT change what is
        playing."""
        if self._active_track_id == track_id:
            return
        self._active_track_id = track_id
        for tid, row in self._track_rows.items():
            row.set_active(tid == track_id)
        self._refresh_selection_row()
        # Color grading is per-track — re-sync the panel so the
        # sliders/preset reflect whatever the new active track has.
        if hasattr(self, "_color_sliders"):
            self._sync_color_panel()
        # Inspector follows the active video track until an audio
        # clip selection overrides it.
        self._refresh_workbench()
        # Audio Scopes — when an audio track is selected, auto-show scopes
        # inside the mixer panel (if the mixer is already visible).
        if hasattr(self, "_audio_mixer_panel"):
            is_audio = track_id in self._audio_rows
            self._active_audio_track_id = track_id if is_audio else None
            # Auto-show scopes column when an audio track is selected,
            # but only if the mixer is already open (don't force-open mixer).
            if is_audio and self._audio_mixer_panel.isVisible():
                self._audio_mixer_panel.set_scopes_visible(True)
                pos = self._player.position() if hasattr(self, "_player") else 0
                self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
                # Sync the scopes toggle button
                scopes_btn = getattr(self, "audio_scopes_tl_btn", None)
                if scopes_btn is not None and not scopes_btn.isChecked():
                    with _block_signals(scopes_btn):
                        scopes_btn.setChecked(True)

    def _refresh_workbench(self) -> None:
        """Push the active video track's current state into the
        right-dock inspector. Called from every handler that mutates
        track data (source, fades, speed, offset, duration) — Qt's
        ``_set_active_track`` early-return for same-id was hiding
        post-drop updates from the inspector, so we have to push
        explicitly each time the track contents change."""
        if not hasattr(self, "_workbench_panel"):
            return
        if self._active_track_id is None:
            self._workbench_panel.clear()
            self._node_grade_target = None
            return
        track = self._find_track(self._active_track_id)
        self._workbench_panel.set_video_track(track)
        # DaVinci routing: bind the Color panel to the primary
        # node by default. The user can re-target by clicking any
        # node in the graph (handled in _on_node_graph_selection).
        primary = self._workbench_panel.primary_node()
        if primary is not None:
            # NOTE: legacy migration (copying track.color_grade onto
            # Node 1) was REMOVED. The old single-grade system stored
            # values on track.color_grade which persisted between
            # sessions. If those values were extreme (contrast=-100,
            # saturation=-100, etc.) the migration silently poisoned
            # every new Node 1, making the preview go gray the moment
            # any control was touched. Node 1 now always starts at
            # identity — users set grades deliberately on nodes.
            self._node_grade_target = primary
        else:
            self._node_grade_target = None
        if hasattr(self, "_sync_color_panel"):
            self._sync_color_panel()
        # DaVinci Phase D: build the per-track grade chain from the
        # newly-loaded scene so ProjectPlayer applies every node's
        # grade in IN→OUT order on the main preview.
        self._rebuild_active_chain()
        # PIP panel visibility + state update.
        self._refresh_pip_panel()

    # ---- PIP panel ----

    def _refresh_pip_panel(self) -> None:
        """Show / populate the PIP panel when a non-bottom track is active."""
        if not hasattr(self, "_pip_section_host"):
            return
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        # PIP is only meaningful on non-bottom tracks (index > 0).
        track_idx = self._tracks.index(track) if track is not None and track in self._tracks else -1
        visible = (track is not None) and (track_idx > 0)
        self._pip_section_host.setVisible(visible)
        if not visible:
            return
        # Populate controls from track state — block signals to avoid feedback.
        for sl, attr, scale in [
            (self._pip_x_slider,      "pip_x",       100.0),
            (self._pip_y_slider,      "pip_y",       100.0),
            (self._pip_scale_slider,  "pip_scale",   100.0),
            (self._pip_opacity_slider,"pip_opacity",  100.0),
        ]:
            sl.blockSignals(True)
            v = int(round(float(getattr(track, attr, 0.5 if attr in ("pip_x", "pip_y") else 0.3 if attr == "pip_scale" else 1.0)) * scale))
            sl.setValue(v)
            sl.blockSignals(False)
        self._pip_x_val.setText(str(self._pip_x_slider.value()))
        self._pip_y_val.setText(str(self._pip_y_slider.value()))
        self._pip_scale_val.setText(str(self._pip_scale_slider.value()))
        self._pip_opacity_val.setText(str(self._pip_opacity_slider.value()))
        self._pip_enable_btn.blockSignals(True)
        self._pip_enable_btn.setChecked(bool(getattr(track, "pip_enabled", False)))
        self._pip_enable_btn.blockSignals(False)
        # Slider rows enabled only when PIP is on.
        _pip_on = bool(getattr(track, "pip_enabled", False))
        for sl in (self._pip_x_slider, self._pip_y_slider,
                   self._pip_scale_slider, self._pip_opacity_slider):
            sl.setEnabled(_pip_on)
        # Refresh keyframe list.
        self._refresh_pip_kf_list(track)

    def _sync_pip_sliders_to_position(self, pos_ms: int) -> None:
        """Update PIP sliders to show interpolated values at the current playhead."""
        if not hasattr(self, "_pip_x_slider"):
            return
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        if track is None or not getattr(track, "pip_enabled", False):
            return
        kfs = getattr(track, "pip_keyframes", [])
        if not kfs:
            return
        from app.project_player import _interpolate_pip_params
        x, y, scale, opacity = _interpolate_pip_params(kfs, pos_ms, track)
        for sl, val in [
            (self._pip_x_slider, x),
            (self._pip_y_slider, y),
            (self._pip_scale_slider, scale),
            (self._pip_opacity_slider, opacity),
        ]:
            sl.blockSignals(True)
            sl.setValue(int(round(val * 100)))
            sl.blockSignals(False)

    def _on_pip_enable_toggled(self, checked: bool) -> None:
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        if track is None:
            return
        track.pip_enabled = checked
        # Toggle slider enablement.
        for sl in (self._pip_x_slider, self._pip_y_slider,
                   self._pip_scale_slider, self._pip_opacity_slider):
            sl.setEnabled(checked)
        # Repaint the track row to show/hide the PIP badge.
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        # Rebuild decoders + refresh preview so the base layer is re-selected.
        self._refresh_player_tracks()
        self._register_change("pip enable")

    def _on_pip_slider_changed(self, attr: str, value: int) -> None:
        """Handle a PIP slider value change.

        If no keyframes exist: update the static PIP fields directly.
        If keyframes exist: create or update a keyframe at the current playhead,
        so the change is always "recorded" at the current time.
        """
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        if track is None:
            return
        normalised = value / 100.0
        setattr(track, attr, normalised)

        kfs = getattr(track, "pip_keyframes", [])
        if kfs:
            # With keyframes active, auto-write the current slider state as a
            # keyframe at the playhead so the user can freely pose at any time.
            pos_ms = self._player.position()
            # Update existing keyframe within 50 ms, or insert a new one.
            snap_ms = 50
            existing = next((k for k in kfs if abs(k["ms"] - pos_ms) <= snap_ms), None)
            if existing is not None:
                existing["x"] = float(track.pip_x)
                existing["y"] = float(track.pip_y)
                existing["scale"] = float(track.pip_scale)
                existing["opacity"] = float(track.pip_opacity)
            else:
                kfs.append({
                    "ms": pos_ms,
                    "x": float(track.pip_x),
                    "y": float(track.pip_y),
                    "scale": float(track.pip_scale),
                    "opacity": float(track.pip_opacity),
                })
                track.pip_keyframes = sorted(kfs, key=lambda k: k["ms"])
            self._refresh_pip_kf_list(track)
            row = self._track_rows.get(track.id)
            if row is not None:
                row.update()

        self._player.refresh_current_frame()

    # ---- PIP keyframe helpers ----

    @staticmethod
    def _ms_to_timecode(ms: int) -> str:
        """Format milliseconds as mm:ss:ff (ff = centiseconds, 0-99)."""
        total_s = ms // 1000
        mm = total_s // 60
        ss = total_s % 60
        ff = (ms % 1000) // 10
        return f"{mm:02d}:{ss:02d}:{ff:02d}"

    def _refresh_pip_kf_list(self, track) -> None:
        """Repopulate the keyframe QListWidget from track.pip_keyframes."""
        if not hasattr(self, "_pip_kf_list"):
            return
        self._pip_kf_list.clear()
        kfs = sorted(getattr(track, "pip_keyframes", []), key=lambda k: k["ms"])
        for kf in kfs:
            tc = self._ms_to_timecode(kf["ms"])
            label = f"{tc}  X:{kf['x']:.2f}  Y:{kf['y']:.2f}  S:{kf['scale']:.2f}"
            self._pip_kf_list.addItem(label)

    def _pip_add_keyframe(self) -> None:
        """Capture current playhead position + slider values as a PIP keyframe."""
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        if track is None or not getattr(track, "pip_enabled", False):
            return
        pos_ms = self._player.position()
        kf = {
            "ms": pos_ms,
            "x": float(track.pip_x),
            "y": float(track.pip_y),
            "scale": float(track.pip_scale),
            "opacity": float(track.pip_opacity),
        }
        kfs = list(getattr(track, "pip_keyframes", []))
        # Replace if a keyframe within 50 ms already exists.
        kfs = [k for k in kfs if abs(k["ms"] - pos_ms) > 50]
        kfs.append(kf)
        track.pip_keyframes = sorted(kfs, key=lambda k: k["ms"])
        self._refresh_pip_kf_list(track)
        self._refresh_player_tracks()
        self._register_change("pip keyframe add")

    def _pip_delete_keyframe(self) -> None:
        """Remove the selected keyframe from the active track."""
        track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
        if track is None:
            return
        row = self._pip_kf_list.currentRow()
        if row < 0:
            return
        kfs = sorted(getattr(track, "pip_keyframes", []), key=lambda k: k["ms"])
        if row < len(kfs):
            kfs.pop(row)
        track.pip_keyframes = kfs
        self._refresh_pip_kf_list(track)
        self._refresh_player_tracks()
        self._register_change("pip keyframe delete")

    # ---- inspector slider handlers ----

    def _on_workbench_fade_in_changed(self, ms: int) -> None:
        target = self._workbench_panel.current_target()
        if target is None:
            return
        ms = max(0, int(ms))
        if target[0] == "video":
            self._set_video_track_leading_fade(target[1], ms)
        elif target[0] == "audio":
            _t, clip = target[1], target[2]
            clip.fade_in_ms = ms
            row = self._audio_rows.get(_t.id)
            if row is not None:
                row.update()
            self._on_audio_track_changed(_t.id)

    def _on_workbench_fade_out_changed(self, ms: int) -> None:
        target = self._workbench_panel.current_target()
        if target is None:
            return
        ms = max(0, int(ms))
        if target[0] == "video":
            self._set_video_track_trailing_fade(target[1], ms)
        elif target[0] == "audio":
            _t, clip = target[1], target[2]
            clip.fade_out_ms = ms
            row = self._audio_rows.get(_t.id)
            if row is not None:
                row.update()
            self._on_audio_track_changed(_t.id)

    def _set_video_track_leading_fade(self, track: VideoTrack, ms: int) -> None:
        """Materialise the inspector's "Fade In" slider value as a
        leading ``kind="in"`` FadeSegment at offset 0. ms == 0 removes
        any existing leading fade; > 0 creates / updates one."""
        fades = list(track.fades or [])
        # Drop the existing leading-in segment if any.
        fades = [
            f for f in fades
            if not (f.start_ms <= 0 and f.kind == "in")
        ]
        if ms > 0:
            fades.append(FadeSegment(start_ms=0, end_ms=ms, kind="in"))
        fades.sort(key=lambda f: f.start_ms)
        track.fades = fades
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        # Repaint preview at the current playhead so the user sees
        # the fade preview update immediately.
        self._player.set_position(self._player.position())

    def _set_video_track_trailing_fade(self, track: VideoTrack, ms: int) -> None:
        """Materialise "Fade Out" as a trailing ``kind="out"`` segment
        ending at the track duration."""
        dur = int(getattr(track, "duration_ms", 0) or 0)
        if dur <= 0:
            return
        fades = list(track.fades or [])
        # Drop any segment that looks like an existing trailing-out
        # (within 100 ms of duration end and kind=="out").
        fades = [
            f for f in fades
            if not (f.end_ms >= dur - 100 and f.kind == "out")
        ]
        if ms > 0:
            start = max(0, dur - ms)
            fades.append(FadeSegment(start_ms=start, end_ms=dur, kind="out"))
        fades.sort(key=lambda f: f.start_ms)
        track.fades = fades
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._player.set_position(self._player.position())

    def _on_workbench_volume_changed(self, db: float) -> None:
        target = self._workbench_panel.current_target()
        if target is None or target[0] != "audio":
            return
        track = target[1]
        track.master_volume = float(db)
        self._audio_mixer.update_track(track)
        row = self._audio_rows.get(track.id)
        if row is not None:
            row.update()

    def _refresh_player_tracks(self) -> None:
        # Include audio tracks in the project duration so playback (and
        # the timeline ruler) extend to whichever is longer — the last
        # video frame or the last audio sample.
        extra = max(
            (track.extent_ms() for track in self._audio_tracks),
            default=0,
        )
        self._player.refresh_tracks(self._tracks, extra_duration_ms=extra)
        self._update_preview_placeholder()
        # Belt-and-suspenders: refresh paint of every video / audio
        # row. ``ProjectPlayer.refresh_tracks`` may have just set
        # ``track.duration_ms`` (legacy field), at which point the
        # row's ``_preferred_width`` and clip rects need a recompute.
        # Without this update some row paths leave the row stuck on
        # the pre-load "empty slot" render.
        for row in self._track_rows.values():
            row.update()
        for row in self._audio_rows.values():
            row.update()

    # -----------------------------------------------------------------------
    # Proxy workflow
    # -----------------------------------------------------------------------

    def _toggle_proxy_mode(self, checked: bool) -> None:
        """Switch all tracks between original and proxy source paths.

        When enabling: for each track that has a proxy, swap source_path to
        the proxy and stash the original in ``track._original_source_path``.
        When disabling: restore ``track.source_path`` from the stash.
        After switching, refresh the player so the new paths take effect.
        """
        self._proxy_mode = checked
        for track in self._tracks:
            if track.source_path is None:
                continue
            if checked:
                orig = track._original_source_path or track.source_path
                proxy_dir = orig.parent / "proxies"
                proxy_candidate = proxy_dir / (orig.stem + "_proxy.mp4")
                if proxy_candidate.exists():
                    track._original_source_path = orig
                    track.source_path = proxy_candidate
            else:
                if track._original_source_path is not None:
                    track.source_path = track._original_source_path
                    track._original_source_path = None
        self._refresh_player_tracks()
        for row in self._track_rows.values():
            row.update()

    def _start_proxy_generation(self, path: Path) -> None:
        """Launch a background proxy generator for ``path``.

        Silently skips if a thread for this path is already running or if
        the proxy already exists on disk.
        """
        key = str(path)
        if key in self._proxy_threads:
            return
        proxy_dir = path.parent / "proxies"
        proxy_candidate = proxy_dir / (path.stem + "_proxy.mp4")
        if proxy_candidate.exists():
            return
        thread = ProxyGeneratorThread(path, parent=self)
        thread.done.connect(self._on_proxy_done)
        thread.failed.connect(self._on_proxy_failed)
        thread.finished.connect(lambda key=key: self._proxy_threads.pop(key, None))
        self._proxy_threads[key] = thread
        thread.start()

    def _on_proxy_done(self, original_path: str, proxy_path: str) -> None:
        """Called when proxy generation completes. If proxy mode is ON, apply immediately."""
        if self._proxy_mode:
            orig = Path(original_path)
            proxy = Path(proxy_path)
            for track in self._tracks:
                effective_orig = track._original_source_path or track.source_path
                if effective_orig == orig and not str(track.source_path).endswith("_proxy.mp4"):
                    track._original_source_path = orig
                    track.source_path = proxy
            self._refresh_player_tracks()
            for row in self._track_rows.values():
                row.update()

    def _on_proxy_failed(self, original_path: str, reason: str) -> None:
        """Called when proxy generation fails — silently ignored."""
        pass

    def _update_preview_placeholder(self) -> None:
        """Flip the preview between "video frame", "sound-only" hint, and
        "no file" hint based on what's loaded. Called after any track
        list mutation so the preview reflects current project state.

        Avoids ``QLabel.clear()`` — that tears down both text and pixmap
        which in turn triggers a layout/resize cascade; on some timings
        that cascade re-enters ``_scale_preview_to_fit`` or the drawing
        canvas and can confuse Qt's widget lifecycle. Explicit
        ``setPixmap(QPixmap())`` + ``setText`` is surgical and leaves
        the widget's size policy alone.
        """
        has_video = any(
            t.source_path is not None or bool(t.clips)
            for t in self._tracks
        )
        has_audio = any(t.is_loaded for t in self._audio_tracks)
        if has_video:
            return
        self._preview_pixmap = None
        self._preview_label.setPixmap(QPixmap())
        if has_audio:
            self._preview_label.setText(tr("veditor.preview.sound_only"))
            self._preview_label.setStyleSheet(
                f"color: {COLOR_ACCENT_BLUE}; font-size: 28px; font-weight: 700;"
            )
        else:
            self._preview_label.setText(tr("veditor.no_file"))
            self._preview_label.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY};"
            )

    def _find_track(self, track_id: int) -> VideoTrack | None:
        for t in self._tracks:
            if t.id == track_id:
                return t
        return None

    def _active_track(self) -> VideoTrack | None:
        if self._active_track_id is None:
            return None
        return self._find_track(self._active_track_id)

    # ----------------- thumbnails -------------------

    def _start_thumbnail_extraction(self, track: VideoTrack) -> None:
        if track.source_path is None:
            return
        prev = self._extractors.pop(track.id, None)
        if prev is not None:
            prev.stop()
        ex = ThumbnailExtractor(track.id, track.source_path, THUMB_H)
        ex.count_determined.connect(self._on_thumb_count)
        ex.thumb_ready.connect(self._on_thumb_ready)
        ex.finished_extracting.connect(self._on_extractor_done)
        track.thumbnails = []
        self._extractors[track.id] = ex
        ex.start()

    def _on_thumb_count(self, track_id: int, count: int) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        track.thumbnails = [None] * count  # type: ignore[list-item]
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_thumb_ready(self, track_id: int, idx: int, pix: QPixmap) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        if idx < 0 or idx >= len(track.thumbnails):
            return
        track.thumbnails[idx] = pix
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_extractor_done(self, track_id: int) -> None:
        ex = self._extractors.pop(track_id, None)
        if ex is not None:
            ex.deleteLater()

    # ----------- per-clip thumbnail extraction (multi-source) -----------

    def _start_thumbnail_extraction_for_clip(
        self, clip, track_id: int
    ) -> None:
        """Start thumbnail extraction for a specific ``VideoClip`` on an
        existing track. Thumbnails land on ``clip.thumbnails`` so the
        paintEvent can render them independently from the track-level
        ``track.thumbnails`` list (which covers only the first source).
        """
        from app.timeline_model import VideoClip as _VC
        sp = getattr(clip, "source_path", None)
        if sp is None:
            return
        clip_id = getattr(clip, "id", -1)
        key = (track_id, clip_id)
        prev = self._clip_extractors.pop(key, None)
        if prev is not None:
            prev.stop()
        clip.thumbnails = []
        ex = ThumbnailExtractor(track_id, sp, THUMB_H, clip_id=clip_id)
        ex.clip_count_determined.connect(self._on_clip_thumb_count)
        ex.clip_thumb_ready.connect(self._on_clip_thumb_ready)
        ex.finished_extracting.connect(self._on_clip_extractor_done)
        self._clip_extractors[key] = ex
        ex.start()

    def _on_clip_thumb_count(self, track_id: int, clip_id: int, count: int) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        clip = next((c for c in track.clips if c.id == clip_id), None)
        if clip is None:
            return
        clip.thumbnails = [None] * count  # type: ignore[list-item]
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_clip_thumb_ready(
        self, track_id: int, clip_id: int, idx: int, pix: QPixmap
    ) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        clip = next((c for c in track.clips if c.id == clip_id), None)
        if clip is None:
            return
        if idx < 0 or idx >= len(clip.thumbnails):
            return
        clip.thumbnails[idx] = pix
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_clip_extractor_done(self, track_id: int) -> None:
        # finished_extracting only carries track_id; clean up by matching
        # the most recently added extractor for this track.
        for key in list(self._clip_extractors.keys()):
            if key[0] == track_id:
                ex = self._clip_extractors.pop(key, None)
                if ex is not None:
                    ex.deleteLater()
                break

    # ----------------- track events -----------------

    def _on_track_position_requested(self, track_id: int, ms: int) -> None:
        # Clicking any track seeks the project (not just its own time)
        if track_id != self._active_track_id:
            self._set_active_track(track_id)
        self._player.set_position(ms)

    def _on_track_selection_changed(self, track_id: int, start: int, end: int) -> None:
        if track_id != self._active_track_id:
            self._set_active_track(track_id)
        self._refresh_selection_row()

    def _on_track_offset_changed(self, track_id: int, _new_offset_ms: int) -> None:
        # Offset repositions the clip on the project timeline → re-broadcast
        # duration and make sure the player's cached track list matches.
        self._refresh_player_tracks()
        self._update_tracks_host_width()
        if track_id == self._active_track_id:
            self._refresh_workbench()

    def _on_track_fades_changed(self, track_id: int) -> None:
        # Nothing to do beyond repaint (done by the row itself) — export path
        # reads the updated list at save time. Inspector reflects the new
        # fade durations though, so push them through.
        if track_id == self._active_track_id:
            self._refresh_workbench()

    def _on_track_speed_changed(self, track_id: int) -> None:
        # Speed segments affect the player's duration / seek mapping,
        # so refresh the player's cache. The row has already repainted.
        self._refresh_player_tracks()
        self._update_tracks_host_width()
        if track_id == self._active_track_id:
            self._refresh_workbench()

    def _on_video_clip_context_menu(self, track_id: int, clip_id: int, global_pos: "QPoint") -> None:
        """Right-click on a video clip — show effects + standard options."""
        track = self._find_track(track_id)
        if track is None:
            return
        clip = next((c for c in getattr(track, "clips", []) if c.id == clip_id), None)
        if clip is None:
            return
        menu = QMenu(self)
        fx_act = menu.addAction("🎨 클립 이펙트…")
        menu.addSeparator()
        split_act = menu.addAction("✂ 여기서 분할")
        del_act = menu.addAction("🗑 삭제")
        chosen = menu.exec(global_pos)
        if chosen is fx_act:
            self._open_clip_effects(track, clip)
        elif chosen is split_act:
            self._blade_at_playhead(track_id=track_id)
        elif chosen is del_act:
            self._delete_selected_clips()

    def _open_clip_effects(self, track, clip) -> None:
        """Open the ClipEffectsDialog for the given clip."""
        try:
            from app.clip_effects_dialog import ClipEffectsDialog
        except ImportError:
            return

        def refresh():
            self._player.refresh_current_frame()

        dlg = ClipEffectsDialog(clip, refresh_fn=refresh, parent=self)
        dlg.effects_changed.connect(refresh)
        dlg.exec()
        self._register_change("클립 이펙트 변경")

    def _on_track_context_menu(self, track_id: int, global_pos: QPoint) -> None:
        self._set_active_track(track_id)
        track = self._find_track(track_id)
        if track is None:
            return

        menu = QMenu(self)
        # DaVinci-style: no "Load video..." menu entry on the track
        # itself. External files always go through the Media Pool —
        # either via the pool's right-click "Load video files…", a
        # drop on the pool, or by dragging an OS file straight onto
        # the track (the existing dropEvent handles that path).

        # Option C: blade at playhead replaces the legacy
        # "cut selection" entry (which depended on Shift+drag selection
        # that no longer exists).
        act_blade = menu.addAction(tr("veditor.menu.blade_at_playhead"))
        act_blade.setEnabled(bool(getattr(track, "clips", None)))

        # Ripple delete the currently-selected clip(s), if any.
        act_ripple = menu.addAction(tr("veditor.menu.ripple_delete"))
        act_ripple.setEnabled(bool(self._selected_clips))

        menu.addSeparator()
        act_extract_audio = menu.addAction(tr("veditor.menu.extract_audio"))
        # Enable if ANY clip in this track has a source (works for multi-source tracks)
        has_any_source = (track.source_path is not None) or any(
            getattr(c, "source_path", None) is not None
            for c in getattr(track, "clips", [])
        )
        act_extract_audio.setEnabled(has_any_source)

        # Audio link menu item — visible when exactly one video clip is selected.
        act_audio_link = None
        _link_clip = None
        if len(self._selected_clips) == 1:
            sel_tid, sel_cid = self._selected_clips[0]
            sel_track = self._find_track(sel_tid)
            if sel_track is not None:
                _link_clip = next(
                    (c for c in getattr(sel_track, "clips", []) if c.id == sel_cid),
                    None,
                )
            if _link_clip is not None and self._audio_tracks:
                menu.addSeparator()
                is_linked = getattr(_link_clip, "linked_audio_id", None) is not None
                link_label = "🔗 오디오 링크 해제" if is_linked else "🔗 오디오 링크"
                act_audio_link = menu.addAction(link_label)

        menu.addSeparator()
        # Track reorder
        idx = self._tracks.index(track) if track in self._tracks else -1
        act_move_up = menu.addAction("↑ 위로 이동 (레이어 올리기)")
        act_move_up.setEnabled(idx > 0)
        act_move_down = menu.addAction("↓ 아래로 이동 (레이어 내리기)")
        act_move_down.setEnabled(0 <= idx < len(self._tracks) - 1)

        menu.addSeparator()
        act_delete = menu.addAction(tr("veditor.menu.delete_track"))
        act_delete.setEnabled(len(self._tracks) > 1 or bool(self._audio_tracks))

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if act_audio_link is not None and chosen is act_audio_link:
            if _link_clip is not None:
                self._toggle_audio_link(sel_track, _link_clip)
            return
        if chosen is act_blade:
            self._blade_at_playhead()
        elif chosen is act_ripple:
            self._delete_selected_clips()
        elif chosen is act_move_up:
            self._move_track(track_id, -1)
        elif chosen is act_move_down:
            self._move_track(track_id, +1)
        elif chosen is act_extract_audio:
            # For multi-source track: extract from the first clip's source
            src = track.source_path
            if src is None:
                for c in getattr(track, "clips", []):
                    if getattr(c, "source_path", None):
                        src = c.source_path
                        break
            if src is not None:
                self._extract_audio_from_video(track)
        elif chosen is act_delete:
            self._delete_track(track_id)

    # ------------- audio link helpers -------------

    def _on_clip_drag_delta(
        self, track_id: int, clip_id: int, new_timeline_in_ms: int, delta_ms: int
    ) -> None:
        """When a VideoClip with ``linked_audio_id`` is dragged, move the
        linked AudioClip by the same delta so they stay in sync."""
        if delta_ms == 0:
            return
        track = self._find_track(track_id)
        if track is None:
            return
        clip = next((c for c in getattr(track, "clips", []) if c.id == clip_id), None)
        if clip is None:
            return
        linked_id = getattr(clip, "linked_audio_id", None)
        if linked_id is None:
            return
        # Find the audio clip with that id across all audio tracks.
        for atrack in self._audio_tracks:
            for aclip in atrack.clips:
                if aclip.id == linked_id:
                    new_offset = max(0, int(aclip.offset_ms) + delta_ms)
                    aclip.offset_ms = new_offset
                    row = self._audio_rows.get(atrack.id)
                    if row is not None:
                        row.update()
                    return

    def _toggle_audio_link(self, track, clip) -> None:
        """Link or unlink the video clip to the nearest audio clip at the
        same timeline position. If already linked, clears ``linked_audio_id``."""
        if getattr(clip, "linked_audio_id", None) is not None:
            clip.linked_audio_id = None
            row = self._track_rows.get(track.id)
            if row is not None:
                row.update()
            return
        # Find the nearest audio clip whose offset_ms is closest to clip.timeline_in_ms.
        best_clip = None
        best_dist = None
        for atrack in self._audio_tracks:
            for aclip in atrack.clips:
                dist = abs(int(aclip.offset_ms) - int(clip.timeline_in_ms))
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_clip = aclip
        if best_clip is not None:
            clip.linked_audio_id = best_clip.id
            row = self._track_rows.get(track.id)
            if row is not None:
                row.update()

    # ------------- track actions (invoked from menu/buttons) -------------
    # ``_load_into_track`` was removed when the track right-click menu
    # dropped the "Load video file…" entry — external files now go
    # through the Media Pool exclusively (DaVinci-style workflow).

    def _cut_selection_in_track(self, track_id: int) -> None:
        """Phase 1.5d Step C: cut becomes a real clip-list mutation.

        The selection is in *track-local source ms*; we map it to
        *project ms* via the FIRST clip whose source range covers the
        selection start (the user always selects within the visible
        clip body so this is unambiguous), then walk ``track.clips``
        and split / drop pieces that overlap the cut window. The
        legacy ``track.cuts`` list is still updated so the existing
        ffmpeg export path keeps working until video_exporter migrates
        to ``track.clips``.
        """
        track = self._find_track(track_id)
        if track is None:
            return
        s, e = track.selection_start_ms, track.selection_end_ms
        if s < 0 or e <= s:
            return

        # --- 1. Update the legacy cuts list (export path / migration) ---
        merged: list[CutSegment] = []
        new_start, new_end = s, e
        for c in track.cuts:
            overlaps = not (c.end_ms <= new_start or new_end <= c.start_ms)
            if overlaps:
                new_start = min(new_start, c.start_ms)
                new_end = max(new_end, c.end_ms)
            else:
                merged.append(c)
        track.speed_segments = [
            seg
            for seg in track.speed_segments
            if not seg.overlaps(new_start, new_end)
        ]
        merged.append(CutSegment(new_start, new_end))
        merged.sort(key=lambda c: c.start_ms)
        track.cuts = merged

        # --- 2. Mutate clips so the cut becomes two independent halves ---
        track.clips = cut_clip_window(
            track.clips, s, e, track_offset_ms=int(getattr(track, "offset_ms", 0) or 0),
        )
        track.clips_explicit = True

        track.selection_start_ms = -1
        track.selection_end_ms = -1
        self._refresh_player_tracks()
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._refresh_selection_row()
        self._register_change("cut")

    def _apply_speed_to_selection(self, speed: float) -> None:
        track = self._active_track()
        if track is None:
            return
        s, e = track.selection_start_ms, track.selection_end_ms
        if s < 0 or e <= s:
            return

        kept = [seg for seg in track.speed_segments if not seg.overlaps(s, e)]
        # Split existing segments that straddle the boundaries
        for seg in track.speed_segments:
            if seg.overlaps(s, e):
                if seg.start_ms < s:
                    kept.append(SpeedSegment(seg.start_ms, s, seg.speed))
                if seg.end_ms > e:
                    kept.append(SpeedSegment(e, seg.end_ms, seg.speed))
        kept.append(SpeedSegment(s, e, speed))
        kept.sort(key=lambda seg: seg.start_ms)
        track.speed_segments = kept

        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()

        if track.id == self._active_track_id:
            pos = self._player.position()
            if s <= pos < e:
                self._current_segment_speed = speed
                self._player.set_speed(speed)
                self.current_speed_label.setText(
                    tr("veditor.current_speed", speed=f"{speed:g}")
                )

    def _clear_selection_active_track(self) -> None:
        track = self._active_track()
        if track is None:
            return
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._refresh_selection_row()

    def _on_reset_active_track(self) -> None:
        track = self._active_track()
        if track is None:
            return
        track.speed_segments.clear()
        track.cuts.clear()
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        self._player.set_speed(1.0)
        self._current_segment_speed = 1.0
        self.current_speed_label.setText(
            tr("veditor.current_speed", speed="1.0")
        )
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._refresh_selection_row()

    # -------------- player integration --------------

    def _toggle_play(self) -> None:
        self._player.toggle()

    # ------------------ jog / shuttle (Phase 7) ------------------

    def _on_jog_delta(self, frames: int) -> None:
        """Inner ring rotated → advance the playhead by ``frames``
        frames (signed). Uses ``REFERENCE_FPS = 30`` like the rest of
        the player so each jog tick is ~33 ms — matches the visual
        granularity of the timeline ruler at default zoom."""
        if not self._tracks:
            return
        ms_per_frame = 1000.0 / 30.0  # ProjectPlayer.REFERENCE_FPS
        new_pos = self._player.position() + int(round(frames * ms_per_frame))
        self._player.set_position(new_pos)

    def _on_shuttle_speed_changed(self, speed: float) -> None:
        """Outer ring rotated → set the player's shuttle rate. ``0``
        pauses; positive values resume play at that multiplier;
        negative values clamp to pause until the player gains reverse
        playback support."""
        self._player.set_shuttle_rate(speed)
        if speed > 0.0 and self._player.state is not PlayerState.PLAYING:
            self._player.play()

    def _on_playback_state_changed(self, state) -> None:
        self.play_btn.setText("⏸" if state is PlayerState.PLAYING else "▶")

    def _on_frame_ready(self, qimg: QImage) -> None:
        # In audio-only projects the player still ticks (so AudioMixer
        # stays synced) and emits blank frames. Don't clobber the
        # "🎵 Sound only" placeholder in that case.
        has_video = any(
            t.source_path is not None or bool(t.clips)
            for t in self._tracks
        )
        if not has_video:
            return
        # Apply 3D LUT if one is loaded.
        if self._lut_data is not None:
            try:
                import numpy as np
                _qimg_lut = qimg.convertToFormat(QImage.Format.Format_RGB888)
                _ptr = _qimg_lut.constBits()
                _arr = np.frombuffer(_ptr, dtype=np.uint8).reshape(
                    _qimg_lut.height(), _qimg_lut.width(), 3
                ).copy()
                _arr = apply_lut(_arr, self._lut_data, self._lut_strength)
                _h, _w = _arr.shape[:2]
                qimg = QImage(
                    _arr.tobytes(), _w, _h, _w * 3, QImage.Format.Format_RGB888
                ).copy()
            except Exception:
                pass
        # Keep the clean original in _preview_pixmap so PaintDialog sees the
        # real frame; fade is applied only to the displayed scaled copy
        # inside _scale_preview_to_fit.
        self._preview_pixmap = QPixmap.fromImage(qimg)
        self._scale_preview_to_fit()
        self._update_subtitle_overlay(self._player.position())
        # Drawing canvas + subtitle overlay sit above both the QLabel
        # and the GL preview surface. Raise them every frame so any
        # auto-stacking from Qt doesn't put them behind.
        self._drawing_canvas.raise_()
        self._subtitle_overlay.raise_()
        self._drawing_canvas.update()
        # Mirror the frame to the pop-out window when one is open.
        if self._preview_popout is not None:
            try:
                self._preview_popout.update_frame(qimg)
            except Exception:
                pass
        # DaVinci-style live node thumbnails — push the latest frame
        # to the workbench's NodeGraph at ~10 Hz. Skip when the player
        # is in a black/blank region (no active clip at current position)
        # so clip deletions don't wipe out the node thumbnails.
        pos = self._player.position()
        _has_active = any(
            int(c.timeline_in_ms) <= pos <= int(c.timeline_out_ms)
            for t in self._tracks
            for c in getattr(t, "clips", [])
            if getattr(c, "source_path", None) is not None
        )
        if not _has_active:
            return
        from time import monotonic
        now_ms = monotonic() * 1000.0
        last_ms = getattr(self, "_last_node_thumb_ms", 0.0)
        if now_ms - last_ms >= 100.0:
            self._last_node_thumb_ms = now_ms
            wb = getattr(self, "_workbench_panel", None)
            if wb is not None and self._preview_pixmap is not None:
                try:
                    wb.set_node_thumbnail(self._preview_pixmap)
                except Exception:
                    pass

    def _on_gpu_frame_ready(self, rgb, grade) -> None:
        """Hand the raw RGB ndarray + optional ColorGrade to the OpenGL
        preview surface.

        ``grade`` is either a ``ColorGrade`` object (passed directly from
        ProjectPlayer for GPU shader grading) or ``None`` (frame is already
        fully composited CPU-side).  Legacy dict hints are also handled for
        backwards compatibility.
        """
        if rgb is None:
            return
        gl = getattr(self, "_preview_gl", None)
        if gl is None:
            return
        try:
            h, w = rgb.shape[:2]
            self._preview_gl_frame_size = (int(w), int(h))
        except Exception:
            pass
        if not gl.isVisible():
            gl.show()
            self._sync_preview_gl_geometry()

        # Resolve the grade object: accept ColorGrade directly or from a
        # legacy hint dict (the blur_sigma hint path has been removed).
        _real_grade = grade
        if isinstance(grade, dict):
            _real_grade = grade.get("grade", None)
        gl.set_blur(0.0)  # blur is CPU-applied; shader blur is disabled

        # Apply 3D LUT using precomputed cache (fast array indexing)
        _lut_cache = getattr(self, "_lut_cache", None)
        if _lut_cache is not None:
            try:
                import numpy as _np
                lut_strength = getattr(self, "_lut_strength", 1.0)
                _is_float = rgb.dtype in (_np.float32, _np.float64)
                _max_1 = _is_float and float(rgb.max()) <= 1.01
                if _is_float:
                    rgb_u8 = _np.clip(rgb * (255 if _max_1 else 1), 0, 255).astype(_np.uint8)
                else:
                    rgb_u8 = _np.asarray(rgb, dtype=_np.uint8)
                # Fast lookup: cache[r, g, b] → new [r, g, b]
                r, g, b = rgb_u8[:,:,0], rgb_u8[:,:,1], rgb_u8[:,:,2]
                lut_out = _lut_cache[r, g, b]  # shape (H, W, 3)
                if lut_strength < 1.0:
                    lut_out = (rgb_u8 * (1 - lut_strength) + lut_out * lut_strength).astype(_np.uint8)
                if _is_float:
                    rgb = lut_out.astype(rgb.dtype) / (255.0 if _max_1 else 1.0)
                else:
                    rgb = lut_out
            except Exception:
                pass
        gl.update_frame(rgb, _real_grade)

        # Forward live frame + grade to the Color Page window when open.
        cpw = getattr(self, "_color_page_window", None)
        if cpw is not None and cpw.isVisible():
            try:
                cpw.update_frame(rgb, _real_grade)
            except Exception:
                pass

    def _toggle_preview_popout(self) -> None:
        """Open a separate top-level preview window (for multi-monitor
        full-screen viewing), or close it and return focus here."""
        if self._preview_popout is not None:
            self._preview_popout.close()
            return
        popout = PreviewPopoutWindow()
        popout.closed.connect(self._on_preview_popout_closed)
        popout.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # Seed the popout with the latest frame if one is cached, so
        # users don't see a black box until the next tick.
        if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
            popout.update_frame(self._preview_pixmap.toImage())
        popout.show()
        self._preview_popout = popout
        self.popout_btn.setProperty("popped", True)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip_docked"))
        self.popout_btn.style().unpolish(self.popout_btn)
        self.popout_btn.style().polish(self.popout_btn)

    def _on_preview_popout_closed(self) -> None:
        self._preview_popout = None
        self.popout_btn.setProperty("popped", False)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
        self.popout_btn.style().unpolish(self.popout_btn)
        self.popout_btn.style().polish(self.popout_btn)

    def _current_fade_multiplier(self, pos_ms: int) -> float:
        """1.0 = full brightness, 0.0 = black. Picks whichever fade on the
        active track contains ``pos_ms`` (project time) and computes its
        in/out multiplier based on kind."""
        track = self._active_track()
        if track is None or not track.fades:
            return 1.0
        local = pos_ms - getattr(track, "offset_ms", 0)
        for fade in track.fades:
            if not fade.contains(local):
                continue
            span = fade.duration_ms
            if span <= 0:
                return 1.0
            t = (local - fade.start_ms) / span  # 0..1 within the fade
            kind = getattr(fade, "kind", "both")
            if kind == "in":
                return t
            if kind == "out":
                return 1.0 - t
            # both: content→black→content
            return 1.0 - 2.0 * abs(t - 0.5)
        return 1.0

    def _update_subtitle_overlay(self, pos_ms: int) -> None:
        sub = self._subtitle_panel.active_subtitle(pos_ms)
        if sub is None or not sub.text.strip():
            self._subtitle_overlay.hide()
            return
        self._subtitle_overlay.setText(sub.text)
        if sub.show_box:
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; "
                "background-color: rgba(0, 0, 0, 180); "
                "padding: 6px 14px; border-radius: 4px; "
                "font-size: 18px; font-weight: 600; }"
            )
        else:
            # No background box — use a text-shadow-like effect via font weight.
            # Qt QLabel has no native text-shadow, but heavier font + white on
            # most content is legible; the export step adds a real outline.
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; "
                "background-color: transparent; "
                "padding: 4px 10px; "
                "font-size: 20px; font-weight: 900; }"
            )
        self._reposition_subtitle_overlay()
        self._subtitle_overlay.show()

    def _reposition_subtitle_overlay(self) -> None:
        host = self._preview_host
        host_size = host.size()
        self._subtitle_overlay.adjustSize()
        ov_w = min(int(host_size.width() * 0.9), max(200, self._subtitle_overlay.width()))
        ov_h = self._subtitle_overlay.heightForWidth(ov_w)
        if ov_h <= 0:
            ov_h = self._subtitle_overlay.height()
        x = (host_size.width() - ov_w) // 2
        y = host_size.height() - ov_h - 12
        self._subtitle_overlay.setFixedWidth(ov_w)
        self._subtitle_overlay.move(max(0, x), max(0, y))

    def _on_subtitles_changed(self) -> None:
        self._update_subtitle_overlay(self._player.position())
        self._register_change("subtitle edit")

    # ------------------ AI subtitle generation (Whisper) ------------------

    def _generate_ai_subtitles(self) -> None:
        """Open WhisperDialog to auto-generate subtitles for the active track."""
        # ── Check Whisper availability ────────────────────────────────────
        has_whisper = False
        try:
            import faster_whisper  # noqa: F401
            has_whisper = True
        except ImportError:
            try:
                import whisper  # noqa: F401
                has_whisper = True
            except ImportError:
                pass

        if not has_whisper:
            ret = QMessageBox.question(
                self,
                "AI 자막",
                "Whisper가 설치되지 않았습니다.\n"
                "pip install faster-whisper 를 실행한 후 다시 시도하세요.\n\n"
                "지금 설치하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                import subprocess
                import sys
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "faster-whisper"],
                    check=False,
                )
            return

        # ── Resolve video path ────────────────────────────────────────────
        path: Path | None = None
        if self._active_track_id is not None:
            t = self._find_track(self._active_track_id)
            if t and t.source_path:
                path = t.source_path
        if path is None:
            for t in self._tracks:
                if t.source_path:
                    path = t.source_path
                    break
        if path is None:
            # Try the first clip source across all tracks
            for t in self._tracks:
                for clip in t.clips:
                    if getattr(clip, "source_path", None):
                        path = clip.source_path
                        break
                if path:
                    break

        if path is None:
            QMessageBox.warning(self, "AI 자막", "먼저 영상을 타임라인에 올려주세요.")
            return

        # ── Run dialog ────────────────────────────────────────────────────
        dlg = WhisperDialog(path, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            segments = dlg.segments
            if not segments:
                return
            from app.subtitles import Subtitle
            layer = self._subtitle_panel.layer
            count = 0
            for seg in segments:
                try:
                    sub = Subtitle(
                        text=seg["text"],
                        start_ms=int(seg["start"] * 1000),
                        end_ms=int(seg["end"] * 1000),
                    )
                    layer.add(sub)
                    count += 1
                except Exception:
                    pass
            try:
                self._subtitle_panel._refresh_list()
            except Exception:
                pass
            try:
                self._subtitle_panel.subtitles_changed.emit()
            except Exception:
                pass
            try:
                self._on_subtitles_changed()
            except Exception:
                pass
            QMessageBox.information(
                self, "AI 자막", f"자막 {count}개 생성 완료!"
            )

    # ------------------ undo / redo (Ctrl+Z / Ctrl+Shift+Z) ------------------

    def _register_change(self, label: str = "") -> None:
        """Capture the editor's state and push it onto the history
        stack. Called at gesture-end sites — cut, clip drag commit,
        subtitle add/edit/delete, workbench fade tweak.

        ``_history_suspended`` is set during ``_on_undo`` / ``_on_redo``
        so applying a snapshot doesn't itself record a new history
        entry (which would push a redundant copy of the snapshot we
        just restored)."""
        if self._history_suspended:
            return
        from app.history import capture_editor_snapshot
        self._history.push(capture_editor_snapshot(self), label=label)

    def _on_undo(self) -> None:
        snap = self._history.undo()
        if snap is None:
            return
        self._apply_history_snapshot(snap)

    def _on_redo(self) -> None:
        snap = self._history.redo()
        if snap is None:
            return
        self._apply_history_snapshot(snap)

    # ---- Option C: blade + ripple delete + selection ----

    def _is_text_focus(self) -> bool:
        """Return True when a text-entry widget owns focus, so global
        editing shortcuts (B / C / Delete / Backspace) don't fight
        with normal typing in subtitle dialogs, workbench panels,
        node-rename modals, etc."""
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QLineEdit,
            QPlainTextEdit,
            QSpinBox,
            QTextEdit,
        )
        fw = QApplication.focusWidget()
        if fw is None:
            return False
        return isinstance(fw, (
            QLineEdit, QTextEdit, QPlainTextEdit,
            QSpinBox, QComboBox,
        ))

    def _blade_at_playhead(self) -> None:
        """DaVinci / Premiere style blade — splits whichever video
        clips contain the playhead, across *every* video track. No-op
        when the playhead lands on a boundary or sits in a gap on
        every track. Shows a user-visible hint instead of failing
        silently when nothing splittable is under the playhead."""
        if self._is_text_focus():
            return
        if not self._tracks:
            self._flash_status(tr("veditor.blade.flash.no_tracks"))
            return
        from app.timeline_model import split_clips_at_project_ms
        playhead_ms = self._player.position()
        any_cut = False
        for track in self._tracks:
            clips = getattr(track, "clips", None)
            if not clips:
                continue
            before = len(clips)
            track.clips = split_clips_at_project_ms(clips, playhead_ms)
            track.clips_explicit = True
            if len(track.clips) != before:
                any_cut = True
                row = self._track_rows.get(track.id)
                if row is not None:
                    row.update()
        if not any_cut:
            self._flash_status(tr("veditor.blade.flash.no_clip"))
            return
        self._refresh_player_tracks()
        self._register_change("blade")

    def _tick_blade_dash(self) -> None:
        """Advance the marching-ants offset for blade markers and clip
        selection animation. Repaint only rows that actually need it."""
        self._blade_dash_offset = (self._blade_dash_offset + 1) % 8
        # Video track rows
        for row in self._track_rows.values():
            clips = getattr(row.track, "clips", None)
            needs_paint = False
            if clips and len(clips) >= 2:
                needs_paint = True
            if row._selected_clip_ids:
                row._march_offset = (row._march_offset + 2) % 12
                needs_paint = True
            if needs_paint:
                row.update()
        # Audio track rows — march ants on active (selected) clip
        for arow in self._audio_rows.values():
            if arow._active_clip_id is not None:
                arow._march_offset = (arow._march_offset + 2) % 12
                arow.update()

    def _flash_status(self, msg: str) -> None:
        """Show a brief banner near the timeline toolbar — replaces a
        QToolTip-based version that was unreliable on some Windows
        setups (no movement → tooltip suppressed)."""
        if not hasattr(self, "_status_banner"):
            from PySide6.QtCore import QTimer
            self._status_banner = QLabel(self)
            self._status_banner.setObjectName("StatusBanner")
            self._status_banner.setStyleSheet(
                "QLabel#StatusBanner {"
                f" background-color: {COLOR_ACCENT_ORANGE};"
                " color: white; font-weight: 600; font-size: 13px;"
                " padding: 8px 16px; border-radius: 6px; }"
            )
            self._status_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._status_banner.hide()
            self._status_banner_timer = QTimer(self)
            self._status_banner_timer.setSingleShot(True)
            self._status_banner_timer.timeout.connect(self._status_banner.hide)
        self._status_banner.setText(msg)
        self._status_banner.adjustSize()
        # Center horizontally, anchor to top-third of the editor.
        x = max(0, (self.width() - self._status_banner.width()) // 2)
        y = self.height() // 3
        self._status_banner.move(x, y)
        self._status_banner.raise_()
        self._status_banner.show()
        self._status_banner_timer.start(1800)

    def _ripple_delete_selected(self) -> None:
        """Delete every selected clip and ripple subsequent clips
        left to close the gap (DaVinci / Premiere "Shift+Delete")."""
        # Don't fire when the user's deleting characters in a text
        # field — Delete is the universal "remove next character"
        # binding and a global shortcut would steal it.
        if self._is_text_focus():
            return
        # If a typography actor is selected, delete it first.
        if getattr(self, "_selected_typo", None) is not None:
            self._delete_selected_typo_actor()
            return
        if not self._selected_clips:
            return
        from app.timeline_model import ripple_delete_clips
        # Group by track so we run one ripple per track.
        by_track: dict[int, set[int]] = {}
        for tid, cid in self._selected_clips:
            by_track.setdefault(tid, set()).add(cid)
        any_change = False
        tracks_to_delete: list[int] = []
        for tid, ids in by_track.items():
            track = self._find_track(tid)
            if track is None or not getattr(track, "clips", None):
                continue
            new_clips = ripple_delete_clips(track.clips, ids)
            if len(new_clips) != len(track.clips):
                any_change = True
                if not new_clips:
                    # Last clip deleted — remove the entire track (CapCut style)
                    tracks_to_delete.append(tid)
                else:
                    track.clips = new_clips
                    track.clips_explicit = True
                    row = self._track_rows.get(tid)
                    if row is not None:
                        row.set_selected_clip_ids(set())
                        row.update()
        # Delete empty tracks (must keep at least 1 video track)
        for tid in tracks_to_delete:
            if len(self._tracks) > 1:
                self._delete_track(tid)
            else:
                # Only one video track: clear clips + source_path so it
                # shows the "drag video here" empty-slot state, not black.
                track = self._find_track(tid)
                if track is not None:
                    track.clips = []
                    track.clips_explicit = True
                    track.source_path = None
                    track.duration_ms = 0
                    row = self._track_rows.get(tid)
                    if row is not None:
                        row.set_selected_clip_ids(set())
                        row._recalc_width()
                        row.update()
                    self._update_tracks_host_width()
        self._selected_clips.clear()
        if any_change:
            self._refresh_player_tracks()
            self._register_change("ripple delete")

    def _on_clip_clicked(
        self, track_id: int, clip_id: int, shift_held: bool,
    ) -> None:
        """TrackRow forwards a clip click here. Shift toggles a clip
        in/out of the selection (multi-select); a plain click
        replaces the selection with a single clip."""
        # Take ownership of the ants — clears audio ants globally.
        import sys as _sys
        _sys.modules[__name__]._ANTS_OWNER = "video"
        key = (int(track_id), int(clip_id))
        if shift_held:
            if key in self._selected_clips:
                self._selected_clips.remove(key)
            else:
                self._selected_clips.append(key)
        else:
            self._selected_clips = [key]
        self._broadcast_clip_selection()

    def _on_track_empty_area_clicked(self, track_id: int) -> None:
        """Click on a track row's blank area clears the selection
        (matches NLE convention — selection is "sticky" until you
        click off it)."""
        if self._selected_clips:
            self._selected_clips.clear()
            self._broadcast_clip_selection()

    def _broadcast_clip_selection(self) -> None:
        """Push the current selection set down to every TrackRow so
        the Tiger Orange selection border updates."""
        per_track: dict[int, set[int]] = {}
        for tid, cid in self._selected_clips:
            per_track.setdefault(tid, set()).add(cid)
        for tid, row in self._track_rows.items():
            row.set_selected_clip_ids(per_track.get(tid, set()))
            row.update()

    # ---- Option C: global I/O markers ----

    def _set_global_in(self, ms: int) -> None:
        self._global_in_ms = max(0, int(ms))
        # If OUT is to the left of IN, push OUT to match (Premiere does
        # this — keeps the marker order monotonic).
        if 0 <= self._global_out_ms < self._global_in_ms:
            self._global_out_ms = self._global_in_ms
        self._timeline_ruler.set_global_markers(
            self._global_in_ms, self._global_out_ms,
        )

    def _set_global_out(self, ms: int) -> None:
        self._global_out_ms = max(0, int(ms))
        if 0 <= self._global_in_ms > self._global_out_ms:
            self._global_in_ms = self._global_out_ms
        self._timeline_ruler.set_global_markers(
            self._global_in_ms, self._global_out_ms,
        )

    def _clear_global_markers(self) -> None:
        self._global_in_ms = -1
        self._global_out_ms = -1
        self._timeline_ruler.set_global_markers(-1, -1)

    # ---- Timeline markers (M key / ♦ M button) ----

    def _add_marker_at_playhead(self) -> None:
        """Add a colored triangle marker at the current playhead position."""
        ms = self._player.position()
        color = self._MARKER_COLORS[len(self._timeline_markers) % len(self._MARKER_COLORS)]
        self._timeline_markers.append({"ms": int(ms), "color": color, "label": ""})
        self._sync_markers_to_ruler()

    def _delete_timeline_marker(self, index: int) -> None:
        """Remove the marker at ``index`` (emitted by TimelineRuler right-click)."""
        if 0 <= index < len(self._timeline_markers):
            del self._timeline_markers[index]
            self._sync_markers_to_ruler()

    def _sync_markers_to_ruler(self) -> None:
        """Push the current marker list to the ruler widget and update all
        track rows with the new set of extra snap targets."""
        self._timeline_ruler.set_timeline_markers(self._timeline_markers)
        self._push_snap_targets_to_rows()

    def _push_snap_targets_to_rows(self) -> None:
        """Collect playhead + marker ms values and push them to every
        TrackRow so clip drags snap to these positions as well."""
        targets: list[int] = [self._player.position()]
        for m in self._timeline_markers:
            targets.append(int(m["ms"]))
        for row in self._track_rows.values():
            row.set_extra_snap_targets(targets)

    def _on_workbench_node_focused(self, kind: str) -> None:
        """User clicked a NodeGraph row in the Workbench. Today the
        ColorNode is the only kind; route the click to the Color
        section by either popping it out (if it's still docked) or
        raising the existing popout window."""
        if kind == "color":
            already_open = (
                self._color_popout is not None
                and self._color_popout.isVisible()
            )
            if already_open:
                self._color_popout.raise_()
                self._color_popout.activateWindow()
            else:
                self._toggle_color_popout()

    def _apply_history_snapshot(self, snap) -> None:
        """Drive ``apply_editor_snapshot`` and refresh every view that
        depends on track / subtitle state. Suspends history capture
        so the restore doesn't push a duplicate entry."""
        from app.history import apply_editor_snapshot
        self._history_suspended = True
        try:
            apply_editor_snapshot(self, snap)
            # Repaint each track row + audio row so geometry / clip
            # rectangles match the restored state.
            for row in self._track_rows.values():
                row._recalc_width()
                row.update()
            for row in self._audio_rows.values():
                row.refresh_from_track()
            # Player must rebuild its clip view cache against the
            # restored ``track.clips`` lists.
            self._refresh_player_tracks()
            self._refresh_workbench()
            self._update_subtitle_overlay(self._player.position())
            if hasattr(self, "_subtitle_lane"):
                self._subtitle_lane.update()
            self._update_tracks_host_width()
        finally:
            self._history_suspended = False

    def _on_subtitle_lane_edit(self, idx: int) -> None:
        """Phase 5 Step B: double-click on a subtitle lane rect opens
        the same modal editor the panel uses, so timing tweaks via
        drag and text edits via dialog stay consistent."""
        layer = self._subtitle_panel.layer
        items = layer.items()
        if idx < 0 or idx >= len(items):
            return
        from app.subtitles import SubtitleEditDialog
        max_ms = max(self._player.duration(), 0)
        dlg = SubtitleEditDialog(self, items[idx], max_ms)
        if dlg.exec():
            layer.replace_at(idx, dlg.result_subtitle())
            self._on_subtitles_changed()

    # ---------- drawing ----------

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_preview_label", None) or \
                obj is getattr(self, "_preview_gl", None):
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._open_paint_dialog()
                    return True
                if event.button() == Qt.MouseButton.RightButton:
                    self._show_preview_context_menu(event.globalPosition().toPoint())
                    return True
        # Wheel over the tracks area zooms the timeline (clip length).
        # Guard: eventFilter may fire during UI build before the scroll area
        # has been constructed.
        scroll = getattr(self, "_tracks_scroll", None)
        if (
            scroll is not None
            and obj is scroll.viewport()
            and event.type() == event.Type.Wheel
        ):
            delta = event.angleDelta().y()
            if delta > 0:
                self._change_zoom(1.2)
            elif delta < 0:
                self._change_zoom(1 / 1.2)
            return True
        return super().eventFilter(obj, event)

    def _show_preview_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        clear_action = menu.addAction(tr("paint.btn.clear_all"))
        clear_action.setEnabled(bool(self._strokes))
        chosen = menu.exec(global_pos)
        if chosen is clear_action:
            self._strokes.clear()
            self._drawing_canvas.update()

    def _open_paint_dialog(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        # Pause playback while drawing so the background stays fixed.
        was_playing = self._player.state() is PlayerState.PLAYING
        if was_playing:
            self._player.pause()

        from app.drawing import PaintDialog

        # Hide preview bubble / sticker items while editing in the
        # dialog; respawn after so the dialog owns the interactive
        # version during the edit.
        for item in list(self._bubble_items):
            item.deleteLater()
        self._bubble_items.clear()
        for item in list(self._sticker_items):
            item.deleteLater()
        self._sticker_items.clear()

        dlg = PaintDialog(
            background_pixmap=self._preview_pixmap,
            initial_strokes=self._strokes,
            time_ms=self._player.position(),
            parent=self,
            initial_bubbles=self._bubbles,
            initial_stickers=self._stickers,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._strokes = dlg.result_strokes()
            self._bubbles = dlg.result_bubbles()
            self._stickers = dlg.result_stickers()
            self._drawing_canvas.update()
        # Respawn passive items so the user sees bubbles / stickers on
        # the preview.
        for sticker in self._stickers:
            self._spawn_sticker_item(sticker)
        for bubble in self._bubbles:
            self._spawn_bubble_item(bubble)
        self._update_bubble_visibility(self._player.position())
        self._update_sticker_visibility(self._player.position())

    # ------------- speech bubbles -------------

    def _spawn_bubble_item(self, bubble: SpeechBubble) -> SpeechBubbleItem:
        # Parent to the drawing canvas (already sized to the video rect), so
        # normalized coords map to the actual video area, not letterbox.
        item = SpeechBubbleItem(bubble, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_bubble())
        item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
        self._bubble_items.append(item)
        return item

    def _remove_bubble(self, bubble: SpeechBubble, item: SpeechBubbleItem) -> None:
        try:
            self._bubbles.remove(bubble)
        except ValueError:
            pass
        try:
            self._bubble_items.remove(item)
        except ValueError:
            pass
        item.deleteLater()

    def _resync_bubbles_to_preview(self) -> None:
        for item in self._bubble_items:
            item.sync_to_parent()

    def _update_bubble_visibility(self, pos_ms: int) -> None:
        for item in self._bubble_items:
            item.setVisible(item.bubble.start_ms <= int(pos_ms))

    # ------------- stickers -------------

    def _spawn_sticker_item(self, sticker):
        from app.drawing import StickerItem
        item = StickerItem(sticker, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_sticker())
        item.deleted.connect(lambda it=item, s=sticker: self._remove_sticker(s, it))
        item.duplicated.connect(lambda s=sticker: self._duplicate_sticker(s))
        item.raise_requested.connect(lambda s=sticker: self._reorder_sticker(s, +1))
        item.lower_requested.connect(lambda s=sticker: self._reorder_sticker(s, -1))
        self._sticker_items.append(item)
        # Bubbles stay on top of stickers.
        for b_item in self._bubble_items:
            b_item.raise_()
        return item

    def _remove_sticker(self, sticker, item) -> None:
        try:
            self._stickers.remove(sticker)
        except ValueError:
            pass
        try:
            self._sticker_items.remove(item)
        except ValueError:
            pass
        item.deleteLater()

    def _duplicate_sticker(self, sticker) -> None:
        import copy
        dup = copy.deepcopy(sticker)
        dup.x_norm = min(0.95, dup.x_norm + 0.03)
        dup.y_norm = min(0.95, dup.y_norm + 0.03)
        current_max = max((s.z_index for s in self._stickers), default=0)
        dup.z_index = current_max + 1
        self._stickers.append(dup)
        self._spawn_sticker_item(dup)
        self._update_sticker_visibility(self._player.position())

    def _reorder_sticker(self, sticker, direction: int) -> None:
        if direction > 0:
            sticker.z_index = max(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) + 1
        else:
            sticker.z_index = min(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) - 1
        self._sticker_items.sort(key=lambda it: int(it.sticker.z_index))
        for it in self._sticker_items:
            it.raise_()
        for b_item in self._bubble_items:
            b_item.raise_()

    def _resync_stickers_to_preview(self) -> None:
        for item in self._sticker_items:
            item.sync_to_parent()

    def _update_sticker_visibility(self, pos_ms: int) -> None:
        from app.drawing import _sticker_active
        t = int(pos_ms)
        for item in self._sticker_items:
            item.setVisible(_sticker_active(item.sticker, t))

    # ------------- typography (Phase 1) -------------

    def _ensure_text_preview_label(self) -> QLabel:
        """Lazily create the QLabel used to render the active text
        clip on top of the preview. Parented to the drawing canvas so
        it shares the canvas's coordinate system (which already maps
        1:1 with the video rect)."""
        if self._text_preview_label is None:
            lbl = QLabel(self._drawing_canvas)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: transparent; color: white;")
            lbl.hide()
            self._text_preview_label = lbl
        return self._text_preview_label

    def _find_typography_actor(self, clip_id: int) -> "tuple[VideoTrack, TextClip] | None":
        """Locate a typography actor by its id across every video track."""
        for track in self._tracks:
            for clip in getattr(track, "typography_actors", []):
                if clip.id == clip_id:
                    return track, clip
        return None

    def _update_text_clip_overlay(self, pos_ms: int) -> None:
        """Show / hide / restyle the preview text based on active
        typography actors at ``pos_ms``. Phase 1: static render of the
        topmost active actor (no animations yet).

        Typography actors live per-VideoTrack in track-local source ms.
        Active-check: track-local time = project_ms - track.offset_ms,
        valid when 0 <= local < track.duration_ms and actor.contains(local).
        """
        lbl = self._ensure_text_preview_label()
        project_ms = int(pos_ms)

        active: list[TextClip] = []
        for track in self._tracks:
            if track.source_path is None or track.duration_ms <= 0:
                continue
            local = project_ms - int(track.offset_ms)
            if local < 0 or local >= track.duration_ms:
                continue
            for clip in getattr(track, "typography_actors", []):
                if clip.contains(local):
                    active.append(clip)

        if not active:
            lbl.hide()
            return

        # Last registered wins — drawn on top. Future phases may honor
        # per-actor z-order the way stickers do.
        clip = active[-1]
        style = clip.style
        canvas = self._drawing_canvas
        cw, ch = canvas.width(), canvas.height()
        if cw <= 0 or ch <= 0:
            lbl.hide()
            return

        font = QFont(style.font_family, int(style.font_size * ch / 1080.0))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        lbl.setFont(font)
        lbl.setStyleSheet(
            f"background: transparent; color: {style.color};"
            " font-weight: 700;"
        )
        lbl.setText(clip.display_text())
        lbl.adjustSize()

        lw = min(int(cw * 0.9), max(40, lbl.width()))
        lh = max(30, lbl.height())
        cx = int(style.position_x * cw)
        cy = int(style.position_y * ch)
        lbl.setGeometry(cx - lw // 2, cy - lh // 2, lw, lh)
        lbl.show()
        lbl.raise_()

    def _on_typography_actor_selected(self, track_id: int, actor_id: int) -> None:
        """Store selected typography actor for Delete key handling."""
        self._selected_typo = (track_id, actor_id)

    def _delete_selected_typo_actor(self) -> None:
        """Delete the currently selected typography actor (Delete key)."""
        sel = getattr(self, "_selected_typo", None)
        if sel is None:
            return
        track_id, actor_id = sel
        track = self._find_track(track_id)
        if track is None:
            return
        actors = getattr(track, "typography_actors", [])
        new_actors = [a for a in actors if a.id != actor_id]
        if len(new_actors) != len(actors):
            track.typography_actors = new_actors
            self._selected_typo = None
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._update_text_clip_overlay(self._player.position())
            self._register_change("delete typography actor")

    def _on_typography_changed(self, track_id: int) -> None:
        """Called after any drag/resize/drop/add/remove of a typography
        actor on any video track."""
        self._update_tracks_host_width()
        self._update_text_clip_overlay(self._player.position())

    def _open_typography_editor(self, track_id: int, clip_id: int) -> None:
        """Double-click handler — opens the (Phase 1 stub) editor for
        the typography actor. Phase 2 replaces this with the full 3-pane
        modal."""
        found = self._find_typography_actor(clip_id)
        if found is None:
            return
        _track, clip = found
        dlg = TypographyEditorDialog(clip, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._update_text_clip_overlay(self._player.position())

    def _show_typography_menu(self, track_id: int, clip_id: int, global_pos) -> None:
        from PySide6.QtWidgets import QMenu

        found = self._find_typography_actor(clip_id)
        if found is None:
            return
        track, clip = found
        menu = QMenu(self)
        a_edit = menu.addAction(tr("veditor.typo_menu.edit"))
        a_dup = menu.addAction(tr("veditor.typo_menu.duplicate"))
        menu.addSeparator()
        a_del = menu.addAction(tr("veditor.typo_menu.delete"))

        chosen = menu.exec(global_pos)
        if chosen is a_edit:
            self._open_typography_editor(track_id, clip_id)
        elif chosen is a_dup:
            import copy
            dup = copy.deepcopy(clip)
            from app.typography import _next_id
            dup.id = _next_id()
            # Nudge so the copy shows up after the original.
            dup.start_ms = clip.end_ms
            dup.end_ms = dup.start_ms + clip.duration_ms
            if dup.end_ms > track.duration_ms:
                dup.end_ms = track.duration_ms
                dup.start_ms = max(0, dup.end_ms - clip.duration_ms)
            track.typography_actors.append(dup)
            track.typography_actors.sort(key=lambda c: c.start_ms)
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_typography_changed(track_id)
        elif chosen is a_del:
            track.typography_actors = [
                c for c in track.typography_actors if c.id != clip_id
            ]
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_typography_changed(track_id)

    # ---- zoom actor handlers ----

    def _find_zoom_actor(self, track_id: int, zactor_id: int) -> "tuple[VideoTrack, ZoomActor] | None":
        for t in self._tracks:
            if t.id != track_id:
                continue
            for z in t.zoom_actors:
                if z.id == zactor_id:
                    return t, z
        return None

    def _on_track_zoom_changed(self, track_id: int) -> None:
        """Called after any drag/resize/drop/add/remove of a zoom actor
        on any video track. Triggers a preview repaint at the current
        position so the new zoom (or its absence) shows immediately."""
        self._update_tracks_host_width()
        self._player.set_position(self._player.position())

    # ---- color section pop-out ----

    def _toggle_color_popout(self) -> None:
        """Detach / re-attach the color section. Same widget tree
        moves between the editor root layout and a floating window
        — sliders/wheels keep their state across the transition."""
        if self._color_popout is not None and self._color_popout.isVisible():
            self._color_popout.close()
            return
        self._color_popout = ColorPopoutWindow(self)
        self._color_popout.closed.connect(self._on_color_popout_closed)
        # Replace in-editor host with a placeholder so the rest of
        # the editor's layout doesn't collapse upward.
        self._color_root_layout.removeWidget(self._color_row_host)
        self._color_placeholder = QLabel(tr("veditor.color_popout.placeholder"))
        self._color_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._color_placeholder.setMinimumHeight(80)
        self._color_placeholder.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
            f"background-color: {COLOR_BG_L2}; "
            f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
        )
        self._color_root_layout.insertWidget(
            self._color_root_index, self._color_placeholder,
        )
        # Move the host into the popout and show it.
        self._color_popout.install(self._color_row_host)
        self._color_popout.show()
        self._color_popout.raise_()
        self._color_popout.activateWindow()

    def _on_color_popout_closed(self) -> None:
        """Pop-out window closing → restore the host into the editor."""
        if self._color_placeholder is not None:
            idx = self._color_root_layout.indexOf(self._color_placeholder)
            self._color_root_layout.removeWidget(self._color_placeholder)
            self._color_placeholder.deleteLater()
            self._color_placeholder = None
        else:
            idx = self._color_root_index
        # Reparent back to the editor.
        self._color_row_host.setParent(self.parent_widget_for_color())
        self._color_root_layout.insertWidget(
            max(0, idx), self._color_row_host,
        )
        self._color_row_host.show()
        if self._color_popout is not None:
            self._color_popout.deleteLater()
            self._color_popout = None

    def parent_widget_for_color(self) -> QWidget:
        """The widget that owns the color row when not popped out.
        Returns ``self`` so reparenting happens to the editor
        window itself; Qt's layout system then re-installs it under
        the right parent on the next insertWidget call."""
        return self

    # ---- timeline section pop-out ----

    def _toggle_timeline_popout(self) -> None:
        """Detach / re-attach the timeline section. Whole timeline host
        (ruler + tracks + audio rows) moves between the editor's main
        column and a floating window — track state, signal connections,
        and selection are all preserved across the transition."""
        if (
            self._timeline_popout is not None
            and self._timeline_popout.isVisible()
        ):
            self._timeline_popout.close()
            return
        self._timeline_popout = TimelinePopoutWindow(self)
        self._timeline_popout.closed.connect(self._on_timeline_popout_closed)
        # Replace in-editor timeline with a placeholder so the surrounding
        # layout doesn't snap closed.  The timeline host now lives inside the
        # QSplitter (_color_timeline_splitter at index 1), so we operate on
        # the splitter rather than the root VBoxLayout.
        splitter = getattr(self, "_color_timeline_splitter", None)
        if splitter is not None:
            # Find the index of _timeline_section_host inside the splitter.
            self._timeline_root_index = splitter.indexOf(self._timeline_section_host)
            self._timeline_section_host.setParent(self)
        else:
            self._timeline_root_layout.removeWidget(self._timeline_section_host)
        self._timeline_placeholder = QLabel(
            tr("veditor.timeline_popout.placeholder"),
        )
        self._timeline_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timeline_placeholder.setMinimumHeight(120)
        self._timeline_placeholder.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
            f"background-color: {COLOR_BG_L2}; "
            f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
        )
        if splitter is not None:
            splitter.insertWidget(self._timeline_root_index, self._timeline_placeholder)
        else:
            self._timeline_root_layout.insertWidget(
                self._timeline_root_index, self._timeline_placeholder, stretch=1,
            )
        self._timeline_popout.install(self._timeline_section_host)
        self._timeline_popout.show()
        self._timeline_popout.raise_()
        self._timeline_popout.activateWindow()

    def _on_timeline_popout_closed(self) -> None:
        splitter = getattr(self, "_color_timeline_splitter", None)
        if self._timeline_placeholder is not None:
            if splitter is not None:
                idx = splitter.indexOf(self._timeline_placeholder)
                self._timeline_placeholder.setParent(None)
            else:
                idx = self._timeline_root_layout.indexOf(self._timeline_placeholder)
                self._timeline_root_layout.removeWidget(self._timeline_placeholder)
            self._timeline_placeholder.deleteLater()
            self._timeline_placeholder = None
        else:
            idx = self._timeline_root_index
        self._timeline_section_host.setParent(self)
        if splitter is not None:
            splitter.insertWidget(max(0, idx), self._timeline_section_host)
        else:
            self._timeline_root_layout.insertWidget(
                max(0, idx), self._timeline_section_host, stretch=1,
            )
        self._timeline_section_host.show()
        if self._timeline_popout is not None:
            self._timeline_popout.deleteLater()
            self._timeline_popout = None

    # ---- Color Page (full-screen workspace) ----

    def _switch_page(self, page: str) -> None:
        """Toggle the page switcher buttons and open/close the Color Page."""
        is_color = (page == "color")
        self._page_edit_btn.setChecked(not is_color)
        self._page_color_btn.setChecked(is_color)
        if is_color:
            self._open_color_page()
        else:
            self._close_color_page()

    def _open_color_page(self) -> None:
        """Open (or raise) the full-screen Color Page window."""
        if self._color_page_window is None:
            from app.color_page_window import ColorPageWindow
            self._color_page_window = ColorPageWindow(self)
            self._color_page_window.grade_changed.connect(
                self._on_color_page_grade_changed
            )
            self._color_page_window.destroyed.connect(
                self._on_color_page_closed
            )
        self._color_page_window.show()
        self._color_page_window.raise_()
        self._color_page_window.activateWindow()
        # Push current grade into the page
        try:
            grade = self._active_color_grade()
            if grade is not None:
                self._color_page_window.update_grade(grade)
        except Exception:
            pass

    def _close_color_page(self) -> None:
        if self._color_page_window is not None:
            self._color_page_window.close()

    def _on_color_page_closed(self) -> None:
        self._color_page_window = None
        btn = getattr(self, "_page_color_btn", None)
        if btn is not None:
            btn.setChecked(False)
        btn2 = getattr(self, "_page_edit_btn", None)
        if btn2 is not None:
            btn2.setChecked(True)

    def _on_color_page_grade_changed(self, grade) -> None:
        """Relay grade changes made in the Color Page back to the editor."""
        try:
            self._on_color_wheel_changed.__func__  # check exists
        except AttributeError:
            pass
        # Sync all editor color-panel widgets without retriggering the page
        try:
            self._sync_color_panel()
        except Exception:
            pass
        # Ask the player to redraw
        try:
            self._player.refresh_current_frame()
        except Exception:
            pass

    # ---- subtitle section pop-out ----

    def _toggle_subtitle_popout(self) -> None:
        """Detach / re-attach the subtitle dock — same reparent
        pattern as colour / timeline. The right dock leaves a
        placeholder behind so its layout doesn't snap closed."""
        if (
            self._subtitle_popout is not None
            and self._subtitle_popout.isVisible()
        ):
            self._subtitle_popout.close()
            return
        self._subtitle_popout = SubtitlePopoutWindow(self)
        self._subtitle_popout.closed.connect(self._on_subtitle_popout_closed)
        self._subtitle_root_layout.removeWidget(self._subtitle_section_host)
        self._subtitle_placeholder = QLabel(
            tr("veditor.subtitle_popout.placeholder"),
        )
        self._subtitle_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_placeholder.setMinimumHeight(80)
        self._subtitle_placeholder.setWordWrap(True)
        self._subtitle_placeholder.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
            f"background-color: {COLOR_BG_L2}; "
            f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
            f"padding: 12px;"
        )
        self._subtitle_root_layout.insertWidget(
            self._subtitle_root_index, self._subtitle_placeholder,
        )
        self._subtitle_popout.install(self._subtitle_section_host)
        self._subtitle_popout.show()
        self._subtitle_popout.raise_()
        self._subtitle_popout.activateWindow()

    def _on_subtitle_popout_closed(self) -> None:
        if self._subtitle_placeholder is not None:
            idx = self._subtitle_root_layout.indexOf(self._subtitle_placeholder)
            self._subtitle_root_layout.removeWidget(self._subtitle_placeholder)
            self._subtitle_placeholder.deleteLater()
            self._subtitle_placeholder = None
        else:
            idx = self._subtitle_root_index
        self._subtitle_section_host.setParent(self)
        self._subtitle_root_layout.insertWidget(
            max(0, idx), self._subtitle_section_host,
        )
        self._subtitle_section_host.show()
        if self._subtitle_popout is not None:
            self._subtitle_popout.deleteLater()
            self._subtitle_popout = None

    # ---- media pool pop-out ----

    def _toggle_media_pool_popout(self) -> None:
        if (
            self._media_pool_popout is not None
            and self._media_pool_popout.isVisible()
        ):
            self._media_pool_popout.close()
            return
        self._media_pool_popout = MediaPoolPopoutWindow(self)
        self._media_pool_popout.closed.connect(self._on_media_pool_popout_closed)
        self._media_pool_root_layout.removeWidget(self._media_pool_section_host)
        self._media_pool_placeholder = QLabel(
            tr("veditor.media_pool_popout.placeholder"),
        )
        self._media_pool_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._media_pool_placeholder.setMinimumHeight(80)
        self._media_pool_placeholder.setWordWrap(True)
        self._media_pool_placeholder.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
            f"background-color: {COLOR_BG_L2}; "
            f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
            f"padding: 12px;"
        )
        self._media_pool_root_layout.insertWidget(
            self._media_pool_root_index, self._media_pool_placeholder,
        )
        self._media_pool_popout.install(self._media_pool_section_host)
        self._media_pool_popout.show()
        self._media_pool_popout.raise_()
        self._media_pool_popout.activateWindow()

    def _on_media_pool_popout_closed(self) -> None:
        if self._media_pool_placeholder is not None:
            idx = self._media_pool_root_layout.indexOf(
                self._media_pool_placeholder,
            )
            self._media_pool_root_layout.removeWidget(
                self._media_pool_placeholder,
            )
            self._media_pool_placeholder.deleteLater()
            self._media_pool_placeholder = None
        else:
            idx = self._media_pool_root_index
        self._media_pool_section_host.setParent(self)
        self._media_pool_root_layout.insertWidget(
            max(0, idx), self._media_pool_section_host, stretch=1,
        )
        self._media_pool_section_host.show()
        if self._media_pool_popout is not None:
            self._media_pool_popout.deleteLater()
            self._media_pool_popout = None

    def _toggle_effects_library_popout(self) -> None:
        # Effects Library section was removed when the four cards
        # moved into the track bar — there's nothing to pop out
        # anymore. Kept as a no-op for any stale code path that may
        # still call it (was wired to the section header button).
        return

    def _on_effects_library_popout_closed(self) -> None:
        return

    def _open_zoom_editor(self, track_id: int, zactor_id: int) -> None:
        """Click handler — opens the modal region picker + duration sliders
        for a zoom actor. Updates the actor in place on Apply."""
        found = self._find_zoom_actor(track_id, zactor_id)
        if found is None:
            return
        track, zactor = found
        dlg = ZoomActorDialog(track, zactor, self._player, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_track_zoom_changed(track_id)

    def _show_zoom_menu(self, track_id: int, zactor_id: int, global_pos) -> None:
        from PySide6.QtWidgets import QMenu

        found = self._find_zoom_actor(track_id, zactor_id)
        if found is None:
            return
        track, zactor = found
        menu = QMenu(self)
        a_edit = menu.addAction(tr("veditor.zoom_menu.edit"))
        menu.addSeparator()
        a_del = menu.addAction(tr("veditor.zoom_menu.delete"))

        chosen = menu.exec(global_pos)
        if chosen is a_edit:
            self._open_zoom_editor(track_id, zactor_id)
        elif chosen is a_del:
            track.zoom_actors = [
                z for z in track.zoom_actors if z.id != zactor_id
            ]
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_track_zoom_changed(track_id)

    def _scale_preview_to_fit(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        avail = self._preview_label.size()
        if avail.width() <= 0 or avail.height() <= 0:
            return
        scaled = self._preview_pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Blend to black by the active fade's multiplier so the preview
        # matches what the exporter produces.
        mult = self._current_fade_multiplier(self._player.position())
        if mult < 0.999:
            faded = QPixmap(scaled.size())
            faded.fill(Qt.GlobalColor.black)
            p = QPainter(faded)
            p.setOpacity(max(0.0, min(1.0, mult)))
            p.drawPixmap(0, 0, scaled)
            p.end()
            scaled = faded
        self._preview_label.setPixmap(scaled)
        self._sync_overlay_to_video_rect()

    def _sync_preview_gl_geometry(self) -> None:
        """Position the GL preview widget exactly where the QLabel
        sits — same parent, so just mirror the label's geometry. Called
        on host resize and the first frame after a track is loaded."""
        gl = getattr(self, "_preview_gl", None)
        if gl is None:
            return
        lbl = self._preview_label
        gl.setGeometry(lbl.x(), lbl.y(), lbl.width(), lbl.height())
        gl.raise_()
        # Ensure the always-on-top overlays (drawing canvas, subtitle)
        # stay above the GL surface.
        if hasattr(self, "_drawing_canvas"):
            self._drawing_canvas.raise_()
        if hasattr(self, "_subtitle_overlay"):
            self._subtitle_overlay.raise_()

    def _sync_overlay_to_video_rect(self) -> None:
        """Size the drawing canvas to exactly the video pixmap rect inside the
        preview label, so strokes can't render in the letterbox area."""
        host = self._preview_host
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            self._drawing_canvas.setGeometry(0, 0, host.width(), host.height())
            return
        # preview_label is laid out inside host via a QVBoxLayout with zero
        # margins, so label top-left == host top-left in host coords.
        label_w = self._preview_label.width()
        label_h = self._preview_label.height()
        if label_w <= 0 or label_h <= 0:
            return
        src_w = self._preview_pixmap.width()
        src_h = self._preview_pixmap.height()
        if src_w <= 0 or src_h <= 0:
            return
        scale = min(label_w / src_w, label_h / src_h)
        vw = max(1, int(src_w * scale))
        vh = max(1, int(src_h * scale))
        vx = (label_w - vw) // 2
        vy = (label_h - vh) // 2
        self._drawing_canvas.setGeometry(vx, vy, vw, vh)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_preview_to_fit()
        if self._subtitle_overlay.isVisible():
            self._reposition_subtitle_overlay()
        self._sync_overlay_to_video_rect()
        self._sync_preview_gl_geometry()
        self._resync_bubbles_to_preview()
        self._resync_stickers_to_preview()
        # Re-layout the active text clip overlay on canvas resize.
        if hasattr(self, "_text_track"):
            self._update_text_clip_overlay(self._player.position())
        # Timeline stretches to viewport width too
        if hasattr(self, "_tracks_scroll"):
            self._update_tracks_host_width()

    def _on_position_changed(self, pos: int) -> None:
        # Playhead shows on every track at project time
        for row in self._track_rows.values():
            row.set_position(pos)
        for row in self._audio_rows.values():
            row.set_position(pos)
        self._timeline_ruler.set_playhead(pos)
        # Keep extra snap targets current so moving the playhead then
        # starting a clip drag snaps to the new playhead position.
        self._push_snap_targets_to_rows()
        # Update audio level meters from waveform data at playhead
        self._update_audio_level_meters(pos)
        # Update Audio Mixer VU meters and built-in scopes if panel is visible
        if hasattr(self, "_audio_mixer_panel") and self._audio_mixer_panel.isVisible():
            self._audio_mixer_panel.update_levels(pos, self._audio_tracks)
            self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
        # Remaining UI updates (subtitle, fade, drawing, bubbles, text)
        self.time_label.setText(
            f"{_format_ms(pos)} / {_format_ms(self._player.duration())}"
        )
        self._update_subtitle_overlay(pos)
        self._scale_preview_to_fit()
        self._drawing_canvas.update()
        # Sync PIP sliders to the interpolated keyframe values at this position.
        self._sync_pip_sliders_to_position(pos)
        self._update_bubble_visibility(pos)
        self._update_sticker_visibility(pos)
        self._update_text_clip_overlay(pos)
        # Report speed at the currently-rendered track
        active_for_render = None
        for t in reversed(self._tracks):
            if t.source_path is None:
                continue
            offset = getattr(t, "offset_ms", 0)
            local = pos - offset
            if local < 0 or local >= t.duration_ms:
                continue
            if any(c.start_ms <= local < c.end_ms for c in t.cuts):
                continue
            active_for_render = t
            break
        if active_for_render is None:
            speed = 1.0
        else:
            local_pos = pos - getattr(active_for_render, "offset_ms", 0)
            speed = self._speed_at(active_for_render, local_pos)
        if speed != self._current_segment_speed:
            self._current_segment_speed = speed
            self.current_speed_label.setText(
                tr("veditor.current_speed", speed=f"{speed:g}")
            )

    def _update_audio_level_meters(self, pos_ms: int) -> None:
        """Sample waveform peaks at the current playhead and push to
        each audio track's level meter display."""
        import numpy as _np
        from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
        for track in self._audio_tracks:
            row = self._audio_rows.get(track.id)
            if row is None:
                continue
            l_peak = r_peak = 0.0
            for clip in track.clips:
                if clip.source_path is None:
                    continue
                # Map project position to source position
                local_ms = pos_ms - clip.offset_ms
                if local_ms < 0 or local_ms > clip.effective_length_ms:
                    continue
                src_ms = clip.trim_start_ms + local_ms
                wf = clip.waveform
                if wf is None or wf.size == 0:
                    continue
                bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
                n = wf.shape[1] if is_stereo else len(wf)
                if 0 <= bucket < n:
                    if is_stereo:
                        l_peak = max(l_peak, float(wf[0, bucket]) * track.volume)
                        r_peak = max(r_peak, float(wf[1, bucket]) * track.volume)
                    else:
                        v = float(wf[bucket]) * track.volume
                        l_peak = max(l_peak, v)
                        r_peak = max(r_peak, v)
            row.set_level(l_peak, r_peak)

    def _on_audio_scopes_toggled(self, checked: bool) -> None:
        """Show/hide the scopes column inside AudioMixerPanel.

        If the mixer is hidden and the user turns scopes on, show the mixer too.
        """
        if not hasattr(self, "_audio_mixer_panel"):
            return
        if checked:
            # Make sure the mixer itself is visible first
            if not self._audio_mixer_panel.isVisible():
                self._audio_mixer_panel.setVisible(True)
                self._audio_mixer_panel.rebuild(self._audio_tracks)
                if hasattr(self, "audio_mixer_tl_btn"):
                    with _block_signals(self.audio_mixer_tl_btn):
                        self.audio_mixer_tl_btn.setChecked(True)
            self._audio_mixer_panel.set_scopes_visible(True)
            pos = self._player.position() if hasattr(self, "_player") else 0
            self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
        else:
            self._audio_mixer_panel.set_scopes_visible(False)

    def _on_audio_mixer_toggled(self, checked: bool) -> None:
        """Show/hide the Audio Mixer panel (with built-in scopes column)."""
        if not hasattr(self, "_audio_mixer_panel"):
            return
        self._audio_mixer_panel.setVisible(checked)
        if checked:
            self._audio_mixer_panel.rebuild(self._audio_tracks)
            # Restore scopes column visibility from the scopes toggle button
            scopes_btn = getattr(self, "audio_scopes_tl_btn", None)
            scopes_on = scopes_btn is not None and scopes_btn.isChecked()
            self._audio_mixer_panel.set_scopes_visible(scopes_on)

    def _on_mixer_fader_changed(self, track_id: int, volume: float) -> None:
        """Called when a mixer fader moves — sync to track and audio engine."""
        track = self._find_audio_track(track_id)
        if track is None:
            return
        track.volume = max(0.0, min(1.5, volume))
        # Sync track row header slider
        row = self._audio_rows.get(track_id)
        if row is not None:
            with _block_signals(row._volume_slider):
                row._volume_slider.setValue(int(round(track.volume * 100)))
        # Sync audio engine
        self._audio_mixer.update_track(track)

    def _on_mixer_pan_changed(self, track_id: int, pan: float) -> None:
        """Called when a mixer pan dial moves — update track.pan and engine."""
        track = self._find_audio_track(track_id)
        if track is None:
            return
        track.pan = max(-1.0, min(1.0, pan))
        # Sync audio engine so _apply_volumes sees the updated pan immediately.
        self._audio_mixer.update_track(track)

    def _on_duration_changed(self, dur: int) -> None:
        for row in self._track_rows.values():
            row._recalc_width()
        self._timeline_ruler.set_project_duration(dur)
        self._update_tracks_host_width()
        self.time_label.setText(f"0:00 / {_format_ms(dur)}")
        self._subtitle_panel.set_project_duration(dur)
        # Track durations are now finalised — push the active track's
        # numbers into the inspector so the duration row matches.
        self._refresh_workbench()

    def _on_player_error(self, error, msg: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        import sys as _sys

        print(f"[veditor] player error {error}: {msg}", file=_sys.stderr, flush=True)
        QMessageBox.warning(
            self,
            tr("veditor.title"),
            f"{msg}\n\n"
            "Codec or file format may not be supported by Windows Media Foundation.",
        )

    def _on_media_status(self, status) -> None:
        import sys as _sys

        print(f"[veditor] media status: {status}", file=_sys.stderr, flush=True)

    @staticmethod
    def _speed_at(track: VideoTrack, pos_ms: int) -> float:
        for seg in track.speed_segments:
            if seg.contains(pos_ms):
                return seg.speed
        return 1.0

    # -------------- selection UI --------------

    def _refresh_selection_row(self) -> None:
        track = self._active_track()
        if track is None:
            has_sel = False
            self.selection_label.setText(tr("veditor.no_selection"))
        else:
            has_sel = (
                track.selection_start_ms >= 0
                and track.selection_end_ms > track.selection_start_ms
            )
            if has_sel:
                self.selection_label.setText(
                    tr(
                        "veditor.selection_range",
                        start=_format_ms(track.selection_start_ms),
                        end=_format_ms(track.selection_end_ms),
                        duration=_format_ms(
                            track.selection_end_ms - track.selection_start_ms
                        ),
                    )
                )
            else:
                self.selection_label.setText(tr("veditor.no_selection"))
        for btn in self._speed_buttons:
            btn.setEnabled(has_sel)
        self.clear_sel_btn.setEnabled(has_sel)

    # -------------- keyboard shortcuts --------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Space:
            self._toggle_play()
            return
        # Ctrl+T: apply Cross Dissolve (500ms) to the selected clip's right edge
        if (
            key == Qt.Key.Key_T
            and mods & Qt.KeyboardModifier.ControlModifier
            and not (mods & Qt.KeyboardModifier.ShiftModifier)
        ):
            self._apply_transition_to_selected("dissolve", 500)
            return
        track = self._active_track()
        step = 5000 if mods & Qt.KeyboardModifier.ShiftModifier else 1000
        if key == Qt.Key.Key_Left:
            self._player.set_position(max(0, self._player.position() - step))
            return
        if key == Qt.Key.Key_Right:
            end = track.duration_ms if track else 0
            self._player.set_position(min(end, self._player.position() + step))
            return
        if key == Qt.Key.Key_Home:
            self._player.set_position(0)
            return
        if key == Qt.Key.Key_End and track:
            self._player.set_position(track.duration_ms)
            return
        super().keyPressEvent(event)

    def _apply_transition_to_selected(self, ttype: str, ms: int) -> None:
        """Apply a clip-boundary transition to all currently selected clips.
        Sets ``transition_out_type`` / ``transition_out_ms`` on each clip and
        triggers a repaint. Called by the Ctrl+T keyboard shortcut."""
        if not self._selected_clips:
            return
        any_change = False
        for tid, cid in self._selected_clips:
            track = self._find_track(tid)
            if track is None:
                continue
            for clip in getattr(track, "clips", []):
                if int(clip.id) == int(cid):
                    clip.transition_out_type = ttype
                    clip.transition_out_ms = max(50, int(ms))
                    any_change = True
                    row = self._track_rows.get(tid)
                    if row is not None:
                        row.update()
                    break
        if any_change:
            self._register_change("Ctrl+T transition")

    def closeEvent(self, event) -> None:
        for ex in list(self._extractors.values()):
            ex.stop()
        for ex in list(self._extractors.values()):
            ex.wait(300)
        try:
            self._player.release()
        except Exception:
            pass
        super().closeEvent(event)

    # -------- export --------

    # ---- export quality dropdown ----

    def _refresh_quality_btn_label(self) -> None:
        from app.video_exporter import get_quality_preset
        from app import tier
        q = get_quality_preset(self._export_quality_id)
        label = tr(q.name_key)
        if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
            label = f"{label} ★"          # PRO unlocked
        self.quality_btn.setText(f"{tr('veditor.export.quality.label')}: {label}  ▾")

    def _build_quality_menu(self) -> None:
        from app.video_exporter import QUALITY_PRESETS
        from app import tier
        menu = QMenu(self.quality_btn)
        menu.setObjectName("QualityMenu")
        # Override the default menu look with explicit padding, larger
        # font, and a strong accent for the currently-selected row so
        # the active quality is obvious at a glance.
        menu.setStyleSheet(
            f"QMenu#QualityMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#QualityMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#QualityMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#QualityMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#QualityMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for q in QUALITY_PRESETS:
            badge = ""
            if tier.requires_pro(q.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(q.feature_id) else "★ PRO  "
            label = f"{badge}{tr(q.name_key)}  ·  {tr(q.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(q.id == self._export_quality_id)
            act.triggered.connect(
                lambda _checked=False, qid=q.id: self._on_quality_picked(qid)
            )
        self.quality_btn.setMenu(menu)

    def _on_quality_picked(self, quality_id: str) -> None:
        from app.video_exporter import get_quality_preset
        from app import tier
        q = get_quality_preset(quality_id)
        if tier.is_locked(q.feature_id):
            self._show_upsell(q.feature_id, tr(q.name_key))
            # Rebuild the menu so the previous selection's checkmark
            # is restored (the click toggled it off).
            self._build_quality_menu()
            return
        self._export_quality_id = quality_id
        self._refresh_quality_btn_label()
        self._build_quality_menu()

    # ---- export format dropdown ----

    def _refresh_format_btn_label(self) -> None:
        from app.video_exporter import get_export_format
        from app import tier
        f = get_export_format(self._export_format_id)
        label = tr(f.name_key)
        if tier.requires_pro(f.feature_id) and not tier.is_locked(f.feature_id):
            label = f"{label} ★"
        self.format_btn.setText(f"{tr('veditor.export.format.label')}: {label}  ▾")

    def _build_format_menu(self) -> None:
        from app.video_exporter import EXPORT_FORMATS
        from app import tier
        menu = QMenu(self.format_btn)
        menu.setObjectName("FormatMenu")
        menu.setStyleSheet(
            f"QMenu#FormatMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#FormatMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#FormatMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#FormatMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#FormatMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for f in EXPORT_FORMATS:
            badge = ""
            if tier.requires_pro(f.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(f.feature_id) else "★ PRO  "
            label = f"{badge}{tr(f.name_key)}  ·  {tr(f.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(f.id == self._export_format_id)
            act.triggered.connect(
                lambda _checked=False, fid=f.id: self._on_format_picked(fid)
            )
        self.format_btn.setMenu(menu)

    def _on_format_picked(self, format_id: str) -> None:
        from app.video_exporter import get_export_format
        from app import tier
        f = get_export_format(format_id)
        if tier.is_locked(f.feature_id):
            self._show_upsell(f.feature_id, tr(f.name_key))
            self._build_format_menu()
            return
        self._export_format_id = format_id
        self._refresh_format_btn_label()
        self._build_format_menu()

    # ---- export resolution dropdown ----

    _RESOLUTION_PRESETS = [
        (None,        "원본 (Original)"),
        ((3840, 2160), "4K  3840×2160"),
        ((1920, 1080), "1080p  1920×1080"),
        ((1280,  720), "720p  1280×720"),
        (( 854,  480), "480p  854×480"),
        ((1080, 1920), "9:16  1080×1920"),
        ((1080, 1080), "1:1  1080×1080"),
    ]

    def _refresh_resolution_btn_label(self) -> None:
        res = self._export_resolution
        if res is None:
            label = "Resolution: 원본"
        else:
            label = f"Resolution: {res[0]}×{res[1]}"
        self.resolution_btn.setText(f"{label}  ▾")

    def _build_resolution_menu(self) -> None:
        menu = QMenu(self.resolution_btn)
        menu.setObjectName("ResolutionMenu")
        _MENU_QSS = (
            f"QMenu#ResolutionMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#ResolutionMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; margin: 1px 0px; }}"
            f"QMenu#ResolutionMenu::item:selected {{ background-color: {COLOR_BG_L5}; }}"
            f"QMenu#ResolutionMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#ResolutionMenu::indicator {{ width: 16px; height: 16px; left: 10px; }}"
        )
        menu.setStyleSheet(_MENU_QSS)
        for res, name in self._RESOLUTION_PRESETS:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(self._export_resolution == res)
            act.triggered.connect(
                lambda _checked=False, r=res: self._on_resolution_picked(r)
            )
        self.resolution_btn.setMenu(menu)

    def _on_resolution_picked(self, res) -> None:
        self._export_resolution = res
        self._refresh_resolution_btn_label()
        self._build_resolution_menu()

    # ---- export FPS dropdown ----

    _FPS_PRESETS = [
        (None,  "원본 (Original)"),
        (60.0,  "60 fps"),
        (30.0,  "30 fps"),
        (25.0,  "25 fps"),
        (24.0,  "24 fps"),
    ]

    def _refresh_fps_btn_label(self) -> None:
        fps = self._export_fps
        if fps is None:
            label = "FPS: 원본"
        else:
            label = f"FPS: {int(fps) if fps == int(fps) else fps}"
        self.fps_btn.setText(f"{label}  ▾")

    def _build_fps_menu(self) -> None:
        menu = QMenu(self.fps_btn)
        menu.setObjectName("FpsMenu")
        _MENU_QSS = (
            f"QMenu#FpsMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#FpsMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; margin: 1px 0px; }}"
            f"QMenu#FpsMenu::item:selected {{ background-color: {COLOR_BG_L5}; }}"
            f"QMenu#FpsMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#FpsMenu::indicator {{ width: 16px; height: 16px; left: 10px; }}"
        )
        menu.setStyleSheet(_MENU_QSS)
        for fps, name in self._FPS_PRESETS:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(self._export_fps == fps)
            act.triggered.connect(
                lambda _checked=False, f=fps: self._on_fps_picked(f)
            )
        self.fps_btn.setMenu(menu)

    def _on_fps_picked(self, fps) -> None:
        self._export_fps = fps
        self._refresh_fps_btn_label()
        self._build_fps_menu()

    def _show_upsell(self, feature_id: str, feature_label: str) -> None:
        """Generic upsell modal — used whenever a Pro-only control is
        triggered by a Free user. Title + body i18n keys are shared,
        but the body interpolates the specific feature label."""
        QMessageBox.information(
            self,
            tr("upsell.title"),
            tr("upsell.body", feature=feature_label),
        )

    # ---- inline color panel (above timeline ruler) ----

    def _build_color_inline_panel(self) -> QWidget:
        """Compact horizontal color panel that appears above the timeline
        ruler when a Color node is selected.  4 wheels in a row at 120px,
        with R/G/B/L readouts below each.  Mirrors the right-dock panel
        but laid out for the wide timeline area."""
        from app.color_page_window import _Wheel

        _BG = "#17171c"
        _BG_SEC = "#1d1d24"
        _LABEL = "#9090aa"
        _TEXT  = "#d4d4e0"
        _VALBG = "#0d0d14"
        _BORD  = "#2c2c38"
        _TINY  = "font-size: 10px; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
        _SB_QSS = (
            f"QDoubleSpinBox{{background:{_VALBG};color:{_TEXT};"
            f"border:1px solid {_BORD};border-radius:2px;{_TINY}"
            "padding:0 2px;min-width:38px;}}"
            "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{width:0;}"
        )
        WHEEL_SIZE = 120

        host = QWidget()
        host.setStyleSheet(f"background:{_BG}; border-bottom:1px solid #2a2a38;")
        host.setFixedHeight(WHEEL_SIZE + 120)  # wheel + label + readouts + sliders

        row = QHBoxLayout(host)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(0)

        self._inline_wheels: dict[str, object]  = {}
        self._inline_lumas:  dict[str, object]  = {}

        specs = [
            ("shadows",    "Lift"),
            ("midtones",   "Gamma"),
            ("highlights", "Gain"),
            ("offset",     "Offset"),
        ]

        for i, (region, label) in enumerate(specs):
            sec = QWidget()
            sec.setAutoFillBackground(True)
            _pal = sec.palette()
            _pal.setColor(sec.backgroundRole(), QColor(_BG_SEC))
            sec.setPalette(_pal)
            vl = QVBoxLayout(sec)
            vl.setContentsMargins(6, 5, 6, 5)
            vl.setSpacing(3)

            # header: label + ↺
            hdr = QHBoxLayout()
            hdr.setContentsMargins(0,0,0,0); hdr.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"background:transparent;border:none;color:{_LABEL};"
                "font-size:10px;font-weight:600;letter-spacing:0.4px;"
            )
            hdr.addWidget(lbl); hdr.addStretch()
            rst = QPushButton("↺")
            rst.setFixedSize(16, 16)
            rst.setCursor(Qt.CursorShape.PointingHandCursor)
            rst.setStyleSheet(
                f"QPushButton{{background:transparent;color:{_LABEL};"
                "border:none;font-size:12px;padding:0;}}"
                f"QPushButton:hover{{color:{_TEXT};}}"
            )
            hdr.addWidget(rst)
            vl.addLayout(hdr)

            # wheel
            w = _Wheel()
            w.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
            w.value_changed.connect(
                lambda x, y, r=region: self._on_color_wheel_changed(r, x, y)
            )
            rst.clicked.connect(
                lambda checked=False, ww=w: ww.set_value(0, 0)
            )
            vl.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
            self._inline_wheels[region] = w

            # readouts
            r4 = QHBoxLayout(); r4.setSpacing(2); r4.setContentsMargins(0,0,0,0)
            for hint in ("R","G","B","L"):
                sb = QDoubleSpinBox()
                sb.setRange(-5.0, 5.0); sb.setValue(0.0)
                sb.setDecimals(2); sb.setSingleStep(0.01)
                sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
                sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sb.setStyleSheet(_SB_QSS)
                sb.setToolTip(hint)
                r4.addWidget(sb)
                if hint == "L":
                    class _Compat:
                        def __init__(self, s): self._s = s
                        def blockSignals(self, v): self._s.blockSignals(v)
                        def setValue(self, v): self._s.setValue(v / 100.0)
                    self._inline_lumas[region] = _Compat(sb)
            vl.addLayout(r4)

            row.addWidget(sec, 1)

            if i < len(specs) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.VLine)
                div.setFixedWidth(1)
                div.setStyleSheet(f"background:{_BORD};border:none;")
                row.addWidget(div)

        # Close (×) button on the right
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_LABEL};"
            "border:none;font-size:16px;padding:0;}}"
            f"QPushButton:hover{{color:{_TEXT};}}"
        )
        close_btn.clicked.connect(
            lambda: self._color_inline_panel.setVisible(False)
        )
        row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        # Bottom bar — Brightness / Contrast / Saturation compact sliders
        _SLIDER_QSS = (
            "QSlider::groove:horizontal{background:#2a2a38;height:3px;border-radius:1px;}"
            "QSlider::handle:horizontal{background:#4a90d8;width:10px;height:10px;"
            "border-radius:5px;margin:-4px 0;}"
            "QSlider::sub-page:horizontal{background:#3a5878;border-radius:1px;}"
        )
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{_BG}; border-top:1px solid {_BORD};")
        blay = QHBoxLayout(bottom)
        blay.setContentsMargins(12, 4, 12, 4)
        blay.setSpacing(16)
        self._inline_sliders: dict[str, object] = {}
        for key, label_str in [("brightness","밝기"),("contrast","대비"),("saturation","채도")]:
            grp = QHBoxLayout(); grp.setSpacing(4); grp.setContentsMargins(0,0,0,0)
            lbl = QLabel(label_str)
            lbl.setStyleSheet(f"color:{_LABEL};font-size:10px;background:transparent;border:none;")
            lbl.setFixedWidth(26)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(-100, 100); sl.setValue(0)
            sl.setStyleSheet(_SLIDER_QSS)
            val_lbl = QLabel("0")
            val_lbl.setFixedWidth(22)
            val_lbl.setStyleSheet(f"color:{_TEXT};font-size:10px;background:transparent;border:none;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sl.valueChanged.connect(
                lambda v, k=key, vl=val_lbl: (
                    vl.setText(str(v)),
                    self._on_color_slider_changed(k, v),
                )
            )
            grp.addWidget(lbl); grp.addWidget(sl, 1); grp.addWidget(val_lbl)
            blay.addLayout(grp, 1)
            self._inline_sliders[key] = sl
        host_outer = QWidget()
        host_outer.setStyleSheet(f"background:{_BG};")
        outer_lay = QVBoxLayout(host_outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        outer_lay.addWidget(host)
        outer_lay.addWidget(bottom)

        return host_outer

    def _sync_color_inline_panel(self) -> None:
        """Sync the inline panel wheels, readouts, and sliders with the active grade."""
        grade = self._active_color_grade()
        # Sync master sliders
        for key, sl in getattr(self, "_inline_sliders", {}).items():
            v = int(getattr(grade, key, 0)) if grade else 0
            sl.blockSignals(True); sl.setValue(v); sl.blockSignals(False)
        for region, wheel in self._inline_wheels.items():
            x = int(getattr(grade, f"{region}_x", 0)) if grade else 0
            y = int(getattr(grade, f"{region}_y", 0)) if grade else 0
            wheel.set_value(x, y, emit=False)
        for region, compat in self._inline_lumas.items():
            v = int(getattr(grade, f"{region}_l", 0)) if grade else 0
            compat.blockSignals(True)
            compat.setValue(v)
            compat.blockSignals(False)

    # ---- color grading panel ----

    def _build_color_grading_panel(self) -> QWidget:
        """DaVinci Resolve-style colour panel — 2×2 wheel grid for the narrow dock."""
        from app.color_page_window import _Wheel

        _BG_SECTION = "#1d1d24"
        _LABEL_CLR  = "#9090aa"
        _TEXT_CLR   = "#d4d4e0"
        _VAL_BG     = "#0d0d14"
        _BORDER_CLR = "#2c2c38"
        _TINY = "font-size: 10px; font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
        _SBOX_QSS = (
            f"QDoubleSpinBox {{ background: {_VAL_BG}; color: {_TEXT_CLR}; "
            f"border: 1px solid {_BORDER_CLR}; border-radius: 2px; {_TINY} "
            "padding: 0 2px; min-width: 40px; }}"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0; }"
        )

        WHEEL_SIZE = 145   # smaller than ColorPage (180) to fit narrow dock

        host = QWidget()
        host.setObjectName("ColorPanel")
        host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        outer = QVBoxLayout(host)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        # Let Qt compute the host's minimumHeight from its children so the
        # scroll area always gets enough space to show the full 2×2 wheel grid.
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        # ── Preset row ─────────────────────────────────────────────────────────
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(4)

        self._color_preset_btn = QToolButton()
        self._color_preset_btn.setObjectName("ColorPresetDropdown")
        self._color_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_preset_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup,
        )
        self._color_preset_btn.setMinimumHeight(28)
        self._color_preset_btn.setStyleSheet(
            f"QToolButton#ColorPresetDropdown {{ "
            f"background-color: {COLOR_BG_L5}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 26px 4px 10px; font-size: 11px; min-height: 24px; }}"
            f"QToolButton#ColorPresetDropdown:hover {{ "
            f"background-color: {COLOR_BG_L6}; border-color: #4a4a52; }}"
            f"QToolButton#ColorPresetDropdown:pressed {{ "
            f"background-color: {COLOR_BG_L4}; }}"
            f"QToolButton#ColorPresetDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 7px; }}"
        )
        preset_row.addWidget(self._color_preset_btn)
        preset_row.addStretch(1)

        rst_all = QPushButton(tr("color.reset"))
        rst_all.setObjectName("ToolButton")
        rst_all.setCursor(Qt.CursorShape.PointingHandCursor)
        rst_all.clicked.connect(self._on_color_reset)
        preset_row.addWidget(rst_all)
        outer.addLayout(preset_row)

        # ── 4 wheel sections in 2×2 grid ───────────────────────────────────────
        self._color_wheels: dict[str, object] = {}   # region → _Wheel
        self._color_lumas:  dict[str, object] = {}   # region → _LumaCompat
        self._color_readouts: dict[str, list] = {}   # region → [sb_r, sb_g, sb_b]
        self._color_luma_dials: dict[str, _LumaDial] = {}  # region → _LumaDial

        wheel_specs = [
            ("shadows",    tr("color.wheel.shadows")),
            ("midtones",   tr("color.wheel.midtones")),
            ("highlights", tr("color.wheel.highlights")),
            ("offset",     tr("color.wheel.offset")),
        ]

        def _make_section(region: str, label: str) -> QWidget:
            sec = QWidget()
            sec.setMinimumWidth(WHEEL_SIZE + 24)
            # Minimum height: label(18) + spacing(4) + wheel + spacing(4) + readouts(22) + margins(12)
            sec.setMinimumHeight(WHEEL_SIZE + 60)
            sec.setAutoFillBackground(True)
            _pal2 = sec.palette()
            _pal2.setColor(sec.backgroundRole(), QColor(_BG_SECTION))
            sec.setPalette(_pal2)
            vl = QVBoxLayout(sec)
            vl.setContentsMargins(6, 6, 6, 6)
            vl.setSpacing(4)

            # header
            hdr = QHBoxLayout()
            hdr.setContentsMargins(0, 0, 0, 0)
            hdr.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"background:transparent; border:none; color:{_LABEL_CLR}; "
                "font-size:10px; font-weight:600; letter-spacing:0.5px;"
            )
            hdr.addWidget(lbl)
            hdr.addStretch()
            rst_btn = QPushButton("↺")
            rst_btn.setFixedSize(18, 18)
            rst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rst_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{_LABEL_CLR}; "
                f"border:none; font-size:13px; padding:0; }}"
                f"QPushButton:hover {{ color:{_TEXT_CLR}; }}"
            )
            hdr.addWidget(rst_btn)
            vl.addLayout(hdr)

            # wheel
            w = _Wheel()
            w.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
            w.value_changed.connect(
                lambda x, y, r=region: self._on_color_wheel_changed(r, x, y)
            )
            w.luma_changed.connect(
                lambda v, r=region: self._on_color_luma_changed(r, v)
            )
            rst_btn.clicked.connect(lambda checked=False, ww=w: (ww.set_value(0, 0), ww.set_luma(0)))
            vl.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
            self._color_wheels[region] = w

            # readouts R G B L
            row4 = QHBoxLayout()
            row4.setSpacing(3)
            row4.setContentsMargins(0, 0, 0, 0)
            _BAR_COLORS = {"R":"#e84040","G":"#40c040","B":"#4080e8","L":"#b0b0b0"}
            for hint in ("R", "G", "B", "L"):
                # Each readout: spinbox + 2px coloured bottom bar
                cell = QWidget()
                cell.setStyleSheet("background:transparent;")
                cl = QVBoxLayout(cell); cl.setContentsMargins(0,0,0,0); cl.setSpacing(1)
                sb = QDoubleSpinBox()
                sb.setRange(-5.0, 5.0)
                sb.setValue(0.0)
                sb.setDecimals(2)
                sb.setSingleStep(0.01)
                sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
                sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sb.setStyleSheet(_SBOX_QSS)
                sb.setToolTip(hint)
                cl.addWidget(sb)
                bar = QFrame(); bar.setFixedHeight(2)
                bar.setStyleSheet(f"background:{_BAR_COLORS[hint]};border:none;")
                cl.addWidget(bar)
                row4.addWidget(cell)
                if hint == "L":
                    class _LumaCompat:
                        def __init__(self, spinbox):
                            self._sb = spinbox
                        def blockSignals(self, v): self._sb.blockSignals(v)
                        def setValue(self, v): self._sb.setValue(v / 100.0)
                    self._color_lumas[region] = _LumaCompat(sb)
                elif hint == "R":
                    self._color_readouts.setdefault(region, [None, None, None])[0] = sb
                elif hint == "G":
                    self._color_readouts.setdefault(region, [None, None, None])[1] = sb
                elif hint == "B":
                    self._color_readouts.setdefault(region, [None, None, None])[2] = sb
            vl.addLayout(row4)

            # Luma dial
            luma_dial = _LumaDial()
            luma_dial.value_changed.connect(
                lambda v, r=region: self._on_color_luma_changed(r, v)
            )
            self._color_luma_dials[region] = luma_dial
            vl.addWidget(luma_dial)
            return sec

        # 4 wheels in a single horizontal row (1×4)
        wheels_row = QHBoxLayout()
        wheels_row.setSpacing(6)
        wheels_row.setContentsMargins(0, 0, 0, 0)
        for region, label in wheel_specs:
            wheels_row.addWidget(_make_section(region, label), 1)
        outer.addLayout(wheels_row)

        # ── Divider ────────────────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(
            f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
        )
        div.setFixedHeight(1)
        outer.addWidget(div)

        # ── Master knobs: Brightness / Contrast / Saturation ───────────────────
        from app.knob_widget import KnobWidget

        self._color_sliders: dict = {}
        # NOTE: _color_readouts is initialized ABOVE (before _make_section calls)
        # and populated by _make_section. Do NOT reset it here.

        def _signed_pct(v: float) -> str:
            n = int(round(v))
            return f"{n:+d}" if n != 0 else "0"

        knob_specs = (
            ("brightness", "color.slider.brightness", "blue"),
            ("contrast",   "color.slider.contrast",   "blue"),
            ("saturation", "color.slider.saturation", "green"),
        )
        knobs_host = QWidget()
        knobs_row = QHBoxLayout(knobs_host)
        knobs_row.setContentsMargins(0, 4, 0, 4)
        knobs_row.setSpacing(8)
        knobs_row.addStretch(1)
        for key, label_key, color in knob_specs:
            knob = KnobWidget(
                label=tr(label_key),
                value=0.0,
                minimum=-100.0,
                maximum=100.0,
                default=0.0,
                color=color,
                bipolar=True,
                formatter=_signed_pct,
            )
            knob.valueChanged.connect(
                lambda v, k=key: self._on_color_slider_changed(k, int(round(v)))
            )
            knobs_row.addWidget(knob, 0)
            self._color_sliders[key] = knob
        knobs_row.addStretch(1)
        outer.addWidget(knobs_host)

        # ── Hue curve ───────────────────────────────────────────────────────────
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(
            f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
        )
        div2.setFixedHeight(1)
        outer.addWidget(div2)

        hue_lbl = QLabel(tr("color.section.hue_curve"))
        hue_lbl.setStyleSheet(
            f"color:{_LABEL_CLR}; font-size:10px; font-weight:600; "
            "background:transparent; border:none; margin-top:4px;"
        )
        outer.addWidget(hue_lbl)

        self._hue_curve = _HueCurveWidget()
        self._hue_curve.setFixedHeight(108)
        self._hue_curve.points_changed.connect(self._on_hue_curve_changed)
        outer.addWidget(self._hue_curve)

        # ── LUT section ─────────────────────────────────────────────────────────
        div3 = QFrame()
        div3.setFrameShape(QFrame.Shape.HLine)
        div3.setStyleSheet(
            f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
        )
        div3.setFixedHeight(1)
        outer.addWidget(div3)

        lut_host = QWidget()
        lut_host.setStyleSheet(
            f"QWidget {{ background: {COLOR_BG_L3}; border-radius: 6px; }}"
        )
        lut_vlay = QVBoxLayout(lut_host)
        lut_vlay.setContentsMargins(10, 8, 10, 8)
        lut_vlay.setSpacing(6)

        # Row 1: LUT title + load/clear buttons
        lut_top = QHBoxLayout()
        lut_top.setSpacing(6)
        lut_title = QLabel("3D LUT")
        lut_title.setStyleSheet(
            "color: #c8c8e8; font-size: 11px; font-weight: bold;"
        )
        lut_top.addWidget(lut_title)
        lut_top.addStretch(1)

        load_lut_btn = QPushButton("불러오기")
        load_lut_btn.setObjectName("ToolButton")
        load_lut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_lut_btn.setFixedHeight(22)
        load_lut_btn.setFixedWidth(70)
        load_lut_btn.clicked.connect(self._load_lut_file)
        lut_top.addWidget(load_lut_btn)

        clear_lut_btn = QPushButton("제거")
        clear_lut_btn.setObjectName("ToolButton")
        clear_lut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_lut_btn.setFixedHeight(22)
        clear_lut_btn.setFixedWidth(44)
        clear_lut_btn.clicked.connect(self._clear_lut)
        lut_top.addWidget(clear_lut_btn)
        lut_vlay.addLayout(lut_top)

        # Row 2: Clickable path field
        _default_lut_dir = str(
            (Path(__file__).parent.parent / "resources" / "luts").resolve()
        ).replace("\\", "/")
        self._lut_name_label = QPushButton(_default_lut_dir)
        self._lut_name_label.setObjectName("LutPathField")
        self._lut_name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lut_name_label.setFlat(True)
        self._lut_name_label.setStyleSheet(
            "QPushButton#LutPathField {"
            "  color: #5a5a7a; font-size: 10px; text-align: left;"
            "  background: transparent; border: 1px solid #2a2a3a;"
            "  border-radius: 3px; padding: 3px 6px;"
            "}"
            "QPushButton#LutPathField:hover { border-color: #5a5a8a; color: #9898c8; }"
        )
        self._lut_name_label.clicked.connect(self._load_lut_file)
        self._lut_name_label.setToolTip("클릭하여 .cube LUT 파일 선택")
        lut_vlay.addWidget(self._lut_name_label)

        # Row 3: Strength slider
        lut_str_row = QHBoxLayout()
        lut_str_row.setSpacing(8)
        lut_str_lbl = QLabel("강도")
        lut_str_lbl.setStyleSheet("color: #9898b8; font-size: 11px;")
        lut_str_lbl.setFixedWidth(28)
        lut_str_row.addWidget(lut_str_lbl)

        self._lut_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self._lut_strength_slider.setRange(0, 100)
        self._lut_strength_slider.setValue(100)
        self._lut_strength_slider.valueChanged.connect(self._on_lut_strength_changed)
        lut_str_row.addWidget(self._lut_strength_slider, 1)

        self._lut_pct_label = QLabel("100%")
        self._lut_pct_label.setStyleSheet("color: #c8c8e8; font-size: 10px;")
        self._lut_pct_label.setFixedWidth(32)
        lut_str_row.addWidget(self._lut_pct_label)
        lut_vlay.addLayout(lut_str_row)

        outer.addWidget(lut_host)

        outer.addStretch(1)

        self._build_color_preset_menu()
        self._sync_color_panel()
        return host

    def _active_color_grade(self):
        """DaVinci routing: the Color panel always edits the
        currently-bound NODE's grade. Falls back to the track's
        legacy ``color_grade`` only when no graph node is bound
        (e.g. an audio clip is selected, or the workbench panel
        hasn't materialised yet).

        ``_node_grade_target`` is the NodeItem bound by
        ``_on_node_graph_selection`` / ``_bind_default_node_grade``.
        We dereference its ``color_grade`` lazily so a node deleted
        while the panel is open falls through gracefully.
        """
        target_node = getattr(self, "_node_grade_target", None)
        if target_node is not None:
            grade = getattr(target_node, "color_grade", None)
            if grade is not None:
                return grade
        track = self._active_track()
        if track is None:
            return None
        if getattr(track, "color_grade", None) is None:
            from app.color_grading import ColorGrade
            track.color_grade = ColorGrade()
        return track.color_grade

    # ---- 3D LUT methods ----

    def _load_lut_file(self) -> None:
        """Open a file dialog to load a .cube LUT file."""
        from pathlib import Path as _P
        _lut_dir = str((_P(__file__).parent.parent / "resources" / "luts").resolve())
        # Use last-loaded directory if available, else default to samples folder
        _start_dir = str(Path(self._lut_path).parent) if self._lut_path else _lut_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "3D LUT 파일 선택",
            _start_dir,
            "LUT Files (*.cube);;All Files (*)",
        )
        if not path:
            return
        lut = parse_cube_lut(path)
        if lut is None:
            QMessageBox.warning(
                self,
                "LUT Error",
                "Could not parse the selected .cube file.\n"
                "Only 3D LUT files (LUT_3D_SIZE) are supported.",
            )
            return
        # Precompute fast 256³ cache table (one-time cost, fast at runtime)
        import numpy as _np
        try:
            s = lut.shape[0]
            vals = _np.arange(256, dtype=_np.float32) * ((s - 1) / 255.0)
            ri = _np.clip(vals.astype(_np.int32), 0, s - 2)
            rf = vals - ri
            ri1 = ri + 1
            # Build (256,256,256,3) cache via broadcasting
            r_, g_, b_ = ri[:, None, None], ri[None, :, None], ri[None, None, :]
            r1_, g1_, b1_ = ri1[:, None, None], ri1[None, :, None], ri1[None, None, :]
            rrf, grf, brf = rf[:, None, None], rf[None, :, None], rf[None, None, :]
            c000 = lut[b_, g_, r_]; c001 = lut[b_, g_, r1_]
            c010 = lut[b_, g1_, r_]; c011 = lut[b_, g1_, r1_]
            c100 = lut[b1_, g_, r_]; c101 = lut[b1_, g_, r1_]
            c110 = lut[b1_, g1_, r_]; c111 = lut[b1_, g1_, r1_]
            cache = (c000*(1-rrf)*(1-grf)*(1-brf) + c001*rrf*(1-grf)*(1-brf) +
                     c010*(1-rrf)*grf*(1-brf)    + c011*rrf*grf*(1-brf)    +
                     c100*(1-rrf)*(1-grf)*brf    + c101*rrf*(1-grf)*brf    +
                     c110*(1-rrf)*grf*brf        + c111*rrf*grf*brf)
            self._lut_cache = _np.clip(cache * 255, 0, 255).astype(_np.uint8)
        except Exception:
            self._lut_cache = None
        self._lut_data = lut
        self._lut_path = path
        name = Path(path).stem
        # Refresh the current frame so the LUT is applied immediately
        if hasattr(self, "_player"):
            try:
                self._player.refresh_current_frame()
            except Exception:
                pass
        label = getattr(self, "_lut_name_label", None)
        if label is not None:
            label.setText(f"✓  {name}")
            label.setStyleSheet(
                "QPushButton#LutPathField {"
                "  color: #c8e8c8; font-size: 10px; text-align: left;"
                "  background: #1a2a1a; border: 1px solid #3a6a3a;"
                "  border-radius: 3px; padding: 3px 6px;"
                "}"
                "QPushButton#LutPathField:hover { border-color: #5a9a5a; }"
            )
            label.setToolTip(path)

    def _clear_lut(self) -> None:
        """Remove the currently loaded LUT."""
        self._lut_data = None
        self._lut_path = ""
        self._lut_strength = 1.0
        label = getattr(self, "_lut_name_label", None)
        if label is not None:
            from pathlib import Path as _P
            _default = str((_P(__file__).parent.parent / "resources" / "luts").resolve()).replace("\\", "/")
            label.setText(_default)
            label.setStyleSheet(
                "QPushButton#LutPathField {"
                "  color: #5a5a7a; font-size: 10px; text-align: left;"
                "  background: transparent; border: 1px solid #2a2a3a;"
                "  border-radius: 3px; padding: 3px 6px;"
                "}"
                "QPushButton#LutPathField:hover { border-color: #5a5a8a; color: #9898c8; }"
            )
            label.setToolTip("클릭하여 .cube LUT 파일 선택")
        slider = getattr(self, "_lut_strength_slider", None)
        if slider is not None:
            slider.blockSignals(True)
            slider.setValue(100)
            slider.blockSignals(False)

    def _on_lut_strength_changed(self, value: int) -> None:
        """Slider moved — update LUT blend strength (0-100 -> 0.0-1.0)."""
        self._lut_strength = value / 100.0
        if hasattr(self, "_lut_pct_label"):
            self._lut_pct_label.setText(f"{value}%")

    def _on_blur_params_changed(self) -> None:
        """Called when blur radius/shape/strength changes. Rebuilds
        the chain and refreshes the preview."""
        self._rebuild_active_chain()

    def _rebuild_active_chain(self) -> None:
        """Build ``track.color_grade_chain`` for the active track.
        During active playback the chain references are updated
        immediately (the next timer tick will pick them up) but we
        skip the expensive ``refresh_current_frame()`` call to avoid
        blocking the GUI thread mid-playback — clicking nodes while
        playing would otherwise queue up multiple full decodes and
        freeze the interface.
        DaVinci-style "main viewer follows the selected node":

          - Selected node X → chain = IN→X (so the main preview shows
            the cumulative result *up to and including* X)
          - No selection / OUT selected → chain = full IN→OUT
          - IN node selected → chain = empty (raw source frame)

        Called on:
          - track switch (set_active_track → set_video_track)
          - graph mutation (node added/removed/connected)
          - node selection change (so the preview updates instantly)

        Slider edits *don't* trigger this — they mutate ColorGrade /
        mask objects in place, and the chain references stay valid.
        """
        track = self._active_track()
        if track is None:
            return
        wb = getattr(self, "_workbench_panel", None)
        ngw = wb.expose_node_graph_widget() if wb is not None else None
        if ngw is None:
            track.color_grade_chain = None
            track.node_mask_chain = None
            return
        target_node = self._select_view_target_node(ngw.scene)
        try:
            grades, masks = self._evaluate_node_chain_with_masks(
                ngw.scene, target_node,
            )
        except Exception:
            grades = []
            masks = []
        # Empty chain when the user selected the IN node (raw source
        # is the right preview). For other "no chain" cases (audio
        # clip, project just loaded) leave None so ProjectPlayer
        # falls back to the legacy single ``track.color_grade``.
        if target_node is not None and getattr(target_node, "kind", "") == "IN":
            track.color_grade_chain = []
            track.node_mask_chain = []
            track.node_item_chain = []
        else:
            track.color_grade_chain = grades or None
            track.node_mask_chain = masks or None
            # Build unified node_item_chain for the new render path.
            # Walks the same IN→target path and collects (node, masks) pairs
            # so that BlurNode items are applied in the correct sequence.
            try:
                ni_chain = self._build_node_item_chain(ngw.scene, target_node)
            except Exception:
                ni_chain = None
            track.node_item_chain = ni_chain or None
        # Only force a frame refresh when paused/stopped.
        from app.simple_video_player import PlayerState
        if (hasattr(self, "_player")
                and self._player.state() is not PlayerState.PLAYING):
            self._player.refresh_current_frame()
        # Also force a thumbnail update so nodes reflect the new
        # chain immediately (otherwise the 100 ms throttle leaves
        # them showing stale/black thumbnails after connecting).
        # Guard: only update when there is an active clip at the current
        # position so a Delete or track-switch doesn't wipe thumbnails black.
        _pos = self._player.position() if hasattr(self, "_player") else 0
        _has_active_now = any(
            int(c.timeline_in_ms) <= _pos <= int(c.timeline_out_ms)
            for t in self._tracks
            for c in getattr(t, "clips", [])
            if getattr(c, "source_path", None) is not None
        )
        if (_has_active_now
                and hasattr(self, "_preview_pixmap")
                and self._preview_pixmap is not None
                and not self._preview_pixmap.isNull()):
            wb = getattr(self, "_workbench_panel", None)
            if wb is not None:
                try:
                    wb.set_node_thumbnail(self._preview_pixmap)
                    self._last_node_thumb_ms = 0.0  # reset throttle
                except Exception:
                    pass

    @staticmethod
    def _build_node_item_chain(scene, target_node=None) -> list:
        """Return ``[(node_item, masks), ...]`` in IN→target order.
        Includes BlurNodeItem and NodeItem/ParallelMixerItem alike.
        Bypassed nodes are excluded. Identity-effect nodes ARE kept so
        that BlurNode with radius=0 still participates (masks matter)."""
        from app.workbench.node_graph.items.io_node import IONodeItem
        from app.workbench.node_graph.items.node_item import NodeItem
        from app.workbench.node_graph.items.parallel_mixer import ParallelMixerItem
        from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
        if target_node is None:
            target_node = scene._out_node
        if isinstance(target_node, IONodeItem) and target_node.kind == "IN":
            return []
        chain_nodes: list = []
        cur = target_node
        seen: set[int] = set()
        # If target is the OUT IO node, step into its upstream connection first
        # so the chain walk picks up all nodes before OUT.
        if isinstance(cur, IONodeItem) and cur.kind == "OUT":
            for port_name in ("rgb_in", "in_port", "input_port"):
                in_p = getattr(cur, port_name, None)
                if in_p is not None and getattr(in_p, "connections", None):
                    upstream = in_p.connections[0].source.parentItem()
                    if upstream is not None:
                        cur = upstream
                    break
        if isinstance(cur, (NodeItem, ParallelMixerItem, BlurNodeItem)):
            chain_nodes.append(cur)
            seen.add(id(cur))
        while True:
            in_port = getattr(cur, "rgb_in", None)
            if in_port is None or not in_port.connections:
                break
            up_conn = in_port.connections[0]
            upstream = up_conn.source.parentItem()
            if upstream is None or id(upstream) in seen:
                break
            seen.add(id(upstream))
            if isinstance(upstream, IONodeItem) and upstream.kind == "IN":
                break
            chain_nodes.append(upstream)
            cur = upstream
        chain_nodes.reverse()
        result = []
        for n in chain_nodes:
            if not isinstance(n, (NodeItem, ParallelMixerItem, BlurNodeItem)):
                continue
            if getattr(n, "bypassed", False):
                continue
            masks = getattr(n, "masks", None) or []
            result.append((n, masks))
        return result

    def _select_view_target_node(self, scene):
        """Decide which node the main preview should render through.

        Priority:
          1. The current ``_node_grade_target`` (the node the Color
             panel is bound to — usually the user's last selection).
          2. Any selected NodeItem in the scene (covers cases where
             the panel binding fell out of sync).
          3. The OUT IO node — full chain.

        Returns the chosen graph item; never returns None when the
        scene exists, so ``evaluate_chain_to`` always has a target.
        """
        from app.workbench.node_graph.items.io_node import IONodeItem
        from app.workbench.node_graph.items.node_item import NodeItem

        # Always render the full chain (IN→OUT) so all effects including
        # BlurNode are always visible. The selected node only controls which
        # grade the Color panel edits — it does NOT limit the render chain.
        return scene._out_node

    @staticmethod
    def _apply_node_effect(node, rgb: "np.ndarray", masks: list, frame_idx: int) -> "np.ndarray":
        """Apply a single node's effect to ``rgb``.

        Dispatches on NODE_KIND:
          - ``"serial"`` / ``"parallel"`` → ``apply_to_rgb(rgb, node.color_grade)``
          - ``"blur"`` → ``blur_params.apply_with_mask(rgb, mask, invert)``

        When the node has masks, the effect is applied only inside/outside
        the masked region (depending on the node's invert setting).
        """
        from app.node_mask import evaluate_node_masks
        kind = getattr(node, "NODE_KIND", "serial")
        if kind == "blur":
            bp = getattr(node, "blur_params", None)
            if bp is None or bp.is_identity():
                return rgb
            if masks:
                mask = evaluate_node_masks(masks, rgb, frame_idx)
            else:
                mask = None
            invert = bool(getattr(node, "blur_invert_mask", True))
            return bp.apply_with_mask(rgb, mask, invert_mask=invert)
        else:
            grade = getattr(node, "color_grade", None)
            if grade is None or grade.is_identity():
                return rgb
            from app.color_grading import apply_to_rgb
            if masks:
                mask = evaluate_node_masks(masks, rgb, frame_idx)
                if mask is not None:
                    graded = apply_to_rgb(rgb, grade).astype("float32")
                    mf = mask[..., None]
                    blended = mf * graded + (1.0 - mf) * rgb.astype("float32")
                    import numpy as _np
                    return _np.clip(blended, 0, 255).astype("uint8")
            return apply_to_rgb(rgb, grade)

    @staticmethod
    def _evaluate_node_chain_with_masks(scene, target_node=None):
        """Walk IN→target through rgb_in connections and return two
        parallel lists: ``[ColorGrade, ...]`` and ``[masks_list, ...]``.

        ``target_node`` defaults to the OUT IO node (= full pipeline).
        Pass any NodeItem / IONodeItem to evaluate the chain *up to
        and including* that node — the DaVinci "show this node's
        output" pattern.

        Bypassed nodes are skipped. Identity grades are kept here
        (ProjectPlayer drops them) so the indexes stay aligned with
        the user's node order while live editing — flipping back
        from contrast=10 to contrast=0 should not reorder rendering.
        """
        from app.workbench.node_graph.items.io_node import IONodeItem
        from app.workbench.node_graph.items.node_item import NodeItem
        from app.workbench.node_graph.items.parallel_mixer import (
            ParallelMixerItem,
        )
        if target_node is None:
            target_node = scene._out_node
        # Selecting the IN node means "show me the source" — empty
        # chain is the right answer (apply zero grades).
        if isinstance(target_node, IONodeItem) and target_node.kind == "IN":
            return [], []
        chain_nodes: list = []
        cur = target_node
        seen: set[int] = set()
        # If target is a real grade node we include it (its grade is
        # part of "up to this node"). If target is OUT we don't
        # include it — OUT has no grade — but we still walk back from
        # it through its rgb_in.
        if isinstance(cur, (NodeItem, ParallelMixerItem)):
            chain_nodes.append(cur)
            seen.add(id(cur))
        # Walk back via rgb_in, collecting upstream grade nodes.
        while True:
            in_port = getattr(cur, "rgb_in", None)
            if in_port is None or not in_port.connections:
                break
            up_conn = in_port.connections[0]
            upstream = up_conn.source.parentItem()
            if upstream is None or id(upstream) in seen:
                break
            seen.add(id(upstream))
            if isinstance(upstream, IONodeItem) and upstream.kind == "IN":
                break
            chain_nodes.append(upstream)
            cur = upstream
        chain_nodes.reverse()
        grades: list = []
        masks: list = []
        for n in chain_nodes:
            if not isinstance(n, (NodeItem, ParallelMixerItem)):
                continue
            if getattr(n, "bypassed", False):
                continue
            g = getattr(n, "color_grade", None)
            if g is None:
                continue
            grades.append(g)
            masks.append(getattr(n, "masks", None) or None)
        return grades, masks

    def _on_node_mask_request(self, node, kind: str) -> None:
        """All mask kinds route through MaskEditorWindow (large
        canvas) for spatial tools, or through simple dialogs for
        non-spatial ones (HSL Qualifier, Magic/Person)."""
        from app.node_mask import HSLQualifier, MagicMask, PowerWindow
        from app.node_mask_dialogs import HSLQualifierDialog, MagicMaskDialog
        if node is None:
            return
        on_change = self._refresh_preview_for_mask_edit

        if kind == "clear":
            node.masks = []
            node.update()
            self._rebuild_active_chain()
            return

        # HSL Qualifier -- sliders only, no spatial drawing.
        if kind == "hsl":
            mask = HSLQualifier()
            node.masks = [mask]
            self._rebuild_active_chain()
            HSLQualifierDialog(mask, on_change=on_change, parent=self).exec()
            on_change()
            return

        # Person / body segmentation -- automatic, no drawing.
        if kind.startswith("magic:"):
            feature = kind.split(":", 1)[1]
            if feature == "eyes":
                node.masks = [MagicMask(feature="left_eye"),
                               MagicMask(feature="right_eye")]
            else:
                node.masks = [MagicMask(feature=feature)]
            node.update()
            self._rebuild_active_chain()
            on_change()
            if node.masks and isinstance(node.masks[0], MagicMask):
                MagicMaskDialog(node.masks[0], on_change=on_change,
                                parent=self).exec()
                on_change()
            return

        # Spatial masks -- open MaskEditorWindow (large canvas).
        if kind in ("power_window", "roto:grabcut", "roto:sam", "edit"):
            rgb = self._current_preview_rgb()
            if rgb is None:
                self._flash_status(tr("nodemask.flash.no_frame"))
                return
            from app.mask_editor_window import MaskEditorWindow
            initial_tool = {
                "power_window": "polygon",
                "roto:grabcut": "rect",
                "roto:sam":     "click",
                "edit":         None,
            }.get(kind, "rect")
            dlg = MaskEditorWindow.open_for_node(
                rgb, node, on_commit=on_change, parent=self,
            )
            if initial_tool:
                dlg._set_tool(initial_tool)
            dlg.exec()
            on_change()
            return

    def _enter_grabcut_mode(self, node) -> None:
        """Stage 1 rotoscope — install a rect-drag hook on the
        DrawingCanvas so the next mouse drag on the preview becomes
        a GrabCut bounding box. Result mask is encoded into a
        BitmapMask and attached to ``node.masks``."""
        canvas = getattr(self, "_drawing_canvas", None)
        if canvas is None:
            return
        self._flash_status(tr("nodemask.flash.draw_rect"))
        self._roto_target = (node, "grabcut")
        canvas.set_rect_hook(self._on_rotoscope_rect)

    def _enter_sam_mode(self, node) -> None:
        """Stage 2 rotoscope — try SAM. Falls back to GrabCut when
        the library / model isn't available so the workflow still
        produces a result."""
        try:
            from app.sam_segment import is_sam_available
            sam_ok = is_sam_available()
        except Exception:
            sam_ok = False
        if not sam_ok:
            self._flash_status(tr("nodemask.flash.sam_unavailable"))
            self._enter_grabcut_mode(node)
            return
        # SAM uses a click hook (single point) instead of a rect
        # drag. Falls back to grabcut if the click misses content.
        canvas = getattr(self, "_drawing_canvas", None)
        if canvas is None:
            return
        self._flash_status(tr("nodemask.flash.draw_rect"))
        self._roto_target = (node, "sam")
        canvas.set_click_hook(self._on_sam_click)

    def _on_rotoscope_rect(self, nx, ny, nw, nh) -> None:
        """DrawingCanvas rect hook. ``(nx, ny, nw, nh)`` are
        normalised [0,1] coordinates of the user's drag rectangle.
        Run GrabCut against the current preview frame and bake the
        result into a BitmapMask attached to the active node."""
        canvas = getattr(self, "_drawing_canvas", None)
        if canvas is not None:
            canvas.set_rect_hook(None)
        target = getattr(self, "_roto_target", None)
        if not target:
            return
        node, _kind = target
        self._roto_target = None
        rgb = self._current_preview_rgb()
        if rgb is None:
            self._flash_status(tr("nodemask.flash.no_frame"))
            return
        from app.node_mask import BitmapMask, grabcut_from_rect
        mask_uint8 = grabcut_from_rect(rgb, (nx, ny, nw, nh), iterations=4)
        if mask_uint8 is None:
            return
        bm = BitmapMask()
        bm.set_from_array(mask_uint8)
        node.masks = [bm]
        node.update()
        self._rebuild_active_chain()
        self._refresh_preview_for_mask_edit()
        self._flash_status(tr("nodemask.flash.grabcut_done"))

    def _on_sam_click(self, nx, ny, kind: str) -> bool:
        """Stage 2 click hook — single point on object → SAM mask."""
        if kind != "click":
            return False
        canvas = getattr(self, "_drawing_canvas", None)
        if canvas is not None:
            canvas.set_click_hook(None)
        target = getattr(self, "_roto_target", None)
        if not target:
            return True
        node, _kind = target
        self._roto_target = None
        rgb = self._current_preview_rgb()
        if rgb is None:
            self._flash_status(tr("nodemask.flash.no_frame"))
            return True
        try:
            from app.sam_segment import sam_mask_from_point
            mask_uint8 = sam_mask_from_point(rgb, nx, ny)
        except Exception:
            mask_uint8 = None
        if mask_uint8 is None:
            self._flash_status(tr("nodemask.flash.sam_unavailable"))
            return True
        from app.node_mask import BitmapMask
        bm = BitmapMask()
        bm.set_from_array(mask_uint8)
        node.masks = [bm]
        node.update()
        self._rebuild_active_chain()
        self._refresh_preview_for_mask_edit()
        self._flash_status(tr("nodemask.flash.grabcut_done"))
        return True

    def _current_preview_rgb(self):
        """Pull the current preview frame as a uint8 H×W×3 RGB
        ndarray for rotoscope tools. Reads from ``_preview_pixmap``
        which the player keeps in sync via ``_on_frame_ready``.
        Returns ``None`` when no frame is available yet."""
        pix = getattr(self, "_preview_pixmap", None)
        if pix is None or pix.isNull():
            return None
        from PySide6.QtGui import QImage
        import numpy as np
        img = pix.toImage().convertToFormat(QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        if w <= 0 or h <= 0:
            return None
        bpl = img.bytesPerLine()
        buf = bytes(img.bits())[:bpl * h]
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, bpl)[:, :w * 3]
        return np.ascontiguousarray(arr.reshape(h, w, 3))

    def _refresh_preview_for_mask_edit(self) -> None:
        """Force a player frame re-render so mask edits show up
        without requiring the user to scrub.

        IMPORTANT: Must call ``_rebuild_active_chain`` first so that
        ``track.node_mask_chain`` reflects the newly-added/changed
        mask. Without this the player would render using the OLD chain
        (which had no mask), producing a gray preview when the user
        subsequently moves a colour slider."""
        # Rebuild chain so ProjectPlayer sees the new mask.
        self._rebuild_active_chain()
        if hasattr(self, "_player"):
            self._player.refresh_current_frame()
        # Also refresh the workbench thumbnails by re-pushing the
        # preview pixmap through the throttled path.
        if (hasattr(self, "_preview_pixmap") and self._preview_pixmap is not None
                and hasattr(self, "_workbench_panel")):
            try:
                self._workbench_panel.set_node_thumbnail(self._preview_pixmap)
            except Exception:
                pass
        # Repaint the node so its mask badge updates.
        wb = getattr(self, "_workbench_panel", None)
        if wb is not None:
            ngw = wb.expose_node_graph_widget()
            if ngw is not None:
                for n in ngw.scene._serial_nodes:
                    n.update()

    def _open_power_window_editor(self, node, mask) -> None:
        """Show the Power Window dialog and enter polygon-edit mode
        on the preview pane. Clicks on the preview append points to
        the mask; double-click closes / commits."""
        from app.node_mask_dialogs import PowerWindowDialog

        # Mark the editor as in polygon-edit mode so preview clicks
        # land on the mask instead of scrubbing.
        self._power_window_target = (node, mask)
        # Install click hook on the drawing canvas so its
        # mousePressEvent routes here while the dialog is open.
        canvas = getattr(self, "_drawing_canvas", None)
        if canvas is not None:
            canvas.set_click_hook(self._on_power_window_click)
            canvas._power_window_preview = mask
            canvas.update()
        dlg = PowerWindowDialog(
            mask, on_change=self._refresh_preview_for_mask_edit, parent=self,
        )
        self._power_window_dialog = dlg
        try:
            dlg.exec()
        finally:
            if canvas is not None:
                canvas.set_click_hook(None)
                canvas._power_window_preview = None
                canvas.update()
            self._power_window_target = None
            self._power_window_dialog = None
            self._refresh_preview_for_mask_edit()

    def _on_power_window_click(self, nx: float, ny: float, kind: str) -> bool:
        """DrawingCanvas click hook for Power Window polygon edit.
        ``kind`` is ``"click"`` (add point) or ``"double"`` (commit).
        Returns True to consume the click."""
        if not getattr(self, "_power_window_target", None):
            return False
        node, mask = self._power_window_target
        if kind == "double":
            # Double-click closes the polygon — no-op on the data
            # since polygons are already closed implicitly. Just
            # refresh and let the user keep editing if they want.
            self._refresh_preview_for_mask_edit()
            dlg = getattr(self, "_power_window_dialog", None)
            if dlg is not None and hasattr(dlg, "refresh_points_count"):
                dlg.refresh_points_count()
            return True
        mask.points.append((float(nx), float(ny)))
        self._refresh_preview_for_mask_edit()
        dlg = getattr(self, "_power_window_dialog", None)
        if dlg is not None and hasattr(dlg, "refresh_points_count"):
            dlg.refresh_points_count()
        return True

    def _on_node_graph_selection(self, node) -> None:
        """User picked a NodeItem/BlurNodeItem (or deselected).
        Routes to the right panel based on node kind:
          - ColorNode → colour dock + _node_grade_target
          - BlurNode  → workbench blur controls
          - None      → fall back to primary node
        """
        from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
        wb = getattr(self, "_workbench_panel", None)
        ngw = wb.expose_node_graph_widget() if wb is not None else None
        is_blur = isinstance(node, BlurNodeItem)
        if node is not None and not is_blur:
            # Color node selected: show chain up to this node.
            self._node_grade_target = node
        elif is_blur or node is None:
            # Blur node selected OR nothing selected:
            # → always show the full IN→OUT chain so Blur/other
            #   effect nodes are always included in the preview.
            # DaVinci behaviour: deselecting returns to final output.
            self._node_grade_target = (
                ngw.scene._out_node if ngw is not None else None
            )
        # Pull the now-active grade into the slider widgets.
        if hasattr(self, "_sync_color_panel"):
            self._sync_color_panel()
        # Reveal / hide the color dock (color nodes only).
        self._update_color_dock_visibility(node if not is_blur else None)
        # Route blur controls in workbench.
        if wb is not None and hasattr(wb, "set_blur_node"):
            if is_blur:
                wb.set_blur_node(node, on_change=self._on_blur_params_changed)
            else:
                wb.set_blur_node(None)
        # Retarget the main preview pipeline so the user sees IN→
        # selected-node output. Without this the preview always
        # showed full IN→OUT regardless of which node the user was
        # tweaking — confusing because mid-chain edits looked
        # smaller than they actually were.
        self._rebuild_active_chain()
        # When the selected node has a non-identity grade (e.g. a
        # colour-wheel position was saved from a previous session),
        # immediately refresh the preview so the user can SEE the
        # current grade before they touch anything. Without this the
        # preview looked unchanged after node selection and only
        # went "gray" on the first interaction, which felt like a bug.
        if (node is not None
                and hasattr(node, "color_grade")
                and node.color_grade is not None
                and not node.color_grade.is_identity()):
            from app.simple_video_player import PlayerState
            if (hasattr(self, "_player")
                    and self._player.state() is not PlayerState.PLAYING):
                self._player.refresh_current_frame()

    def _update_color_dock_visibility(self, selected_node=None) -> None:
        """Show the bottom color dock only when a colour-grading node
        is the active selection. Other node types (future Blur / LUT /
        etc.) will surface their controls in the right-side workbench
        panel — keeping the bottom dock dedicated to wide-format
        wheel work where it actually fits."""
        # If a popout is open the header strip is showing a
        # placeholder, not the panel — leave it alone.
        if getattr(self, "_color_popout", None) is not None:
            return
        if not hasattr(self, "_color_header_widget"):
            return
        from app.workbench.node_graph.items.node_item import NodeItem
        # Color-grading nodes today are vanilla Serial NodeItems —
        # they all have a ``color_grade`` field. Future filter-only
        # nodes (Blur, etc.) will subclass NodeItem with a different
        # NODE_KIND and we'll exclude those here.
        is_color_node = (
            selected_node is not None
            and isinstance(selected_node, NodeItem)
            and getattr(selected_node, "color_grade", None) is not None
        )
        self._color_header_widget.setVisible(is_color_node)
        self._color_row_host.setVisible(is_color_node)
        # Mask toolbar follows the dock — same activation rule.
        if hasattr(self, "_mask_toolbar_widget"):
            self._mask_toolbar_widget.setVisible(is_color_node)
        # Show/hide the splitter pane that wraps header + toolbar + row.
        # When hidden the splitter collapses that pane to zero so the
        # timeline section gets all the available vertical space.
        if hasattr(self, "_color_container"):
            self._color_container.setVisible(is_color_node)

    def _mask_toolbar_action(self, kind: str) -> None:
        """Toolbar handler — applies the requested mask kind to the
        currently bound node (``_node_grade_target``). Empty target
        = no-op (the toolbar is only visible when a colour node is
        selected, so this guard rarely fires in practice)."""
        node = getattr(self, "_node_grade_target", None)
        if node is None:
            return
        # Reuse the right-click handler so toolbar + context menu
        # share one code path.
        self._on_node_mask_request(node, kind)

    def _sync_color_panel(self) -> None:
        """Pull current track's grade into wheels + knobs + preset
        label. Blocks signals so this isn't recorded as a user-driven
        change. Safe to call before a track exists."""
        grade = self._active_color_grade()
        for key, knob in getattr(self, "_color_sliders", {}).items():
            value = int(getattr(grade, key)) if grade is not None else 0
            knob.blockSignals(True)
            knob.setValue(float(value), emit=False)
            knob.blockSignals(False)
        for region, wheel in getattr(self, "_color_wheels", {}).items():
            if grade is not None:
                x = int(getattr(grade, f"{region}_x", 0))
                y = int(getattr(grade, f"{region}_y", 0))
                lv = int(getattr(grade, f"{region}_l", 0))
            else:
                x = y = lv = 0
            wheel.set_value(x, y, emit=False)
            # Sync luma arc indicator
            if hasattr(wheel, "set_luma"):
                wheel.set_luma(lv, emit=False)
            # Sync readout spinboxes
            self._update_wheel_readouts(region, x, y)
        for region, luma in getattr(self, "_color_lumas", {}).items():
            value = int(getattr(grade, f"{region}_l", 0)) if grade is not None else 0
            luma.blockSignals(True)
            luma.setValue(value)
            luma.blockSignals(False)
        for region, dial in getattr(self, "_color_luma_dials", {}).items():
            v = int(getattr(grade, f"{region}_l", 0)) if grade is not None else 0
            dial.blockSignals(True)
            dial.set_value(v, emit=False)
            dial.blockSignals(False)
        if hasattr(self, "_hue_curve"):
            pts = list(grade.hue_vs_hue) if grade is not None else []
            # Block signal so set_points doesn't bounce back through
            # _on_hue_curve_changed and dirty the preset id.
            self._hue_curve.blockSignals(True)
            self._hue_curve.set_points(pts)
            self._hue_curve.blockSignals(False)
        self._refresh_color_preset_btn_label()
        self._build_color_preset_menu()

    def _on_color_slider_changed(self, key: str, value: int) -> None:
        import sys
        grade = self._active_color_grade()
        if grade is None:
            return
        setattr(grade, key, int(value))
        # Any manual knob drag detaches the grade from a named preset.
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        # Re-render the current frame so the preview reflects the change.
        self._player.set_position(self._player.position())

    def _on_color_wheel_changed(self, region: str, x: int, y: int) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        setattr(grade, f"{region}_x", int(x))
        setattr(grade, f"{region}_y", int(y))
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        # Update R/G/B readout spinboxes from wheel x/y
        self._update_wheel_readouts(region, x, y)
        # Sync wheel positions across panels
        self._sync_both_color_panels_except(region)
        # Force preview refresh — must use refresh_current_frame so the
        # GPU grading uniforms are recomputed even without a seek.
        self._player.refresh_current_frame()

    def _sync_both_color_panels_except(self, changed_region: str = "") -> None:
        """Lightweight sync: update dock wheels from grade."""
        grade = self._active_color_grade()
        if grade is None:
            return
        for region, wheel in getattr(self, "_color_wheels", {}).items():
            x = int(getattr(grade, f"{region}_x", 0))
            y = int(getattr(grade, f"{region}_y", 0))
            wheel.set_value(x, y, emit=False)

    def _update_wheel_readouts(self, region: str, x: int, y: int) -> None:
        """Update R/G/B spinbox readouts for the given region's wheel position."""
        sbs = getattr(self, "_color_readouts", {}).get(region)
        if not sbs or len(sbs) < 3:
            return
        try:
            from app.color_grading import _wheel_to_rgb_offset
            dR, dG, dB = _wheel_to_rgb_offset(x, y)
            for sb, v in zip(sbs[:3], (dR, dG, dB)):
                if sb is not None:
                    sb.blockSignals(True)
                    sb.setValue(round(float(v), 2))
                    sb.blockSignals(False)
        except Exception:
            pass

    def _on_color_luma_changed(self, region: str, value: int) -> None:
        """Per-region luma slider drag — mutate the matching ``_l``
        field on the active grade and re-render the preview."""
        grade = self._active_color_grade()
        if grade is None:
            return
        setattr(grade, f"{region}_l", int(value))
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        self._player.set_position(self._player.position())

    def _on_hue_curve_changed(self, points) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        grade.hue_vs_hue = list(points)
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        self._player.set_position(self._player.position())

    def _on_color_reset(self) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        grade.reset()
        self._sync_color_panel()
        self._player.set_position(self._player.position())

    def _refresh_color_preset_btn_label(self) -> None:
        from app.color_grading import get_preset
        grade = self._active_color_grade()
        if grade is None:
            label = tr("color.preset.none")
        elif grade.preset_id == "custom":
            label = tr("color.preset.custom")
        else:
            label = tr(get_preset(grade.preset_id).name_key)
        self._color_preset_btn.setText(
            f"{tr('color.preset.label')}: {label}  ▾"
        )

    def _build_color_preset_menu(self) -> None:
        from app.color_grading import COLOR_PRESETS
        from app import tier
        menu = QMenu(self._color_preset_btn)
        menu.setObjectName("ColorPresetMenu")
        menu.setStyleSheet(
            f"QMenu#ColorPresetMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#ColorPresetMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; margin: 1px 0px; }}"
            f"QMenu#ColorPresetMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#ColorPresetMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
        )
        grade = self._active_color_grade()
        current_id = grade.preset_id if grade is not None else "none"
        for p in COLOR_PRESETS:
            badge = ""
            if tier.requires_pro(p.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(p.feature_id) else "★ PRO  "
            label = f"{p.icon}  {badge}{tr(p.name_key)}  ·  {tr(p.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(p.id == current_id)
            act.triggered.connect(
                lambda _checked=False, pid=p.id: self._on_color_preset_picked(pid)
            )
        self._color_preset_btn.setMenu(menu)

    def _on_color_preset_picked(self, preset_id: str) -> None:
        from app.color_grading import apply_preset, get_preset
        from app import tier
        p = get_preset(preset_id)
        if tier.is_locked(p.feature_id):
            self._show_upsell(p.feature_id, tr(p.name_key))
            self._build_color_preset_menu()
            return
        grade = self._active_color_grade()
        if grade is None:
            return
        apply_preset(grade, preset_id)
        self._sync_color_panel()
        self._player.set_position(self._player.position())

    def _on_new_project(self) -> None:
        """Open the New Project dialog and reset the session."""
        from app.new_project_dialog import NewProjectDialog
        from PySide6.QtWidgets import QMessageBox
        from app.project_io import _clear_editor

        # Warn if there are unsaved changes
        if self._tracks or self._audio_tracks:
            btn = QMessageBox.question(
                self, "새 프로젝트",
                "현재 프로젝트를 닫고 새로 만드시겠습니까?\n저장하지 않은 변경 사항은 사라집니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if btn != QMessageBox.StandardButton.Yes:
                return

        dlg = NewProjectDialog(self)
        if dlg.exec() != NewProjectDialog.DialogCode.Accepted:
            return
        s = dlg.result_settings
        if s is None:
            return

        # Store project settings on the editor
        self._project_settings = {
            "name": s.name,
            "canvas_width": s.width,
            "canvas_height": s.height,
            "fps": s.fps,
            "ratio_label": s.ratio_label,
        }

        # Apply FPS to the player reference rate
        self._player.REFERENCE_FPS = s.fps

        # Apply canvas ratio to the export defaults
        self._export_resolution = (s.width, s.height)
        self._export_fps = s.fps

        # Clear current session
        _clear_editor(self)
        self._project_path = None
        self.setWindowTitle(f"TigerCapture — {s.name}  [{s.ratio_label}  {s.width}×{s.height}  {s.fps:.3g}fps]")
        self._refresh_player_tracks()

        # Show project settings badge in toolbar
        if not hasattr(self, "_proj_info_label"):
            from PySide6.QtWidgets import QLabel as _QLabel
            self._proj_info_label = _QLabel()
            self._proj_info_label.setStyleSheet(
                "color:#8899cc; font-size:10px; padding:2px 6px;"
                "background:#202030; border-radius:3px;"
            )
            # Insert after new_project_btn in toolbar (best-effort)
            try:
                self.new_project_btn.parentWidget().layout().insertWidget(1, self._proj_info_label)
            except Exception:
                pass
        self._proj_info_label.setText(f"{s.ratio_label}  {s.width}×{s.height}  {s.fps:.3g}fps")

    def _on_save_project(self) -> None:
        """Save the current session to a .tgp file."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.project_io import save_project, EXTENSION
        path, _ = QFileDialog.getSaveFileName(
            self,
            "프로젝트 저장",
            "",
            f"TigerCapture 프로젝트 (*{EXTENSION});;모든 파일 (*.*)",
        )
        if not path:
            return
        try:
            save_project(self, path)
            self._project_path = Path(path)
            QMessageBox.information(self, "저장 완료", f"저장됨:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))

    def _do_autosave(self) -> None:
        """Auto-save handler — fires every 5 minutes. Saves silently to a
        sibling ``*~autosave.tgp`` file and shows a brief status banner."""
        from app.project_io import save_project
        try:
            if self._project_path is not None:
                autosave_path = self._project_path.with_name(
                    self._project_path.stem + "~autosave.tgp"
                )
            else:
                autosave_path = Path.home() / "autosave.tgp"
            save_project(self, autosave_path)
            self._flash_status("자동 저장됨")
        except Exception:
            pass  # Never interrupt the user

    def _on_open_project(self) -> None:
        """Open a .tgp project file, replacing the current session."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.project_io import load_project, EXTENSION
        path, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트 열기",
            "",
            f"TigerCapture 프로젝트 (*{EXTENSION});;모든 파일 (*.*)",
        )
        if not path:
            return
        reply = QMessageBox.question(
            self,
            "프로젝트 열기",
            "현재 세션이 닫힙니다.\n저장하지 않은 작업은 사라집니다.\n계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            load_project(self, path)
            self._project_path = Path(path)
        except Exception as e:
            import traceback
            detail = traceback.format_exc()
            QMessageBox.warning(self, "열기 실패", f"{e}\n\n{detail[:800]}")

    def _on_export(self) -> None:
        track = self._active_track()
        if track is None or track.source_path is None:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_source")
            )
            return
        # Phase 1.5e: drive segments from ``track.clips`` so user splits
        # + per-clip drags actually show up in the exported file.
        # ``build_segments_from_clips`` falls back to one segment per
        # clip in project-time order; for a single-clip track the
        # output is byte-equivalent to the legacy ``build_segments``.
        segments = build_segments_from_clips(
            track.clips, track.speed_segments,
        )
        if not segments:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_segments")
            )
            return

        from app.video_exporter import get_export_format
        fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))
        default_name = f"{track.source_path.stem}_edited{fmt.extension}"
        default_path = track.source_path.parent / default_name
        filter_str = tr(f"veditor.export.filter.{fmt.id}")
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("veditor.export.dialog_title"),
            str(default_path),
            filter_str,
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != fmt.extension:
            out = out.with_suffix(fmt.extension)

        # HDR Phase 2b: when the source is HDR and the container can
        # carry HEVC (mp4 / mov), offer the user a passthrough vs
        # tonemap choice. WebM doesn't support HEVC, so HDR sources
        # always tonemap into VP9 SDR there. The dialog defaults to
        # "Keep HDR" for HEVC-friendly containers because that's the
        # losslessness expectation.
        hdr_info = getattr(track, "hdr_info", None)
        hdr_passthrough = False
        if (
            hdr_info is not None
            and getattr(hdr_info, "is_hdr", False)
            and fmt.extension in (".mp4", ".mov")
        ):
            label = getattr(hdr_info, "standard_label", "HDR")
            choice = QMessageBox.question(
                self,
                tr("veditor.export.hdr_dialog.title"),
                tr("veditor.export.hdr_dialog.body", label=label),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            hdr_passthrough = choice == QMessageBox.StandardButton.Yes

        from PySide6.QtWidgets import QProgressDialog

        total = int(sum((e - s) / sp for (s, e, sp) in segments) + 0.5)
        dlg = QProgressDialog(
            tr("veditor.export.note"),
            None,
            0,
            max(1, total),
            self,
        )
        dlg.setWindowTitle(tr("veditor.export.progress_title"))
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setCancelButton(None)
        dlg.show()

        # Typography actors live per-VideoTrack in track-local source
        # ms. Pass the active track's actors as (start, end, clip)
        # tuples — they'll be rendered to alpha MOVs and overlaid by
        # the exporter. (Phase 5b: support actors on inactive tracks
        # via project-time mapping.)
        from app import tier
        all_actors = [
            (actor.start_ms, actor.end_ms, actor)
            for actor in getattr(track, "typography_actors", [])
            if actor.end_ms > actor.start_ms
        ]
        if all_actors and tier.is_locked("export.typography"):
            # Free user has typography placed but it can't ship in the
            # rendered file. Confirm before stripping so they know why
            # the output looks different from preview.
            choice = QMessageBox.warning(
                self,
                tr("upsell.title"),
                tr("export.typography.locked.body", count=len(all_actors)),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            text_actors_source: list = []
        else:
            text_actors_source = all_actors

        _res = getattr(self, "_export_resolution", None)
        _fps = getattr(self, "_export_fps", None)
        thread = VideoExportThread(
            track.source_path,
            out,
            segments,
            self._subtitle_panel.subtitles(),
            self._strokes,
            cuts=track.cuts,
            fade_segments=track.fades,
            bubbles=self._bubbles,
            stickers=self._stickers,
            audio_tracks=[t for t in self._audio_tracks if t.is_loaded],
            text_actors_source=text_actors_source,
            quality_id=getattr(self, "_export_quality_id", "high"),
            format_id=getattr(self, "_export_format_id", "mp4"),
            color_grade=getattr(track, "color_grade", None),
            zoom_actors=list(getattr(track, "zoom_actors", []) or []),
            hdr_info=hdr_info,
            hdr_passthrough=hdr_passthrough,
            target_width=_res[0] if _res is not None else None,
            target_height=_res[1] if _res is not None else None,
            target_fps=_fps,
        )
        thread.progress.connect(
            lambda cur, tot: (dlg.setMaximum(max(1, tot)), dlg.setValue(cur))
        )
        thread.stage.connect(
            lambda s: dlg.setLabelText(f"{s}\n\n{tr('veditor.export.note')}")
        )

        def _on_success(p: Path, size: int) -> None:
            dlg.close()
            QMessageBox.information(
                self,
                tr("veditor.title"),
                tr(
                    "veditor.export.done",
                    path=str(p),
                    size=_format_size(size),
                ),
            )

        def _on_error(msg: str) -> None:
            dlg.close()
            QMessageBox.critical(
                self, tr("veditor.export.failed"), msg
            )

        thread.finished_success.connect(_on_success)
        thread.finished_error.connect(_on_error)
        thread.finished.connect(thread.deleteLater)
        self._export_thread = thread  # keep reference
        thread.start()

    def _on_batch_export(self) -> None:
        """Open the batch-export queue dialog.

        Marker segments on the timeline ruler become individual export jobs.
        If no markers are set, a single job for the full project is created.
        Each job exports the active video track's content trimmed to that
        time range.  The user picks an output folder via QFileDialog, and the
        dialog runs the jobs sequentially.
        """
        from app.batch_export_dialog import BatchExportDialog, BatchExportItem

        track = self._active_track()
        if track is None or track.source_path is None:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_source")
            )
            return

        # Collect marker-defined ranges.  Markers are stored as
        # {"ms": int, "color": str, "label": str} in self._timeline_markers.
        markers = sorted(self._timeline_markers, key=lambda m: m["ms"])
        project_end_ms = max(self._player.duration(), 1)

        if len(markers) >= 2:
            ranges = [
                (markers[i]["ms"], markers[i + 1]["ms"],
                 markers[i].get("label") or f"Segment {i + 1}")
                for i in range(len(markers) - 1)
            ]
        elif len(markers) == 1:
            ranges = [(markers[0]["ms"], project_end_ms,
                       markers[0].get("label") or "Segment 1")]
        else:
            ranges = [(0, project_end_ms, "Full export")]

        # Filter out zero-length segments.
        ranges = [(s, e, lbl) for s, e, lbl in ranges if e > s]
        if not ranges:
            QMessageBox.information(
                self, "일괄 내보내기", "내보낼 구간이 없습니다."
            )
            return

        from app.video_exporter import get_export_format
        fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))

        # Ask for output folder.
        out_folder = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택", str(track.source_path.parent)
        )
        if not out_folder:
            return
        out_dir = Path(out_folder)

        items = [
            BatchExportItem(
                label=lbl,
                out_path=str(out_dir / f"{track.source_path.stem}_{lbl}{fmt.extension}"),
                in_ms=in_ms,
                out_ms=out_ms,
            )
            for in_ms, out_ms, lbl in ranges
        ]

        # Per-segment export factory passed to BatchExportDialog.
        # Returns a QThread with .start() and .finished signal.
        def _export_fn(in_ms: int, out_ms: int, out_path: str, progress_cb=None):
            from app.video_exporter import VideoExportThread, build_segments_from_clips

            segments = build_segments_from_clips(track.clips, track.speed_segments)
            trimmed = []
            for seg_start, seg_end, speed in segments:
                s = max(seg_start, in_ms)
                e = min(seg_end, out_ms)
                if e > s:
                    trimmed.append((s, e, speed))
            if not trimmed:
                trimmed = [(in_ms, out_ms, 1.0)]

            _t = VideoExportThread(
                track.source_path,
                Path(out_path),
                trimmed,
                self._subtitle_panel.subtitles(),
                self._strokes,
                cuts=track.cuts,
                fade_segments=track.fades,
                bubbles=self._bubbles,
                stickers=self._stickers,
                audio_tracks=[_a for _a in self._audio_tracks if _a.is_loaded],
                text_actors_source=[],
                quality_id=getattr(self, "_export_quality_id", "high"),
                format_id=getattr(self, "_export_format_id", "mp4"),
                color_grade=getattr(track, "color_grade", None),
                zoom_actors=list(getattr(track, "zoom_actors", []) or []),
            )
            if progress_cb is not None:
                _t.progress.connect(
                    lambda cur, tot: progress_cb(int(cur * 100 / max(tot, 1)))
                )
            return _t

        dlg = BatchExportDialog(items, _export_fn, parent=self)
        dlg.exec()

    def _on_player_error(self, msg: str) -> None:
        import sys as _sys

        print(f"[veditor] player error: {msg}", file=_sys.stderr, flush=True)
        QMessageBox.warning(self, tr("veditor.title"), msg)


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _format_speed(p: float) -> str:
    """Format a speed factor as '2x' or '0.5x' for UI labels."""
    if abs(p - round(p)) < 1e-3:
        return f"{int(round(p))}x"
    return f"{p:g}x"


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
