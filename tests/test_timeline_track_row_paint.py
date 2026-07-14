from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

import app.timeline_track_row_paint as paint_mod
from app.timeline_model import CutSegment, VideoClip, VideoTrack
from app.timeline_track_row import TRACK_V_PADDING, TrackRow
from app.timeline_track_row_paint import (
    _paint_timeline_playhead_sharp_thumb_window,
    _paint_timeline_thumb_tile_layer,
    _paint_clip_track_identity_strip,
    _timeline_playhead_detail_boost,
    _timeline_thumb_tile_left_fade,
    _timeline_thumb_tile,
    _timeline_playhead_sharp_window_metrics,
    _timeline_track_focus_values,
    _timeline_thumb_blend_width,
    _timeline_thumb_tile_rects,
)
from app.studio_theme import paint_studio_playhead


def _ensure_qapp():
    return QApplication.instance() or QApplication([])


def test_timeline_thumb_tiles_cover_long_clip_with_overlap():
    preview = QRect(100, 12, 920, 44)
    blend = _timeline_thumb_blend_width(240, preview.height())

    rects = _timeline_thumb_tile_rects(preview, 240, blend)

    assert len(rects) > 1
    assert rects[0].left() == preview.left()
    assert rects[-1].right() >= preview.right()
    for prev, nxt in zip(rects, rects[1:]):
        assert prev.right() - nxt.left() + 1 >= blend - 1


def test_timeline_thumb_blend_is_strong_but_never_consumes_tile():
    blend = _timeline_thumb_blend_width(180, 48)

    assert blend >= 48
    assert blend < 180


def test_timeline_thumb_tiles_handle_short_visible_clip():
    preview = QRect(40, 10, 36, 30)
    blend = _timeline_thumb_blend_width(80, preview.height())

    rects = _timeline_thumb_tile_rects(preview, 80, blend)

    assert len(rects) == 1
    assert rects[0].left() == preview.left()
    assert rects[0].right() >= preview.right()


def _striped_thumb(width: int = 180, height: int = 56) -> QPixmap:
    thumb = QPixmap(width, height)
    thumb.fill(QColor(28, 30, 34))
    painter = QPainter(thumb)
    for x in range(0, width, 3):
        color = QColor(246, 248, 252) if (x // 3) % 2 == 0 else QColor(22, 26, 30)
        painter.fillRect(x, 0, 3, height, color)
    painter.end()
    return thumb


def _window_edge_contrast(image, x: int, y: int, width: int, height: int) -> float:
    total = 0.0
    count = 0
    for yy in range(max(0, y), min(image.height(), y + height)):
        prev = None
        for xx in range(max(0, x), min(image.width(), x + width)):
            color = image.pixelColor(xx, yy)
            luma = (color.red() + color.green() + color.blue()) / 3.0
            if prev is not None:
                total += abs(luma - prev)
                count += 1
            prev = luma
    return total / max(1, count)


def test_playhead_sharp_thumbnail_window_restores_detail_over_blur():
    _ensure_qapp()
    thumb = _striped_thumb()
    preview = QRect(20, 10, 820, 56)
    blend = _timeline_thumb_blend_width(160, preview.height())
    tile_rects = _timeline_thumb_tile_rects(preview, 160, blend)
    playhead_x = preview.left() + preview.width() // 2

    canvas = QPixmap(870, 84)
    canvas.fill(QColor(6, 8, 10))
    painter = QPainter(canvas)
    pixmap_for_rect = lambda _rect: thumb
    _paint_timeline_thumb_tile_layer(
        None,
        painter,
        preview,
        tile_rects,
        blend,
        1.0,
        pixmap_for_rect,
    )
    _paint_timeline_playhead_sharp_thumb_window(
        SimpleNamespace(_px_per_sec=90.0),
        painter,
        preview,
        tile_rects,
        blend,
        pixmap_for_rect,
        playhead_x,
    )
    painter.end()

    image = canvas.toImage()
    sharp = _window_edge_contrast(image, playhead_x - 20, preview.top() + 8, 40, 36)
    blurred = _window_edge_contrast(image, preview.left() + 14, preview.top() + 8, 40, 36)
    assert sharp > blurred + 5.0


def test_playhead_detail_boost_increases_thumbnail_contrast():
    _ensure_qapp()
    thumb = _striped_thumb(width=180, height=56)

    boosted = _timeline_playhead_detail_boost(thumb)

    original_contrast = _window_edge_contrast(thumb.toImage(), 20, 8, 80, 40)
    boosted_contrast = _window_edge_contrast(boosted.toImage(), 20, 8, 80, 40)
    assert boosted_contrast > original_contrast * 1.10


def test_studio_playhead_paints_crisp_opaque_core():
    _ensure_qapp()
    canvas = QPixmap(24, 32)
    canvas.fill(QColor(0, 0, 0, 0))
    painter = QPainter(canvas)
    paint_studio_playhead(painter, 12, 2, 29, show_handle=False)
    painter.end()

    image = canvas.toImage()
    core = image.pixelColor(12, 14)
    left = image.pixelColor(10, 14)
    right = image.pixelColor(14, 14)

    assert core.alpha() == 255
    assert core.red() > 240
    assert left.alpha() == 0
    assert right.alpha() == 0


def test_timeline_soft_thumb_uses_layered_blur_not_plain_solid():
    _ensure_qapp()
    thumb = _striped_thumb(width=180, height=56)

    sharp = _timeline_thumb_tile(None, thumb, 180, 56, 0.0)
    soft = _timeline_thumb_tile(None, thumb, 180, 56, 1.0)

    sharp_contrast = _window_edge_contrast(sharp.toImage(), 20, 8, 80, 40)
    soft_contrast = _window_edge_contrast(soft.toImage(), 20, 8, 80, 40)
    assert soft_contrast < sharp_contrast * 0.55
    assert soft_contrast > 0.5


def test_timeline_thumb_crossfade_uses_continuous_alpha_gradient():
    _ensure_qapp()
    tile = QPixmap(100, 24)
    tile.fill(QColor(220, 120, 40, 255))

    faded = _timeline_thumb_tile_left_fade(tile, 60).toImage()
    alphas = [faded.pixelColor(x, 12).alpha() for x in range(0, 61)]

    assert alphas[0] < 8
    assert alphas[-1] > 246
    assert all(left <= right for left, right in zip(alphas, alphas[1:]))
    assert len(set(alphas)) > 30


def test_track_focus_reduces_selected_track_blur_while_preserving_playhead_reveal():
    active_soften, active_opacity, active_detail = _timeline_track_focus_values(True)
    inactive_soften, inactive_opacity, inactive_detail = _timeline_track_focus_values(False)

    assert active_soften == inactive_soften * 0.70
    assert active_opacity > inactive_opacity
    assert active_opacity == 0.76
    assert inactive_opacity == 0.64
    assert active_detail == inactive_detail == 1.0


def test_video_track_row_uses_compact_separator_instead_of_header_gap():
    row = TrackRow(_track_with_pattern_thumbnails())

    assert row.LABEL_H == 0
    assert row.height() == row.LABEL_H + row.TIMELINE_H + TRACK_V_PADDING
    assert TRACK_V_PADDING == 0
    assert row.height() == row.TIMELINE_H


def test_clip_track_identity_strip_uses_track_accent_color():
    _ensure_qapp()
    canvas = QPixmap(90, 42)
    canvas.fill(QColor(0, 0, 0, 0))
    painter = QPainter(canvas)
    accent = QColor("#89B4D6")
    _paint_clip_track_identity_strip(
        painter,
        QRect(10, 4, 70, 34),
        accent,
        active=True,
        selected=False,
    )
    painter.end()

    pixel = canvas.toImage().pixelColor(14, 20)
    assert pixel.alpha() > 180
    assert pixel.blue() > pixel.red()


def test_playhead_sharp_window_uses_higher_detail_and_wider_blend():
    preview = QRect(20, 10, 820, 56)
    playhead_x = preview.left() + preview.width() // 2
    old_sharp = int(max(28, min(120, 90.0 * 0.78)))
    old_feather = int(max(36, min(144, 90.0 * 0.90, old_sharp * 2)))

    metrics = _timeline_playhead_sharp_window_metrics(
        SimpleNamespace(_px_per_sec=90.0),
        preview,
        playhead_x,
    )

    assert metrics is not None
    _left, _right, sharp_half, feather = metrics
    assert sharp_half >= int(old_sharp * 1.3)
    assert feather >= int(old_feather * 1.5)


def _track_with_pattern_thumbnails() -> VideoTrack:
    thumb = _striped_thumb()
    clip = VideoClip(
        id=101,
        source_path=Path("sample.mp4"),
        source_duration_ms=6_000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=6_000,
        thumbnails=[thumb] * 6,
    )
    track = VideoTrack(id=4, clips=[clip])
    for name, value in {
        "offset_ms": 0,
        "source_path": Path("sample.mp4"),
        "thumbnails": clip.thumbnails,
        "speed_segments": [],
        "cuts": [],
        "fades": [],
        "typography_actors": [],
        "zoom_actors": [],
    }.items():
        setattr(track, name, value)
    return track


def _track_with_two_clips_and_gap() -> VideoTrack:
    thumb = _striped_thumb()
    clip_a = VideoClip(
        id=201,
        source_path=Path("sample.mp4"),
        source_duration_ms=1_000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=1_000,
        thumbnails=[thumb] * 2,
    )
    clip_b = VideoClip(
        id=202,
        source_path=Path("sample.mp4"),
        source_duration_ms=1_000,
        timeline_in_ms=2_000,
        source_in_ms=0,
        source_out_ms=1_000,
        thumbnails=[thumb] * 2,
    )
    track = VideoTrack(id=2, clips=[clip_a, clip_b])
    for name, value in {
        "offset_ms": 0,
        "source_path": Path("sample.mp4"),
        "thumbnails": clip_a.thumbnails,
        "speed_segments": [],
        "cuts": [],
        "fades": [],
        "typography_actors": [],
        "zoom_actors": [],
    }.items():
        setattr(track, name, value)
    return track


def _track_with_legacy_cut_overlay() -> VideoTrack:
    thumb = _striped_thumb()
    clip = VideoClip(
        id=301,
        source_path=Path("sample.mp4"),
        source_duration_ms=3_000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=3_000,
        thumbnails=[thumb] * 4,
    )
    track = VideoTrack(id=2, clips=[clip])
    for name, value in {
        "offset_ms": 0,
        "source_path": Path("sample.mp4"),
        "thumbnails": clip.thumbnails,
        "speed_segments": [],
        "cuts": [CutSegment(1_000, 1_800)],
        "fades": [],
        "typography_actors": [],
        "zoom_actors": [],
    }.items():
        setattr(track, name, value)
    return track


def _render_track_pixel(track: VideoTrack, project_ms: int) -> QColor:
    _ensure_qapp()
    row = TrackRow(track)
    row.set_px_per_sec(90.0)
    row.resize(640, row.height())
    row.show()
    QApplication.processEvents()
    canvas = QPixmap(row.width(), row.height())
    canvas.fill(QColor(0, 0, 0))
    row.render(canvas)
    image = canvas.toImage()
    return image.pixelColor(
        row._project_ms_to_x(project_ms),
        row.LABEL_H + row.TIMELINE_H // 2,
    )


def test_track_background_keeps_track_hue_inside_empty_clip_gap():
    pixel = _render_track_pixel(_track_with_two_clips_and_gap(), 1_500)

    assert pixel.blue() > pixel.red() + 2
    assert pixel.green() >= pixel.red()


def test_legacy_cut_overlay_preserves_track_background_hue():
    pixel = _render_track_pixel(_track_with_legacy_cut_overlay(), 1_400)

    assert pixel.blue() > pixel.red() + 2
    assert pixel.green() >= pixel.red()


def test_track_row_paints_playhead_sharp_window_for_visible_clip(monkeypatch):
    _ensure_qapp()
    row = TrackRow(_track_with_pattern_thumbnails())
    row.set_px_per_sec(90.0)
    row.set_position(2_400)
    row.resize(760, row.height())
    calls: list[int] = []
    original = paint_mod._paint_timeline_playhead_sharp_thumb_window

    def spy(owner, painter, preview_rect, tile_rects, blend_w, pixmap_for_rect, playhead_x, **kwargs):
        calls.append(int(playhead_x))
        return original(owner, painter, preview_rect, tile_rects, blend_w, pixmap_for_rect, playhead_x, **kwargs)

    monkeypatch.setattr(paint_mod, "_paint_timeline_playhead_sharp_thumb_window", spy)
    canvas = QPixmap(row.width(), row.height())
    canvas.fill(QColor(0, 0, 0))
    row.render(canvas)

    assert calls == [row._project_ms_to_x(2_400)]
