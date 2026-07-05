from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from app.color_grading import ColorGrade
from app.timeline_model import VideoClip, VideoTrack
from app.timeline_track_row import TrackRow


def _ensure_qapp():
    return QApplication.instance() or QApplication([])


def _track_with_clip(*, graded: bool) -> VideoTrack:
    thumb = QPixmap(160, 48)
    thumb.fill(QColor(238, 238, 238))
    clip = VideoClip(
        id=77,
        source_path=Path("sample.mp4"),
        source_duration_ms=5_000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=5_000,
        thumbnails=[thumb] * 6,
    )
    if graded:
        clip.color_grade = ColorGrade(contrast=12, saturation=8)
    track = VideoTrack(id=1, clips=[clip])
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


def _render_row_luma(*, graded: bool) -> int:
    _ensure_qapp()
    row = TrackRow(_track_with_clip(graded=graded))
    row.set_px_per_sec(80)
    row.resize(680, row.height())
    row.show()
    QApplication.processEvents()
    canvas = QPixmap(row.width(), row.height())
    canvas.fill(Qt.GlobalColor.black)
    row.render(canvas)
    image = canvas.toImage()
    pixel = image.pixelColor(row.MARGIN + 220, row.LABEL_H + 10)
    return int((pixel.red() + pixel.green() + pixel.blue()) / 3)


def _track_with_boundary_clip(*, graded_second: bool) -> VideoTrack:
    thumb = QPixmap(160, 48)
    thumb.fill(QColor(220, 220, 220))
    segment_ms = 2_500
    clip_a = VideoClip(
        id=91,
        source_path=Path("sample.mp4"),
        source_duration_ms=segment_ms,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=segment_ms,
        thumbnails=[thumb] * 6,
    )
    clip_b = VideoClip(
        id=92,
        source_path=Path("sample.mp4"),
        source_duration_ms=segment_ms,
        timeline_in_ms=segment_ms,
        source_in_ms=0,
        source_out_ms=segment_ms,
        thumbnails=[thumb] * 6,
    )
    if graded_second:
        clip_b.color_grade = ColorGrade(contrast=12, saturation=8)
    track = VideoTrack(id=1, clips=[clip_a, clip_b])
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


def _render_boundary_left_luma(*, graded_second: bool) -> int:
    _ensure_qapp()
    row = TrackRow(_track_with_boundary_clip(graded_second=graded_second))
    row.set_px_per_sec(80)
    row.resize(760, row.height())
    row.show()
    QApplication.processEvents()
    canvas = QPixmap(row.width(), row.height())
    canvas.fill(Qt.GlobalColor.black)
    row.render(canvas)
    image = canvas.toImage()
    boundary_x = row.MARGIN + int(2_500 / 1000.0 * row._px_per_sec)
    pixel = image.pixelColor(boundary_x - 8, row.LABEL_H + 12)
    return int((pixel.red() + pixel.green() + pixel.blue()) / 3)


def test_color_grade_layer_darkens_thumbnail_underlay():
    assert _render_row_luma(graded=True) < _render_row_luma(graded=False) - 16


def test_color_grade_underlay_bleeds_left_over_start_boundary():
    assert (
        _render_boundary_left_luma(graded_second=True)
        < _render_boundary_left_luma(graded_second=False) - 10
    )
