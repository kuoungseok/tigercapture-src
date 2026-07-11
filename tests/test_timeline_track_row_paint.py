from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

import app.timeline_track_row_paint as paint_mod
from app.timeline_model import VideoClip, VideoTrack
from app.timeline_track_row import TrackRow
from app.timeline_track_row_paint import (
    _paint_timeline_playhead_sharp_thumb_window,
    _paint_timeline_thumb_tile_layer,
    _timeline_thumb_blend_width,
    _timeline_thumb_tile_rects,
)


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


def test_track_row_paints_playhead_sharp_window_for_visible_clip(monkeypatch):
    _ensure_qapp()
    row = TrackRow(_track_with_pattern_thumbnails())
    row.set_px_per_sec(90.0)
    row.set_position(2_400)
    row.resize(760, row.height())
    calls: list[int] = []
    original = paint_mod._paint_timeline_playhead_sharp_thumb_window

    def spy(owner, painter, preview_rect, tile_rects, blend_w, pixmap_for_rect, playhead_x):
        calls.append(int(playhead_x))
        return original(owner, painter, preview_rect, tile_rects, blend_w, pixmap_for_rect, playhead_x)

    monkeypatch.setattr(paint_mod, "_paint_timeline_playhead_sharp_thumb_window", spy)
    canvas = QPixmap(row.width(), row.height())
    canvas.fill(QColor(0, 0, 0))
    row.render(canvas)

    assert calls == [row._project_ms_to_x(2_400)]
